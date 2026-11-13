import json
from pathlib import Path
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.frontend import add_extra_js_url
import homeassistant.helpers.config_validation as cv

DOMAIN = "vlc_transport_ha"
CARD_URL = "/vlc_transport_ha/vlc-transport-ha-card.js"
PLATFORMS: list[Platform] = [Platform.SENSOR]
VERSION: str = json.loads(
    (Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
)["version"]

# Configuration schema for UI-only integrations
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register static path and Lovelace card on startup."""
    frontend_path = Path(__file__).parent / "frontend" / "vlc-transport-ha-card.js"
    await hass.http.async_register_static_paths([
        StaticPathConfig(CARD_URL, str(frontend_path), cache_headers=False)
    ])
    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Valencia Transit from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
