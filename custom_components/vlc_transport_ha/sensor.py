from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import html
import logging
import re
from typing import Any
import xml.etree.ElementTree as ET

import aiohttp

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

VLC_TZ = ZoneInfo("Europe/Madrid")

# Regex to extract: (1) line number, (2) destination in <b>...</b>, (3) arrival time in <span>...</span>
FGV_ROW_RE = re.compile(
    r'class="imagenParada".*?<span>\s*(\d+)\s*-[^<]*</span>.*?<b>([^<]+)</b>\s*-\s*<span>\s*([^<]+?)\s*</span>',
    re.IGNORECASE | re.DOTALL,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "vlc_transport_ha"
EMT_URL = "https://www.emtvalencia.es/EMT/mapfunctions/MapUtilsPetitions.php"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor from UI config entry."""
    provider = entry.data["provider"]
    stop_id = str(entry.data["stop_id"])
    name = entry.data["name"]

    coordinator = ValenciaTransitCoordinator(hass, entry, provider, stop_id)
    await coordinator.async_refresh()
    async_add_entities(
        [ValenciaTransitSensor(coordinator, name, provider, stop_id)], False
    )


class ValenciaTransitCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator to fetch real-time departures for EMT and Metrovalencia."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        provider: str,
        stop_id: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{provider}_{stop_id}",
            update_interval=timedelta(seconds=30),
        )
        self.provider = provider
        self.stop_id = stop_id
        self.last_success_time: datetime | None = None
        self.last_error: str | None = None

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from operator API and record last success timestamp."""
        try:
            if self.provider == "emt":
                data = await self._fetch_emt()
            else:
                data = await self._fetch_metrovalencia()

            self.last_success_time = datetime.now(VLC_TZ)
            self.last_error = None
            return data
        except UpdateFailed as err:
            self.last_error = str(err)
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            self.last_error = f"Network error while polling {self.provider} (#{self.stop_id}): {err}"
            raise UpdateFailed(self.last_error) from err
        except Exception as err:
            self.last_error = f"Error getting data for {self.provider} (#{self.stop_id}): {err}"
            raise UpdateFailed(self.last_error) from err

    async def _fetch_emt(self) -> list[dict[str, Any]]:
        """Fetch bus times from EMT Valencia and normalize all times to exact HH:MM and ISO timestamp."""
        session = async_get_clientsession(self.hass)
        async with session.get(
            EMT_URL,
            params={"sec": "getSAE", "parada": self.stop_id, "adaptados": "false"},
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; HomeAssistant/ValenciaTransit)",
                "Accept": "*/*",
                "Referer": "https://www.emtvalencia.es",
            },
            timeout=aiohttp.ClientTimeout(total=12),
        ) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"EMT returned HTTP status {resp.status}")
            response = await resp.text()

        return self._parse_emt_response(response)

    def _parse_emt_response(self, response: str) -> list[dict[str, Any]]:
        """Parse EMT's XML response, retaining valid rows in partial failures."""
        try:
            root = ET.fromstring(response)
        except ET.ParseError as err:
            raise UpdateFailed(f"Invalid XML response from EMT: {err}") from err
        if root.tag != "estimacion" or len(root) == 0:
            raise UpdateFailed("Invalid XML response from EMT: missing estimacion data")

        errors: list[str] = []
        now = datetime.now(VLC_TZ)
        departures: list[dict[str, Any]] = []

        for bus in root[0]:
            if bus.tag != "bus":
                continue
            if len(bus) == 3:
                errors.append(bus[2].text or "Unknown EMT error")
                continue
            if len(bus) != 5:
                errors.append(f"Invalid EMT bus response: {len(bus)} fields")
                continue

            line, destination, minutes, arrival, error = (child.text for child in bus)
            if error:
                errors.append(error)
                continue
            # emtvlcapi maps the provider's "Próximo" estimate to one minute.
            raw_val = (minutes or arrival or "").strip()
            clean_val = re.sub(r"\s*min\.?$", "", raw_val, flags=re.IGNORECASE).strip()
            if clean_val.lower().startswith("pr"):
                clean_val = "1"

            try:
                dep_dt = self._resolve_exact_datetime(now, clean_val)
            except ValueError:
                dep_dt = None
            if dep_dt is None:
                errors.append(f"Invalid EMT departure time: {raw_val!r}")
                continue

            # The provider can return UTF-8 text decoded as Latin-1.
            destination = destination or ""
            try:
                destination = destination.encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
            departures.append(
                {
                    "line": (line or "—").strip(),
                    "destination": destination.strip(),
                    "time": dep_dt.strftime("%H:%M"),
                    "timestamp": dep_dt.isoformat(),
                    "provider": "emt",
                }
            )
        if errors:
            message = "; ".join(errors)
            if not departures:
                raise UpdateFailed(f"EMT returned errors: {message}")
            _LOGGER.warning(
                "Some departures from EMT stop %s could not be read: %s",
                self.stop_id,
                message,
            )
        return departures

    async def _fetch_metrovalencia(self) -> list[dict[str, Any]]:
        """Fetch train/tram predictions from Valencia Geoportal official endpoint."""
        session = async_get_clientsession(self.hass)
        url = (
            "https://geoportal.valencia.es/geoportal-services/api/v1/"
            f"salidas-metro.html?estacion={self.stop_id}&lang=es"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; HomeAssistant/ValenciaTransit)",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        }

        async with session.get(
            url, headers=headers, timeout=aiohttp.ClientTimeout(total=12)
        ) as resp:
            if resp.status != 200:
                raise UpdateFailed(
                    f"Metrovalencia Geoportal returned HTTP status {resp.status}"
                )
            text = await resp.text()
            return self._parse_fgv_response(text)

    def _parse_fgv_response(self, html_text: str) -> list[dict[str, Any]]:
        """Parse HTML and normalize all departures to exact HH:MM and ISO timestamp."""
        if not html_text:
            return []

        now = datetime.now(VLC_TZ)
        departures: list[dict[str, Any]] = []

        for match in FGV_ROW_RE.finditer(html_text):
            line = match.group(1).strip()
            destination = html.unescape(match.group(2)).strip()
            raw_time = match.group(3).strip()

            dep_dt = self._resolve_exact_datetime(now, raw_time)
            if dep_dt is None:
                continue

            departures.append(
                {
                    "line": line,
                    "destination": destination,
                    "time": dep_dt.strftime("%H:%M"),
                    "timestamp": dep_dt.isoformat(),
                    "provider": "metrovalencia",
                }
            )

        return departures

    def _resolve_exact_datetime(self, now: datetime, value: str) -> datetime | None:
        """Convert relative minutes, 'Próximo', or HH:MM(:SS) string into an exact timezone-aware datetime."""
        if not value:
            return None

        low = value.lower()
        if low in ("0", "próximo", "proximo", "inmediato", "llegando", "now"):
            return now.replace(microsecond=0)

        if value.isdigit():
            return (now + timedelta(minutes=int(value))).replace(microsecond=0)

        if ":" in value:
            parts = value.split(":")
            if len(parts) >= 2 and all(p.isdigit() for p in parts[:2]):
                dep_hour = int(parts[0])
                dep_min = int(parts[1])
                dep_sec = (
                    int(parts[2])
                    if len(parts) > 2 and parts[2].isdigit()
                    else 0
                )

                extra_days = dep_hour // 24
                norm_hour = dep_hour % 24

                dep_dt = now.replace(
                    hour=norm_hour, minute=dep_min, second=dep_sec, microsecond=0
                ) + timedelta(days=extra_days)

                if (dep_dt - now).total_seconds() < -600 and extra_days == 0:
                    dep_dt += timedelta(days=1)

                return dep_dt

        return None


