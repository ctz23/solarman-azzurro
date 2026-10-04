"""Exercise the actual Home Assistant flow manager and entry lifecycle."""
import asyncio

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solarman_azzurro.api import ProtocolError
from custom_components.solarman_azzurro.const import DOMAIN
from custom_components.solarman_azzurro.discovery import DiscoveredLogger

pytestmark = pytest.mark.asyncio
DATA = {"name": "Azzurro", "host": "logger.example", "logger_serial": 1234567890,
        "port": 8899, "scan_interval": 10, "full_scan_interval": 30}


def entry(hass):
    result = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id=str(DATA["logger_serial"]))
    result.add_to_hass(hass)
    return result


async def test_manual_setup_and_unload(hass, logger_read):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Azzurro"
    config_entry = result["result"]
    assert config_entry.unique_id == str(DATA["logger_serial"])
    registry = er.async_get(hass)
    assert er.async_entries_for_config_entry(registry, config_entry.entry_id)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize("failure,error", [(OSError(), "cannot_connect"),
    (TimeoutError(), "cannot_connect"), (asyncio.IncompleteReadError(b"", 3), "cannot_connect"), (ProtocolError("bad profile"), "unsupported_profile")])
async def test_setup_failure_is_recoverable(hass, logger_read, failure, error):
    logger_read.side_effect = failure
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert not hass.config_entries.async_entries(DOMAIN)
    logger_read.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_does_not_change_existing_connection(hass, logger_read):
    existing = entry(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**DATA, "host": "wrong.example"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert existing.data["host"] == DATA["host"]
    logger_read.assert_not_awaited()


async def test_single_discovery_prefills_without_creating_entry(hass, no_real_discovery):
    no_real_discovery.return_value = [DiscoveredLogger("127.0.0.1", 1234567890)]
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    defaults = result["data_schema"]({})
    assert defaults["host"] == "127.0.0.1"
    assert defaults["logger_serial"] == 1234567890
    assert defaults["port"] == 8899
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize("choice", ["127.0.0.2/1234567891", "manual"])
async def test_multiple_discovery_requires_choice(hass, no_real_discovery, choice):
    no_real_discovery.return_value = [DiscoveredLogger("127.0.0.1", 1234567890),
                                    DiscoveredLogger("127.0.0.2", 1234567891)]
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["step_id"] == "select_logger"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"logger": choice})
    assert result["step_id"] == "user"
    fields = {marker.schema: marker for marker in result["data_schema"].schema}
    assert fields["host"].default() == ("127.0.0.2" if choice != "manual" else "")
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_discovery_socket_failure_falls_back_to_manual(hass, no_real_discovery):
    no_real_discovery.side_effect = OSError("broadcast unavailable")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_configured_logger_not_proposed_again(hass, no_real_discovery):
    entry(hass)
    no_real_discovery.return_value = [DiscoveredLogger("127.0.0.1", 1234567890)]
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    fields = {marker.schema: marker for marker in result["data_schema"].schema}
    assert fields["host"].default() == ""


async def test_failed_reconfigure_retains_data(hass, logger_read):
    existing = entry(hass)
    logger_read.side_effect = ProtocolError("wrong logger")
    result = await hass.config_entries.flow.async_init(DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": existing.entry_id})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "wrong.example", "port": 8899})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_profile"}
    assert dict(existing.data) == DATA


async def test_reconfigure_preserves_entity_ids_and_unique_ids(hass, logger_read):
    existing = entry(hass)
    assert await hass.config_entries.async_setup(existing.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    before = {(item.entity_id, item.unique_id) for item in er.async_entries_for_config_entry(registry, existing.entry_id)}
    result = await hass.config_entries.flow.async_init(DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": existing.entry_id})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "new.example", "port": 8898})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert existing.data["host"] == "new.example"
    assert existing.data["logger_serial"] == DATA["logger_serial"]
    assert existing.unique_id == str(DATA["logger_serial"])
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert before == {(item.entity_id, item.unique_id) for item in er.async_entries_for_config_entry(registry, existing.entry_id)}


async def test_options_reload_with_new_interval(hass, logger_read):
    existing = entry(hass)
    assert await hass.config_entries.async_setup(existing.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(existing.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"scan_interval": 15, "full_scan_interval": 30})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert existing.options == {"scan_interval": 15, "full_scan_interval": 30}
    assert existing.runtime_data.interval == 15
    assert existing.runtime_data.update_interval.total_seconds() == 15


@pytest.mark.parametrize("field", ["name", "host"])
async def test_whitespace_name_and_host_rejected(hass, logger_read, field):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**DATA, field: "   "})
    assert result["errors"] == {field: "required"}
    logger_read.assert_not_awaited()


