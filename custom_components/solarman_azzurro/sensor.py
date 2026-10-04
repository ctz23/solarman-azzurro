"""Read-only sensors; calculated measurements are explicitly identified."""
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory
from .entity import AzzurroEntity
from .profile import MEASUREMENTS


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities([AzzurroSensor(coordinator, entry, item) for item in MEASUREMENTS]
                       + [SampleTimeSensor(coordinator, entry)])


class AzzurroSensor(AzzurroEntity, SensorEntity):
    def __init__(self, coordinator, entry, item):
        super().__init__(coordinator, entry, item.key)
        self.item = item
        self.entity_description = SensorEntityDescription(
            key=item.key, translation_key=item.key, native_unit_of_measurement=item.unit,
            device_class=item.device_class, state_class=item.state_class,
            entity_category=EntityCategory.DIAGNOSTIC if item.diagnostic else None,
        )
        self._data_source = "local_derived" if item.derived else "local_register"

    @property
    def extra_state_attributes(self):
        attributes = {"data_source": self._data_source}
        if self.item.key in ("codici_allarme", "messaggi_inverter", "errori_inverter", "numero_errori", "protezioni_inverter"):
            events = self.coordinator.data.get("eventi_attivi", [])
            if self.item.key == "messaggi_inverter":
                events = [event for event in events if event["kind"] == "message"]
            elif self.item.key in ("errori_inverter", "numero_errori"):
                events = [event for event in events if event["kind"] in ("error", "unknown")]
            elif self.item.key == "protezioni_inverter":
                events = [event for event in events if event["kind"] == "protection"]
            attributes.update(active_events=events)
        return attributes

    @property
    def available(self):
        return super().available and self.coordinator.data.get(self.item.key) is not None

    @property
    def native_value(self):
        return self.coordinator.data.get(self.item.key)


class SampleTimeSensor(AzzurroEntity, SensorEntity):
    _attr_translation_key = "ultimo_aggiornamento_locale"
    _attr_device_class = "timestamp"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "ultimo_aggiornamento_locale")

    @property
    def native_value(self):
        return self.coordinator.last_sample

    @property
    def extra_state_attributes(self):
        return {"tcp_connected": self.coordinator.client.connected,
                "tcp_connection_count": self.coordinator.client.connection_count,
                "modbus_request_count": self.coordinator.client.request_count,
                "scan_interval_seconds": self.coordinator.interval,
                "sample_duration_seconds": self.coordinator.sample_duration,
                "full_snapshot_interval_seconds": self.coordinator.full_interval,
                "last_full_snapshot": self.coordinator.last_full_sample.isoformat() if self.coordinator.last_full_sample else None}
