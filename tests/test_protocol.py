"""Independent mock wire replies and synthetic register values; no private data."""
import asyncio
from contextlib import suppress
import importlib
import pathlib
import struct
import sys
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
package = types.ModuleType("azzurro_test")
package.__path__ = [str(ROOT / "custom_components/solarman_azzurro")]
sys.modules.setdefault("azzurro_test", package)
api = importlib.import_module("azzurro_test.api")
profile = importlib.import_module("azzurro_test.profile")
SERIAL = 1234567890


def reply(sequence=1, serial=SERIAL, values=(3,), exception=None):
    rtu = (bytes((1, 0x83, exception)) if exception else
           bytes((1, 3, len(values) * 2)) + struct.pack(f">{len(values)}H", *values))
    rtu += struct.pack("<H", api.crc16(rtu))
    frame = (b"\xa5" + struct.pack("<H", 14 + len(rtu)) + b"\x10\x15"
             + struct.pack("<H", sequence) + struct.pack("<I", serial) + b"\x02" + bytes(13) + rtu)
    return frame + bytes((sum(frame[1:]) & 255, 0x15))


def v5_checksum(frame):
    frame = bytearray(frame)
    frame[-2] = sum(frame[1:-2]) & 255
    return bytes(frame)


def snapshot():
    r = {start + i: 0 for start, count in profile.WINDOWS for i in range(count)}
    r.update({0x0404: 2, 0x0608: 60, 0x0609: 95, 0x048D: 2300, 0x0484: 5000,
              0x0586: 150, 0x0589: 100, 0x04AF: 200, 0x0604: 520,
              0x0418: 35, 0x041A: 30, 0x0607: 25})
    return r


class ProtocolTests(unittest.TestCase):
    def test_crc_known_modbus_request(self):
        self.assertEqual(api.crc16(bytes.fromhex("010300000001")), 0x0A84)

    def test_request_is_fc03_only(self):
        frame = api.read_request(SERIAL, 1, 0x0404, 13)
        self.assertEqual(frame[26:32], bytes.fromhex("01030404000d"))
        self.assertEqual(len(frame), 13 + int.from_bytes(frame[1:3], "little"))

    def test_reply(self):
        self.assertEqual(api.parse_response(reply(values=(2, 5000)), SERIAL, 1, 2), (2, 5000))

    def test_corrupt_v5_checksum(self):
        frame = bytearray(reply()); frame[12] ^= 1
        with self.assertRaisesRegex(api.ProtocolError, "checksum"):
            api.parse_response(bytes(frame), SERIAL, 1, 1)

    def test_corrupt_rtu_crc(self):
        frame = bytearray(reply()); frame[-3] ^= 1
        with self.assertRaisesRegex(api.ProtocolError, "CRC"):
            api.parse_response(v5_checksum(frame), SERIAL, 1, 1)

    def test_wrong_logger_or_sequence(self):
        for frame in (reply(serial=42), reply(sequence=2)):
            with self.assertRaisesRegex(api.ProtocolError, "transaction"):
                api.parse_response(frame, SERIAL, 1, 1)

    def test_wrong_count(self):
        with self.assertRaisesRegex(api.ProtocolError, "count"):
            api.parse_response(reply(), SERIAL, 1, 2)

    def test_modbus_exception(self):
        with self.assertRaisesRegex(api.ProtocolError, "exception 2"):
            api.parse_response(reply(exception=2), SERIAL, 1, 1)

    def test_invalid_frame_length(self):
        with self.assertRaises(api.ProtocolError):
            api.parse_response(reply()[:-1], SERIAL, 1, 1)

    def test_refuses_unbounded_read(self):
        for count in (0, 126):
            with self.assertRaises(ValueError):
                api.read_request(SERIAL, 1, 0x0400, count)


