"""Button platform for Mercury Switch - PoE port power cycle."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MercurySwitchConfigEntry
from .const import DOMAIN, POE_PORT_COUNT
from .coordinator import MercurySwitchCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MercurySwitchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mercury Switch PoE power cycle buttons."""
    coordinator: MercurySwitchCoordinator = entry.runtime_data.coordinator

    entities = []
    for port_idx in range(POE_PORT_COUNT):
        entities.append(MercuryPoePowerCycleButton(coordinator, entry, port_idx))

    async_add_entities(entities)


class MercuryPoePowerCycleButton(
    CoordinatorEntity[MercurySwitchCoordinator], ButtonEntity
):
    """Button to power cycle (重新上电) a PoE port."""

    def __init__(
        self,
        coordinator: MercurySwitchCoordinator,
        entry: MercurySwitchConfigEntry,
        port_index: int,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._port_index = port_index
        self._port_number = port_index + 1

        self._attr_unique_id = (
            f"{entry.entry_id}_poe_power_cycle_{self._port_number}"
        )
        self._attr_name = f"PoE Port {self._port_number} Power Cycle"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mercury Switch ({entry.data.get('host', '')})",
            "manufacturer": "Mercury (水星)",
            "model": "SE109P Pro",
        }
        self._attr_icon = "mdi:restart"
        self._attr_translation_key = "poe_power_cycle"

    async def async_press(self) -> None:
        """Handle the button press."""
        api = self.coordinator.api
        success = await api.power_cycle_port(self._port_number)
        if success:
            _LOGGER.info("Power cycled PoE port %d", self._port_number)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to power cycle PoE port %d", self._port_number)
