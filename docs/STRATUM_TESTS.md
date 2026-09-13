# Stratum test guide

`mining-qa-testcode` provides public-pool Stratum V1 coverage and local
Stratum V1/V2 regression suites:

- the public-pool smoke test checks normal mining against a real pool;
- the local regression suite checks the miner's Stratum client with a fake pool
  on the test host.

All suites collect device state, telemetry, logs, and share evidence. USB is
optional: omit `devices.interfaces.serial` or set its `enabled = false` for a
network-only run. HTTP controls the miner, WebSocket/HTTP supplies telemetry,
and the miner connects directly to the test host's Stratum TCP listeners.

## Public-pool smoke test

Configure the pool and the test identity:

```toml
[tests.public_pool_smoke]
host = "public-pool.io"
port = 3333
username_env = "MINER_TEST_POOL_USER"
configure_device = true
```

Set the username without putting it in the file:

```bash
export MINER_TEST_POOL_USER='your-test-identity'
```

The test opens its own Stratum connection to check the pool handshake. At the
same time, it watches the mining device over its configured interfaces and
captures the ESP serial log when serial is enabled.

With `configure_device = true`, the configured host and port are applied to the
miner. If no replacement username is supplied, the miner keeps its current
pool username. A separate `probe_username` remains probe-only.

Run only this test:

```bash
miner-test --config config.local.toml \
  --pattern 'test_public_pool_smoke.py'
```

For a read-only run, set `configure_device = false`. The device must already
point to the configured host and port.

## Local Stratum V1 regression suite

The local suite starts a fake pool on the computer running `miner-test`. The
mining device must be able to connect to that computer over the LAN.

```toml
[tests.stratum_v1_regression]
advertised_host = "192.168.1.10"
bind_host = "0.0.0.0"
port = 0
allow_existing_device_password = false
share_difficulty = 256
changed_difficulty = 512
```

- `advertised_host` is the test computer's address as seen by the miner.
- `bind_host` selects the local interfaces on which the fake pool listens.
- `port = 0` asks the operating system to choose an available port.
- the two difficulty values are used before and after a difficulty-change
  check.

Run only the regression module:

```bash
miner-test --config config.local.toml \
  --pattern 'test_stratum_v1_regression.py'
```

This suite changes the device's pool settings and restarts it. The adapter
cannot be read-only. The runner saves the old settings first and restores them
when the suite ends.

### Password choices

The safest setup uses a temporary password supplied through
`temporary_password_env`. Also set
`devices.options.baseline_stratum_password_env` so the original write-only
password can be restored.

`allow_existing_device_password = true` lets the test reuse the current
device password. Use this only on a trusted test host and LAN. The value is an
explicit opt-in because the local fake pool receives that password during
authorization.

Passwords and raw authorization lines are removed from saved fake-pool
transcripts.

## What the regression checks

The normal suite reports separate checks for:

1. Stratum capability negotiation;
2. subscription;
3. authorization;
4. new work and a submitted share;
5. a difficulty change followed by fresh work.

The suite stops later protocol checks after the first failure. It still closes
the fake server and restores the device.

Additional parser-hardening cases are kept as optional pull-request validation.
They cover input fragmentation, consecutive messages, size boundaries, invalid
field types, invalid hex, invalid difficulty, and unsafe extranonce lengths.

Enable the cases for a target firmware pull request:

```bash
miner-test --config config.local.toml --validation-pr 1849
```

Cases that were not selected are reported as neutral skips.

## Use the fake pool from another test

Advanced tests may drive the fake pool directly:

```python
from miner_testcode.interfaces.fake_stratum import FakeStratumV1Server, MiningJob

async with FakeStratumV1Server(host="0.0.0.0") as pool:
    handshake = await pool.wait_for_handshake(require_configure=True)
    job = MiningJob.standard("regression-1")
    await pool.send_job(job, difficulty=256, session=handshake.connection_id)
    share = await pool.wait_for_submission(job_id=job.job_id, timeout=45)
```

Use `send_json()` for one message, `send_batch()` for several messages in one
write, and `send_raw()` for controlled framing input. The wait methods provide
synchronization without adding arbitrary sleeps.

Each run saves a redacted `fake-stratum.jsonl`.

## Local Stratum V2 regression suite

The V2 suite follows the same lifecycle as the V1 suite, but starts an
encrypted binary fake pool. It creates an ephemeral authority key and
certificate for the run and configures the miner to authenticate that key.
No pool password is needed or changed.

```toml
[tests.stratum_v2_regression]
advertised_host = "192.168.1.10"
bind_host = "0.0.0.0"
port = 0
username = "stratum-v2-regression.worker"
channel_type = "extended"
share_difficulty = 256
changed_difficulty = 512
```

Use `channel_type = "standard"` to exercise a standard mining channel. Run
only this module with:

```bash
miner-test --config config.local.toml \
  --pattern 'test_stratum_v2_regression.py'
```

The ordered checks cover the authenticated Noise handshake,
`SetupConnection`, channel opening, future-job activation, accepted and
rejected submissions, a target change, and a fresh authenticated connection
after the server disconnects the miner. The runner restores the captured V1
or V2 protocol, channel, authority, and authentication fields during cleanup.

Each run saves `fake-stratum-v2.jsonl`. The bounded transcript records decoded
message metadata but redacts endpoint coordinates, device identifiers, and
mining identities; it never contains traffic ciphertext or private keys.

## Add chart markers

A test can mark an important point in the telemetry charts:

```python
self.chart("Healthy mining and fresh pool work observed", status="good")
```

Use `status="good"` for a successful milestone and `status="bad"` for a
failure. Leave it out for a neutral information marker.

The runner also adds a final outcome marker for each test. Marker text is
sanitized before publication. Offline periods are stored as gaps, so charts do
not show invented zero values or connect lines across an outage.
