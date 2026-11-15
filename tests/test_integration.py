"""Focused integration tests with lightweight Home Assistant test doubles.

Run with: python3 -m unittest discover -s tests -p 'test_*.py'
"""
import importlib.util
import logging
from datetime import datetime
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "vlc_transport_ha"


test_modules = {}


def module(name):
    value = types.ModuleType(name)
    test_modules[name] = value
    return value


# This repository has no Home Assistant test environment; replace its imports so
# the coordinator, XML parsing, network paths, and config fallback can run.
for name in (
    "homeassistant", "homeassistant.components", "homeassistant.config_entries",
    "homeassistant.const", "homeassistant.core", "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client", "homeassistant.helpers.config_validation",
    "homeassistant.helpers.device_registry", "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.update_coordinator", "homeassistant.components.frontend",
    "homeassistant.components.http", "homeassistant.components.sensor",
    "homeassistant.helpers.selector", "aiohttp", "voluptuous",
):
    module(name)


class Generic:
    def __class_getitem__(cls, item):
        return cls


class Coordinator(Generic):
    def __init__(self, hass, logger, **kwargs):
        self.hass = hass


class CoordinatorEntity(Generic):
    def __init__(self, coordinator):
        self.coordinator = coordinator


class ConfigFlow:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        pass

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(self, *, step_id, data_schema, errors=None):
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }


class ClientError(Exception):
    pass


class UpdateFailed(Exception):
    pass


test_modules["homeassistant.components.sensor"].SensorEntity = type("SensorEntity", (), {})
test_modules["homeassistant.components.sensor"].SensorDeviceClass = types.SimpleNamespace(
    DURATION="duration"
)
test_modules["homeassistant.components.sensor"].SensorStateClass = types.SimpleNamespace(
    MEASUREMENT="measurement"
)
test_modules["homeassistant.components.http"].StaticPathConfig = (
    lambda url_path, path, cache_headers=True: types.SimpleNamespace(
        url_path=url_path, path=path, cache_headers=cache_headers
    )
)
test_modules["homeassistant.components.frontend"].add_extra_js_url = (
    lambda hass, url: hass.extra_js_urls.append(url)
)
test_modules["homeassistant.const"].Platform = types.SimpleNamespace(SENSOR="sensor")
test_modules["homeassistant.const"].UnitOfTime = types.SimpleNamespace(MINUTES="min")
test_modules["homeassistant.helpers.config_validation"].config_entry_only_config_schema = (
    lambda domain: {"domain": domain}
)
test_modules["homeassistant.config_entries"].ConfigEntry = object
test_modules["homeassistant.config_entries"].ConfigFlow = ConfigFlow
test_modules["homeassistant.config_entries"].ConfigFlowResult = dict
test_modules["homeassistant.core"].HomeAssistant = object
test_modules["homeassistant.helpers"].config_validation = test_modules["homeassistant.helpers.config_validation"]
test_modules["homeassistant.helpers.aiohttp_client"].async_get_clientsession = lambda hass: hass.session
test_modules["homeassistant.helpers.device_registry"].DeviceEntryType = types.SimpleNamespace(SERVICE="service")
test_modules["homeassistant.helpers.device_registry"].DeviceInfo = dict
test_modules["homeassistant.helpers.entity_platform"].AddEntitiesCallback = object
coordinator_module = test_modules["homeassistant.helpers.update_coordinator"]
coordinator_module.CoordinatorEntity = CoordinatorEntity
coordinator_module.DataUpdateCoordinator = Coordinator
coordinator_module.UpdateFailed = UpdateFailed
selector_module = test_modules["homeassistant.helpers.selector"]
selector_module.SelectOptionDict = lambda **kwargs: kwargs
selector_module.SelectSelector = lambda config=None: types.SimpleNamespace(config=config)
selector_module.SelectSelectorConfig = lambda **kwargs: types.SimpleNamespace(**kwargs)
selector_module.SelectSelectorMode = types.SimpleNamespace(DROPDOWN="dropdown")
selector_module.TextSelector = lambda: "TextSelector"
vol_module = test_modules["voluptuous"]
vol_module.Schema = lambda schema: schema
vol_module.Required = lambda key, **kwargs: key
vol_module.Optional = lambda key, **kwargs: key
vol_module.In = lambda container: container
test_modules["aiohttp"].ClientError = ClientError
test_modules["aiohttp"].ClientTimeout = lambda total: types.SimpleNamespace(total=total)


