# Mining QA mock device contract v1

This contract defines deterministic, loopback-only device simulation for local
component and three-project integration tests. `mining-qa-testcode` owns the
mock implementation because it owns device adapters, lifecycle, cleanup, and
protocol behavior. The Status-owned integration harness launches and controls
it but does not implement hardware semantics.

The mock is test infrastructure, never a production device emulator or HIL
substitute. It must refuse non-loopback binding unless a future change adds an
explicit isolated-network authorization model.

## Process interface

The implementation exposes an executable with this target interface:

```text
python -m miner_testcode.mock_device \
  --host 127.0.0.1 \
  --port 0 \
  --state-file /private/run/mock-east.json \
  --events-file /private/run/mock-east-events.jsonl
```

- `--host` must resolve to loopback. `--port 0` asks the OS for an available
  port; the selected base URL is written atomically to the state file.
- State and event paths must remain below the harness-owned temporary run
  directory and must not be symlinks.
- Startup must complete within 10 seconds. `SIGTERM` triggers bounded shutdown
  within 5 seconds. Exit is nonzero on invalid config, bind failure, state-file
  failure, or internal task failure.
- The HTTP request/response body limit is 64 KiB. The event ledger is capped at
  2,000 records and 2 MiB; exceeding either limit fails the scenario explicitly
  instead of silently dropping required evidence.

## Initial device model

Version 1 emulates one AxeOS-compatible Gamma 602 at the existing adapter
boundary:

```json
{
  "boardVersion": "602",
  "ASICModel": "BM1370",
  "version": "mock-1.0.0",
  "hashRate": 1000.0,
  "sharesAccepted": 0,
  "sharesRejected": 0,
  "stratumURL": "127.0.0.1",
  "stratumPort": 3333,
  "stratumUser": "integration.worker",
  "stratumProtocol": "SV1",
  "stratumTLS": 0,
  "stratumSuggestedDifficulty": 1,
  "miningPaused": false,
  "uptimeSeconds": 1,
  "smallCoreCount": 2040
}
```

The runner uses the real `bitaxe_602` adapter against this process. No special
mock adapter is selected in the full integration path. That exercises normal
identity, settings, restart, state, lifecycle, cleanup, artifact, and privacy
code.

## Device-facing API

The mock implements only the AxeOS subset required by the proof of concept:

| Method and path | Behavior |
|---|---|
| `GET /api/system/info` | Return the current device object and advance bounded uptime. |
| `PATCH /api/system` | Validate and atomically apply supported pool fields or `pools[]`; preserve masked passwords. |
| `POST /api/system/restart` | Enter `restarting`, apply pending settings, reset uptime, then return online after the configured delay. |
| `POST /api/system/pause` | Set `miningPaused=true` and `hashRate=0`. |
| `POST /api/system/resume` | Set `miningPaused=false` and restore configured running hashrate unless a fault is active. |
| `GET /api/system/logs` | Return a bounded synthetic log containing configured privacy canaries when requested. |
| `GET /api/ws/live` | Optional WebSocket stream of bounded AxeOS `update` events. |

Unknown device endpoints return `404`. OTA, factory reset, arbitrary command,
serial, and filesystem operations are unsupported in v1; attempts return `409
unsupported_operation` and are recorded as forbidden events. All writes record
the previous and next sanitized state. Request authorization values and pool
passwords are never recorded.

## Simulated miner and Stratum

After an accepted restart/resume with mining enabled, the mock behaves as a
minimal miner client:

1. Connect to the configured `stratumURL:stratumPort` only when the host is
   loopback or an explicitly supplied harness network alias.
2. Send bounded `mining.configure` when enabled, then `mining.subscribe` and
   `mining.authorize` using the configured synthetic identity.
3. Consume `mining.set_difficulty` and `mining.notify` from the existing
   `FakeStratumV1Server`.
4. Submit a deterministic share or remain silent according to the selected
   scenario.
5. Update accepted/rejected counters from the response and reconnect only
   under the bounded selected policy.

This client is deliberately small. It validates runner-to-device configuration
and device-to-fake-pool integration; it does not claim firmware conformance,
share correctness, hashrate accuracy, or real ASIC behavior.

## Harness control API

Control endpoints are served on the same loopback listener under `__mock` and
are never called by production runner code.

### Health and state

- `GET /__mock/v1/health` returns `200` with contract version, process state,
  and event sequence.
- `GET /__mock/v1/state` returns current sanitized device, lifecycle, selected
  scenario, active faults, and event sequence.
- `GET /__mock/v1/events?after={sequence}&limit={limit}` returns ordered events.
  `sequence` is a nonnegative integer; `limit` is 1–200.

