"""Local event labels and classification. ID124 is informational; unknown bits stay faults."""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Event:
    description: str
    kind: str = "error"

# Related event IDs share a brief condition label.
_GROUPS = (
    ((1, 9, 10), "Utility voltage above limit"),
    ((2,), "Utility voltage below limit"),
    ((3, 114), "Utility frequency above limit"),
    ((4, 115), "Utility frequency below limit"),
    ((5, 21, 22, 29), "Residual-current condition"),
    ((6,), "High-voltage ride-through condition"), ((7,), "Low-voltage ride-through condition"),
    ((8,), "Islanding-check condition"), ((11,), "Utility-side sensing issue"),
    ((12,), "Inverter voltage above limit"), ((13,), "Export-control condition"),
    ((17, 18), "Current-sensing issue"), ((19, 20, 23, 30), "Voltage-sensing issue"),
    ((24,), "Input-sensing issue"), ((33, 34, 153, 154, 155), "Internal data exchange interrupted"),
    ((35, 36), "Control circuitry issue"), ((37,), "Auxiliary supply issue"),
    ((41, 140), "Switching relay issue"), ((42,), "Insulation-check issue"),
    ((43,), "Earthing-check issue"), ((44, 137), "PV setup inconsistency"),
    ((45,), "Current transformer sensing issue"), ((47,), "Parallel setup inconsistency"),
    ((48, 169, 175), "Cooling fan issue"), ((49,), "Battery temperature outside range"),
    ((50, 51, 52, 53, 54, 55), "Heat sink temperature outside range"),
    ((57, 58), "Surrounding temperature outside range"), ((59, 60, 61), "Power module temperature outside range"),
    ((65, 66, 141), "DC-link balance issue"), ((67, 68), "DC-link voltage below limit"),
    ((69,), "PV input voltage above limit"), ((70,), "Battery terminal voltage above limit"),
    ((71, 72, 73, 97, 98, 130, 131), "DC-link voltage above limit"),
    ((81, 100, 133), "Battery current above limit"), ((82,), "DC injection current above limit"),
    ((83, 85, 103, 129, 134), "AC output current above limit"),
    ((84, 99), "Power conversion current above limit"),
    ((86, 102, 138, 139), "PV input current above limit"),
    ((87, 132), "PV input balance issue"), ((88, 135), "AC output balance issue"),
    ((105,), "Meter connection not detected"), ((110, 111, 112), "Demand exceeds operating limit"),
    ((113,), "Output reduced for temperature"), ((116,), "Output reduced for voltage"),
    ((117,), "Operating voltage too low"), ((125,), "Battery discharge paused"),
    ((145,), "USB connection issue"), ((146,), "Wi-Fi connection issue"),
    ((147,), "Bluetooth connection issue"), ((148,), "Timekeeping issue"),
    ((149, 150), "Data exchange storage issue"), ((152, 156), "Software version mismatch"),
    ((157,), "BMS data exchange interrupted"), ((161,), "Operation stopped by command"),
    ((162,), "External stop request active"), ((163,), "Demand-response stop request active"),
    ((165, 166, 167), "Requested output reduction active"),
    ((177,), "BMS reports voltage above limit"), ((178,), "BMS reports voltage below limit"),
    ((179,), "BMS reports temperature above limit"), ((180,), "BMS reports temperature below limit"),
    ((181,), "BMS reports current above limit"), ((182,), "BMS reports short-circuit condition"),
)
CATALOG = {f"ID{number:03d}": Event(text) for ids, text in _GROUPS for number in ids}
for ids, kind in (
    ((1, 2, 3, 4, 5, 8, 9, 10, 12, 49, 50, 51, 52, 53, 54, 55, 57, 58,
      59, 60, 61, 67, 68, 69, 70, 71, 72, 73, 81, 82, 83, 84, 85, 86,
      97, 98, 99, 100, 102, 103, 110, 111, 112, 113, 114, 115, 116, 117,
      125, 177, 178, 179, 180, 181, 182), "protection"),
    ((13, 161, 162, 163, 165, 166, 167), "message"),
):
    for number in ids:
        code = f"ID{number:03d}"
        CATALOG[code] = replace(CATALOG[code], kind=kind)

CATALOG["ID124"] = Event("Reduced battery-voltage indication", "message")


def describe_events(codes: list[str]) -> list[dict[str, str | bool]]:
    """Keep every original code, including unrecognized future firmware bits."""
    return [{"code": code,
             "description": CATALOG[code].description if code in CATALOG else "Uncatalogued code",
             "kind": CATALOG[code].kind if code in CATALOG else "unknown",
             "known": code in CATALOG,
             "permanent": code in {f"ID{n:03d}" for n in (129, 130, 131, 132, 133, 134, 135, 137, 138, 139, 140, 141)}} for code in codes]


def event_summary(events: list[dict], *kinds: str) -> str:
    text = "; ".join(f"{e['code']}: {e['description']}" for e in events if e["kind"] in kinds)
    # HA states have a 255-character limit; attributes retain the complete list.
    return text[:252] + "..." if len(text) > 255 else text or "none"
