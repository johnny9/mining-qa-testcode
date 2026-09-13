from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from miner_testcode import capabilities as caps
from miner_testcode.artifacts import TestArtifacts
from miner_testcode.config import DeviceConfig
from miner_testcode.devices.bitaxe_bonanza import BitaxeBonanzaDevice
from miner_testcode.errors import ConfigError, UpgradeError
from tests.unit.test_bonanza_lifecycle import FakeApi


class NetworkOnlyTest(unittest.IsolatedAsyncioTestCase):
    def make_device(self, directory, serial=None, upgrade=None):
        interfaces = {
            "api": {"base_url": "http://127.0.0.1"},
            "websocket": {"enabled": False},
        }
        if serial is not None:
            interfaces["serial"] = serial
        if upgrade is not None:
            interfaces["upgrade"] = upgrade
        device = BitaxeBonanzaDevice(
            DeviceConfig(name="network-test", type="bitaxe_bonanza", interfaces=interfaces),
            project_dir=Path(directory),
            artifacts=TestArtifacts.create(Path(directory) / "case"),
            logger=logging.getLogger("test-network-only"),
        )
        device.api = FakeApi()
        device.api.info["version"] = "old-version"
        return device

    async def test_network_lifecycle_never_constructs_serial(self):
        for serial in (None, {"enabled": False}, {
            "enabled": False, "required": True, "capture": True,
            "port": "/not/a/device", "flash_command": ["must-not-run"],
        }):
            with self.subTest(serial=serial), tempfile.TemporaryDirectory() as directory:
                with patch("miner_testcode.devices.bitaxe.EspSerialInterface") as constructor:
                    constructor.side_effect = AssertionError("network-only run touched serial")
                    device = self.make_device(directory, serial)
                    self.assertIsNone(device.serial)
                    self.assertNotIn(caps.SERIAL_LOG, device.capabilities)
                    self.assertNotIn(caps.USB_FLASH, device.capabilities)
                    self.assertIn(caps.OTA_UPGRADE, device.capabilities)
                    try:
                        await device.start()
                        baseline = await device.snapshot_clean_state()
                        await device.restore_clean_state(baseline)
                        self.assertEqual(device.api.patches, [])
                    finally:
                        await device.close()
                    constructor.assert_not_called()

    async def test_disabled_serial_rejects_usb_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            device = self.make_device(directory, {"enabled": False}, {
                "enabled": True, "method": "usb", "expected_version": "new-version",
            })
            with self.assertRaisesRegex(UpgradeError, "enabled.*serial"):
                await device.ensure_target_firmware()
            self.assertEqual(device.api.patches, [])

    async def test_legacy_serial_configuration_remains_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            device = self.make_device(directory, {
                "port": "/not/opened", "flash_command": ["flasher", "{port}"],
            })
            self.assertIsNotNone(device.serial)
            self.assertIn(caps.SERIAL_LOG, device.capabilities)
            self.assertIn(caps.USB_FLASH, device.capabilities)

    async def test_serial_enabled_must_be_boolean(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ConfigError, "serial.enabled.*boolean"):
                self.make_device(directory, {"enabled": "false"})
