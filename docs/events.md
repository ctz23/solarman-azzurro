# Inverter events: messages, protections and faults

Scope: the verified HYD HP profile and the local event catalog in version 0.1.6.

Labels provide brief English condition summaries. Categories are integration policy, not a manufacturer severity scale. Use the raw event ID when requesting device support; labels are not repair instructions or a diagnosis. Codes outside this catalog remain unknown and are reported.

## Sensors and behavior

**Inverter event codes** retains original IDs. **Inverter messages**, **Inverter protections** and **Inverter faults** show active descriptions; **Inverter fault count** counts faults and unknown codes. The `active_events` attribute retains each code, description, category, recognition flag and permanent-fault flag. Long states are shortened to 255 characters; attributes retain the complete list.

**Inverter alarm** turns on for faults, protections, unknown codes or an inverter state of `fault`/`permanent_fault`. Informational messages alone do not activate it. Events update on complete snapshots, default 30 seconds, configurable from 1 to 300 seconds. Complete reads cannot run more frequently than power reads.

ID124 is informational in this integration. It reports a battery protection condition and may accompany reaching the configured reserve. It does not establish the cause or expose the reserve SOC setting. The original bit remains visible and another alarm or fault state remains active. ID125 remains a separate protection.

Commanded shutdowns and derating are messages. Protections identify operating conditions to observe; faults identify measurement, communication or hardware problems. Permanent faults retain their permanent flag.

## Catalog: 119 supported codes

