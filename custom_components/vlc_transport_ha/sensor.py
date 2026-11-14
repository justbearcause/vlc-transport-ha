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

_LOGGER = logging.getLogger(__name__)

DOMAIN = "vlc_transport_ha"
EMT_URL = "https://www.emtvalencia.es/EMT/mapfunctions/MapUtilsPetitions.php"
EMT_NO_ESTIMATIONS = frozenset({"SENSE ESTIMACIONS", "SIN ESTIMACIONES"})
FGV_PREVISION_URL = (
    "https://www.fgv.es/ap18/api/public/es/api/v1/V/horarios-prevision-3"
)

FGV_ENCODING_FIXES: tuple[tuple[str, str], ...] = (
    ("Mar?tim", "Marítim"),
    ("Arag?", "Aragó"),
    ("Castell?", "Castelló"),
    ("B?tera", "Bétera"),
    ("Ll?ria", "Llíria"),
    ("T?ria", "Túria"),
    ("Val?ncia", "València"),
    ("?ngel", "Àngel"),
    ("Guimer?", "Guimerà"),
    ("Jes?s", "Jesús"),
    ("Nept?", "Neptú"),
    ("Beter?", "Beteró"),
    ("Garb?", "Garbí"),
    ("Zaragoz?", "Zaragozà"),
    ("Andr?s", "Andrés"),
    ("Estell?s", "Estellés"),
    ("Tr?nsits", "Trànsits"),
    ("Oceanogr?fic", "Oceanogràfic"),
    ("Ci?ncies", "Ciències"),
    ("Just?cia", "Justícia"),
    ("Benim?met", "Benimàmet"),
    ("Alm?ssera", "Almàssera"),
    ("Alc?dia", "Alcúdia"),
    ("Massalav?s", "Massalavés"),
    ("Ausi?s", "Ausiàs"),
    ("Real?n", "Realón"),
    ("Bail?n", "Bailén"),
    ("Cient?fic", "Científic"),
    ("Tom?s", "Tomás"),
    ("Col?legi", "Col·legi"),
    ("X?tiva", "Xàtiva"),
    ("Col?n", "Colón"),
    ("Polit?cnica", "Politècnica"),
    ("? Punt", "À Punt"),
)


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
                error_text = (bus[2].text or "").strip()
                if error_text.upper() in EMT_NO_ESTIMATIONS:
                    continue
                errors.append(error_text or "Unknown EMT error")
                continue
            if len(bus) != 5:
                errors.append(f"Invalid EMT bus response: {len(bus)} fields")
                continue

            line, destination, minutes, arrival, error = (child.text for child in bus)
            if error:
                error_text = error.strip()
                if error_text.upper() in EMT_NO_ESTIMATIONS:
                    continue
                errors.append(error_text)
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
        """Fetch real-time train/tram predictions from the official FGV API."""
        session = async_get_clientsession(self.hass)
        url = f"{FGV_PREVISION_URL}/{self.stop_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; HomeAssistant/ValenciaTransit)",
            "Accept": "application/json",
        }

        async with session.get(
            url, headers=headers, timeout=aiohttp.ClientTimeout(total=12)
        ) as resp:
            if resp.status != 200:
                raise UpdateFailed(
                    f"Metrovalencia FGV API returned HTTP status {resp.status}"
                )
            try:
                payload = await resp.json(content_type=None)
            except ValueError as err:
                raise UpdateFailed(
                    f"Invalid JSON response from Metrovalencia FGV API: {err}"
                ) from err
            return self._parse_fgv_response(payload)

    def _clean_fgv_text(self, text: str) -> str:
        """Fix broken character encodings returned in FGV destination strings."""
        cleaned = html.unescape(text or "").strip()
        try:
            cleaned = cleaned.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        if "\ufffd" in cleaned:
            cleaned = cleaned.replace("\ufffd", "?")
        if "?" in cleaned:
            for broken, fixed in FGV_ENCODING_FIXES:
                if broken in cleaned:
                    cleaned = cleaned.replace(broken, fixed)
        return cleaned.strip()

    def _parse_fgv_response(self, payload: Any) -> list[dict[str, Any]]:
        """Parse official FGV real-time JSON payload into sorted departures."""
        if isinstance(payload, list):
            previsiones = payload
        elif isinstance(payload, dict):
            if "previsiones" not in payload:
                if "resultado" in payload:
                    raise UpdateFailed(
                        f"Metrovalencia FGV API error: {payload['resultado']}"
                    )
                raise UpdateFailed(
                    "Invalid JSON response from Metrovalencia FGV API: missing previsiones"
                )
            previsiones = payload.get("previsiones") or []
            if not isinstance(previsiones, list):
                raise UpdateFailed(
                    "Invalid JSON response from Metrovalencia FGV API: previsiones is not a list"
                )
        else:
            raise UpdateFailed(
                "Invalid JSON response from Metrovalencia FGV API"
            )

        now = datetime.now(VLC_TZ).replace(microsecond=0)
        departures: list[dict[str, Any]] = []

        for line_group in previsiones:
            if not isinstance(line_group, dict):
                continue
            group_line = (
                line_group.get("line")
                if line_group.get("line") is not None
                else line_group.get("line_id")
            )
            trains = line_group.get("trains")
            if not isinstance(trains, list):
                continue

            for train in trains:
                if not isinstance(train, dict):
                    continue
                raw_seconds = train.get("seconds")
                if isinstance(raw_seconds, bool) or raw_seconds is None:
                    continue
                try:
                    seconds = int(raw_seconds)
                except (TypeError, ValueError):
                    continue
                if seconds < 0:
                    continue

                raw_dest = str(train.get("destino") or "").strip()
                if not raw_dest:
                    continue
                destination = self._clean_fgv_text(raw_dest)

                raw_line = (
                    group_line
                    if group_line is not None
                    else train.get("line_id")
                )
                line = (
                    str(raw_line).strip()
                    if raw_line is not None and str(raw_line).strip()
                    else "—"
                )

                dep_dt = now + timedelta(seconds=seconds)
                minutes = seconds // 60

                dep_item: dict[str, Any] = {
                    "line": line,
                    "destination": destination,
                    "time": dep_dt.strftime("%H:%M"),
                    "timestamp": dep_dt.isoformat(),
                    "minutes": minutes,
                    "seconds": seconds,
                    "provider": "metrovalencia",
                }

                vehicle = train.get("vehicle")
                if vehicle is not None and str(vehicle).strip():
                    dep_item["vehicle"] = str(vehicle).strip()

                meters = train.get("meters")
                if (
                    not isinstance(meters, bool)
                    and isinstance(meters, (int, float))
                    and meters >= 0
                ):
                    dep_item["meters"] = int(meters)

                capacity = train.get("capacity")
                if (
                    not isinstance(capacity, bool)
                    and isinstance(capacity, (int, float))
                    and capacity > 0
                ):
                    dep_item["capacity"] = int(capacity)

                lat = train.get("latitude")
                lon = train.get("longitude")
                if (
                    not isinstance(lat, bool)
                    and not isinstance(lon, bool)
                    and isinstance(lat, (int, float))
                    and isinstance(lon, (int, float))
                    and (lat != 0 or lon != 0)
                ):
                    dep_item["latitude"] = float(lat)
                    dep_item["longitude"] = float(lon)

                departures.append(dep_item)

        departures.sort(key=lambda item: item["seconds"])
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
