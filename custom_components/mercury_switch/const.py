"""Constants for Mercury Switch integration."""

DOMAIN = "mercury_switch"
PLATFORMS = ["sensor", "switch", "button", "binary_sensor"]

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

DEFAULT_POLL_INTERVAL = 30

POE_PORT_COUNT = 8
ETH_PORT_COUNT = 9

# PoE power status codes
POE_STATUS_MAP = {
    0: "未供电", 1: "开启中", 2: "供电", 3: "过载",
    4: "短路", 5: "非标准PD", 6: "电压过高",
    7: "电压过低", 8: "硬件错误", 9: "温度过高",
}
POE_STATUS_ICON_MAP = {
    0: "mdi:power-plug-off", 1: "mdi:power-plug", 2: "mdi:power-plug",
    3: "mdi:alert", 4: "mdi:alert-circle", 5: "mdi:help-circle",
    6: "mdi:flash-alert", 7: "mdi:flash-alert",
    8: "mdi:close-circle", 9: "mdi:thermometer-alert",
}

# Speed mapping
SPEED_MAP = {
    0: "断开", 1: "自动", 2: "10M半双工", 3: "10M全双工",
    4: "100M半双工", 5: "100M全双工", 6: "1000M全双工",
    7: "2.5G全双工", 8: "10G全双工",
}

# PD Class mapping
PD_CLASS_MAP = {0: "Class 0", 1: "Class 1", 2: "Class 2",
                 3: "Class 3", 4: "Class 4", 5: "未知"}
