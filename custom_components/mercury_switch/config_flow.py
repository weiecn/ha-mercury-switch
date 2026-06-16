"""Config flow for Mercury Switch integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .api import MercurySwitchAPI

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _test_connection(hass: HomeAssistant, data: dict) -> dict:
    """Validate the connection by logging in and fetching system info."""
    api = MercurySwitchAPI(
        host=data[CONF_HOST],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
    )

    try:
        logged_in = await api.login()
        if not logged_in:
            return {"reason": "登录失败，请在HA系统日志中查看详细错误"}

        sysinfo = await api.get_system_info()
        if not sysinfo:
            return {"reason": "无法获取设备信息，请检查IP地址是否正确"}

        return {"success": True, "device": sysinfo.get("description", "Unknown")}

    except Exception as exc:
        _LOGGER.exception("连接测试异常")
        return {"reason": f"异常: {exc}"}
    finally:
        # Don't close the session — it's HA's shared session
        pass


class MercurySwitchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mercury Switch."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            result = await _test_connection(self.hass, user_input)
            if result.get("success"):
                await self.async_set_unique_id(
                    f"mercury_switch_{user_input[CONF_HOST]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Mercury Switch ({result['device']})",
                    data=user_input,
                )
            errors["base"] = result.get("reason", "unknown_error")

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
