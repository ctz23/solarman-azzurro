"""Verified HYD HP/G3 register facts, decoding, and derived flow measurements."""
from __future__ import annotations

from dataclasses import dataclass
from .api import ProtocolError
from .alarms import describe_events, event_summary

# Smaller, independently verified windows avoid undocumented register ranges.
WINDOWS = ((0x0404, 13), (0x0418, 3), (0x0484, 10), (0x04AF, 1),
           (0x0584, 6), (0x0604, 7), (0x0684, 24))
FAST_WINDOWS = ((0x0484, 10), (0x04AF, 1), (0x0584, 6), (0x0604, 7))
PROFILE_NAME = "Azzurro HYD HP / Sofar G3"


@dataclass(frozen=True)
class Measurement:
    key: str
    name: str
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = "measurement"
    diagnostic: bool = False
    derived: bool = False


# Keep persisted measurement keys unchanged across language updates.
LEGACY_KEYS = (
    "stato", "potenza_prodotta", "energia_prodotta_oggi", "totale_energia_prodotta",
    "potenza_consumata", "energia_consumata_oggi", "totale_energia_consumata",
    "potenza_autoconsumata", "energia_autoconsumata_oggi", "totale_enegia_autoconsumata",
    "potenza_carica", "energia_carica_oggi", "totale_energia_carica", "potenza_scarica",
    "energia_scarica_oggi", "totale_energia_scarica", "potenza_importata",
    "energia_importata_oggi", "totale_energia_importata", "potenza_esportata",
    "energia_esportata_oggi", "totale_energia_esportata", "batteria",
    "temperatura_inverter", "corrente_dc", "voltaggio_dc", "potenza_dc",
)


def definition(key: str, name: str, unit: str, cls: str | None, *, derived: bool = False, diagnostic: bool = False) -> Measurement:
    state_class = ("total_increasing" if key.endswith("_oggi") else "total") if cls == "energy" else "measurement"
    return Measurement(key, name, unit, cls, state_class, diagnostic, derived)


MEASUREMENTS = (
    Measurement("stato", "Status", state_class=None, derived=True),
    *(definition(key, name, "W", "power", derived=derived) for key, name, derived in (
        ("potenza_prodotta", "Solar production power", True),
        ("potenza_consumata", "Consumption power", False),
        ("potenza_autoconsumata", "Self-consumption power", True),
        ("potenza_importata", "Grid import power", True),
        ("potenza_esportata", "Grid export power", True),
        ("potenza_carica", "Battery charging power", True),
        ("potenza_scarica", "Battery discharging power", True),
        ("potenza_rete", "Grid power (positive import)", True),
        ("potenza_batteria", "Battery power (positive discharge)", True),
        ("potenza_dc", "DC string 1 power", True),
        ("potenza_pv1", "PV1 power", False), ("potenza_pv2", "PV2 power", False),
    )),
    *(definition(key, name, "kWh", "energy", derived=derived) for key, name, derived in (
        ("energia_prodotta_oggi", "Solar production today", False),
        ("totale_energia_prodotta", "Total solar production", False),
        ("energia_consumata_oggi", "Consumption today", False),
        ("totale_energia_consumata", "Total consumption", False),
        ("energia_importata_oggi", "Grid import today", False),
        ("totale_energia_importata", "Total grid import", False),
        ("energia_esportata_oggi", "Grid export today", False),
        ("totale_energia_esportata", "Total grid export", False),
        ("energia_carica_oggi", "Battery charge today", False),
        ("totale_energia_carica", "Total battery charge", False),
        ("energia_scarica_oggi", "Battery discharge today", False),
        ("totale_energia_scarica", "Total battery discharge", False),
        ("energia_autoconsumata_oggi", "Self-consumption today (estimated)", True),
        ("totale_enegia_autoconsumata", "Total self-consumption (estimated)", True),
    )),
    definition("batteria", "Battery", "%", "battery"),
    definition("salute_batteria", "Battery health (BMS)", "%", None),
    definition("temperatura_inverter", "Inverter temperature", "°C", "temperature"),
    definition("temperatura_ambiente", "Inverter ambient temperature", "°C", "temperature"),
    definition("temperatura_batteria", "Battery temperature", "°C", "temperature"),
    *(definition(key, name, "V", "voltage") for key, name in (
        ("tensione_rete", "Grid voltage"), ("tensione_batteria", "Battery voltage"),
        ("voltaggio_dc", "DC string 1 voltage"),
        ("tensione_pv1", "PV1 voltage"), ("tensione_pv2", "PV2 voltage"),
    )),
    *(definition(key, name, "A", "current") for key, name in (
        ("corrente_dc", "DC string 1 current"), ("corrente_pv1", "PV1 current"),
        ("corrente_pv2", "PV2 current"), ("corrente_batteria", "Battery current (positive charge)"),
    )),
    definition("frequenza_rete", "Grid frequency", "Hz", "frequency"),
    Measurement("stato_inverter", "Inverter state", state_class=None),
    Measurement("codici_allarme", "Inverter event codes", state_class=None, diagnostic=True),
    Measurement("messaggi_inverter", "Inverter messages", state_class=None, diagnostic=True),
    Measurement("errori_inverter", "Inverter faults", state_class=None, diagnostic=True),
    Measurement("protezioni_inverter", "Inverter protections", state_class=None, diagnostic=True),
    Measurement("numero_errori", "Inverter fault count", state_class=None, diagnostic=True),
    Measurement("flusso_batteria", "Battery flow", state_class=None, derived=True),
    Measurement("flusso_rete", "Grid flow", state_class=None, derived=True),
)


