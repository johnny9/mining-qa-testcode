from __future__ import annotations

import unittest
from types import SimpleNamespace

from miner_testcode.testcase import MinerTestCase, validation_test


class ValidationTestSelectionTest(unittest.TestCase):
    def test_skips_unselected_pr_and_runs_selected_pr(self) -> None:
        class ValidationSelectionCase(MinerTestCase):
            @validation_test(1849, 1900)
            def test_related_prs(self) -> None:
                pass

        case = ValidationSelectionCase("test_related_prs")
        case._context = SimpleNamespace(validation_prs=frozenset())  # type: ignore[assignment]
        with self.assertRaisesRegex(unittest.SkipTest, "#1849, #1900"):
            case.setUp()

        case._context = SimpleNamespace(  # type: ignore[assignment]
            validation_prs=frozenset({1900})
        )
        case.setUp()

    def test_rejects_invalid_pr_declarations(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integer"):
            validation_test()
        with self.assertRaisesRegex(ValueError, "positive integer"):
            validation_test(0)

    def test_pr_1897_stratum_cases_remain_opt_in(self) -> None:
        from tests.e2e.test_stratum_v1_regression import StratumV1RegressionTest

        names = (
            "test_92_version_rolling_requires_accepted_configure",
            "test_93_zero_length_extranonce2_produces_work",
            "test_94_healthy_client_reconnects_reset_retry_history",
            "test_95_oversized_jobs_are_rejected_without_state_change",
            "test_96_burst_keeps_latest_clean_job_valid",
        )
        for name in names:
            with self.subTest(name=name):
                method = getattr(StratumV1RegressionTest, name)
                self.assertEqual(method.validation_prs, frozenset({1897}))


if __name__ == "__main__":
    unittest.main()


class StratumTimestampTest(unittest.TestCase):
    def make_case(self, allowance):
        from tests.e2e.test_stratum_v1_regression import StratumV1RegressionTest
        case = StratumV1RegressionTest("_class_fixture")
        case.settings_for = lambda name: {"max_ntime_roll_seconds": allowance}
        return case

    def test_timestamp_rolling_is_opt_in_and_bounded(self):
        self.make_case(0)._assert_submission_ntime("60000000", "60000000")
        with self.assertRaises(AssertionError):
            self.make_case(0)._assert_submission_ntime("60000001", "60000000")
        case = self.make_case(60)
        case._assert_submission_ntime("60000001", "60000000")
        case._assert_submission_ntime("6000003c", "60000000")
        for invalid in ("5fffffff", "6000003d", "6000000z", "600000000"):
            with self.subTest(invalid=invalid), self.assertRaises(AssertionError):
                case._assert_submission_ntime(invalid, "60000000")

    def test_invalid_rolling_bounds_fail_configuration(self):
        for invalid in (True, -1, 121, "60", 1.5):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.make_case(invalid)._max_ntime_roll_seconds()


class OversizedNotificationTest(unittest.IsolatedAsyncioTestCase):
    async def test_malformed_id_reaches_wire_without_relaxing_valid_job_bounds(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from miner_testcode.interfaces.fake_stratum import FakeStratumV1Server
        from tests.e2e.test_stratum_v1_regression import StratumV1RegressionTest

        case = StratumV1RegressionTest("_class_fixture")
        case.device = SimpleNamespace(current_info=AsyncMock(return_value={"workReceived": 1}))
        case.logger = SimpleNamespace(info=lambda *args: None)
        case._processing_barrier = AsyncMock()
        case._mine_one_share = AsyncMock()
        server = AsyncMock(spec=FakeStratumV1Server)
        server.requests = []
        server.extranonce1 = "01020304050607"
        server.extranonce2_size = 8
        await case._case_95_oversized_jobs_are_rejected_without_state_change(
            server, SimpleNamespace(connection_id=7), {})
        self.assertEqual(server.send_json.await_count, 3)
        first = server.send_json.await_args_list[0]
        self.assertEqual(first.args[0]["method"], "mining.notify")
        self.assertEqual(first.args[0]["params"][0], "j" * 512)
        self.assertEqual(first.kwargs["session"], 7)
        self.assertEqual(case._mine_one_share.await_count, 4)
        final_job = case._mine_one_share.await_args.args[1]
        self.assertEqual(final_job.job_id, "large-valid-suffix")
