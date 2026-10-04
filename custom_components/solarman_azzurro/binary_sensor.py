"""Read-only connectivity and alarm diagnostics."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from .entity import AzzurroEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ConnectionSensor(entry.runtime_data, entry), AlarmSensor(entry.runtime_data, entry)])


class ConnectionSensor(AzzurroEntity, BinarySensorEntity):
    _attr_translation_key = "collegamento_locale"
    _attr_device_class = "connectivity"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "collegamento_locale")

    @property
    def available(self):
        return True

    @property
    def is_on(self):
        return self.coordinator.last_update_success


class AlarmSensor(AzzurroEntity, BinarySensorEntity):
    _attr_translation_key = "allarme_inverter"
    _attr_device_class = "problem"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "allarme_inverter")

    @property
    def is_on(self):
        return self.coordinator.data["allarme"]

    @property
    def extra_state_attributes(self):
        return {"error_count": self.coordinator.data["numero_errori"],
                "active_alarms": [e for e in self.coordinator.data["eventi_attivi"] if e["kind"] != "message"],
                "inverter_state": self.coordinator.data["stato_inverter"]}
