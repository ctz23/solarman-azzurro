# Supported profile and measurements

Scope: the HYD HP / Sofar G3 register family reached through a Solarman V5 logger, TCP 8899, slave 1, read function 03. The verified installation is single-phase; multi-phase, older HYD ES, KTL and other logger generations are untested and must not be assumed compatible.

## Cadence and transport

Power, PV strings, grid voltage/frequency and battery telemetry use `scan_interval`, default 10 seconds. Status, events, inverter temperatures and energy counters use `full_scan_interval`, default 30 seconds. Both intervals accept 1–300 seconds. The full interval cannot be shorter than the power interval; full reads run on the first polling cycle after that interval has elapsed. Setting both to 10 reads the complete profile at every cycle. Existing configurations below 1 second use the new minimum without changing entity IDs. The TCP connection stays open between successful snapshots; one background reader handles validated idle heartbeat packets and their V5 acknowledgements. Late or unsolicited measurements are discarded. Errors close the session, and the next read establishes a new one. No additional Modbus keepalive polling is performed. Sessions are closed on validation completion, failed setup, unload and Home Assistant shutdown. Very short intervals increase Modbus traffic and may cause timeouts or reconnections on some firmware/networks. Increase either interval if errors occur; configured cadence does not guarantee fresh measurements at that cadence. Only one snapshot runs at a time, including when it exceeds the chosen interval. All network operations are asynchronous. A lock prevents overlapping transactions. Inverter firmware determines the underlying measurement refresh rate and power resolution is generally 10 W.

Complete transactions validate V5 framing, length, additive checksum, logger identity, sequence, response type, Modbus slave/function, byte count and CRC16. Invalid or incomplete snapshots produce unavailable sensors, never an apparently current cached power value. Compatible snapshots are required before setup. A temporary socket error, timeout or truncated TCP reply triggers one new connection and a fresh read of every requested window, within a shared 20-second deadline. Registers from the failed attempt are discarded. Protocol, identity and checksum errors are rejected without retry. If the bounded retry also fails, sensors become unavailable and recover on the next successful poll.

## Measurements

| Group | Exposed data |
| --- | --- |
| Power | PV total and per string; household consumption; grid import/export; battery charge/discharge; signed net grid/battery power |
| Energy | Daily and lifetime production, consumption, import, export, battery charge/discharge; estimated direct solar self-consumption |
| PV1/PV2 | Voltage, current, power for each string |
| Battery | SOC, BMS-reported SOH, voltage, signed current, temperature |
| Grid | Voltage and frequency |
| Inverter | Operating state, internal/ambient and heatsink temperature, alarm bit codes, English messages/protections/faults |
| Diagnostics | Connection, alarm flag, local update timestamp, polling interval, snapshot duration, full-snapshot time, TCP session state and connection/request counts |

Positive normalized grid power means import. Positive normalized battery power means discharge. Raw registers 0x0488 and 0x0606 have the opposite sign and are multiplied by -10. Battery current retains the device convention: positive charging.

Self-consumption is a derived estimate: `max(PV − export − battery charge, 0)` for power and the equivalent counter subtraction for energy. Conversion losses and firmware accounting can differ; the sensors identify this with `data_source: local_derived`. Compatibility DC power is derived from PV1 voltage × current. Other decoded sensors use `local_register`.

There is no verified second battery or module temperature measurement. Unavailable BMS SOH/temperature values remain unavailable. SOH is a BMS estimate, not an independent battery capacity test. Alarm flags can include protective conditions while the inverter state remains normal; do not interpret every bit as a critical failure without the inverter manual.

## Register windows

The integration reads only these verified intervals: 0x0404–0x0410, 0x0418–0x041A, 0x0484–0x048D, 0x04AF, 0x0584–0x0589, 0x0604–0x060A, 0x0684–0x069B. Thirty-two-bit counters are high-word first on the wire; daily resolution 0.01 kWh and lifetime resolution 0.1 kWh.

Register facts and framing were cross-checked against the independent public implementations [Stephan Joubert HYD HP map](https://github.com/StephanJoubert/home_assistant_solarman/blob/main/custom_components/solarman/inverter_definitions/hyd-zss-hp-3k-6k.yaml), [Sofar G3HYD map](https://github.com/StephanJoubert/home_assistant_solarman/blob/main/custom_components/solarman/inverter_definitions/sofar_g3hyd.yaml), [David Rapan signed-flow conventions](https://github.com/davidrapan/ha-solarman/blob/main/custom_components/solarman/inverter_definitions/sofar_g3hyd.yaml) and [PySolarmanV5 protocol](https://pysolarmanv5.readthedocs.io/en/latest/solarmanv5_protocol.html). The implementation is independently written and contains no upstream integration code.

## Further measurements

Battery and grid flow states are derived from the verified signed power readings.
The battery-cycle register 0x060A is already included in the read window but returned zero on the verified installation; its validity is not established, so it is not exposed as a confirmed cycle count. EPS output, insulation resistance, firmware/serial details, battery capacity and configured SOC thresholds need separate register verification. Estimated backup autonomy also requires actual battery capacity and a clear load/efficiency model.

See [Event classification](events.md) for descriptions and the treatment of ID124. The integration reads inverter values; it does not change reserve thresholds.

## V5 control packets

The logger may interleave short heartbeat/control packets with measurement replies, including a one-byte heartbeat belonging to the previous register window. The transport consumes their declared frame length, validates their V5 checksum, end marker and logger identity, then skips them while waiting for the requested measurement. These packets never become sensor values. Measurement replies still require the correct transaction, Modbus CRC and complete register count. The maximum frame size, eight-frame limit per response and transaction deadline remain bounded.
