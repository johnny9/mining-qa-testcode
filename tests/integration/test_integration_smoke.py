from __future__ import annotations

import asyncio

from miner_testcode import capabilities as caps
from miner_testcode.devices.base import PoolSettings
from miner_testcode.interfaces.fake_stratum import FakeStratumV1Server, MiningJob
from miner_testcode.testcase import MinerTestCase


class MockDeviceIntegrationTest(MinerTestCase):
    required_capabilities = frozenset(
        {caps.API, caps.MINING_STATE, caps.POOL_CONFIG, caps.STRATUM_V1}
    )

    async def test_real_gamma_adapter_and_stratum_lifecycle(self) -> None:
        settings = self.settings_for("mock_device_integration")
        server = FakeStratumV1Server(host="127.0.0.1", port=0)
        await server.start()
        self.addAsyncCleanup(server.close)

        username = str(settings.get("username", "integration-smoke.worker"))
        await self.device.configure_pool(
            PoolSettings(
                host="127.0.0.1",
                port=server.port,
                username=username,
                password=None,
                tls=False,
            )
        )
        handshake = await server.wait_for_handshake(timeout=10.0)
        self.assertEqual(handshake.authorize.params[0], username)
        job = MiningJob.standard("integration-job")
        await server.send_job(job, difficulty=1.0, session=handshake.connection_id)
        submission = await server.wait_for_submission(
            job_id=job.job_id,
            connection_id=handshake.connection_id,
            timeout=10.0,
        )
        self.assertEqual(submission.username, username)

        async with asyncio.timeout(10.0):
            while True:
                info = await self.device.current_info()
                if int(info.get("sharesAccepted", 0)) >= 1:
                    break
                if int(info.get("sharesRejected", 0)):
                    self.fail("mock device recorded a rejected deterministic share")
                await asyncio.sleep(0.1)
        self.assertEqual(int(info.get("sharesRejected", 0)), 0)
        self.chart("Mock Gamma HTTP and Stratum lifecycle completed", status="good")
