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
    "homeassistant.core", "homeassistant.helpers", "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.device_registry", "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.update_coordinator", "homeassistant.components.sensor",
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
    pass


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
test_modules["homeassistant.config_entries"].ConfigEntry = object
test_modules["homeassistant.config_entries"].ConfigFlow = ConfigFlow
test_modules["homeassistant.config_entries"].ConfigFlowResult = dict
test_modules["homeassistant.core"].HomeAssistant = object
test_modules["homeassistant.helpers.aiohttp_client"].async_get_clientsession = lambda hass: hass.session
test_modules["homeassistant.helpers.device_registry"].DeviceEntryType = type("DeviceEntryType", (), {})
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
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


with patch.dict(sys.modules, test_modules):
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


if __name__ == "__main__":
    unittest.main()
