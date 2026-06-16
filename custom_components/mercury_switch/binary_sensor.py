"""Binary sensor platform for Mercury Switch."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MercurySwitchConfigEntry
from .const import DOMAIN
from .coordinator import MercurySwitchCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MercurySwitchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mercury Switch binary sensors."""
    coordinator: MercurySwitchCoordinator = entry.runtime_data.coordinator
    async_add_entities([
        MercuryLoopDetectedSensor(coordinator, entry),
    ])


class MercuryLoopDetectedSensor(
    CoordinatorEntity[MercurySwitchCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether a network loop has been detected."""

    def __init__(
        self,
        coordinator: MercurySwitchCoordinator,
        entry: MercurySwitchConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_loop_detected"
        self._attr_name = "Loop Detected"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_icon = "mdi:lan"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mercury Switch ({entry.data.get('host', '')})",
            "manufacturer": "Mercury (水星)",
            "model": "SE109P Pro",
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if a loop is detected."""
        data = self.coordinator.data
        if not data:
            return None
        return data.get("main", {}).get("loop_detected", None)
