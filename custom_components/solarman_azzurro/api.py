"""Strict, asynchronous, read-only Solarman V5 transport (standard library only)."""
from __future__ import annotations

import asyncio
from contextlib import suppress
import secrets
import socket
import time
import struct


SNAPSHOT_TIMEOUT = 20


class ProtocolError(Exception):
    """A reply cannot safely be used as an inverter measurement."""


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def read_request(serial: int, sequence: int, start: int, count: int) -> bytes:
    """Only FC03 is implemented; no function accepts a write operation."""
    if not 0 < serial <= 0xFFFFFFFF or not 0 <= sequence < 256:
        raise ValueError("Invalid logger identity")
    if not 0 <= start <= 0xFFFF or not 1 <= count <= 125 or start + count > 65536:
        raise ValueError("Invalid read window")
    rtu = struct.pack(">BBHH", 1, 3, start, count)
    rtu += struct.pack("<H", crc16(rtu))
    frame = (b"\xa5" + struct.pack("<H", 15 + len(rtu)) + b"\x10\x45"
             + struct.pack("<H", sequence) + struct.pack("<I", serial)
             + b"\x02" + bytes(14) + rtu)
    return frame + bytes((sum(frame[1:]) & 255, 0x15))


def parse_response(frame: bytes, serial: int, sequence: int, count: int) -> tuple[int, ...]:
    if (len(frame) < 28 or frame[0] != 0xA5 or frame[-1] != 0x15
            or len(frame) != 13 + struct.unpack("<H", frame[1:3])[0]):
        raise ProtocolError("Invalid V5 frame length or boundaries")
    if sum(frame[1:-2]) & 255 != frame[-2]:
        raise ProtocolError("Invalid V5 checksum")
    if frame[5] != sequence or frame[7:11] != struct.pack("<I", serial):
        raise ProtocolError("Mismatched V5 transaction or logger")
    if frame[3:5] != b"\x10\x15" or frame[11] != 2:
        raise ProtocolError("Unexpected V5 response type")
    rtu = frame[25:-2]
    # Some logger firmware adds two zero bytes after a valid RTU CRC.
    if rtu.endswith(b"\x00\x00") and len(rtu) >= 7 and crc16(rtu[:-4]) == int.from_bytes(rtu[-4:-2], "little"):
        rtu = rtu[:-2]
    if len(rtu) < 5 or crc16(rtu[:-2]) != int.from_bytes(rtu[-2:], "little"):
        raise ProtocolError("Invalid Modbus CRC")
    if rtu[0] != 1:
        raise ProtocolError("Unexpected Modbus slave")
    if rtu[1] & 0x80:
        raise ProtocolError(f"Modbus exception {rtu[2]}")
    if rtu[:2] != b"\x01\x03" or rtu[2] != count * 2 or len(rtu) != count * 2 + 5:
        raise ProtocolError("Unexpected Modbus function or register count")
    return struct.unpack(f">{count}H", rtu[3:-2])


