"""DataUpdateCoordinator for Mercury Switch."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MercurySwitchAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MercurySwitchCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch data from Mercury Switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: MercurySwitchAPI,
        poll_interval: int = 30,
    ):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.api = api

    async def _async_update_data(self) -> dict:
        """Fetch all data from the switch."""
        data: dict = {}

        # PoE status
        poe = await self.api.get_poe_status()
        if poe is None:
            raise UpdateFailed("无法获取PoE状态数据")
        data["poe"] = poe

        # Port status (link, speed)
        eth = await self.api.get_port_status()
        if eth is None:
            raise UpdateFailed("无法获取端口状态数据")
        data["eth"] = eth

        # Main page (uptime, packet rates, loop detection)
        main = await self.api.get_main_status()
        if main:
            data["main"] = main

        # Port statistics (packet counts)
        stats = await self.api.get_port_statistics()
        if stats:
            data["stats"] = stats

        # Loop prevention config
        loop = await self.api.get_loop_prevention()
        if loop:
            data["loop_prevention"] = loop

        return data