### Reset and scenario selection

`POST /__mock/v1/reset` accepts:

```json
{
  "contract_version": 1,
  "baseline": "gamma-running",
  "scenario": "pass",
  "privacy_canaries": ["device-canary", "pool-canary", "/private/canary/path"]
}
```

Reset is rejected while a request is being mutated. It atomically restores the
named baseline, clears faults/counters/events, sets event sequence to zero, and
starts the requested scenario. There are at most 16 canaries, each 1–200
characters. Canaries are test-only values and never real credentials or
coordinates.

`PUT /__mock/v1/scenario` switches only before runner lifecycle start:

```json
{
  "contract_version": 1,
  "scenario": "cleanup-restore-mismatch",
  "transition_delay_ms": 50
}
```

`transition_delay_ms` is 0–2,000. Mid-run scenario replacement returns `409
scenario_active` so test timing cannot silently change.

## Required scenarios and fault states

| Scenario | Deterministic behavior | Expected runner effect |
|---|---|---|
| `pass` | Correct identity, online, pool change/restart succeeds, Stratum share accepted, cleanup restores baseline. | `passed` with verified restore. |
| `test-failure` | Device remains healthy but selected assertion receives a deterministic rejected share. | `failed`; cleanup still restores. |
| `identity-mismatch` | Return board `601` or ASIC `BZM`. | Error before the first device write. |
| `http-unavailable` | Bounded connection failures on configured reads. | Explicit device/infrastructure error and bounded timeout. |
| `malformed-info` | Return a bounded wrong-shape system object. | Validation error; never a pass. |
| `restart-never-returns` | Accept settings/restart, remain unavailable through timeout. | Cleanup/infrastructure error with bounded exit. |
| `cleanup-restore-rejected` | Permit test mutation, reject the restore PATCH. | Result `error`; cleanup failure visible. |
| `cleanup-restore-mismatch` | Accept restore but report different final pool/pause state. | Result `error`; final-state mismatch visible. |
| `stratum-disconnect` | Disconnect after authorize or work notification. | Deterministic failed/error protocol evidence. |
| `log-privacy-canary` | Emit all configured canaries in raw device logs. | Raw remains private; published sanitized log contains none. |

Only one primary scenario is active. Independent faults may be added through
`PUT /__mock/v1/faults` for a scenario that names them explicitly. Required
faults are `http_status`, `drop_connection`, `delay_ms`, `malformed_json`,
`reject_patch`, `ignore_patch`, `stay_offline_after_restart`, and
`stratum_disconnect_stage`. Each has a bounded count; a fault cannot remain
implicitly active after reset.

## Event ledger

Every record is one UTF-8 JSON line:

```json
{
  "sequence": 12,
  "at": "2026-08-14T12:00:30Z",
  "kind": "settings_patch",
  "request_id": "mock-request-0012",
  "detail": {
    "keys": ["stratumPort", "stratumURL", "stratumUser"]
  }
}
```

Allowed kinds include `started`, `info_read`, `settings_patch`, `restart`,
`offline`, `online`, `pause`, `resume`, `stratum_connect`,
`stratum_authorize`, `stratum_notify`, `stratum_submit`, `log_read`,
`fault_applied`, `unsupported_operation`, and `stopped`. Detail is an
allowlisted bounded object and cannot contain passwords, authorization headers,
raw URLs with credentials, or arbitrary request bodies.

The integration harness uses the ledger to prove ordering, no-write guards,
restart behavior, Stratum behavior, and cleanup. It does not infer device truth
from process logs.

## State machines

```text
process: starting -> ready -> stopping -> stopped
device:  online -> restarting -> offline -> online
mining:  running <-> paused
         running -> fault
         fault -> running       (only explicit reset/recovery)
```

Settings PATCH creates pending settings. Only successful restart commits them
for the flat AxeOS schema used in v1. Cleanup is verified from the final
`GET /api/system/info`, not from the presence of a PATCH event.

## Isolation and cleanup

- Bind only to loopback and use OS-assigned ports to avoid collision.
- Each Lab gets its own mock process, state file, event file, fake Stratum
  listener, synthetic pool identity, and temporary directory.
- No Docker socket, host device, USB/serial node, production profile, external
  network, or real credential is mounted or passed.
- Harness teardown sends `SIGTERM`, waits 5 seconds, records diagnostics, then
  may force-kill only the exact child PID it created.
- A scenario passes teardown only when the process stopped, listeners closed,
  no child process remains, and the temporary directory is either archived as
  declared evidence or removed.

Unit and local integration evidence from this contract must always be labeled
simulation. It never satisfies a HIL acceptance criterion.
