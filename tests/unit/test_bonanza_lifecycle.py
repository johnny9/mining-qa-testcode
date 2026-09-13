from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

from miner_testcode.artifacts import TestArtifacts
from miner_testcode.config import DeviceConfig
from miner_testcode.devices.base import PoolSettings
from miner_testcode.devices.bitaxe_bonanza import BitaxeBonanzaDevice
from miner_testcode.errors import DeviceError


class FakeApi:
    base_url = "http://fake"

    def __init__(self) -> None:
        self.info: dict[str, Any] = {
            "boardVersion": "1002",
            "ASICModel": "BZM",
            "stratumURL": "old.pool",
            "stratumPort": 3333,
            "stratumUser": "old.worker",
            "stratumSuggestedDifficulty": 1000,
            "stratumProtocol": "SV1",
            "stratumTLS": 0,
            "stratumExtranonceSubscribe": False,
            "stratumDecodeCoinbase": True,
            "stratumV2ChannelType": "extended",
            "stratumV2AuthorityPubkey": "old-authority-key",
            "stratumV2RequireAuth": False,
            "miningPaused": False,
            "uptimeSeconds": 100,
            "asicHealth": {"lifecycle": "MINING", "lastFaultCode": 0},
        }
        self.patches: list[dict[str, Any]] = []

    async def get_json(self, path: str) -> dict[str, Any]:
        result = dict(self.info)
        self.info["uptimeSeconds"] += 1
        return result

    async def patch_json(self, path: str, value: Mapping[str, Any]) -> bytes:
        patch = dict(value)
        self.patches.append(patch)
        self.info.update({key: item for key, item in patch.items() if key != "stratumPassword"})
        return b""

    async def post_json(self, path: str, value=None) -> bytes:
        if path == "/api/system/restart":
            self.info["uptimeSeconds"] = 0
        return b"{}"


class FakePoolsApi(FakeApi):
    def __init__(self) -> None:
        super().__init__()
        self.info.update(
            {
                "pools": [
                    {
                        "id": 0,
                        "stratumURL": "old.pool",
                        "stratumPort": 3333,
                        "stratumUser": "old.worker",
                        "stratumPassword": "*****",
                        "stratumSuggestedDifficulty": 1000,
                        "stratumProtocol": "SV1",
                        "stratumTLS": 0,
                        "stratumExtranonceSubscribe": False,
                        "stratumDecodeCoinbase": True,
                        "stratumV2ChannelType": "extended",
                        "stratumV2AuthorityPubkey": "old-primary-authority",
                        "stratumV2RequireAuth": False,
                    },
                    {
                        "id": 1,
                        "stratumURL": "backup.pool",
                        "stratumPort": 4444,
                        "stratumUser": "backup.worker",
                        "stratumPassword": "*****",
                        "stratumSuggestedDifficulty": 512,
                        "stratumProtocol": "SV1",
                        "stratumTLS": 0,
                        "stratumExtranonceSubscribe": False,
                        "stratumDecodeCoinbase": True,
                        "stratumV2ChannelType": "standard",
                        "stratumV2AuthorityPubkey": "old-backup-authority",
                        "stratumV2RequireAuth": True,
                    },
                ],
                "primaryPoolIndex": 0,
                "secondaryPoolIndex": 1,
                "useFallbackStratum": True,
            }
        )

    async def patch_json(self, path: str, value: Mapping[str, Any]) -> bytes:
        patch = dict(value)
        self.patches.append(patch)
        if "pools" not in patch:
            self.info.update(patch)
            return b""
        by_id = {int(pool["id"]): dict(pool) for pool in self.info["pools"]}
        for incoming in patch["pools"]:
            pool = dict(incoming)
            pool_id = int(pool["id"])
            if pool.get("stratumPassword") == "*****":
                pool["stratumPassword"] = by_id[pool_id]["stratumPassword"]
            by_id[pool_id].update(pool)
        self.info["pools"] = [by_id[key] for key in sorted(by_id)]
        primary = by_id[int(self.info["primaryPoolIndex"])]
        self.info.update(
            {
                key: value
                for key, value in primary.items()
                if key.startswith("stratum") and key != "stratumPassword"
            }
        )
        return b""


