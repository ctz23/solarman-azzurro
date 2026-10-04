"""Read-only UDP discovery; replies only suggest connection parameters."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from ipaddress import IPv4Address
import re
import socket

DISCOVERY_PORT = 48899
DISCOVERY_QUERY = b"WIFIKIT-214028-READ"
DISCOVERY_TIMEOUT = 2.0


@dataclass(frozen=True)
class DiscoveredLogger:
    """A logger identity advertised from its own IPv4 address."""

    host: str
    serial: int


def parse_discovery_reply(data: bytes, sender: str) -> DiscoveredLogger | None:
    """Ignore malformed replies and advertised addresses unlike the sender."""
    if len(data) > 128:
        return None
    try:
        host, mac, serial = (field.strip() for field in data.decode("ascii").strip("\x00\r\n ").split(","))
        address = IPv4Address(host)
        if (address != IPv4Address(sender) or address.is_multicast
                or address.is_unspecified or host == "255.255.255.255"):
            return None
        if not re.fullmatch(r"(?:[0-9a-fA-F]{12}|(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})", mac):
            return None
        if not serial.isdecimal() or not 0 < int(serial) <= 0xFFFFFFFF:
            return None
    except (ValueError, UnicodeDecodeError):
        return None
    return DiscoveredLogger(str(address), int(serial))


class _DiscoveryProtocol(asyncio.DatagramProtocol):
    """Collect a bounded, deduplicated set of valid replies."""

    def __init__(self):
        self.loggers: dict[tuple[str, int], DiscoveredLogger] = {}

    def datagram_received(self, data, addr):
        if len(self.loggers) < 64 and (logger := parse_discovery_reply(data, addr[0])):
            self.loggers[(logger.host, logger.serial)] = logger


async def async_discover(addresses: list[str], *, timeout: float = DISCOVERY_TIMEOUT,
                         port: int = DISCOVERY_PORT) -> list[DiscoveredLogger]:
    """Send only a discovery query, close the socket and return suggestions."""
    if not addresses:
        return []
    transport, protocol = await asyncio.get_running_loop().create_datagram_endpoint(
        _DiscoveryProtocol, local_addr=("0.0.0.0", 0), family=socket.AF_INET,
        allow_broadcast=True,
    )
    try:
        for address in sorted(set(addresses)):
            try:
                transport.sendto(DISCOVERY_QUERY, (address, port))
            except OSError:
                continue
        await asyncio.sleep(timeout)
        return sorted(protocol.loggers.values(), key=lambda logger: (logger.host, logger.serial))
    finally:
        transport.close()
