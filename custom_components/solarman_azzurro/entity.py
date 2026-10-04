"""Shared coordinator-backed device metadata."""
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import CONF_SERIAL, DOMAIN
from .profile import PROFILE_NAME


class AzzurroEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.data[CONF_SERIAL]))},
            name=entry.data[CONF_NAME], manufacturer="ZCS Azzurro / Sofar",
            model=PROFILE_NAME, configuration_url=f"http://{entry.data[CONF_HOST]}",
        )
