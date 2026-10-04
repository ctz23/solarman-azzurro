"""Use real Home Assistant with synthetic data and no external networking."""
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

import pytest

from tests.test_protocol import snapshot


@pytest.fixture(autouse=True)
def custom_components_enabled(enable_custom_integrations):
    """Allow this independently installed integration in the HA fixture."""


@pytest.fixture
def hass_config_dir(tmp_path):
    """Keep the isolated HA config under pytest's explicitly selected basetemp."""
    return str(tmp_path)


@pytest.fixture(autouse=True)
def no_real_discovery():
    """Discovery is mocked; UDP itself is exercised by standalone tests."""
    with patch("custom_components.solarman_azzurro.config_flow.network.async_get_ipv4_broadcast_addresses",
               AsyncMock(return_value={IPv4Address("255.255.255.255")})), \
         patch("custom_components.solarman_azzurro.config_flow.async_discover", AsyncMock(return_value=[])) as discover:
        yield discover


@pytest.fixture
def logger_read():
    """A complete synthetic snapshot valid for the supported profile."""
    with patch("custom_components.solarman_azzurro.api.SolarmanClient.read", AsyncMock(return_value=snapshot())) as read:
        yield read