def load(name, filename):
    pkg = "custom_components.vlc_transport_ha"
    full_name = pkg if filename == "__init__.py" else f"{pkg}.{Path(filename).stem}"
    spec = importlib.util.spec_from_file_location(
        full_name,
        ROOT / filename,
        submodule_search_locations=[str(ROOT)] if filename == "__init__.py" else None,
    )
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


with patch.dict(sys.modules, test_modules):
    const = load("vlc_const_test", "const.py")
    init = load("vlc_init_test", "__init__.py")
    sensor = load("vlc_sensor_test", "sensor.py")
    config_flow = load("vlc_config_flow_test", "config_flow.py")


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 13, 23, 59, 59, tzinfo=tz)


class Response:
    def __init__(self, body="", status=200, error=None, json_data=None):
        self.body = body
        self.status = status
        self.error = error
        self.json_data = json_data

    async def __aenter__(self):
        if self.error:
            raise self.error
        return self

    async def __aexit__(self, *args):
        return False

    async def text(self):
        return self.body

    async def json(self, content_type=None):
        if self.json_data is not None:
            return self.json_data
        raise ValueError("Invalid JSON")


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.response, list):
            return self.response.pop(0)
        return self.response


def xml(*rows):
    return "<estimacion><parada>" + "".join(rows) + "</parada></estimacion>"


