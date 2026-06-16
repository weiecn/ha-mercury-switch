"""Switch platform for Mercury Switch - PoE power control."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
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
    """Set up Mercury Switch PoE switches."""
    coordinator: MercurySwitchCoordinator = entry.runtime_data.coordinator

    entities = []
    for port_idx in range(POE_PORT_COUNT):
        entities.append(MercuryPoeSwitch(coordinator, entry, port_idx))

    async_add_entities(entities)


class MercuryPoeSwitch(
    CoordinatorEntity[MercurySwitchCoordinator], SwitchEntity
):
    """Representation of a PoE port switch."""

    def __init__(
        self,
        coordinator: MercurySwitchCoordinator,
        entry: MercurySwitchConfigEntry,
        port_index: int,
    ) -> None:
        """Initialize the PoE switch."""
        super().__init__(coordinator)
        self._port_index = port_index
        self._port_number = port_index + 1

        self._attr_unique_id = f"{entry.entry_id}_poe_switch_{self._port_number}"
        self._attr_name = f"PoE Port {self._port_number}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mercury Switch ({entry.data.get('host', '')})",
            "manufacturer": "Mercury (水星)",
            "model": "SE109P Pro",
        }
        self._attr_icon = "mdi:power-plug"

    @property
    def is_on(self) -> bool | None:
        """Return true if PoE is enabled on this port."""
        data = self.coordinator.data
        if not data:
            return None
        ports = data.get("poe", {}).get("ports", [])
        if self._port_index < len(ports):
            return ports[self._port_index].get("enabled", False)
        return None

    async def async_turn_on(self, **kwargs) -> None:
        """Enable PoE on this port."""
        api = self.coordinator.api
        success = await api.set_poe_port_state(self._port_number, True)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to enable PoE on port %d", self._port_number)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable PoE on this port."""
        api = self.coordinator.api
        success = await api.set_poe_port_state(self._port_number, False)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to disable PoE on port %d", self._port_number)
