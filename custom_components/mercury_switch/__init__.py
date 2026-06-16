"""Integration for Mercury SE109P Pro PoE Switch."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .api import MercurySwitchAPI
from .const import DOMAIN, PLATFORMS
from .coordinator import MercurySwitchCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class MercurySwitchRuntimeData:
    """Runtime data for the integration."""

    api: MercurySwitchAPI
    coordinator: MercurySwitchCoordinator


MercurySwitchConfigEntry = ConfigEntry[MercurySwitchRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: MercurySwitchConfigEntry
) -> bool:
    """Set up Mercury Switch from a config entry."""
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    api = MercurySwitchAPI(host=host, username=username, password=password)
    coordinator = MercurySwitchCoordinator(hass, api)

    # Initial fetch
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = MercurySwitchRuntimeData(
        api=api,
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MercurySwitchConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        api = entry.runtime_data.api
        await api.close()
    return unload_ok
