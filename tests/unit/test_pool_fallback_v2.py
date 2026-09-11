from __future__ import annotations

import asyncio
import copy
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from miner_testcode.errors import ConfigError, DeviceError
from miner_testcode.pool_fallback import TemporaryPools
from miner_testcode.pool_fallback_v2 import WorkingV2Pool
from miner_testcode.interfaces import fake_stratum_v2 as sv2
from miner_testcode.module_catalog import load_module_catalog
from tests.unit.test_fake_stratum_v2 import _connect_test_client
from tests.unit.test_pool_fallback import FakeApi


class WorkingV2PoolTest(unittest.IsolatedAsyncioTestCase):
    async def pool(self, label="primary"):
        pool = WorkingV2Pool(label, "127.0.0.1", 256)
        await pool.start()
        self.addAsyncCleanup(pool.close)
        return pool

    async def client(self, pool, channel):
        client = await _connect_test_client(pool, channel, identity="fallback-regression.primary")
        self.addAsyncCleanup(client.close)
        return client

    async def job(self, pool, client):
        await pool.publish_work()
        frames = [await asyncio.wait_for(client.noise.receive_frame(), 2) for _ in range(3)]
        self.assertEqual(frames[0].message_type, sv2.SV2_MSG_SET_TARGET)
        self.assertEqual(frames[2].message_type, sv2.SV2_MSG_SET_NEW_PREV_HASH)
        return int.from_bytes(frames[1].payload[4:8], "little")

    async def submit(self, client, job, sequence):
        payload = struct.pack("<IIIIII", client.channel_id, sequence, job, 42, 123, 0x20000000)
        message = sv2.SV2_MSG_SUBMIT_SHARES_STANDARD
        if client.channel_type == "extended":
            message = sv2.SV2_MSG_SUBMIT_SHARES_EXTENDED
            payload += b"\x08" + bytes(8)
        await client.noise.send_frame(sv2.SV2_CHANNEL_MESSAGE, message, payload)

    async def test_both_channels_resume_authenticated_work_after_silence(self):
        for channel in ("standard", "extended"):
            with self.subTest(channel=channel):
                pool = await self.pool()
                client = await self.client(pool, channel)
                job = await self.job(pool, client)
                await self.submit(client, job, 1)
                ack = await asyncio.wait_for(client.noise.receive_frame(), 2)
                self.assertEqual(ack.message_type, sv2.SV2_MSG_SUBMIT_SHARES_SUCCESS)
                self.assertEqual(pool.mining_submissions[0].username, "fallback-regression.primary")
                self.assertEqual(pool.mining_submissions[0].job_id, job)
                self.assertEqual(pool.mining_submissions[0].channel_type, channel)
                connection = pool.sessions[0].connection_id
                pool.silent = True
                await self.submit(client, job, 2)
                await pool.publish_work()
                with self.assertRaises(TimeoutError):
                    await asyncio.wait_for(client.noise.receive_frame(), .03)
                self.assertEqual(pool.silent_requests, 1)
                self.assertEqual(len(pool.submissions), 2)
                self.assertEqual(len(pool.mining_submissions), 1, "unacknowledged share counted")
                self.assertTrue(pool.sessions[0].connected)
                pool.silent = False
                new_job = await self.job(pool, client)
                self.assertNotEqual(new_job, job)
                await self.submit(client, new_job, 3)
                ack = await asyncio.wait_for(client.noise.receive_frame(), 2)
                self.assertEqual(ack.message_type, sv2.SV2_MSG_SUBMIT_SHARES_SUCCESS)
                self.assertEqual(pool.mining_submissions[-1].connection_id, connection)
                self.assertEqual(len(pool.mining_submissions), 2)
                # Worker, channel and authority material must not reach artifacts.
                with tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / "transcript.jsonl"
                    pool.write_transcript(path)
                    content = path.read_text()
                    for private in ("fallback-regression.primary", "private-device", pool.authority_public_key_base58):
                        self.assertNotIn(private, content)
                await client.close()
                await pool.close()

    async def test_silence_also_withholds_reconnect_noise_handshake(self):
        pool = await self.pool()
        pool.silent = True
        reader, writer = await asyncio.open_connection("127.0.0.1", pool.port)
        try:
            writer.write(sv2._generate_ellswift_key().encoded_public_key)
            await writer.drain()
            with self.assertRaises(TimeoutError):
                await asyncio.wait_for(reader.read(1), .03)
            self.assertTrue(pool.sessions[0].connected)
            pool.silent = False
            self.assertEqual(len(await asyncio.wait_for(reader.readexactly(234), 2)), 234)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_endpoint_outage_reopens_same_port_and_authority(self):
        pool = await self.pool()
        fallback = await self.pool("fallback")
        self.assertNotEqual(pool.authority_public_key_base58, fallback.authority_public_key_base58)
        client = await self.client(pool, "extended")
        port, authority = pool.port, pool.authority_public_key_base58
        await pool.set_available(False)
        self.assertEqual(await asyncio.wait_for(client.reader.read(), 1), b"")
        await pool.set_available(True)
        self.assertEqual(pool.port, port)
        self.assertEqual(pool.authority_public_key_base58, authority)
        resumed = await self.client(pool, "extended")
        self.assertNotEqual(resumed.channel_id, client.channel_id)
        self.assertIn(await self.job(pool, resumed), pool.jobs)

    async def test_limits_are_visible_instead_of_becoming_missing_share_timeouts(self):
        pool = await self.pool()
        pool.job_counter = 4096
        with self.assertRaises(ConnectionError):
            await pool._send_work(None)
        with self.assertRaises(DeviceError):
            pool.check_limits()
        pool = await self.pool()
        pool.max_events = len(pool._events)
        with self.assertRaises(RuntimeError):
            await pool._record_event("limit")
        with self.assertRaises(DeviceError):
            pool.check_limits()


