"""Solarman Azzurro: local, read-only inverter telemetry."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ProtocolError, SolarmanClient
from .const import (CONF_FULL_INTERVAL, CONF_INTERVAL, CONF_SERIAL, DEFAULT_FULL_INTERVAL,
                    DEFAULT_INTERVAL, DEFAULT_PORT, DOMAIN, MIN_INTERVAL)
from .profile import FAST_WINDOWS, WINDOWS, decode

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


class AzzurroCoordinator(DataUpdateCoordinator):
    """A failed transaction invalidates all live values; retry on the next interval."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.client = SolarmanClient(entry.data[CONF_HOST], entry.data[CONF_SERIAL], entry.data.get(CONF_PORT, DEFAULT_PORT))
        self.last_sample = None
        self.sample_duration = 0.0
        self.last_full_sample = None
        self.interval = max(MIN_INTERVAL, entry.options.get(CONF_INTERVAL, entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL)))
        self.full_interval = max(self.interval, entry.options.get(CONF_FULL_INTERVAL,
                                 entry.data.get(CONF_FULL_INTERVAL, DEFAULT_FULL_INTERVAL)))
        self._last_full_monotonic = 0.0
        self._registers = {}
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=self.interval), always_update=True)

    async def _async_update_data(self):
        started = asyncio.get_running_loop().time()
        try:
            full = not self._registers or started - self._last_full_monotonic >= self.full_interval
            windows = WINDOWS if full else FAST_WINDOWS
            fresh = await self.client.read(windows)
            if any(start + offset not in fresh for start, count in windows for offset in range(count)):
                raise ProtocolError("Incomplete polling snapshot")
            merged = self._registers | fresh
            data = decode(merged)
        except (OSError, TimeoutError, asyncio.IncompleteReadError, ProtocolError) as err:
            raise UpdateFailed(f"Local inverter read failed: {err}") from err
        self.last_sample = dt_util.utcnow()
        self._registers = merged
        if full:
            self.last_full_sample = self.last_sample
            self._last_full_monotonic = started
        self.sample_duration = round(asyncio.get_running_loop().time() - started, 3)
        return data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = AzzurroCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator

        async def stop_client(event):
            await coordinator.client.async_close()

        entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_client))
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.client.async_close()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.async_close()
        return True
    return False