def decode(registers: dict[int, int]) -> dict[str, int | float | str | None]:
    expected = {start + i for start, count in WINDOWS for i in range(count)}
    if not expected <= registers.keys():
        raise ProtocolError("Incomplete measurement snapshot")
    r = registers

    def unsigned(address: int, scale: float = 1) -> float | int:
        return round(r[address] * scale, 4)

    def signed(address: int, scale: float = 1) -> float | int:
        value = r[address] - 65536 if r[address] >= 32768 else r[address]
        return round(value * scale, 4)

    def temperature(address: int) -> int | None:
        value = signed(address)
        return value if r[address] != 0xFFFF and -40 <= value <= 150 else None

    def energy(address: int, scale: float) -> float | None:
        # Register pair is high word first on the wire.
        value = (r[address] << 16) | r[address + 1]
        return None if value == 0xFFFFFFFF else round(value * scale, 2)

    if not 0 <= r[0x0608] <= 100 or not 0 <= r[0x0404] <= 4:
        raise ProtocolError("Unsupported HYD profile or invalid battery/status register")
    grid, battery = signed(0x0488, -10), signed(0x0606, -10)
    pv1, pv2 = unsigned(0x0586, 10), unsigned(0x0589, 10)
    pv = pv1 + pv2
    imported, exported = max(grid, 0), max(-grid, 0)
    charged, discharged = max(-battery, 0), max(battery, 0)
    consumed = max(signed(0x04AF, 10), 0)
    if max(pv, imported, exported, charged, discharged, consumed) > 100000:
        raise ProtocolError("Implausible power: wrong profile or invalid registers")
    values = {
        "potenza_prodotta": pv, "potenza_consumata": consumed,
        "potenza_importata": imported, "potenza_esportata": exported,
        "potenza_carica": charged, "potenza_scarica": discharged,
        "potenza_rete": grid, "potenza_batteria": battery,
        "potenza_autoconsumata": max(pv - exported - charged, 0),
        "potenza_pv1": pv1, "potenza_pv2": pv2,
        "tensione_pv1": unsigned(0x0584, .1), "tensione_pv2": unsigned(0x0587, .1),
        "corrente_pv1": unsigned(0x0585, .01), "corrente_pv2": unsigned(0x0588, .01),
        "batteria": r[0x0608],
        "salute_batteria": r[0x0609] if r[0x0609] <= 100 else None,
        "tensione_batteria": unsigned(0x0604, .1), "corrente_batteria": signed(0x0605, .01),
        "temperatura_batteria": temperature(0x0607),
        "tensione_rete": unsigned(0x048D, .1), "frequenza_rete": unsigned(0x0484, .01),
        "temperatura_inverter": temperature(0x041A), "temperatura_ambiente": temperature(0x0418),
        "stato_inverter": ("standby", "self_check", "normal", "fault", "permanent_fault")[r[0x0404]],
    }
    values.update(voltaggio_dc=values["tensione_pv1"], corrente_dc=values["corrente_pv1"],
                  potenza_dc=round(values["tensione_pv1"] * values["corrente_pv1"], 2))
    for key, address, scale in (
        ("energia_prodotta_oggi", 0x0684, .01), ("totale_energia_prodotta", 0x0686, .1),
        ("energia_consumata_oggi", 0x0688, .01), ("totale_energia_consumata", 0x068A, .1),
        ("energia_importata_oggi", 0x068C, .01), ("totale_energia_importata", 0x068E, .1),
        ("energia_esportata_oggi", 0x0690, .01), ("totale_energia_esportata", 0x0692, .1),
        ("energia_carica_oggi", 0x0694, .01), ("totale_energia_carica", 0x0696, .1),
        ("energia_scarica_oggi", 0x0698, .01), ("totale_energia_scarica", 0x069A, .1),
    ):
        values[key] = energy(address, scale)
    for destination, inputs in (
        ("energia_autoconsumata_oggi", ("energia_prodotta_oggi", "energia_esportata_oggi", "energia_carica_oggi")),
        ("totale_enegia_autoconsumata", ("totale_energia_prodotta", "totale_energia_esportata", "totale_energia_carica")),
    ):
        operands = [values[key] for key in inputs]
        values[destination] = None if None in operands else round(max(operands[0] - operands[1] - operands[2], 0), 2)
    autoconsumed = values["potenza_autoconsumata"]
    values["stato"] = ("generating_consuming_from_network" if pv > 0 and imported > 0 else
                       "generating_consuming_from_produced" if pv > 0 and autoconsumed > 0 else
                       "generating" if pv > 0 else "consuming_from_network" if imported > 0 else
                       "consuming_from_produced" if discharged > 0 else "off")
    alarms = [f"ID{(address - 0x0405) * 16 + bit + 1:03d}"
              for address in range(0x0405, 0x0411) for bit in range(16) if r[address] & (1 << bit)]
    codes_text = ", ".join(alarms)
    values["codici_allarme"] = codes_text[:252] + "..." if len(codes_text) > 255 else codes_text or "none"
    events = describe_events(alarms)
    values["eventi_attivi"] = events
    values["messaggi_inverter"] = event_summary(events, "message")
    values["errori_inverter"] = event_summary(events, "error", "unknown")
    values["protezioni_inverter"] = event_summary(events, "protection")
    values["numero_errori"] = sum(e["kind"] in ("error", "unknown") for e in events)
    values["allarme"] = any(e["kind"] != "message" for e in events) or r[0x0404] in (3, 4)
    # Legacy raw flow states remain stable for existing automations and history.
    values["flusso_batteria"] = "scarica" if battery > 0 else "carica" if battery < 0 else "inattiva"
    values["flusso_rete"] = "importazione" if grid > 0 else "esportazione" if grid < 0 else "nessuno"
    return values
