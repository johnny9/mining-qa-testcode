from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tests.e2e.test_public_pool_smoke import _resolve_pool_usernames


class PublicPoolSmokeConfigurationTest(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_reconfiguration_preserves_current_device_username(self) -> None:
        device_username, probe_username = _resolve_pool_usernames(
            {
                "username_env": "UNSET_POOL_USER",
                "probe_username": "disposable-probe.worker",
            },
            {"stratumUser": "existing-device.worker"},
            configure_device=True,
        )

        self.assertEqual(device_username, "existing-device.worker")
        self.assertEqual(probe_username, "disposable-probe.worker")

    @patch.dict(os.environ, {"TEST_POOL_USER": "configured-device.worker"}, clear=True)
    def test_configured_username_takes_precedence_over_device_state(self) -> None:
        device_username, probe_username = _resolve_pool_usernames(
            {
                "username_env": "TEST_POOL_USER",
                "probe_username": "disposable-probe.worker",
            },
            {"stratumUser": "existing-device.worker"},
            configure_device=True,
        )

        self.assertEqual(device_username, "configured-device.worker")
        self.assertEqual(probe_username, "disposable-probe.worker")

    @patch.dict(os.environ, {}, clear=True)
    def test_observational_mode_keeps_probe_username_fallback(self) -> None:
        device_username, probe_username = _resolve_pool_usernames(
            {
                "username_env": "UNSET_POOL_USER",
                "probe_username": "disposable-probe.worker",
            },
            {"stratumUser": "existing-device.worker"},
            configure_device=False,
        )

        self.assertEqual(device_username, "disposable-probe.worker")
        self.assertEqual(probe_username, "disposable-probe.worker")


if __name__ == "__main__":
    unittest.main()
