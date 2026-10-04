"""UDP discovery tests use only synthetic loopback replies."""
import asyncio
import importlib
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
package = types.ModuleType("azzurro_discovery_test")
package.__path__ = [str(ROOT / "custom_components/solarman_azzurro")]
sys.modules.setdefault("azzurro_discovery_test", package)
discovery = importlib.import_module("azzurro_discovery_test.discovery")
REPLY = b"127.0.0.1,112233aabbcc,1234567890"


class DiscoveryReplyTests(unittest.TestCase):
    def test_valid_reply(self):
        self.assertEqual(discovery.parse_discovery_reply(REPLY + b"\r\n", "127.0.0.1"),
                         discovery.DiscoveredLogger("127.0.0.1", 1234567890))

    def test_rejects_malformed_replies(self):
        for reply in (b"", b"127.0.0.1,123", b"\xff", b"x" * 129,
                      b"127.0.0.1,112233aabbcc,0", b"127.0.0.1,112233aabbcc,4294967296",
                      b"127.0.0.1,112233aabbcc,inverter", b"127.0.0.1,badmac,1234567890",
                      b"0.0.0.0,112233aabbcc,1234567890", b"224.0.0.1,112233aabbcc,1234567890"):
            with self.subTest(reply=reply):
                self.assertIsNone(discovery.parse_discovery_reply(reply, "127.0.0.1"))

    def test_rejects_advertised_ip_unlike_sender(self):
        self.assertIsNone(discovery.parse_discovery_reply(REPLY, "127.0.0.2"))

    def test_no_addresses(self):
        self.assertEqual(asyncio.run(discovery.async_discover([])), [])


class DiscoveryNetworkTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_udp_query_and_deduplication(self):
        queries = []

        class Responder(asyncio.DatagramProtocol):
            def connection_made(self, transport):
                self.transport = transport

            def datagram_received(self, data, addr):
                queries.append(data)
                for reply in (REPLY, REPLY, b"invalid"):
                    self.transport.sendto(reply, addr)

        transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            Responder, local_addr=("127.0.0.1", 0))
        try:
            result = await discovery.async_discover(["127.0.0.1"],
                timeout=.05, port=transport.get_extra_info("sockname")[1])
        finally:
            transport.close()
        self.assertEqual(queries, [discovery.DISCOVERY_QUERY])
        self.assertEqual(result, [discovery.DiscoveredLogger("127.0.0.1", 1234567890)])

    async def test_no_replies_timeout(self):
        class SilentResponder(asyncio.DatagramProtocol):
            pass
        transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            SilentResponder, local_addr=("127.0.0.1", 0))
        try:
            result = await discovery.async_discover(["127.0.0.1"],
                timeout=.02, port=transport.get_extra_info("sockname")[1])
        finally:
            transport.close()
        self.assertEqual(result, [])