@pytest.mark.parametrize("field", ["scan_interval", "full_scan_interval"])
async def test_interval_below_one_rejected(field):
    import voluptuous as vol
    from custom_components.solarman_azzurro.config_flow import schema
    with pytest.raises(vol.Invalid):
        schema()({**DATA, field: 0})


async def test_full_interval_must_not_be_shorter_than_power(hass, logger_read):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"],
        {**DATA, "scan_interval": 30, "full_scan_interval": 10})
    assert result["errors"] == {"full_scan_interval": "full_interval_too_short"}
    logger_read.assert_not_awaited()


async def test_options_can_request_full_snapshot_every_ten_seconds(hass, logger_read):
    existing = entry(hass)
    assert await hass.config_entries.async_setup(existing.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(existing.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"],
        {"scan_interval": 10, "full_scan_interval": 10})
    await hass.async_block_till_done()
    assert existing.runtime_data.interval == 10
    assert existing.runtime_data.full_interval == 10


async def test_invalid_options_preserve_configuration(hass):
    existing = entry(hass)
    result = await hass.config_entries.options.async_init(existing.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"],
        {"scan_interval": 30, "full_scan_interval": 10})
    assert result["errors"] == {"full_scan_interval": "full_interval_too_short"}
    assert existing.options == {}


async def test_wizard_forms_are_serializable_for_real_frontend(hass, no_real_discovery):
    from homeassistant.helpers.data_entry_flow import _BaseFlowManagerView
    view = _BaseFlowManagerView(hass.config_entries.flow)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    serialized = view._prepare_result_json(result)
    fields = {field["name"]: field for field in serialized["data_schema"]}
    assert fields["scan_interval"]["default"] == 10
    assert fields["full_scan_interval"]["default"] == 30
    for key in ("scan_interval", "full_scan_interval"):
        assert fields[key]["valueMin"] == 1
        assert fields[key]["valueMax"] == 300
    assert "default" not in fields["logger_serial"]
    no_real_discovery.return_value = [DiscoveredLogger("127.0.0.1", 1234567890),
                                    DiscoveredLogger("127.0.0.2", 1234567891)]
    selected = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert view._prepare_result_json(selected)["data_schema"]
    selected = await hass.config_entries.flow.async_configure(selected["flow_id"], {"logger": "manual"})
    assert view._prepare_result_json(selected)["data_schema"]
    existing = entry(hass)
    reconfigure = await hass.config_entries.flow.async_init(DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": existing.entry_id})
    assert view._prepare_result_json(reconfigure)["data_schema"]
    options = await hass.config_entries.options.async_init(existing.entry_id)
    assert view._prepare_result_json(options)["data_schema"]


async def test_add_integration_over_real_ha_http_api(hass, hass_client, logger_read):
    from homeassistant.setup import async_setup_component
    assert await async_setup_component(hass, "config", {})
    client = await hass_client()
    response = await client.post("/api/config/config_entries/flow", json={"handler": DOMAIN})
    assert response.status == 200
    form = await response.json()
    assert form["type"] == "form"
    fields = {field["name"]: field for field in form["data_schema"]}
    assert fields["scan_interval"]["default"] == 10
    assert fields["full_scan_interval"]["default"] == 30
    response = await client.post("/api/config/config_entries/flow/" + form["flow_id"], json=DATA)
    assert response.status == 200
    created = await response.json()
    assert created["type"] == "create_entry"
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_options_accept_five_seconds_and_close_previous_client(hass, logger_read):
    existing = entry(hass)
    assert await hass.config_entries.async_setup(existing.entry_id)
    await hass.async_block_till_done()
    previous = existing.runtime_data.client
    result = await hass.config_entries.options.async_init(existing.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"],
        {"scan_interval": 5, "full_scan_interval": 30})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert previous._closed
    assert existing.runtime_data.interval == 5
    assert existing.runtime_data.full_interval == 30
    assert existing.data == DATA


async def test_new_wizard_accepts_one_second_for_both_intervals(hass, logger_read):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"],
        {**DATA, "scan_interval": 1, "full_scan_interval": 1})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    existing = result["result"]
    assert existing.runtime_data.interval == 1
    assert existing.runtime_data.full_interval == 1