class ProfileTests(unittest.TestCase):
    def test_import_export_sign(self):
        r = snapshot();r[0x0488] = 65536 - 75
        d = profile.decode(r)
        self.assertEqual((d['potenza_importata'], d['potenza_esportata']), (750, 0))
        r[0x0488] = 75;d = profile.decode(r)
        self.assertEqual((d['potenza_importata'], d['potenza_esportata']), (0, 750))

    def test_battery_direction(self):
        r = snapshot();r[0x0606] = 50
        d = profile.decode(r)
        self.assertEqual((d['potenza_carica'], d['potenza_scarica']), (500, 0))
        r[0x0606] = 65536 - 50;d = profile.decode(r)
        self.assertEqual((d['potenza_carica'], d['potenza_scarica']), (0, 500))

    def test_energy_word_order(self):
        r = snapshot();r[0x0686] = 1;r[0x0687] = 2
        self.assertEqual(profile.decode(r)['totale_energia_prodotta'], 6553.8)

    def test_day_reset(self):
        r = snapshot();r[0x0685] = 500
        self.assertEqual(profile.decode(r)['energia_prodotta_oggi'], 5)
        r[0x0685] = 0
        self.assertEqual(profile.decode(r)['energia_prodotta_oggi'], 0)

    def test_energy_sentinel_propagates_to_estimate(self):
        r = snapshot();r[0x0686] = r[0x0687] = 65535
        d = profile.decode(r)
        self.assertIsNone(d['totale_energia_prodotta'])
        self.assertIsNone(d['totale_enegia_autoconsumata'])

    def test_no_fake_temperature_or_soh(self):
        r = snapshot();r[0x0607] = 65535;r[0x0609] = 65535
        d = profile.decode(r)
        self.assertIsNone(d['temperatura_batteria']);self.assertIsNone(d['salute_batteria'])

    def test_derived_self_consumption_excludes_charging(self):
        r = snapshot();r[0x0488] = 20;r[0x0606] = 50
        d = profile.decode(r)
        self.assertEqual(d['potenza_autoconsumata'], 1800)

    def test_alarm_bit_index(self):
        r = snapshot();r[0x040C] = 1 << 11
        d = profile.decode(r)
        self.assertEqual(d['codici_allarme'], 'ID124');self.assertFalse(d['allarme'])

    def test_rejects_incomplete_snapshot(self):
        r = snapshot();del r[0x0608]
        with self.assertRaises(api.ProtocolError):profile.decode(r)

    def test_rejects_wrong_profile(self):
        r = snapshot();r[0x0608] = 255
        with self.assertRaises(api.ProtocolError):profile.decode(r)

    def test_metadata_supports_energy_statistics(self):
        items = {i.key: i for i in profile.MEASUREMENTS}
        self.assertEqual(items['energia_prodotta_oggi'].state_class, 'total_increasing')
        self.assertEqual(items['totale_energia_prodotta'].state_class, 'total')
        self.assertEqual(items['totale_energia_prodotta'].unit, 'kWh')
        self.assertTrue(items['energia_autoconsumata_oggi'].derived)


class NetworkTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.behavior = 'fragmented';self.calls = 0;self.connections = 0;self.requests = []
        self.tasks = set();self.heartbeat_length = 0
        self.clients = [];self.writers = [];self.acks = [];self.sequences = []
        self.server = await asyncio.start_server(self.handle, '127.0.0.1', 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        for client in self.clients:await client.async_close()
        self.server.close();await self.server.wait_closed()
        for task in self.tasks:task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def handle(self, reader, writer):
        task = asyncio.current_task();self.tasks.add(task)
        self.connections += 1
        connection = self.connections
        self.writers.append(writer)
        try:
            while True:
                head = await reader.readexactly(3)
                request = head + await reader.readexactly(int.from_bytes(head[1:3], 'little') + 10)
                if request[3:5] == b"\x10\x17":
                    self.acks.append(request)
                    continue
                self.sequences.append(request[5])
                self.calls += 1
                self.requests.append((connection, int.from_bytes(request[28:30], 'big')))
                count = int.from_bytes(request[30:32], 'big')
                if self.behavior == 'timeout' or (self.behavior == 'timeout_once' and connection == 1):
                    await asyncio.sleep(1);return
                if (self.behavior == 'partial' and self.calls % 2 == 0) or (self.behavior == 'partial_once' and self.calls == 2):
                    writer.write(reply(sequence=request[5], values=(3,))[:15]);await writer.drain();return
                frame = reply(sequence=request[5], values=tuple(range(count)) if self.behavior not in ('partial_once', 'close_after_first_window') else (connection,) * count)
                if self.behavior == 'close_after_first_window' and connection == 1:
                    writer.write(frame);await writer.drain();return
                if self.behavior == 'stale_before_valid':
                    writer.write(reply(sequence=(request[5] - 1) & 255, values=(999,) * count))
                if self.behavior == 'corrupt':
                    damaged = bytearray(frame);damaged[-2] ^= 1;frame = bytes(damaged)
                if self.behavior == 'heartbeat':
                    heartbeat = bytearray(frame);heartbeat[4] = 0x47
                    writer.write(v5_checksum(heartbeat))
                if self.behavior.startswith('short_'):
                    payload = bytes(self.heartbeat_length)
                    control = b"\x10\x15" if self.behavior == 'short_measurement' else b"\x10\x47"
                    serial = 42 if self.behavior == 'short_wrong_logger' else SERIAL
                    sequence = (request[5] - 1) & 255 if self.behavior == 'short_stale' else request[5]
                    short = (b"\xa5" + struct.pack("<H", len(payload)) + control
                             + struct.pack("<H", sequence) + struct.pack("<I", serial) + payload)
                    short += bytes((sum(short[1:]) & 255, 0x15))
                    if self.behavior == 'short_bad_checksum':
                        damaged = bytearray(short);damaged[-2] ^= 1;short = bytes(damaged)
                    if self.behavior == 'short_flood':
                        writer.write(short * 9)
                    elif self.behavior == 'short_fragmented':
                        for offset in range(0, len(short), 2):
                            writer.write(short[offset:offset+2]);await writer.drain();await asyncio.sleep(.001)
                    else:writer.write(short)
                if self.behavior == 'fragmented':
                    for offset in range(0, len(frame), 3):
                        writer.write(frame[offset:offset+3]);await writer.drain();await asyncio.sleep(.001)
                else:writer.write(frame);await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()
            with suppress(OSError):await writer.wait_closed()
            self.tasks.discard(task)

    def client(self):
        client = api.SolarmanClient('127.0.0.1', SERIAL, self.port, timeout=.1)
        self.clients.append(client)
        return client

    async def test_fragmented_tcp_frames(self):
        self.assertEqual(await self.client().read(((0x0404, 2),)), {0x0404: 0, 0x0405: 1})

    async def test_heartbeat_before_measurement(self):
        self.behavior = 'heartbeat'
        self.assertEqual(await self.client().read(((0x0404, 1),)), {0x0404: 0})

    async def test_short_heartbeats_before_measurement(self):
        self.behavior = 'short_heartbeat'
        for length in (0, 1, 12, 14):
            with self.subTest(payload_length=length):
                self.heartbeat_length = length
                self.assertEqual(await self.client().read(((0x0404, 1),)), {0x0404: 0})
        self.assertEqual(self.connections, 4)

    async def test_short_heartbeat_for_previous_window_does_not_break_snapshot(self):
        self.behavior = 'short_stale';self.heartbeat_length = 1
        self.assertEqual(await self.client().read(((0x0404, 1), (0x0604, 1))),
                         {0x0404: 0, 0x0604: 0})
        self.assertEqual(self.connections, 1)
        self.assertEqual(self.requests, [(1, 0x0404), (1, 0x0604)])

    async def test_fragmented_short_heartbeat_before_measurement(self):
        self.behavior = 'short_fragmented'
        self.assertEqual(await self.client().read(((0x0404, 1),)), {0x0404: 0})
        self.assertEqual(self.connections, 1)

    async def test_corrupt_short_heartbeat_is_rejected(self):
        self.behavior = 'short_bad_checksum'
        with self.assertRaisesRegex(api.ProtocolError, 'checksum, boundaries or logger identity'):
            await self.client().read(((0x0404, 1),))
        self.assertEqual(self.connections, 1)

    async def test_short_frame_from_wrong_logger_is_rejected(self):
        self.behavior = 'short_wrong_logger'
        with self.assertRaisesRegex(api.ProtocolError, 'checksum, boundaries or logger identity'):
            await self.client().read(((0x0404, 1),))
        self.assertEqual(self.connections, 1)

    async def test_short_matching_measurement_is_not_accepted(self):
        self.behavior = 'short_measurement'
        with self.assertRaises(api.ProtocolError):
            await self.client().read(((0x0404, 1),))
        self.assertEqual(self.connections, 1)

    async def test_heartbeat_flood_stops_at_frame_limit(self):
        self.behavior = 'short_flood'
        with self.assertRaisesRegex(api.ProtocolError, 'No matching'):
            await self.client().read(((0x0404, 1),))
        self.assertEqual(self.connections, 1)

    async def test_partial_transaction_is_not_returned(self):
        self.behavior = 'partial'
        with self.assertRaises(asyncio.IncompleteReadError):
            await self.client().read(((0x0404, 1), (0x0604, 1)))

    async def test_transient_timeout_reconnects_once(self):
        self.behavior = 'timeout_once'
        self.assertEqual(await self.client().read(((0x0404, 1),)), {0x0404: 0})
        self.assertEqual(self.connections, 2)
        self.assertEqual(self.calls, 2)

    async def test_retry_discards_all_registers_of_partial_attempt(self):
        self.behavior = 'partial_once'
        result = await self.client().read(((0x0404, 1), (0x0604, 1)))
        self.assertEqual(result, {0x0404: 2, 0x0604: 2})
        self.assertEqual(self.requests, [(1, 0x0404), (1, 0x0604), (2, 0x0404), (2, 0x0604)])

    async def test_persistent_timeout_stops_after_two_connections(self):
        self.behavior = 'timeout'
        with self.assertRaisesRegex(TimeoutError, "0x0404"):
            await self.client().read(((0x0404, 1),))
        self.assertEqual(self.connections, 2)

    async def test_corrupt_measurement_is_rejected_without_retry(self):
        self.behavior = 'corrupt'
        with self.assertRaisesRegex(api.ProtocolError, "checksum"):
            await self.client().read(((0x0404, 1),))
        self.assertEqual(self.connections, 1)

    async def test_cancellation_stops_without_retry(self):
        self.behavior = 'timeout'
        task = asyncio.create_task(self.client().read(((0x0404, 1),)))
        while not self.calls:
            await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.connections, 1)

    async def test_timeout_then_recovery(self):
        self.behavior = 'timeout'
        client = self.client()
        with self.assertRaises(TimeoutError):await client.read(((0x0404, 1),))
        self.behavior = 'normal'
        self.assertEqual(await client.read(((0x0404, 1),)), {0x0404: 0})


    async def test_multiple_snapshots_reuse_one_connection(self):
        client = self.client()
        for _ in range(4):
            self.assertEqual(await client.read(((0x0404, 1), (0x0604, 1))), {0x0404: 0, 0x0604: 0})
            self.assertTrue(client.connected)
        self.assertEqual(self.connections, 1)
        self.assertEqual(client.connection_count, 1)
        self.assertEqual(client.request_count, 8)
        self.assertEqual(len(set(self.sequences)), 8)

    async def test_concurrent_snapshots_are_ordered_on_one_session(self):
        client = self.client()
        await asyncio.gather(client.read(((0x0404, 1), (0x0604, 1))),
                             client.read(((0x0404, 1), (0x0604, 1))))
        self.assertEqual(self.requests, [(1, 0x0404), (1, 0x0604)] * 2)
        self.assertEqual(self.connections, 1)

    async def test_idle_heartbeat_is_acknowledged_without_polling(self):
        client = self.client()
        await client.read(((0x0404, 1),))
        heartbeat = b"\xa5\x00\x00\x10\x47" + bytes((255, 3)) + struct.pack("<I", SERIAL)
        heartbeat += bytes((sum(heartbeat[1:]) & 255, 0x15))
        self.writers[0].write(heartbeat);await self.writers[0].drain()
        async with asyncio.timeout(.3):
            while not self.acks:await asyncio.sleep(.001)
        ack = self.acks[0]
        self.assertEqual(ack[5:7], bytes((0, 3)))
        self.assertEqual(ack[7:11], struct.pack("<I", SERIAL))
        self.assertEqual(sum(ack[1:-2]) & 255, ack[-2])
        self.assertEqual(self.calls, 1)
        self.assertEqual(client.request_count, 1)
        await client.read(((0x0604, 1),))
        self.assertEqual(self.connections, 1)

    async def test_late_measurements_are_not_reused(self):
        client = self.client()
        await client.read(((0x0404, 1),))
        self.behavior = 'stale_before_valid'
        self.assertEqual(await client.read(((0x0604, 1),)), {0x0604: 0})
        self.assertEqual(self.connections, 1)

    async def test_peer_close_between_snapshots_reconnects(self):
        client = self.client()
        await client.read(((0x0404, 1),))
        self.writers[0].close();await self.writers[0].wait_closed()
        async with asyncio.timeout(.3):
            while client.connected:await asyncio.sleep(.001)
        self.assertEqual(await client.read(((0x0604, 1),)), {0x0604: 0})
        self.assertEqual(self.connections, 2)

    async def test_bad_snapshot_drops_session_then_recovery_is_fresh(self):
        client = self.client();self.behavior = 'corrupt'
        with self.assertRaises(api.ProtocolError):await client.read(((0x0404, 1),))
        self.assertFalse(client.connected)
        self.behavior = 'normal'
        self.assertEqual(await client.read(((0x0604, 1),)), {0x0604: 0})
        self.assertEqual(self.connections, 2)

    async def test_close_idle_session_is_final_and_idempotent(self):
        client = self.client();await client.read(((0x0404, 1),))
        task = client._reader_task
        await client.async_close();await client.async_close()
        self.assertFalse(client.connected)
        self.assertTrue(task.done())
        with self.assertRaises(ConnectionError):await client.read(((0x0404, 1),))
        self.assertEqual(self.connections, 1)

    async def test_close_while_reading_prevents_reconnect(self):
        client = self.client();self.behavior = 'timeout'
        task = asyncio.create_task(client.read(((0x0404, 1),)))
        while not self.calls:await asyncio.sleep(0)
        await client.async_close()
        with self.assertRaises(ConnectionError):await task
        self.assertFalse(client.connected)
        self.assertEqual(self.connections, 1)

    async def test_cancelled_read_can_recover_without_old_reply(self):
        client = self.client();self.behavior = 'timeout'
        task = asyncio.create_task(client.read(((0x0404, 1),)))
        while not self.calls:await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertFalse(client.connected)
        self.behavior = 'normal'
        self.assertEqual(await client.read(((0x0604, 1),)), {0x0604: 0})
        self.assertEqual(self.connections, 2)


    async def test_total_deadline_cleans_session_without_extra_retry(self):
        client = self.client();self.behavior = 'timeout'
        with patch.object(api, 'SNAPSHOT_TIMEOUT', .05):
            with self.assertRaises(TimeoutError):await client.read(((0x0404, 1),))
        self.assertFalse(client.connected)
        self.assertIsNone(client._reader_task)
        self.assertEqual(self.connections, 1)

    async def test_close_during_connect_leaves_no_reader_or_socket(self):
        client = self.client();started = asyncio.Event();proceed = asyncio.Event()
        real_open = asyncio.open_connection
        async def delayed_open(*args):
            started.set();await proceed.wait()
            return await real_open(*args)
        with patch.object(api.asyncio, 'open_connection', delayed_open):
            task = asyncio.create_task(client.read(((0x0404, 1),)))
            await started.wait()
            closer = asyncio.create_task(client.async_close())
            await asyncio.sleep(0);proceed.set()
            with self.assertRaises(ConnectionError):await task
            await closer
        self.assertFalse(client.connected)
        self.assertIsNone(client._reader_task)
        self.assertEqual(client.request_count, 0)


    async def test_close_after_valid_window_discards_attempt_and_retries(self):
        client = self.client();self.behavior = 'close_after_first_window'
        self.assertEqual(await client.read(((0x0404, 1), (0x0604, 1))),
                         {0x0404: 2, 0x0604: 2})
        self.assertEqual(self.connections, 2)


