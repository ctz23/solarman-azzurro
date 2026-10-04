"""Downloadable diagnostics containing only explicitly selected metadata."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_FULL_INTERVAL, CONF_INTERVAL, DEFAULT_FULL_INTERVAL, DEFAULT_INTERVAL, MIN_INTERVAL
from .profile import PROFILE_NAME


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry):
    """Exclude names, addresses, serials, raw registers and household readings."""
    interval = max(MIN_INTERVAL, entry.options.get(CONF_INTERVAL, entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL)))
    full_interval = max(interval, entry.options.get(CONF_FULL_INTERVAL, entry.data.get(CONF_FULL_INTERVAL, DEFAULT_FULL_INTERVAL)))
    result = {
        "profile": PROFILE_NAME,
        "scan_interval_seconds": interval,
        "full_snapshot_interval_seconds": full_interval,
        "runtime_available": hasattr(entry, "runtime_data"),
    }
    if hasattr(entry, "runtime_data"):
        coordinator = entry.runtime_data
        result.update(
            tcp_connected=coordinator.client.connected,
            tcp_connection_count=coordinator.client.connection_count,
            modbus_request_count=coordinator.client.request_count,
            last_update_success=coordinator.last_update_success,
            sample_duration_seconds=coordinator.sample_duration,
            has_sample=coordinator.last_sample is not None,
            has_full_sample=coordinator.last_full_sample is not None,
            active_event_codes=[event["code"] for event in (coordinator.data or {}).get("eventi_attivi", [])],
        )
    return result