class SolarmanClient:
    """One persistent connection and one ordered snapshot at a time."""

    def __init__(self, host: str, serial: int, port: int = 8899, timeout: float = 5):
        self.host, self.serial, self.port, self.timeout = host, serial, port, timeout
        self._lock = asyncio.Lock()
        self._reader = None
        self._writer = None
        self._reader_task = None
        self._pending = None
        self._ignored = 0
        self._closed = False
        self._sequence = secrets.randbelow(256)
        self.connection_count = 0
        self.request_count = 0

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def async_close(self):
        """Stop the session, including a read or connect currently in flight."""
        self._closed = True
        await self._disconnect()
        async with self._lock:
            await self._disconnect()

    def _fail_pending(self, error):
        if self._pending is not None and not self._pending[2].done():
            self._pending[2].set_exception(error)

    async def _disconnect(self):
        task, writer = self._reader_task, self._writer
        self._reader_task = self._reader = self._writer = None
        self._fail_pending(ConnectionError("Logger session closed"))
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if writer is not None:
            writer.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 1)

    async def _connect(self):
        if self._closed:
            raise ConnectionError("Logger client is closed")
        if self.connected:
            return
        await self._disconnect()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), self.timeout
        )
        if self._closed:
            writer.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 1)
            raise ConnectionError("Logger client is closed")
        sock = writer.get_extra_info("socket")
        if sock is not None:
            with suppress(OSError):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self._reader, self._writer = reader, writer
        self.connection_count += 1
        self._reader_task = asyncio.create_task(self._receive(reader, writer))

    async def _receive(self, reader, writer):
        """Consume idle heartbeat frames; never cache unsolicited measurements."""
        error = ConnectionError("Logger connection closed")
        try:
            while True:
                header = await reader.readexactly(3)
                length = int.from_bytes(header[1:3], "little")
                if header[0] != 0xA5 or length > 4096:
                    raise ProtocolError("Invalid V5 header")
                frame = header + await asyncio.wait_for(reader.readexactly(length + 10), self.timeout)
                if (frame[-1] != 0x15 or sum(frame[1:-2]) & 255 != frame[-2]
                        or frame[7:11] != struct.pack("<I", self.serial)):
                    raise ProtocolError("Invalid V5 checksum, boundaries or logger identity")
                if frame[3:5] == b"\x10\x47":
                    # V5 heartbeat acknowledgement; no Modbus write or settings.
                    payload = b"\x00\x01" + struct.pack("<I", int(time.time())) + bytes(4)
                    ack = (b"\xa5\x0a\x00\x10\x17"
                           + bytes(((frame[5] + 1) & 255, frame[6])) + frame[7:11] + payload)
                    writer.write(ack + bytes((sum(ack[1:]) & 255, 0x15)))
                    await asyncio.wait_for(writer.drain(), self.timeout)
                elif (self._pending is not None and not self._pending[2].done()
                      and frame[3:5] == b"\x10\x15" and frame[5] == self._pending[0]):
                    sequence, count, future = self._pending
                    future.set_result(parse_response(frame, self.serial, sequence, count))
                    continue
                if self._pending is not None and not self._pending[2].done():
                    self._ignored += 1
                    if self._ignored >= 8:
                        raise ProtocolError("No matching V5 measurement reply")
        except (OSError, asyncio.IncompleteReadError, ProtocolError) as err:
            error = err
        finally:
            self._fail_pending(error)
            if self._writer is writer:
                self._reader = self._writer = None
            writer.close()
            try:
                with suppress(OSError, TimeoutError):
                    await asyncio.wait_for(writer.wait_closed(), 1)
            finally:
                if self._reader_task is asyncio.current_task():
                    self._reader_task = None

    async def read(self, windows: tuple[tuple[int, int], ...]) -> dict[int, int]:
        """Retry a transport failure once, rereading the whole snapshot."""
        async with self._lock:
            try:
                async with asyncio.timeout(SNAPSHOT_TIMEOUT):
                    for attempt in range(2):
                        try:
                            return await self._read_once(windows)
                        except (OSError, asyncio.IncompleteReadError):
                            await self._disconnect()
                            if attempt or self._closed:
                                raise
                            await asyncio.sleep(min(0.25, self.timeout))
            except BaseException:
                # Includes protocol errors, total deadline and cancellation.
                await self._disconnect()
                raise

    async def _read_once(self, windows: tuple[tuple[int, int], ...]) -> dict[int, int]:
        phase = "connecting to the logger"
        try:
            await self._connect()
            registers = {}
            for start, count in windows:
                phase = f"reading register window 0x{start:04X} ({count} registers)"
                self._sequence = (self._sequence + 1) & 255
                request = read_request(self.serial, self._sequence, start, count)
                writer = self._writer
                if writer is None or writer.is_closing():
                    raise ConnectionError("Logger session ended during snapshot")
                future = asyncio.get_running_loop().create_future()
                self._pending = (self._sequence, count, future)
                self._ignored = 0
                try:
                    async with asyncio.timeout(self.timeout):
                        writer.write(request)
                        self.request_count += 1
                        await writer.drain()
                        values = await future
                    registers.update({start + index: value for index, value in enumerate(values)})
                finally:
                    self._pending = None
                    if not future.done():
                        future.cancel()
                    elif not future.cancelled():
                        future.exception()  # Observe failures if drain raised first.
            return registers
        except TimeoutError as err:
            raise TimeoutError(f"Timed out {phase}") from err
