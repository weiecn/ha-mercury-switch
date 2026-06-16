"""Sensor platform for Mercury Switch."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.const import (
    UnitOfPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MercurySwitchConfigEntry
from .const import (
    DOMAIN,
    POE_PORT_COUNT,
    ETH_PORT_COUNT,
    POE_STATUS_MAP,
    SPEED_MAP,
    PD_CLASS_MAP,
    POE_STATUS_ICON_MAP,
)
from .coordinator import MercurySwitchCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MercurySensorDescription(SensorEntityDescription):
    """Describes a Mercury switch sensor."""

    value_fn: Callable[[dict], str | float | int | None] = lambda d: None
    group: str = "system"
    port_index: int = 0


SYSTEM_SENSORS: tuple[MercurySensorDescription, ...] = (
    MercurySensorDescription(
        key="total_power",
        translation_key="system_total_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        group="poe_global",
        value_fn=lambda d: d.get("global", {}).get("total_power"),
    ),
    MercurySensorDescription(
        key="used_power",
        translation_key="system_used_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        group="poe_global",
        value_fn=lambda d: d.get("global", {}).get("used_power"),
    ),
    MercurySensorDescription(
        key="remaining_power",
        translation_key="system_remaining_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        group="poe_global",
        value_fn=lambda d: d.get("global", {}).get("remaining_power"),
    ),
    MercurySensorDescription(
        key="power_usage_pct",
        translation_key="system_power_usage_pct",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        group="poe_global",
        value_fn=lambda d: (
            round(
                d.get("used_power", 0) / d.get("total_power", 1) * 100, 1
            ) if d.get("total_power", 0) > 0 else 0
        ),
    ),
    MercurySensorDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        group="main",
        value_fn=lambda d: d.get("uptime", ""),
    ),
    MercurySensorDescription(
        key="loop_prevention",
        translation_key="loop_prevention",
        group="loop",
        value_fn=lambda d: "启用" if d.get("enabled") else "禁用",
    ),
)


def _make_poe_sensors() -> list[MercurySensorDescription]:
    """Generate per-port PoE sensor descriptions."""
    descs = []
    for port_idx in range(POE_PORT_COUNT):
        descs.extend([
            MercurySensorDescription(
                key=f"poe_{port_idx+1}_power",
                translation_key="poe_port_power",
                native_unit_of_measurement=UnitOfPower.WATT,
                device_class=SensorDeviceClass.POWER,
                state_class=SensorStateClass.MEASUREMENT,
                suggested_display_precision=1,
                group="poe_port",
                port_index=port_idx,
                value_fn=lambda p: p.get("power_w", 0),
            ),
            MercurySensorDescription(
                key=f"poe_{port_idx+1}_current",
                translation_key="poe_port_current",
                native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
                device_class=SensorDeviceClass.CURRENT,
                state_class=SensorStateClass.MEASUREMENT,
                suggested_display_precision=0,
                group="poe_port",
                port_index=port_idx,
                value_fn=lambda p: p.get("current_ma", 0),
            ),
            MercurySensorDescription(
                key=f"poe_{port_idx+1}_voltage",
                translation_key="poe_port_voltage",
                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                device_class=SensorDeviceClass.VOLTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                suggested_display_precision=1,
                group="poe_port",
                port_index=port_idx,
                value_fn=lambda p: p.get("voltage_v", 0),
            ),
            MercurySensorDescription(
                key=f"poe_{port_idx+1}_status",
                translation_key="poe_port_status",
                device_class=SensorDeviceClass.ENUM,
                options=list(POE_STATUS_MAP.values()),
                group="poe_port",
                port_index=port_idx,
                value_fn=lambda p: POE_STATUS_MAP.get(p.get("power_status", 0), "未知"),
            ),
            MercurySensorDescription(
                key=f"poe_{port_idx+1}_pd_class",
                translation_key="poe_port_pd_class",
                entity_category=EntityCategory.DIAGNOSTIC,
                group="poe_port",
                port_index=port_idx,
                value_fn=lambda p: PD_CLASS_MAP.get(p.get("pd_class", 5), "未知"),
            ),
        ])
    return descs


def _make_rate_sensors() -> list[MercurySensorDescription]:
    """Generate per-port packet rate sensor descriptions."""
    descs = []
    for port_idx in range(ETH_PORT_COUNT):
        descs.extend([
            MercurySensorDescription(
                key=f"port_{port_idx+1}_rx_rate",
                translation_key="port_rx_rate",
                native_unit_of_measurement="pkts/s",
                state_class=SensorStateClass.MEASUREMENT,
                group="port_rate",
                port_index=port_idx,
                value_fn=lambda p: p.get("rx_rate", 0),
            ),
            MercurySensorDescription(
                key=f"port_{port_idx+1}_tx_rate",
                translation_key="port_tx_rate",
                native_unit_of_measurement="pkts/s",
                state_class=SensorStateClass.MEASUREMENT,
                group="port_rate",
                port_index=port_idx,
                value_fn=lambda p: p.get("tx_rate", 0),
            ),
        ])
    return descs


def _make_stats_sensors() -> list[MercurySensorDescription]:
    """Generate per-port packet count sensor descriptions."""
    descs = []
    for port_idx in range(ETH_PORT_COUNT):
        descs.extend([
            MercurySensorDescription(
                key=f"port_{port_idx+1}_tx_good",
                translation_key="port_tx_good",
                state_class=SensorStateClass.TOTAL_INCREASING,
                group="port_stats",
                port_index=port_idx,
                value_fn=lambda p: p.get("tx_good_packets", 0),
            ),
            MercurySensorDescription(
                key=f"port_{port_idx+1}_tx_bad",
                translation_key="port_tx_bad",
                state_class=SensorStateClass.TOTAL_INCREASING,
                group="port_stats",
                port_index=port_idx,
                value_fn=lambda p: p.get("tx_bad_packets", 0),
            ),
            MercurySensorDescription(
                key=f"port_{port_idx+1}_rx_good",
                translation_key="port_rx_good",
                state_class=SensorStateClass.TOTAL_INCREASING,
                group="port_stats",
                port_index=port_idx,
                value_fn=lambda p: p.get("rx_good_packets", 0),
            ),
            MercurySensorDescription(
                key=f"port_{port_idx+1}_rx_bad",
                translation_key="port_rx_bad",
                state_class=SensorStateClass.TOTAL_INCREASING,
                group="port_stats",
                port_index=port_idx,
                value_fn=lambda p: p.get("rx_bad_packets", 0),
            ),
        ])
    return descs


def _make_link_sensors() -> list[MercurySensorDescription]:
    """Generate per-port link status sensor descriptions."""
    descs = []
    for port_idx in range(ETH_PORT_COUNT):
        descs.extend([
            MercurySensorDescription(
                key=f"port_{port_idx+1}_link_status",
                translation_key="eth_link_status",
                group="eth_port",
                port_index=port_idx,
                value_fn=lambda p: "已连接" if p.get("speed_actual", 0) > 0 else "未连接",
            ),
            MercurySensorDescription(
                key=f"port_{port_idx+1}_link_speed",
                translation_key="eth_link_speed",
                entity_category=EntityCategory.DIAGNOSTIC,
                group="eth_port",
                port_index=port_idx,
                value_fn=lambda p: SPEED_MAP.get(p.get("speed_actual", 0), "未知"),
            ),
        ])
    return descs


DESCRIPTIONS: list[MercurySensorDescription] = (
    list(SYSTEM_SENSORS)
    + _make_poe_sensors()
    + _make_rate_sensors()
    + _make_stats_sensors()
    + _make_link_sensors()
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MercurySwitchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mercury Switch sensors."""
    coordinator: MercurySwitchCoordinator = entry.runtime_data.coordinator

    entities: list[MercurySensor] = []
    for desc in DESCRIPTIONS:
        entities.append(MercurySensor(coordinator, entry, desc))

    async_add_entities(entities)