class TemporaryV2PoolTest(unittest.IsolatedAsyncioTestCase):
    async def test_authentication_role_swap_and_partial_setup_restore(self):
        primary, fallback = [WorkingV2Pool(label, "127.0.0.1", 256) for label in ("primary", "fallback")]
        keys = (primary.authority_public_key_base58, fallback.authority_public_key_base58)
        for channel in ("standard", "extended"):
            for failing_write in (None, 1, 2):
                with self.subTest(channel=channel, failing_write=failing_write):
                    api = FakeApi()
                    original = copy.deepcopy(api.info)
                    pools = TemporaryPools(api, api.read, api.info, read_only=False)
                    api.fail_after_patch = failing_write
                    if failing_write:
                        with self.assertRaises(OSError):
                            await pools.install("test-host", 4333, 4334, 256, protocol="SV2",
                                                channel_type=channel, authority_keys=keys)
                    else:
                        await pools.install("test-host", 4333, 4334, 256, protocol="SV2",
                                            channel_type=channel, authority_keys=keys)
                        for index, key in zip(pools.ids, (keys[0], keys[1], keys[1])):
                            row = pools.entries[index]
                            self.assertEqual(row["stratumProtocol"], "SV2")
                            self.assertEqual(row["stratumV2ChannelType"], channel)
                            self.assertTrue(row["stratumV2RequireAuth"])
                            self.assertEqual(row["stratumV2AuthorityPubkey"], key)
                        await pools.select(pools.secondary, pools.primary, save_entries=True)
                    await pools.restore()
                    self.assertEqual(api.info, original)
                    for private in ("private-user-canary", "private-backup-canary", "*****", "stratumPassword"):
                        self.assertNotIn(private, json.dumps(api.writes))

    async def test_invalid_protocol_authentication_rejected_before_any_write(self):
        for settings in ({"protocol": "SV3"}, {"protocol": "SV2"},
                         {"protocol": "SV1", "channel_type": "extended"},
                         {"protocol": "SV2", "channel_type": "extended", "authority_keys": ("*****", "${KEY}")}):
            api = FakeApi()
            pools = TemporaryPools(api, api.read, api.info, read_only=False)
            with self.assertRaises(ConfigError):
                await pools.install("test-host", 4333, 4334, 256, **settings)
            self.assertEqual(api.writes, [])
            self.assertFalse(pools.owned)


class V2FallbackDiscoveryTest(unittest.TestCase):
    def test_catalog_and_discovery_cover_both_channels_without_duplicate_sv1_cases(self):
        catalog = load_module_catalog().module("pool_fallback_v2_regression")
        self.assertEqual(catalog.required_capabilities, ("http", "stratum-v2"))
        directory = Path(__file__).parents[1] / "e2e"
        before = list(sys.path)
        try:
            suite = unittest.TestLoader().discover(str(directory), pattern=catalog.test_pattern)
            cases = [test for module in suite for cls in module for test in cls]
        finally:
            sys.path[:] = before
        self.assertEqual(len(cases), 18)
        self.assertEqual({case.channel_type for case in cases}, {"standard", "extended"})
        for case in cases:
            self.assertEqual(case.protocol, "SV2")
            self.assertEqual(case.settings_section, catalog.id)
        source = directory / "test_pool_fallback_regression.py"
        self.assertIn("PoolFallbackRegressionTest", source.read_text())