if __name__ == '__main__':unittest.main()


class EventClassificationTests(unittest.TestCase):
    def with_codes(self, *numbers, state=2):
        registers = snapshot()
        registers[0x0404] = state
        for number in numbers:
            registers[0x0405 + (number - 1) // 16] |= 1 << ((number - 1) % 16)
        return profile.decode(registers)

    def test_reserve_message_is_not_fault(self):
        data = self.with_codes(124)
        self.assertFalse(data["allarme"])
        self.assertEqual(data["numero_errori"], 0)
        self.assertEqual(data["codici_allarme"], "ID124")
        self.assertIn("ID124", data["messaggi_inverter"])
        self.assertEqual(data["errori_inverter"], "none")

    def test_message_cannot_hide_real_fault(self):
        data = self.with_codes(124, 157)
        self.assertTrue(data["allarme"])
        self.assertEqual(data["numero_errori"], 1)
        self.assertIn("BMS", data["errori_inverter"])

    def test_protection_stays_visible(self):
        data = self.with_codes(125)
        self.assertTrue(data["allarme"])
        self.assertIn("ID125", data["protezioni_inverter"])
        self.assertEqual(data["messaggi_inverter"], "none")

    def test_unknown_code_is_not_silenced(self):
        data = self.with_codes(192)
        self.assertTrue(data["allarme"])
        self.assertEqual(data["eventi_attivi"][0]["kind"], "unknown")
        self.assertFalse(data["eventi_attivi"][0]["known"])

    def test_fault_state_without_bits_stays_fault(self):
        for state in (3, 4):
            self.assertTrue(self.with_codes(124, state=state)["allarme"])

    def test_many_codes_fit_state_without_losing_details(self):
        data = self.with_codes(*range(1, 193))
        self.assertLessEqual(len(data["errori_inverter"]), 255)
        self.assertLessEqual(len(data["codici_allarme"]), 255)
        self.assertEqual(len(data["eventi_attivi"]), 192)

    def test_net_flow_directions(self):
        registers = snapshot()
        registers.update({0x0606: 65526, 0x0488: 10})
        data = profile.decode(registers)
        self.assertEqual(data["flusso_batteria"], "scarica")
        self.assertEqual(data["flusso_rete"], "esportazione")
