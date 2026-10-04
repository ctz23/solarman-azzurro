# Installation, configuration and migration

Scope: Solarman Azzurro 0.1.6, Home Assistant 2026.9 or later, HYD HP / Sofar G3 profile verified on a single-phase installation.

## Requirements

- An inverter matching the [verified profile](measurements.md) and a **Solarman V5** logger. Other HYD generations, KTL models, V4 loggers and three-phase systems need separate verification.
- A logger already connected to the local network, preferably with a DHCP reservation, and its numeric serial number.
- Home Assistant must reach the logger on its configured TCP port, normally **8899**. Separate VLANs need appropriate routing and firewall rules. Reaching the logger's web page from a computer does not establish that Home Assistant can reach its V5 port.

Readings come directly from the local network. No ZCS/Solarman account, cloud password, App ID, App Secret, MQTT, add-on or separately installed Python library is required. The logger web password only applies to its web page. Keep the logger's TCP port private to the local network.

## Installation

In HACS, open **Custom repositories**, add `https://github.com/ctz23/solarman-azzurro` with category **Integration**, then find and download **Solarman Azzurro**. You can also [add the repository directly to HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=ctz23&repository=solarman-azzurro&category=integration). Restart Home Assistant to load the component.

For manual installation, copy `custom_components/solarman_azzurro/` into your Home Assistant configuration's `custom_components/` directory. The resulting path must contain `custom_components/solarman_azzurro/manifest.json`, without an extra directory level. Restart Home Assistant.

Downloading the component and adding a device are separate steps. This project is available as a custom repository; inclusion in HACS's default catalog requires separate review. See [Publishing and HACS](publishing.md).

## Add a device

Open **Settings → Devices & services → Add integration → Solarman Azzurro**. Discovery runs for about two seconds. One discovered logger pre-fills its address and numeric serial; several loggers produce a selection form. Review and confirm the form before saving. If discovery finds nothing, enter the same fields manually:

| Field | Internal key | Meaning and accepted values |
| --- | --- | --- |
| Device name | `name` | A readable name, default `Azzurro`. |
| Local IP address | `host` | Logger address reachable from Home Assistant; use a DHCP reservation. |
| Numeric logger serial | `logger_serial` | Integer from 1 to 4294967295. This belongs to the logger, separately from the inverter's alphanumeric serial. Without discovery the field is empty and requires the real logger serial. |
| TCP port | `port` | Default **8899**, range 1–65535. Change it only if the logger uses another V5 port. |
| Power and battery interval (seconds) | `scan_interval` | Default **10**, range **1–300** seconds. |
| Counters, events and other readings interval (seconds) | `full_scan_interval` | Default **30**, range **1–300** seconds; at least as long as the power interval. |

Discovery obtains the address and numeric serial through UDP broadcast on port 48899 (`WIFIKIT-214028-READ`). Broadcast may not cross VLANs or guest networks; use the router and logger status page to find those parameters manually. TCP port 8899 and the supported profile are defaults checked by the subsequent read, not values recovered through discovery. Ordinary polling does not use the UDP port.

Submitting the form reads and decodes the complete supported profile. Connection failures or invalid responses prevent entry creation. Validation checks the protocol, logger identity, completeness and plausibility of registers; it does not certify other inverter models.

Configuration is through the UI only. There is no `configuration.yaml` import. Examples using `sensor: - platform: solarman` belong to another integration; this component's domain is `solarman_azzurro`.

## Fixed profile parameters

The **HYD HP / Sofar G3** profile, **Modbus slave 1** and FC03 reads are fixed. There are no selectors for register YAML files, direct Modbus TCP, phase count, battery count or battery capacity. Register definitions ship with the component.

SOC and other battery readings come from the inverter without a battery-model setting. The profile does not provide a second battery or capacity-based runtime estimate. The inverter controls its reserve SOC threshold; the integration does not change it. Event classifications are built in, including ID124; see [Inverter events](events.md).

## Change configuration

Open the integration's **options** to change polling. Saving reloads the entry automatically. The first interval controls power, PV strings, grid and battery telemetry, default 10 seconds. The second controls complete snapshots including energy counters, state, events and inverter temperatures, default 30 seconds. Both accept 1–300 seconds. Complete reads run on the first polling cycle after the full interval has elapsed and cannot run more frequently than power reads. The first cycle is always complete.

