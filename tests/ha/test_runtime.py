"""Offline/recovery and diagnostics are tested with real HA entities."""
import json

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solarman_azzurro.const import DOMAIN
from custom_components.solarman_azzurro.diagnostics import async_get_config_entry_diagnostics
from tests.test_protocol import snapshot

pytestmark = pytest.mark.asyncio
DATA = {"name": "Synthetic private name", "host": "private.example", "logger_serial": 1234567890,
        "port": 8899, "scan_interval": 10, "full_scan_interval": 30}


def entry(hass):
    result = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id=str(DATA["logger_serial"]))
    result.add_to_hass(hass)
    return result


async def test_unavailable_and_recovery(hass, logger_read):
    existing = entry(hass)
    assert await hass.config_entries.async_setup(existing.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    power_id = registry.async_get_entity_id("sensor", DOMAIN, f'{DATA["logger_serial"]}_potenza_prodotta')
    connection_id = registry.async_get_entity_id("binary_sensor", DOMAIN, f'{DATA["logger_serial"]}_collegamento_locale')
    assert hass.states.get(power_id).state == "2500"
    logger_read.side_effect = OSError("synthetic disconnect")
    await existing.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(power_id).state == "unavailable"
    assert hass.states.get(connection_id).state == "off"
    logger_read.side_effect = None
    await existing.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(power_id).state == "2500"
    assert hass.states.get(connection_id).state == "on"


async def test_diagnostics_exclude_identity_and_household_readings(hass, logger_read):
    existing = entry(hass)
    registers = snapshot()
    registers[0x040C] = 1 << 11
    logger_read.return_value = registers
    assert await hass.config_entries.async_setup(existing.entry_id)
    await hass.async_block_till_done()
    data = await async_get_config_entry_diagnostics(hass, existing)
    assert data["active_event_codes"] == ["ID124"]
    assert data["last_update_success"] is True
    text = json.dumps(data)
    for private in (DATA["name"], DATA["host"], str(DATA["logger_serial"]), existing.entry_id, "potenza_prodotta", "2500"):
        assert private not in text
    assert dict(existing.data) == DATA


async def test_diagnostics_before_first_successful_setup(hass):
    data = await async_get_config_entry_diagnostics(hass, entry(hass))
    assert data["runtime_available"] is False
    assert data["scan_interval_seconds"] == 10
    assert data["full_snapshot_interval_seconds"] == 30


async def test_fast_full_polling_and_failure_keep_correct_timestamps(hass, logger_read):
    from custom_components.solarman_azzurro.profile import FAST_WINDOWS, WINDOWS
    existing = entry(hass)
    assert await hass.config_entries.async_setup(existing.entry_id)
    await hass.async_block_till_done()
    coordinator = existing.runtime_data
    assert logger_read.call_args.args == (WINDOWS,)
    old_full_sample = coordinator.last_full_sample
    await coordinator.async_refresh()
    assert logger_read.call_args.args == (FAST_WINDOWS,)
    assert coordinator.last_full_sample == old_full_sample
    logger_read.return_value = {0x0404: 2}
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    assert coordinator.last_full_sample == old_full_sample
    logger_read.return_value = snapshot()
    coordinator._last_full_monotonic = 0
    await coordinator.async_refresh()
    assert logger_read.call_args.args == (WINDOWS,)
    assert coordinator.last_update_success is True
    assert coordinator.last_full_sample > old_full_sample


@pytest.mark.parametrize("configured,expected", [(0, 1), (3, 3)])
async def test_existing_interval_preserves_identity_and_uses_minimum(hass, logger_read, configured, expected):
    existing = MockConfigEntry(domain=DOMAIN, data={**DATA, "scan_interval": configured},
                               unique_id=str(DATA["logger_serial"]))
    existing.add_to_hass(hass)
    assert await hass.config_entries.async_setup(existing.entry_id)
    await hass.async_block_till_done()
    assert existing.runtime_data.interval == expected
    assert existing.runtime_data.full_interval == 30
    assert existing.unique_id == str(DATA["logger_serial"])


async def test_unload_and_ha_stop_close_clients(hass, logger_read):
    from homeassistant.const import EVENT_HOMEASSISTANT_STOP
    existing = entry(hass)
    assert await hass.config_entries.async_setup(existing.entry_id)
    await hass.async_block_till_done()
    previous = existing.runtime_data.client
    assert await hass.config_entries.async_unload(existing.entry_id)
    assert previous._closed
    assert await hass.config_entries.async_setup(existing.entry_id)
    await hass.async_block_till_done()
    current = existing.runtime_data.client
    assert not current._closed
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert current._closed


@pytest.mark.parametrize("language,power_name", [("en", "Solar production power"), ("it", "Potenza prodotta")])
async def test_translated_names_preserve_existing_registry(hass, logger_read, language, power_name):
    """A language update must retain every registered ID and user override."""
    from custom_components.solarman_azzurro.profile import MEASUREMENTS

    hass.config.language = language
    existing = entry(hass)
    registry = er.async_get(hass)
    for platform, keys in (
        ("sensor", [item.key for item in MEASUREMENTS] + ["ultimo_aggiornamento_locale"]),
        ("binary_sensor", ["collegamento_locale", "allarme_inverter"]),
    ):
        for key in keys:
            registered = registry.async_get_or_create(
                platform, DOMAIN, f'{DATA["logger_serial"]}_{key}',
                suggested_object_id=f"legacy_{key}", config_entry=existing,
            )
            if key == "batteria":
                registry.async_update_entity(registered.entity_id, name="My battery")
    before = {(item.entity_id, item.unique_id) for item in er.async_entries_for_config_entry(registry, existing.entry_id)}
    original_data = dict(existing.data)
    original_options = dict(existing.options)
    assert await hass.config_entries.async_setup(existing.entry_id)
    await hass.async_block_till_done()
    after = er.async_entries_for_config_entry(registry, existing.entry_id)
    assert len(after) == 53
    assert before == {(item.entity_id, item.unique_id) for item in after}
    assert registry.async_get("sensor.legacy_potenza_prodotta").original_name == power_name
    assert registry.async_get("sensor.legacy_batteria").name == "My battery"
    assert hass.states.get("sensor.legacy_batteria").attributes["friendly_name"] == "My battery"
    assert dict(existing.data) == original_data
    assert dict(existing.options) == original_options
    assert hass.states.get("sensor.legacy_potenza_prodotta").state == "2500"