class ValenciaTransitSensor(
    CoordinatorEntity[ValenciaTransitCoordinator], SensorEntity
):
    """Sensor representing upcoming departures at a Valencia transit stop."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ValenciaTransitCoordinator,
        name: str,
        provider: str,
        stop_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = None
        self._attr_unique_id = f"vlc_{provider}_{stop_id}"
        self._attr_icon = (
            "mdi:bus-clock" if provider == "emt" else "mdi:subway-variant"
        )

        provider_label = (
            "EMT València" if provider == "emt" else "Metrovalencia (FGV)"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{provider}_{stop_id}")},
            name=name,
            manufacturer=provider_label,
            model=f"{'EMT Stop' if provider == 'emt' else 'FGV Station'} #{stop_id}",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=(
                "https://www.emtvalencia.es/"
                if provider == "emt"
                else "https://www.metrovalencia.es/"
            ),
        )

    @property
    def available(self) -> bool:
        """Keep entity available if cached data exists so the card can still render last known departures."""
        return self.coordinator.last_update_success or self.coordinator.data is not None

    @property
    def native_value(self) -> str | None:
        """Always return the exact departure time (HH:MM) of the next departure."""
        deps = self.coordinator.data
        if deps and len(deps) > 0:
            return str(deps[0].get("time"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return upcoming departures, last update timestamp, and error state."""
        return {
            "provider": self.coordinator.provider,
            "stop_id": self.coordinator.stop_id,
            "departures": self.coordinator.data or [],
            "last_updated": (
                self.coordinator.last_success_time.isoformat()
                if self.coordinator.last_success_time
                else None
            ),
            "update_failed": not self.coordinator.last_update_success,
            "last_error": self.coordinator.last_error,
        }