def bus(minutes="", arrival="", destination="Centre", error=""):
    return (f"<bus><linea>7</linea><destino>{destination}</destino>"
            f"<minutos>{minutes}</minutos><horaLlegada>{arrival}</horaLlegada>"
            f"<error>{error}</error></bus>")


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = Session(Response())
        self.hass = types.SimpleNamespace(session=self.session)
        self.coordinator = sensor.ValenciaTransitCoordinator(self.hass, None, "emt", "508")
        self.time_patch = patch.object(sensor, "datetime", FrozenDateTime)
        self.time_patch.start()
        self.addCleanup(self.time_patch.stop)

    async def test_emt_times_empty_and_encoding(self):
        self.session.response = Response(xml(
            bus(minutes="1 min.", destination="Pass. MarÃ­tim"),
            bus(arrival="00:15"), bus(minutes="Próximo")))
        result = await self.coordinator._fetch_emt()
        self.assertEqual([row["time"] for row in result], ["00:00", "00:15", "00:00"])
        self.assertEqual([row["minutes"] for row in result], [1, 15, 1])
        self.assertEqual(result[0]["timestamp"], "2026-11-14T00:00:59+01:00")
        self.assertEqual(result[0]["destination"], "Pass. Marítim")
        self.assertEqual(self.session.calls[0][1]["timeout"].total, 12)
        self.assertEqual(self.session.calls[0][1]["params"]["parada"], "508")
        self.session.response = Response(xml())
        self.assertEqual(await self.coordinator._fetch_emt(), [])

    async def test_emt_errors_and_partial_results(self):
        error = "<bus><linea>7</linea><destino>Centre</destino><error>Unavailable</error></bus>"
        self.session.response = Response(xml(error))
        with self.assertRaisesRegex(UpdateFailed, "Unavailable"):
            await self.coordinator._async_update_data()
        self.assertIn("Unavailable", self.coordinator.last_error)
        self.session.response = Response(xml(error, bus(minutes="4 min.")))
        with self.assertLogs(sensor._LOGGER, logging.WARNING) as logs:
            result = await self.coordinator._async_update_data()
        self.assertEqual(len(result), 1)
        self.assertIn("Unavailable", logs.output[0])
        self.assertIsNone(self.coordinator.last_error)
        self.session.response = Response(xml(bus(arrival="12:99"), bus(minutes="4 min.")))
        with self.assertLogs(sensor._LOGGER, logging.WARNING):
            self.assertEqual(len(await self.coordinator._fetch_emt()), 1)
        self.session.response = Response(xml(bus(minutes="unrecognized")))
        with self.assertRaisesRegex(UpdateFailed, "Invalid EMT departure time"):
            await self.coordinator._fetch_emt()

    async def test_emt_no_estimations_treated_as_empty_schedule(self):
        for payload in (
            "<bus><imagen>img</imagen><icono>ico</icono><error>SENSE ESTIMACIONS</error></bus>",
            "<bus><imagen>img</imagen><icono>ico</icono><error> Sin estimaciones </error></bus>",
            bus(error="SENSE ESTIMACIONS"),
            bus(error="SIN ESTIMACIONES"),
        ):
            with self.subTest(payload=payload):
                self.coordinator.last_error = "Previous error"
                self.session.response = Response(xml(payload))
                result = await self.coordinator._async_update_data()
                self.assertEqual(result, [])
                self.assertIsNone(self.coordinator.last_error)
                self.assertIsNotNone(self.coordinator.last_success_time)

        # Mixed response: SENSE ESTIMACIONS alongside a valid bus does not log a warning
        no_est_3 = "<bus><imagen>img</imagen><icono>ico</icono><error>SENSE ESTIMACIONS</error></bus>"
        self.session.response = Response(xml(no_est_3, bus(minutes="4 min.")))
        with patch.object(sensor._LOGGER, "warning") as mock_warning:
            result = await self.coordinator._async_update_data()
        mock_warning.assert_not_called()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["time"], "00:03")

    async def test_emt_bad_xml_http_and_timeout(self):
        for response, message in (
            (Response("<broken"), "Invalid XML"),
            (Response("<other/>"), "Invalid XML"),
            (Response(status=503), "HTTP status 503"),
            (Response(error=TimeoutError("timed out")), "Network error"),
        ):
            with self.subTest(message=message):
                self.session.response = response
                with self.assertRaisesRegex(UpdateFailed, message):
                    await self.coordinator._async_update_data()

    async def test_metro_and_station_list_use_tls_and_fallback(self):
        self.coordinator.provider = "metrovalencia"
        self.session.response = Response(error=ClientError("certificate verify failed"))
        with self.assertRaises(UpdateFailed):
            await self.coordinator._async_update_data()
        self.assertNotIn("ssl", self.session.calls[-1][1])
        flow = config_flow.ValenciaTransitConfigFlow()
        flow.hass = self.hass
        with self.assertLogs(config_flow._LOGGER, logging.WARNING):
            stations = await flow._async_fetch_fgv_stations()
        self.assertEqual(stations, config_flow.FALLBACK_FGV_STATIONS)
        self.assertNotIn("ssl", self.session.calls[-1][1])

        # Official FGV /sincronizacion JSON response (and direct list)
        self.session.response = Response(
            json_data={
                "timestamp": "2026-11-14 12:00",
                "data": {
                    "estaciones": [
                        {"estacion_id_FGV": 16, "nombre": "Xàtiva"},
                        {
                            "estacion_id_FGV": 999,
                            "nombre": "Nueva Estación",
                            "latitud": 39.501234,
                            "longitud": -0.401234,
                        },
                    ]
                },
            }
        )
        stations_live = await flow._async_fetch_fgv_stations()
        self.assertEqual(stations_live["16"], "Xàtiva")
        self.assertEqual(stations_live["999"], "Nueva Estación")

        # Creating entry for known station uses built-in FGV_STATION_COORDINATES
        entry_16 = await flow.async_step_metrovalencia({"stop_id": "16"})
        self.assertEqual(entry_16["data"]["station_latitude"], 39.467186)
        self.assertEqual(entry_16["data"]["station_longitude"], -0.377375)

        # Creating entry for newly synced station uses coordinates from API
        entry_999 = await flow.async_step_metrovalencia({"stop_id": "999"})
        self.assertEqual(entry_999["data"]["station_latitude"], 39.501234)
        self.assertEqual(entry_999["data"]["station_longitude"], -0.401234)

        # ValenciaTransitSensor exposes station_latitude/station_longitude for Metrovalencia (including legacy entries without coords in entry.data)
        self.coordinator.data = []
        self.coordinator.last_update_success = True
        self.coordinator.last_success_time = None
        self.coordinator.last_error = None
        metro_sensor = sensor.ValenciaTransitSensor(
            self.coordinator, "Metrovalencia Xàtiva", "metrovalencia", "16"
        )
        metro_attrs = metro_sensor.extra_state_attributes
        self.assertEqual(metro_attrs["station_latitude"], 39.467186)
        self.assertEqual(metro_attrs["station_longitude"], -0.377375)

        # EMT sensor does not expose station_latitude/station_longitude
        emt_coordinator = sensor.ValenciaTransitCoordinator(self.hass, None, "emt", "16")
        emt_coordinator.data = []
        emt_coordinator.last_update_success = True
        emt_sensor = sensor.ValenciaTransitSensor(
            emt_coordinator, "EMT 16", "emt", "16"
        )
        self.assertNotIn("station_latitude", emt_sensor.extra_state_attributes)
        self.assertNotIn("station_longitude", emt_sensor.extra_state_attributes)

        # Sensor uses continuous duration measurement metadata and unrecorded attributes
        self.assertEqual(emt_sensor._attr_device_class, "duration")
        self.assertEqual(emt_sensor._attr_native_unit_of_measurement, "min")
        self.assertEqual(emt_sensor._attr_state_class, "measurement")
        self.assertEqual(
            emt_sensor._unrecorded_attributes,
            frozenset({"departures", "last_updated", "update_failed", "last_error"}),
        )
        self.assertIsNone(emt_sensor.native_value)
        emt_coordinator.data = [{"line": "7", "destination": "Centre", "time": "00:04", "minutes": 4}]
        self.assertEqual(emt_sensor.native_value, 4)
        self.coordinator.data = [{"line": "3", "destination": "Aeroport", "time": "00:00", "minutes": 0, "seconds": 45}]
        self.assertEqual(metro_sensor.native_value, 0)

    async def test_metro_realtime_fgv_api_parsing_sorting_and_errors(self):
        self.coordinator.provider = "metrovalencia"
        self.coordinator.stop_id = "16"
        self.session.response = Response(
            json_data={
                "aforo_bloqueado": {"desde": None, "hasta": None},
                "previsiones": [
                    {
                        "line": 5,
                        "line_id": 5,
                        "linea_id_interna": 10,
                        "trains": [
                            {
                                "cabecera": False,
                                "capacity": 397,
                                "destino": "Marítim",
                                "latitude": 39.4699,
                                "line_id": 5,
                                "longitude": -0.3763,
                                "meters": 450,
                                "seconds": 172,
                                "vehicle": "1166",
                            },
                            {
                                "destino": "Invalid negative",
                                "seconds": -5,
                            },
                        ],
                    },
                    {
                        "line": 3,
                        "line_id": 3,
                        "trains": [
                            {
                                "destino": "Aeroport",
                                "seconds": 45,
                                "meters": 120,
                                "vehicle": "4302",
                            }
                        ],
                    },
                ],
            }
        )

        result = await self.coordinator._async_update_data()
        self.assertEqual(
            self.session.calls[-1][0],
            "https://www.fgv.es/fgv/app/es/api/v1/V/horarios-prevision-3/16",
        )
        self.assertEqual(len(result), 2)
        # Sorted by seconds ascending (45s first, then 172s)
        self.assertEqual(result[0]["line"], "3")
        self.assertEqual(result[0]["destination"], "Aeroport")
        self.assertEqual(result[0]["seconds"], 45)
        self.assertEqual(result[0]["minutes"], 0)
        self.assertEqual(result[0]["time"], "00:00")
        self.assertEqual(result[0]["timestamp"], "2026-11-14T00:00:44+01:00")
        self.assertEqual(result[0]["meters"], 120)
        self.assertEqual(result[0]["vehicle"], "4302")

        self.assertEqual(result[1]["line"], "5")
        self.assertEqual(result[1]["destination"], "Marítim")
        self.assertEqual(result[1]["seconds"], 172)
        self.assertEqual(result[1]["minutes"], 2)
        self.assertEqual(result[1]["time"], "00:02")
        self.assertEqual(result[1]["timestamp"], "2026-11-14T00:02:51+01:00")
        self.assertEqual(result[1]["meters"], 450)
        self.assertEqual(result[1]["vehicle"], "1166")
        self.assertEqual(result[1]["capacity"], 397)
        self.assertEqual(result[1]["latitude"], 39.4699)
        self.assertEqual(result[1]["longitude"], -0.3763)

        # Empty previsiones returns empty list without error
        self.session.response = Response(json_data={"previsiones": []})
        self.assertEqual(await self.coordinator._async_update_data(), [])

        # Fallback to vh_first / vh_second when trains is empty
        self.session.response = Response(
            json_data={
                "previsiones": [
                    {
                        "line": "4",
                        "line_id": 4,
                        "trains": [],
                        "vh_first": {"destino": "Mas del Rosari", "seconds": 90, "meters": 300},
                        "vh_second": {"destino": "Ll. Llarga", "seconds": 240, "meters": 800},
                    }
                ]
            }
        )
        vh_result = await self.coordinator._async_update_data()
        self.assertEqual(len(vh_result), 2)
        self.assertEqual(vh_result[0]["destination"], "Mas del Rosari")
        self.assertEqual(vh_result[1]["destination"], "Ll. Llarga")

        # Error responses raise UpdateFailed
        for bad_resp, expected_msg in (
            (Response(status=502), "HTTP status 502"),
            (Response(body="not json"), "Invalid JSON"),
            (Response(json_data={"resultado": "Sin servicio"}), "Sin servicio"),
            (Response(json_data={"unexpected": 1}), "missing previsiones"),
            (Response(error=TimeoutError()), "TimeoutError"),
        ):
            with self.subTest(expected_msg=expected_msg):
                self.session.response = bad_resp
                with self.assertRaisesRegex(UpdateFailed, expected_msg):
                    await self.coordinator._async_update_data()

    async def test_emt_stops_fetch_pagination_and_step(self):
        flow = config_flow.ValenciaTransitConfigFlow()
        flow.hass = self.hass

        # 1. Multi-page fetch with exceededTransferLimit (and trailing "(id)" in denominacion)
        self.session.response = [
            Response(
                json_data={
                    "features": [
                        {"attributes": {"id_parada": 2230, "denominacion": "Palau de Congressos (2230)"}},
                        {"attributes": {"id_parada": 508, "denominacion": "Plaça de l'Ajuntament (508)"}},
                    ],
                    "exceededTransferLimit": True,
                }
            ),
            Response(
                json_data={
                    "features": [
                        {"attributes": {"id_parada": 10, "denominacion": "Tetuan"}},
                    ],
                    "exceededTransferLimit": False,
                }
            ),
        ]

        form = await flow.async_step_emt()
        self.assertEqual(form["type"], "form")
        self.assertEqual(len(self.session.calls), 2)
        self.assertNotIn("params", self.session.calls[0][1])
        self.assertEqual(self.session.calls[1][1]["params"], {"resultOffset": "2"})

        options = form["data_schema"]["stop_id"].config.options
        self.assertEqual(
            options,
            [
                {"value": "10", "label": "10: Tetuan"},
                {"value": "508", "label": "508: Plaça de l'Ajuntament"},
                {"value": "2230", "label": "2230: Palau de Congressos"},
            ],
        )
        self.assertTrue(form["data_schema"]["stop_id"].config.custom_value)

        # 2. Selecting a known stop creates "EMT {stop_id}: {stop_name}" without trailing (id)
        entry = await flow.async_step_emt({"stop_id": "2230"})
        self.assertEqual(entry["title"], "EMT 2230: Palau de Congressos")
        self.assertEqual(
            entry["data"],
            {
                "provider": "emt",
                "stop_id": "2230",
                "name": "EMT 2230: Palau de Congressos",
            },
        )

        # 3. Manual stop ID not in list creates "EMT {stop_id}"
        entry_unknown = await flow.async_step_emt({"stop_id": "9999"})
        self.assertEqual(entry_unknown["title"], "EMT 9999")

        # 4. Custom name overrides default title
        entry_custom = await flow.async_step_emt({"stop_id": "508", "name": "My Bus Stop"})
        self.assertEqual(entry_custom["title"], "My Bus Stop")

        # 5. Invalid stop ID returns form with error
        invalid = await flow.async_step_emt({"stop_id": "abc"})
        self.assertEqual(invalid["errors"], {"stop_id": "invalid_stop_id"})

    async def test_emt_stops_no_fallback_on_network_error(self):
        flow = config_flow.ValenciaTransitConfigFlow()
        flow.hass = self.hass
        self.session.response = Response(error=ClientError("network down"))

        with self.assertLogs(config_flow._LOGGER, logging.WARNING):
            form = await flow.async_step_emt()

        self.assertEqual(flow._emt_stops, {})
        self.assertEqual(form["data_schema"]["stop_id"].config.options, [])
        # Submitting manual ID after failed fetch does not re-fetch and succeeds
        calls_before = len(self.session.calls)
        entry = await flow.async_step_emt({"stop_id": "1330"})
        self.assertEqual(len(self.session.calls), calls_before)
        self.assertEqual(entry["title"], "EMT 1330")

    def test_translations_match_strings_schema(self):
        import json

        def collect_keys(obj, prefix=""):
            keys = set()
            for k, v in obj.items():
                full = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys |= collect_keys(v, full)
                else:
                    self.assertIsInstance(v, str)
                    self.assertTrue(v.strip(), f"Empty translation for {full}")
                    keys.add(full)
            return keys

        strings_data = json.loads((ROOT / "strings.json").read_text(encoding="utf-8"))
        expected_keys = collect_keys(strings_data)

        for lang in ("en", "ru", "es", "ca"):
            path = ROOT / "translations" / f"{lang}.json"
            self.assertTrue(path.is_file(), f"Missing translation file: {path}")
            lang_data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                collect_keys(lang_data),
                expected_keys,
                f"Translation keys mismatch in {lang}.json",
            )

    async def test_version_and_async_setup_card_registration(self):
        import json
        import re

        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        manifest_version = manifest["version"]
        self.assertRegex(
            manifest_version,
            r"^\d+\.\d+\.\d+(?:[-a-zA-Z0-9.]+)?$",
            "manifest.json version must be a valid SemVer string",
        )
        self.assertEqual(init.VERSION, manifest_version)

        registered_paths = []

        async def async_register_static_paths(configs):
            registered_paths.extend(configs)

        hass = types.SimpleNamespace(
            http=types.SimpleNamespace(
                async_register_static_paths=async_register_static_paths
            ),
            extra_js_urls=[],
        )
        result = await init.async_setup(hass, {})
        self.assertTrue(result)
        self.assertEqual(len(registered_paths), 1)
        self.assertEqual(registered_paths[0].url_path, init.CARD_URL)
        self.assertFalse(registered_paths[0].cache_headers)
        self.assertEqual(
            hass.extra_js_urls,
            [f"{init.CARD_URL}?v={manifest_version}"],
        )


if __name__ == "__main__":
    unittest.main()
