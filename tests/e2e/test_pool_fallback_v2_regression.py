from miner_testcode import capabilities as caps
from miner_testcode import pool_fallback_cases as cases
from miner_testcode.pool_fallback_v2 import WorkingV2Pool


class PoolFallbackV2StandardRegressionTest(cases.PoolFallbackCases):
    """Run every fallback scenario over authenticated SV2 standard channels."""
    settings_section = "pool_fallback_v2_regression"
    protocol = "SV2"
    channel_type = "standard"
    pool_type = WorkingV2Pool
    required_capabilities = frozenset({caps.API, caps.MINING_STATE, caps.POOL_CONFIG, caps.STRATUM_V2})


class PoolFallbackV2ExtendedRegressionTest(PoolFallbackV2StandardRegressionTest):
    """Run every fallback scenario over authenticated SV2 extended channels."""
    channel_type = "extended"