class MercurySensor(CoordinatorEntity[MercurySwitchCoordinator], SensorEntity):
    """Representation of a Mercury Switch sensor."""

    entity_description: MercurySensorDescription

    def __init__(
        self,
        coordinator: MercurySwitchCoordinator,
        entry: MercurySwitchConfigEntry,
        description: MercurySensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._port_index = description.port_index
        self._group = description.group
        self._key = description.key

        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mercury Switch ({entry.data.get('host', '')})",
            "manufacturer": "Mercury (水星)",
            "model": "SE109P Pro",
        }

        # Generate human-readable name
        port = self._port_index + 1
        if self._group == "poe_global":
            names = {
                "total_power": "总功率", "used_power": "已用功率",
                "remaining_power": "剩余功率", "power_usage_pct": "功率使用率",
            }
            self._attr_name = f"PoE {names.get(self._key, self._key)}"
        elif self._group == "poe_port":
            names = {
                "_power": "功率", "_current": "电流",
                "_voltage": "电压", "_status": "供电状态",
                "_pd_class": "PD Class", "_power_limit": "功率限制",
            }
            base = next((v for k, v in names.items() if k in self._key), self._key)
            self._attr_name = f"PoE 端口 {port} {base}"
        elif self._group == "port_rate":
            names = {"rx_rate": "收包速率", "tx_rate": "发包速率"}
            base = next((v for k, v in names.items() if k in self._key), self._key)
            self._attr_name = f"端口 {port} {base}"
        elif self._group == "port_stats":
            names = {
                "tx_good": "正常发包", "tx_bad": "失败发包",
                "rx_good": "正常收包", "rx_bad": "失败收包",
            }
            base = next((v for k, v in names.items() if k in self._key), self._key)
            self._attr_name = f"端口 {port} {base}"
        elif self._group == "eth_port":
            names = {"link_status": "连接状态", "link_speed": "实际速率"}
            base = next((v for k, v in names.items() if k in self._key), self._key)
            self._attr_name = f"端口 {port} {base}"
        elif self._group == "main":
            if self._key == "uptime":
                self._attr_name = "运行时间"
        elif self._group == "loop":
            self._attr_name = "环回保护"
        else:
            self._attr_name = f"Mercury {self._key}"

    @property
    def native_value(self) -> str | float | int | None:
        """Return the sensor value."""
        data = self.coordinator.data
        if not data:
            return None

        try:
            if self._group == "poe_global":
                poe = data.get("poe", {})
                return self.entity_description.value_fn(poe)
            elif self._group == "poe_port":
                ports = data.get("poe", {}).get("ports", [])
                if self._port_index < len(ports):
                    return self.entity_description.value_fn(ports[self._port_index])
                return None
            elif self._group == "main":
                main = data.get("main", {})
                return self.entity_description.value_fn(main)
            elif self._group == "loop":
                loop = data.get("loop_prevention", {})
                return self.entity_description.value_fn(loop)
            elif self._group == "port_rate":
                ports = data.get("main", {}).get("port_rates", [])
                if self._port_index < len(ports):
                    return self.entity_description.value_fn(ports[self._port_index])
                return None
            elif self._group == "port_stats":
                ports = data.get("stats", {}).get("ports", [])
                if self._port_index < len(ports):
                    return self.entity_description.value_fn(ports[self._port_index])
                return None
            elif self._group == "eth_port":
                ports = data.get("eth", {}).get("ports", [])
                if self._port_index < len(ports):
                    return self.entity_description.value_fn(ports[self._port_index])
                return None
        except (KeyError, IndexError, TypeError) as exc:
            _LOGGER.debug("Error getting sensor value for %s: %s", self._key, exc)
            return None

        return None

    @property
    def icon(self) -> str | None:
        """Return icon based on status."""
        if self._group == "poe_port" and "_status" in self._key:
            data = self.coordinator.data
            if data:
                ports = data.get("poe", {}).get("ports", [])
                if self._port_index < len(ports):
                    status_code = ports[self._port_index].get("power_status", 0)
                    return POE_STATUS_ICON_MAP.get(status_code, "mdi:help")
        return super().icon