class DelayedRestartApi(FakeApi):
    def __init__(self) -> None:
        super().__init__()
        self.restart_requested = False
        self.transient_injected = False
        self.rebooted = False
        self.restart_task: asyncio.Task[None] | None = None

    async def get_json(self, path: str) -> dict[str, Any]:
        if self.restart_requested and not self.transient_injected:
            self.transient_injected = True
            raise TimeoutError("transient API timeout before delayed reboot")
        if self.restart_requested and not self.rebooted:
            result = dict(self.info)
            result["uptimeSeconds"] = 0
            return result
        return await super().get_json(path)

    async def post_json(self, path: str, value=None) -> bytes:
        if path == "/api/system/restart":
            self.restart_requested = True
            self.restart_task = asyncio.create_task(self._complete_restart())
        return b"{}"

    async def _complete_restart(self) -> None:
        await asyncio.sleep(1.1)
        self.info["uptimeSeconds"] = 0
        self.rebooted = True


class BonanzaLifecycleTest(unittest.IsolatedAsyncioTestCase):
    def make_device(
        self, directory: str, artifacts: TestArtifacts, *, name: str
    ) -> BitaxeBonanzaDevice:
        config = DeviceConfig(
            name="fake-bonanza",
            type="bitaxe_bonanza",
            interfaces={
                "api": {"base_url": "http://127.0.0.1", "online_timeout": 2}
            },
        )
        return BitaxeBonanzaDevice(
            config,
            project_dir=Path(directory),
            artifacts=artifacts,
            logger=logging.getLogger(name),
        )

    async def test_restart_wait_does_not_treat_transient_timeout_as_reboot(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifacts = TestArtifacts.create(Path(directory) / "case")
            device = self.make_device(
                directory, artifacts, name="test-delayed-restart"
            )
            fake_api = DelayedRestartApi()
            device.api = fake_api  # type: ignore[assignment]

            await device._restart_and_wait(expected={"stratumURL": "old.pool"})

            self.assertTrue(fake_api.rebooted)
            self.assertIsNotNone(fake_api.restart_task)

    def test_sv1_restart_expectation_ignores_sv2_only_aliases(self) -> None:
        fake_api = FakePoolsApi()

        expected = BitaxeBonanzaDevice._pool_expected_settings(
            fake_api.info["pools"], fake_api.info["primaryPoolIndex"]
        )

        self.assertEqual(expected["stratumProtocol"], "SV1")
        self.assertNotIn("stratumV2ChannelType", expected)
        self.assertNotIn("stratumV2AuthorityPubkey", expected)
        self.assertNotIn("stratumV2RequireAuth", expected)

    def test_restart_expectation_falls_back_to_primary_pool_fields(self) -> None:
        fake_api = FakePoolsApi()
        fake_api.info["pools"][0]["stratumV2RequireAuth"] = True
        fake_api.info.pop("stratumV2RequireAuth")

        self.assertTrue(
            BitaxeBonanzaDevice._settings_match(
                fake_api.info,
                {"stratumV2RequireAuth": True},
            )
        )

    async def test_rejects_redacted_identity_in_device_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifacts = TestArtifacts.create(Path(directory) / "case")
            device = self.make_device(
                directory, artifacts, name="test-redacted-device-baseline"
            )
            fake_api = FakePoolsApi()
            fake_api.info["pools"][0]["stratumUser"] = "<redacted-pool-identity>"
            device.api = fake_api  # type: ignore[assignment]

            with self.assertRaisesRegex(DeviceError, "redaction marker"):
                await device.snapshot_clean_state()

            self.assertEqual(fake_api.patches, [])

    async def test_rejects_redacted_identity_before_pool_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifacts = TestArtifacts.create(Path(directory) / "case")
            device = self.make_device(
                directory, artifacts, name="test-redacted-pool-write"
            )
            fake_api = FakePoolsApi()
            device.api = fake_api  # type: ignore[assignment]

            for marker in ("<redacted>", "<redacted-pool-identity>"):
                with self.subTest(marker=marker):
                    with self.assertRaisesRegex(DeviceError, "redaction marker"):
                        await device.configure_pool(
                            PoolSettings(
                                host="new.pool",
                                port=5555,
                                username=marker,
                            )
                        )

            self.assertEqual(fake_api.patches, [])

    async def test_rejects_redacted_identity_before_restore_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifacts = TestArtifacts.create(Path(directory) / "case")
            device = self.make_device(
                directory, artifacts, name="test-redacted-pool-restore"
            )
            fake_api = FakePoolsApi()
            device.api = fake_api  # type: ignore[assignment]
            baseline = await device.snapshot_clean_state()
            baseline.settings["pools"][0]["stratumUser"] = (  # type: ignore[index]
                "<redacted-pool-identity>"
            )

            with self.assertRaisesRegex(DeviceError, "redaction marker"):
                await device.restore_clean_state(baseline)

            self.assertEqual(fake_api.patches, [])

    async def test_new_pool_schema_is_configured_and_fully_restored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = DeviceConfig(
                name="fake-bonanza",
                type="bitaxe_bonanza",
                interfaces={
                    "api": {"base_url": "http://127.0.0.1", "online_timeout": 2}
                },
            )
            artifacts = TestArtifacts.create(Path(directory) / "case")
            device = BitaxeBonanzaDevice(
                config,
                project_dir=Path(directory),
                artifacts=artifacts,
                logger=logging.getLogger("test-bonanza-pool-schema"),
            )
            fake_api = FakePoolsApi()
            device.api = fake_api  # type: ignore[assignment]

            baseline = await device.snapshot_clean_state()
            await device.configure_pool(
                PoolSettings(
                    host="new.pool",
                    port=5555,
                    username="new.worker",
                    protocol="SV2",
                    sv2_channel_type="standard",
                    sv2_authority_pubkey="ephemeral-authority-key",
                    sv2_require_auth=True,
                )
            )

            self.assertEqual(set(fake_api.patches[0]), {"pools"})
            configured = fake_api.patches[0]["pools"][0]
            self.assertEqual(configured["id"], 0)
            self.assertEqual(configured["stratumURL"], "new.pool")
            self.assertEqual(configured["stratumPort"], 5555)
            self.assertEqual(configured["stratumPassword"], "*****")
            self.assertEqual(configured["stratumProtocol"], "SV2")
            self.assertEqual(configured["stratumV2ChannelType"], "standard")
            self.assertEqual(
                configured["stratumV2AuthorityPubkey"], "ephemeral-authority-key"
            )
            self.assertTrue(configured["stratumV2RequireAuth"])
            self.assertEqual(fake_api.info["stratumURL"], "new.pool")
            self.assertEqual(fake_api.info["stratumPort"], 5555)

            await device.restore_clean_state(baseline)

            restored = fake_api.patches[-1]["pools"]
            self.assertEqual(len(restored), 2)
            self.assertEqual(restored[0]["stratumURL"], "old.pool")
            self.assertEqual(restored[0]["stratumPort"], 3333)
            self.assertEqual(restored[0]["stratumProtocol"], "SV1")
            self.assertEqual(restored[0]["stratumV2ChannelType"], "extended")
            self.assertEqual(
                restored[0]["stratumV2AuthorityPubkey"], "old-primary-authority"
            )
            self.assertFalse(restored[0]["stratumV2RequireAuth"])
            self.assertEqual(restored[1]["stratumURL"], "backup.pool")
            self.assertEqual(fake_api.info["stratumURL"], "old.pool")
            self.assertEqual(fake_api.info["stratumPort"], 3333)
            self.assertEqual(fake_api.info["primaryPoolIndex"], 0)
            self.assertEqual(fake_api.info["secondaryPoolIndex"], 1)
            self.assertTrue(fake_api.info["useFallbackStratum"])

            baseline_artifact = (artifacts.path / "baseline.json").read_text()
            self.assertNotIn("old.worker", baseline_artifact)
            self.assertNotIn("backup.worker", baseline_artifact)
            self.assertNotIn("old-primary-authority", baseline_artifact)
            self.assertNotIn("old-backup-authority", baseline_artifact)

    async def test_flat_pool_schema_configures_sv2_and_restores_all_fields(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifacts = TestArtifacts.create(Path(directory) / "case")
            device = self.make_device(directory, artifacts, name="test-flat-sv2")
            fake_api = FakeApi()
            device.api = fake_api  # type: ignore[assignment]

            baseline = await device.snapshot_clean_state()
            baseline_artifact = (artifacts.path / "baseline.json").read_text()
            self.assertNotIn("old-authority-key", baseline_artifact)
            await device.configure_pool(
                PoolSettings(
                    host="sv2.pool",
                    port=3336,
                    username="sv2.worker",
                    protocol="sv2",
                    sv2_channel_type="standard",
                    sv2_authority_pubkey="ephemeral-authority-key",
                    sv2_require_auth=True,
                )
            )

            configured = fake_api.patches[0]
            self.assertEqual(configured["stratumProtocol"], "SV2")
            self.assertEqual(configured["stratumV2ChannelType"], "standard")
            self.assertEqual(
                configured["stratumV2AuthorityPubkey"], "ephemeral-authority-key"
            )
            self.assertTrue(configured["stratumV2RequireAuth"])

            await device.restore_clean_state(baseline)

            restored = fake_api.patches[-1]
            self.assertEqual(restored["stratumProtocol"], "SV1")
            self.assertEqual(restored["stratumV2ChannelType"], "extended")
            self.assertEqual(
                restored["stratumV2AuthorityPubkey"], "old-authority-key"
            )
            self.assertFalse(restored["stratumV2RequireAuth"])

    async def test_pool_protocol_validation_happens_without_api_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifacts = TestArtifacts.create(Path(directory) / "case")
            device = self.make_device(directory, artifacts, name="test-sv2-validation")
            fake_api = FakeApi()
            device.api = fake_api  # type: ignore[assignment]

            invalid = (
                PoolSettings("pool", 3333, "worker", protocol="SV3"),
                PoolSettings(
                    "pool",
                    3333,
                    "worker",
                    protocol="SV2",
                    sv2_channel_type="group",
                ),
                PoolSettings(
                    "pool",
                    3333,
                    "worker",
                    protocol="SV1",
                    sv2_channel_type="standard",
                ),
            )
            for settings in invalid:
                with self.subTest(settings=settings), self.assertRaises(DeviceError):
                    await device.configure_pool(settings)

            self.assertEqual(fake_api.patches, [])

    async def test_restores_write_only_password_from_environment_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            os.environ["TEST_BASELINE_POOL_PASSWORD"] = "original-secret"
            self.addCleanup(os.environ.pop, "TEST_BASELINE_POOL_PASSWORD", None)
            config = DeviceConfig(
                name="fake-bonanza",
                type="bitaxe_bonanza",
                interfaces={"api": {"base_url": "http://127.0.0.1", "online_timeout": 2}},
                options={
                    "baseline_stratum_password_env": "TEST_BASELINE_POOL_PASSWORD"
                },
            )
            artifacts = TestArtifacts.create(Path(directory) / "case")
            device = BitaxeBonanzaDevice(
                config,
                project_dir=Path(directory),
                artifacts=artifacts,
                logger=logging.getLogger("test-bonanza-lifecycle"),
            )
            fake_api = FakeApi()
            device.api = fake_api  # type: ignore[assignment]

            baseline = await device.snapshot_clean_state()
            await device.configure_pool(
                PoolSettings(
                    host="new.pool",
                    port=4444,
                    username="new.worker",
                    password="test-secret",
                )
            )
            await device.restore_clean_state(baseline)

            self.assertEqual(fake_api.patches[0]["stratumPassword"], "test-secret")
            self.assertEqual(fake_api.patches[-1]["stratumPassword"], "original-secret")
            self.assertEqual(fake_api.info["stratumURL"], "old.pool")
            baseline_artifact = (artifacts.path / "baseline.json").read_text()
            self.assertNotIn("original-secret", baseline_artifact)
            self.assertNotIn("old.worker", baseline_artifact)


class RestartReadinessTest(unittest.IsolatedAsyncioTestCase):
    make_device = BonanzaLifecycleTest.make_device

    async def test_restore_never_resumes_faulted_or_starting_device(self):
        class NoWriteApi(FakeApi):
            async def post_json(self, path, value=None):
                raise AssertionError("Must not resume a faulted or starting device")

        for lifecycle, fault, overheat in (
            ("FAULT", 4103, False),
            ("FAULT", 0, False),
            ("MINING", 0, True),
            ("STARTING", 0, False),
        ):
            with self.subTest(lifecycle=lifecycle, fault=fault, overheat=overheat):
                with tempfile.TemporaryDirectory() as directory:
                    device = self.make_device(
                        directory,
                        TestArtifacts.create(Path(directory) / "case"),
                        name="unsafe-resume",
                    )
                    device.api = NoWriteApi()
                    baseline = await device.snapshot_clean_state()
                    device.api.info.update(
                        miningPaused=True,
                        overheat_mode=overheat,
                        asicHealth={"lifecycle": lifecycle, "lastFaultCode": fault},
                    )
                    with self.assertRaisesRegex(DeviceError, "safety fault|still starting"):
                        await device.restore_clean_state(baseline)
                    self.assertEqual(device.api.patches, [])

    async def test_restore_waits_for_staged_boot_without_resuming_it(self):
        class StagedApi(FakeApi):
            def __init__(self):
                super().__init__()
                self.remaining = 0
                self.posts = []

            async def post_json(self, path, value=None):
                self.posts.append(path)
                if path != "/api/system/restart":
                    raise AssertionError("Must not resume an in-progress staged boot")
                self.info["uptimeSeconds"] = 0
                self.remaining = 2
                return b"{}"

            async def get_json(self, path):
                if self.remaining:
                    self.remaining -= 1
                    self.info["miningPaused"] = True
                    self.info["asicHealth"]["lifecycle"] = "STARTING"
                else:
                    self.info["miningPaused"] = False
                    self.info["asicHealth"]["lifecycle"] = "MINING"
                return await super().get_json(path)

        with tempfile.TemporaryDirectory() as directory:
            device = self.make_device(directory, TestArtifacts.create(Path(directory)/"case"), name="staged-restart")
            device.api = StagedApi()
            baseline = await device.snapshot_clean_state()
            device.api.info["stratumURL"] = "temporary.pool"
            await device.restore_clean_state(baseline)
            self.assertEqual(device.api.posts, ["/api/system/restart"])
            self.assertEqual(device.api.info["stratumURL"], "old.pool")
            self.assertFalse(device.api.info["miningPaused"])

    async def test_restart_safety_fault_fails_before_resume(self):
        class FaultApi(FakeApi):
            async def post_json(self, path, value=None):
                if path != "/api/system/restart":
                    raise AssertionError("Must not resume a faulted device")
                self.info["asicHealth"]["lastFaultCode"] = 42
                return await super().post_json(path, value)

        with tempfile.TemporaryDirectory() as directory:
            device = self.make_device(directory, TestArtifacts.create(Path(directory)/"case"), name="faulted-restart")
            device.api = FaultApi()
            await device.current_info()
            with self.assertRaisesRegex(DeviceError, "safety fault"):
                await device._restart_and_wait(expected={})

    async def test_ota_waits_for_staged_boot_before_baseline(self):
        class UpgradeApi(FakeApi):
            def __init__(self):
                super().__init__()
                self.info["uptimeSeconds"] = 0
                self.remaining = 2

            async def get_json(self, path):
                starting = self.remaining > 0
                self.remaining -= 1
                self.info["asicHealth"]["lifecycle"] = "STARTING" if starting else "MINING"
                self.info["miningPaused"] = starting
                return await super().get_json(path)

        with tempfile.TemporaryDirectory() as directory:
            device = self.make_device(directory, TestArtifacts.create(Path(directory)/"case"), name="staged-ota")
            device.api = UpgradeApi()
            device.online_timeout = 4
            info = await device._wait_after_upgrade(100)
            self.assertEqual(info["asicHealth"]["lifecycle"], "MINING")
            self.assertFalse(info["miningPaused"])
