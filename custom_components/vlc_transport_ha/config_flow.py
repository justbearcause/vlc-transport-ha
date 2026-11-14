from __future__ import annotations

import re
from typing import Any
import aiohttp
import voluptuous as vol
import logging

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "vlc_transport_ha"

PROVIDERS = {
    "emt": "EMT València (Bus)",
    "metrovalencia": "Metrovalencia (Metro / Tram)",
}

# Open Data Valencia dataset URL for all EMT bus stops
EMT_STOPS_API_URL = (
    "https://geoportal.valencia.es/server/rest/services/OPENDATA/Trafico/"
    "MapServer/226/query?where=1%3D1&outFields=id_parada,denominacion"
    "&returnGeometry=false&f=json"
)

# Official FGV (Metrovalencia) app synchronization endpoint for station updates
FGV_STATIONS_API_URL = (
    "https://www.fgv.es/fgv/app/es/api/v1/V/sincronizacion?fecha_desde=2025-11-13%2015:45"
)

# Fallback directory of official FGV metro and tram stations (used if API is unavailable)
FALLBACK_FGV_STATIONS: dict[str, str] = {
    "1": "Rafelbunyol",
    "2": "La Pobla de Farnals",
    "3": "Massamagrell",
    "4": "Museros",
    "5": "Albalat dels Sorells",
    "6": "Foios",
    "7": "Meliana",
    "8": "Almàssera",
    "9": "Alboraia Peris Aragó",
    "10": "Alboraia Palmaret",
    "11": "Machado",
    "12": "Benimaclet",
    "13": "Facultats - Manuel Broseta",
    "14": "Alameda",
    "15": "Colón",
    "16": "Xàtiva",
    "17": "Àngel Guimerà",
    "18": "Av. del Cid",
    "19": "Nou d'Octubre",
    "20": "Mislata",
    "21": "Mislata Almassil",
    "22": "Ayora",
    "23": "Amistat",
    "24": "Aragó",
    "25": "Jesús",
    "26": "Patraix",
    "27": "Safranar",
    "28": "Sant Isidre",
    "30": "València Sud",
    "31": "Paiporta",
    "32": "Picanya",
    "33": "Torrent",
    "34": "Torrent Avinguda",
    "35": "Castelló",
    "36": "Alberic",
    "37": "Massalavés",
    "38": "Montortal",
    "39": "L'Alcúdia",
    "40": "Benimodo",
    "41": "Carlet",
    "42": "Ausiàs March",
    "43": "Alginet",
    "44": "Font Almaguer",
    "45": "Espioca",
    "46": "Omet",
    "47": "Picassent",
    "48": "Sant Ramon",
    "49": "Realón",
    "50": "Col·legi El Vedat",
    "51": "Pl. Espanya",
    "52": "Túria",
    "53": "Campanar",
    "54": "Beniferri",
    "55": "Empalme",
    "56": "Cantereria",
    "57": "Benimàmet",
    "58": "Les Carolines - Fira",
    "59": "Campament",
    "60": "Paterna",
    "61": "Santa Rita",
    "62": "Fuente del Jarro",
    "63": "La Canyada",
    "64": "La Vallesa",
    "65": "Entrepins",
    "66": "Montesol",
    "67": "L'Eliana",
    "68": "La Pobla de Vallbona",
    "69": "Fondo de Benaguasil",
    "70": "Benaguasil",
    "71": "Llíria",
    "72": "Burjassot",
    "73": "Burjassot - Godella",
    "74": "Godella",
    "75": "Rocafort",
    "76": "Massarrojos",
    "77": "Moncada - Alfara",
    "78": "Seminari - CEU",
    "79": "Masies",
    "80": "Horta Vella",
    "81": "Platja Malva-rosa",
    "82": "Platja les Arenes",
    "83": "Dr. Lluch",
    "84": "Cabanyal",
    "85": "La Cadena",
    "86": "Beteró",
    "87": "Tarongers - Ernest Lluch",
    "88": "La Carrasca",
    "89": "Universitat Politècnica",
    "90": "Vicente Zaragozà",
    "91": "Trinitat",
    "92": "Pont de Fusta",
    "93": "Sagunt",
    "94": "Reus",
    "95": "Marxalenes",
    "96": "Trànsits",
    "97": "Benicalap",
    "98": "Garbí",
    "99": "Florista",
    "100": "Palau de Congressos",
    "101": "La Granja",
    "102": "Sant Joan",
    "103": "Campus",
    "104": "Vicent Andrés Estellés",
    "105": "À Punt",
    "106": "Fira València",
    "107": "Bétera",
    "108": "El Clot",
    "109": "Bailén",
    "110": "Mas del Rosari",
    "111": "La Coma",
    "112": "Tomás y Valiente",
    "113": "Parc Científic",
    "114": "Ll. Llarga - Terramelar",
    "115": "Marítim",
    "117": "Quart de Poblet",
    "118": "Salt de l'Aigua",
    "119": "Manises",
    "120": "Roses",
    "121": "Aeroport",
    "122": "Francesc Cubells",
    "123": "Grau - La Marina",
    "126": "Neptú",
    "127": "Canyamelar",
    "128": "Alfauir",
    "129": "Orriols",
    "130": "Estadi Ciutat de València",
    "131": "Sant Miquel dels Reis",
    "132": "Tossal del Rei",
    "183": "La Cova",
    "184": "La Presa",
    "185": "Masia de Traver",
    "186": "Riba-roja de Túria",
    "188": "València la Vella",
    "190": "Alacant",
    "191": "Russafa",
    "192": "Amado Granell - Montolivet",
    "193": "Quatre Carreres",
    "194": "Ciutat Arts i Ciències - Justícia",
    "195": "Oceanogràfic",
    "196": "Moreres",
    "197": "Natzaret",
    "198": "Font del Barranc",
    "200": "Faitanar",
    "201": "Gallipont - Torre del Virrei",
}


class ValenciaTransitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Valencia Transit."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._stations: dict[str, str] = {}
        self._emt_stops: dict[str, str] = {}
        self._emt_stops_loaded = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: Choose transport operator."""
        if user_input is not None:
            if user_input["provider"] == "emt":
                return await self.async_step_emt()
            return await self.async_step_metrovalencia()

        schema = vol.Schema(
            {
                vol.Required("provider", default="emt"): vol.In(PROVIDERS),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_emt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2A: Configure an EMT Valencia bus stop via searchable dropdown."""
        errors: dict[str, str] = {}

        if not self._emt_stops and not self._emt_stops_loaded:
            self._emt_stops = await self._async_fetch_emt_stops()
            self._emt_stops_loaded = True

        if user_input is not None:
            raw_val = str(user_input["stop_id"]).strip()
            # Extract numeric ID even if the user entered a custom string
            match = re.search(r"\d+", raw_val)
            stop_id = match.group(0) if match else ""

            if not stop_id:
                errors["stop_id"] = "invalid_stop_id"
            else:
                await self.async_set_unique_id(f"emt_{stop_id}")
                self._abort_if_unique_id_configured()

                stop_name = self._emt_stops.get(stop_id)
                default_title = (
                    f"EMT {stop_id}: {stop_name}"
                    if stop_name
                    else f"EMT {stop_id}"
                )
                custom_name = user_input.get("name", "").strip()
                title = custom_name or default_title

                return self.async_create_entry(
                    title=title,
                    data={
                        "provider": "emt",
                        "stop_id": stop_id,
                        "name": title,
                    },
                )

        # Build a numerically sorted list of stops for the dropdown menu
        options = [
            SelectOptionDict(value=code, label=f"{code}: {name}")
            for code, name in sorted(
                self._emt_stops.items(), key=lambda item: int(item[0])
            )
        ]

        schema = vol.Schema(
            {
                vol.Required("stop_id"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,  # Also allows entering any ID manually
                    )
                ),
                vol.Optional("name"): TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="emt", data_schema=schema, errors=errors
        )

    async def async_step_metrovalencia(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2B: Configure a Metrovalencia station via searchable dropdown."""
        errors: dict[str, str] = {}

        if not self._stations:
            self._stations = await self._async_fetch_fgv_stations()

        if user_input is not None:
            raw_val = str(user_input["stop_id"]).strip()
            # Extract numeric ID even if the user entered a custom string
            match = re.search(r"\d+", raw_val)
            stop_id = match.group(0) if match else ""

            if not stop_id:
                errors["stop_id"] = "invalid_stop_id"
            else:
                await self.async_set_unique_id(f"metrovalencia_{stop_id}")
                self._abort_if_unique_id_configured()

                station_name = self._stations.get(stop_id, f"#{stop_id}")
                custom_name = user_input.get("name", "").strip()
                title = custom_name or f"Metrovalencia {station_name}"

                return self.async_create_entry(
                    title=title,
                    data={
                        "provider": "metrovalencia",
                        "stop_id": stop_id,
                        "name": title,
                    },
                )

        # Build an alphabetically sorted list of stations for the dropdown menu
        options = [
            SelectOptionDict(value=code, label=f"{name} (#{code})")
            for code, name in sorted(
                self._stations.items(), key=lambda item: item[1].lower()
            )
        ]

        schema = vol.Schema(
            {
                vol.Required("stop_id"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,  # Also allows entering any ID manually
                    )
                ),
                vol.Optional("name"): TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="metrovalencia", data_schema=schema, errors=errors
        )

    async def _async_fetch_emt_stops(self) -> dict[str, str]:
        """Fetch full list of EMT bus stops from Valencia Geoportal with pagination."""
        stops: dict[str, str] = {}
        session = async_get_clientsession(self.hass)
        offset = 0
        max_pages = 10
        loaded_count = 0

        try:
            for _ in range(max_pages):
                kwargs: dict[str, Any] = {
                    "timeout": aiohttp.ClientTimeout(total=10),
                }
                if offset > 0:
                    kwargs["params"] = {"resultOffset": str(offset)}

                async with session.get(EMT_STOPS_API_URL, **kwargs) as resp:
                    if resp.status != 200:
                        _LOGGER.warning(
                            "Failed to fetch EMT stops list: HTTP %s from %s",
                            resp.status,
                            EMT_STOPS_API_URL,
                        )
                        return stops

                    data = await resp.json(content_type=None)

                    if isinstance(data, dict) and "features" in data:
                        rows = [
                            feat.get("attributes") or feat.get("properties") or {}
                            for feat in data["features"]
                            if isinstance(feat, dict)
                        ]
                    elif isinstance(data, dict) and "results" in data:
                        rows = data["results"]
                    elif isinstance(data, list):
                        rows = data
                    else:
                        _LOGGER.warning(
                            "Unexpected JSON structure for EMT stops list: %s",
                            list(data.keys()) if isinstance(data, dict) else type(data),
                        )
                        return stops

                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        raw_code = row.get("id_parada") or row.get("ID_PARADA")
                        raw_name = row.get("denominacion") or row.get("DENOMINACION")
                        if raw_code is not None and raw_name:
                            code = str(raw_code).strip()
                            name = re.sub(
                                r"\s*\(\d+\)\s*$", "", str(raw_name)
                            ).strip()
                            if code.isdigit() and name:
                                stops[code] = name
                                loaded_count += 1

                    if (
                        isinstance(data, dict)
                        and data.get("exceededTransferLimit")
                        and rows
                    ):
                        offset += len(rows)
                        continue
                    break

            _LOGGER.debug(
                "Loaded %d EMT stops (total unique in list: %d)",
                loaded_count,
                len(stops),
            )

        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.warning(
                "Error fetching full EMT stops list: %s",
                err,
            )

        return stops

    async def _async_fetch_fgv_stations(self) -> dict[str, str]:
        """Fetch full list of FGV stations from the official FGV API with fallback."""
        stations = dict(FALLBACK_FGV_STATIONS)
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                FGV_STATIONS_API_URL,
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning(
                        "Failed to fetch FGV stations list: HTTP %s from %s",
                        resp.status,
                        FGV_STATIONS_API_URL,
                    )
                    return stations

                # content_type=None in case the server returns JSON with a text/plain header
                data = await resp.json(content_type=None)

                if isinstance(data, list):
                    rows = data
                elif (
                    isinstance(data, dict)
                    and isinstance(data.get("data"), dict)
                    and isinstance(data["data"].get("estaciones"), list)
                ):
                    rows = data["data"]["estaciones"]
                elif isinstance(data, dict) and "estaciones" in data:
                    rows = data["estaciones"]
                elif isinstance(data, dict) and "paradas" in data:
                    rows = data["paradas"]
                elif isinstance(data, dict) and "features" in data:
                    rows = [
                        feat.get("attributes") or feat.get("properties") or {}
                        for feat in data["features"]
                        if isinstance(feat, dict)
                    ]
                elif isinstance(data, dict) and "results" in data:
                    rows = data["results"]
                else:
                    _LOGGER.warning(
                        "Unexpected JSON structure for FGV stations list: %s",
                        list(data.keys()) if isinstance(data, dict) else type(data),
                    )
                    return stations

                loaded_count = 0
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    raw_code = (
                        row.get("estacion_id_FGV")
                        or row.get("estacion_id_fgv")
                        or row.get("id_fgv")
                        or row.get("id")
                        or row.get("codigo")
                        or row.get("CODIGO")
                    )
                    raw_name = (
                        row.get("nombre")
                        or row.get("NOMBRE")
                        or row.get("name")
                    )
                    if raw_code is not None and raw_name:
                        code = str(raw_code).strip()
                        name = str(raw_name).strip()
                        if code.isdigit() and name:
                            stations[code] = name
                            loaded_count += 1

                _LOGGER.debug(
                    "Loaded %d Metrovalencia stations (total in list: %d)",
                    loaded_count,
                    len(stations),
                )

        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.warning(
                "Error fetching full FGV stations list (using fallback): %s",
                err,
            )

        return stations