| Code | English description | Category | Permanent |
| --- | --- | --- | --- |
| ID001 | Utility voltage above limit | Protection | No |
| ID002 | Utility voltage below limit | Protection | No |
| ID003 | Utility frequency above limit | Protection | No |
| ID004 | Utility frequency below limit | Protection | No |
| ID005 | Residual-current condition | Protection | No |
| ID006 | High-voltage ride-through condition | Fault | No |
| ID007 | Low-voltage ride-through condition | Fault | No |
| ID008 | Islanding-check condition | Protection | No |
| ID009 | Utility voltage above limit | Protection | No |
| ID010 | Utility voltage above limit | Protection | No |
| ID011 | Utility-side sensing issue | Fault | No |
| ID012 | Inverter voltage above limit | Protection | No |
| ID013 | Export-control condition | Message | No |
| ID017 | Current-sensing issue | Fault | No |
| ID018 | Current-sensing issue | Fault | No |
| ID019 | Voltage-sensing issue | Fault | No |
| ID020 | Voltage-sensing issue | Fault | No |
| ID021 | Residual-current condition | Fault | No |
| ID022 | Residual-current condition | Fault | No |
| ID023 | Voltage-sensing issue | Fault | No |
| ID024 | Input-sensing issue | Fault | No |
| ID029 | Residual-current condition | Fault | No |
| ID030 | Voltage-sensing issue | Fault | No |
| ID033 | Internal data exchange interrupted | Fault | No |
| ID034 | Internal data exchange interrupted | Fault | No |
| ID035 | Control circuitry issue | Fault | No |
| ID036 | Control circuitry issue | Fault | No |
| ID037 | Auxiliary supply issue | Fault | No |
| ID041 | Switching relay issue | Fault | No |
| ID042 | Insulation-check issue | Fault | No |
| ID043 | Earthing-check issue | Fault | No |
| ID044 | PV setup inconsistency | Fault | No |
| ID045 | Current transformer sensing issue | Fault | No |
| ID047 | Parallel setup inconsistency | Fault | No |
| ID048 | Cooling fan issue | Fault | No |
| ID049 | Battery temperature outside range | Protection | No |
| ID050 | Heat sink temperature outside range | Protection | No |
| ID051 | Heat sink temperature outside range | Protection | No |
| ID052 | Heat sink temperature outside range | Protection | No |
| ID053 | Heat sink temperature outside range | Protection | No |
| ID054 | Heat sink temperature outside range | Protection | No |
| ID055 | Heat sink temperature outside range | Protection | No |
| ID057 | Surrounding temperature outside range | Protection | No |
| ID058 | Surrounding temperature outside range | Protection | No |
| ID059 | Power module temperature outside range | Protection | No |
| ID060 | Power module temperature outside range | Protection | No |
| ID061 | Power module temperature outside range | Protection | No |
| ID065 | DC-link balance issue | Fault | No |
| ID066 | DC-link balance issue | Fault | No |
| ID067 | DC-link voltage below limit | Protection | No |
| ID068 | DC-link voltage below limit | Protection | No |
| ID069 | PV input voltage above limit | Protection | No |
| ID070 | Battery terminal voltage above limit | Protection | No |
| ID071 | DC-link voltage above limit | Protection | No |
| ID072 | DC-link voltage above limit | Protection | No |
| ID073 | DC-link voltage above limit | Protection | No |
| ID081 | Battery current above limit | Protection | No |
| ID082 | DC injection current above limit | Protection | No |
| ID083 | AC output current above limit | Protection | No |
| ID084 | Power conversion current above limit | Protection | No |
| ID085 | AC output current above limit | Protection | No |
| ID086 | PV input current above limit | Protection | No |
| ID087 | PV input balance issue | Fault | No |
| ID088 | AC output balance issue | Fault | No |
| ID097 | DC-link voltage above limit | Protection | No |
| ID098 | DC-link voltage above limit | Protection | No |
| ID099 | Power conversion current above limit | Protection | No |
| ID100 | Battery current above limit | Protection | No |
| ID102 | PV input current above limit | Protection | No |
| ID103 | AC output current above limit | Protection | No |
| ID105 | Meter connection not detected | Fault | No |
| ID110 | Demand exceeds operating limit | Protection | No |
| ID111 | Demand exceeds operating limit | Protection | No |
| ID112 | Demand exceeds operating limit | Protection | No |
| ID113 | Output reduced for temperature | Protection | No |
| ID114 | Utility frequency above limit | Protection | No |
| ID115 | Utility frequency below limit | Protection | No |
| ID116 | Output reduced for voltage | Protection | No |
| ID117 | Operating voltage too low | Protection | No |
| ID124 | Reduced battery-voltage indication | Message | No |
| ID125 | Battery discharge paused | Protection | No |
| ID129 | AC output current above limit | Fault | Yes |
| ID130 | DC-link voltage above limit | Fault | Yes |
| ID131 | DC-link voltage above limit | Fault | Yes |
| ID132 | PV input balance issue | Fault | Yes |
| ID133 | Battery current above limit | Fault | Yes |
| ID134 | AC output current above limit | Fault | Yes |
| ID135 | AC output balance issue | Fault | Yes |
| ID137 | PV setup inconsistency | Fault | Yes |
| ID138 | PV input current above limit | Fault | Yes |
| ID139 | PV input current above limit | Fault | Yes |
| ID140 | Switching relay issue | Fault | Yes |
| ID141 | DC-link balance issue | Fault | Yes |
| ID145 | USB connection issue | Fault | No |
| ID146 | Wi-Fi connection issue | Fault | No |
| ID147 | Bluetooth connection issue | Fault | No |
| ID148 | Timekeeping issue | Fault | No |
| ID149 | Data exchange storage issue | Fault | No |
| ID150 | Data exchange storage issue | Fault | No |
| ID152 | Software version mismatch | Fault | No |
| ID153 | Internal data exchange interrupted | Fault | No |
| ID154 | Internal data exchange interrupted | Fault | No |
| ID155 | Internal data exchange interrupted | Fault | No |
| ID156 | Software version mismatch | Fault | No |
| ID157 | BMS data exchange interrupted | Fault | No |
| ID161 | Operation stopped by command | Message | No |
| ID162 | External stop request active | Message | No |
| ID163 | Demand-response stop request active | Message | No |
| ID165 | Requested output reduction active | Message | No |
| ID166 | Requested output reduction active | Message | No |
| ID167 | Requested output reduction active | Message | No |
| ID169 | Cooling fan issue | Fault | No |
| ID175 | Cooling fan issue | Fault | No |
| ID177 | BMS reports voltage above limit | Protection | No |
| ID178 | BMS reports voltage below limit | Protection | No |
| ID179 | BMS reports temperature above limit | Protection | No |
| ID180 | BMS reports temperature below limit | Protection | No |
| ID181 | BMS reports current above limit | Protection | No |
| ID182 | BMS reports short-circuit condition | Protection | No |

## Verification

Tests cover ID124 alone, ID124 with a BMS fault, ID125, unknown codes, a fault state without event bits and long lists. The integration does not change inverter settings.

Event IDs, classifications and permanent flags remain stable in version 0.1.6. Descriptive text has changed and the `manual_url` attribute has been removed. Automations should match event IDs rather than full descriptions.