For example, **1/30** requests live measurements every second and complete snapshots about every 30 seconds. The selectable minimum is experimental and does not guarantee fresh data every second. A persistent TCP session handles ordered reads and idle heartbeats. Transport failures invalidate the session and trigger bounded reconnection. Existing configurations below one second use the minimum without changing entity identities.

**Short polling intervals require verification on your installation.** Firmware, logger, network conditions and other clients affect response times and failures. A persistent session reduces TCP connection openings, but lowering the interval still increases Modbus requests. Only one snapshot runs at a time; slow replies reduce the actual update rate. If timeouts, frequent reconnections or unavailable sensors occur, increase the live interval to 2, 5 or 10 seconds, or another suitable value, and increase the full interval if necessary. Defaults remain **10/30**.

Use **Reconfigure** in the existing entry's menu to change its host or port. The new connection is validated before saving; the serial, name and intervals are retained. Adding the same serial again stops as a duplicate. A replacement logger with a different serial requires a new entry. Do not delete an existing entry just to fix its address.

## Language and entity compatibility

Documentation, default labels and event descriptions use English. An optional Italian UI translation provides entity names and setup text. Existing entity IDs, unique IDs, measurement keys and raw flow states remain unchanged; they include legacy Italian identifiers. Language changes do not migrate Recorder history or energy statistics. Existing user-assigned entity names are retained. New entity names follow Home Assistant's backend language.

## Energy dashboard

Select the local device's cumulative counters in the **Energy** dashboard settings:

| Energy setting | Sensor name |
| --- | --- |
| Grid consumption | Total grid import |
| Return to grid | Total grid export |
| Solar production | Total solar production |
| Energy going into the battery | Total battery charge |
| Energy coming out of the battery | Total battery discharge |

These sensors use **kWh**, device class `energy` and state class `total`. Select the actual entities from your installation: their IDs may depend on existing names and prior renames. Instantaneous W sensors do not replace energy counters. See [Measurements and limits](measurements.md) for estimated self-consumption.

## Migration from ZCSAzzurro cloud sensors

Install the local integration alongside the cloud entry first. Compare values, units, register profile, grid/battery directions and cumulative counters. Keep a private backup of configuration, entity/device registries and Energy settings.

Update dashboard, automation and Energy references to verified local entities, preserving original cloud entities as disabled historical sources. Before any identity migration, also take a complete Recorder database backup.

**Renaming an entity also renames its state/history and statistics IDs in Recorder. Reusing its original ID for a new local entity does not merge historical series.** Do not use a rename sequence as a history migration. If a previous change moved history to backup IDs, keep those series and plan a separately tested restoration with a full database backup. Do not delete statistics to resolve ID collisions.

Daily counters use `total_increasing`; cumulative counters use `total`, matching the previous cloud integration. Cloud delays or different measurement methods can create a difference at cutover. The component does not apply artificial offsets.

A second battery has no verified measurement; keep any older entity disabled or unavailable. Compatibility DC sensors refer to string 1; PV1/PV2 sensors expose both strings separately. Self-consumption estimates exclude battery charging energy.

Disable any reload automation specific to the old cloud component once local sensors take over. After a temporary transport error, the client retries once on a new connection and discards partial data. If that attempt also fails, sensors become unavailable and the coordinator tries again on the next poll.

## Verification and troubleshooting

Check **Last local update**, connectivity, powers, battery and counters. The timestamp should advance with successful reads; `last_full_snapshot` should follow complete reads. `tcp_connection_count` and `modbus_request_count` distinguish connection reuse from register requests. When the logger is unreachable, connectivity turns off and measurements become unavailable; a successful subsequent read restores them.

| Symptom | Check |
| --- | --- |
| Integration missing from Add integration | Component path, minimum HA version, restart and HA logs. |
| Cannot read the local logger | Address, port, logger serial and TCP access from HA, including VLAN/firewall rules. |
| Response does not match the supported profile | Logger serial, inverter generation, V5 protocol and Modbus slave 1. The message also covers protocol validation errors. |
| Logger already configured | Use Reconfigure on the existing entry to change its address or port. |
| Events or counters update less often than power | Full interval, default 30 seconds; counter resolution and firmware cadence can keep a value unchanged. |
| Missing battery readings | Only verified readings are exposed; invalid temperature or SOH remains unavailable. |

See [Development and verification](development.md) for protocol tests. Testing another installation requires Home Assistant and compatible hardware.
