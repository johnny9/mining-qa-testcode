# Pool fallback regression — design

## Components and responsibilities

The E2E module (`tests/e2e/test_pool_fallback_regression.py`) owns scenarios;
`src/miner_testcode/pool_fallback.py` owns native indexed-pool
writes and removal; two fake SV1 endpoints provide work and submission evidence.
The normal runner retains identity, baseline, logs, telemetry, and publication.
`src/miner_testcode/pool_form.py` drives the real pool settings form and guards
browser writes so only disposable rows and submitted role indices reach the
device.

## Interfaces and contracts

### CLI

Use `--pattern test_pool_fallback_regression.py`. PR-specific settings coverage
uses the existing `--validation-pr 1957` or `--validation-pr 1962` selector.

### Configuration

`tests.pool_fallback_regression.enabled` defaults false. Bind and advertised
addresses, phase bounds, difficulty, and optional dashboard CDP URL come from
the ignored profile. Device options must explicitly allow writes. No new
orchestration fields are introduced.

`primary_port` and `fallback_port` default to zero (unused ports chosen by the
host); operators may supply two distinct fixed ports permitted by their host
firewall. The test does not change firewall rules.

The versioned module catalog registers `pool_fallback_regression` with the
existing coordinator capabilities `http` and `stratum-v1`. Its portable options
are integer `phase_timeout` (5–300), `share_difficulty` (1–65536),
`stable_seconds` (0–60, default 5), `transition_cycles` (2–5, default 3), and
`outage_seconds` (15–180, default 45). The stability window must be shorter
than the phase deadline. Zero disables the additional stability requirement.
Enablement, addresses, ports, browser attachment, and target identity remain
local profile settings; catalog selection does not authorize hardware writes.

### Environment

None required. New temporary slots omit passwords and use the firmware's
default disposable password; existing credentials remain untouched.

### Python API

The helper uses the adapter's serialized HTTP interface and live info reader.
It requires the ESP-Miner indexed pool API, detected before any write.

### HTTP or external protocols

Use `/api/system/info`, settings PATCH, and indexed-pool DELETE. Local SV1
endpoints automatically supply work after authorization. Optional browser
checks use an operator-started, loopback-only Chrome DevTools endpoint and the
existing `websockets` dependency; the module never starts a browser itself.

### Files, artifacts, payloads, and persistent state

Per-test phase observations and fake-pool transcripts are sanitized artifacts.
Baseline data stays in memory and is never read back from sanitized evidence.
Only three initially unused device pool slots and selection flags are mutated.
`pool-outage.jsonl` records loss of work and `pool-form.jsonl` records verified
browser saves and persistence. Browser input and raw intercepted bodies are
never artifacts.

## Contract constraints

### Required invariants

Every phase needs new work and accepted-share evidence, not merely an open
connection or a successful probe. Automatic recovery performs no selection
write. Settings-save validation permits a reconnect. Cleanup selects original
rows before deleting owned temporary rows and verifies the original table.
The stability window resets when selection or mining evidence stops matching;
it requires another job and additional accepted shares after the first match.

The browser case edits a worker and causes a secondary-role collision, saves,
then edits and causes the opposite primary-role collision in the same form
instance. It reloads, edits an idle row, saves again, and reloads to verify
persistence. The request guard preserves the form's submitted workers and
roles; it never repairs a regression by substituting the expected outcome.
It removes original rows, passwords, and dormant protocol defaults. Unexpected
role indices, changed original fields, changed temporary endpoints, malformed
bodies, and unrelated device writes are aborted before transmission. The
actual Save response and subsequent live API reads determine success.

### Forbidden behavior

Never overwrite original rows, write masked credentials, delete selected or
unowned rows, accept stale submissions, or report UI success without a browser.

## Data and state

Each native unittest case has an independent device lifecycle and temporary
pool allocation. Per-phase request and job cursors exclude stale evidence.

## Control and data flow

Validate config and baseline; start endpoints; register cleanup; create slots;
verify mining; drive endpoint outages and settings; verify each phase; restore
selection and delete slots before the generic lifecycle cleanup.

Independent full-outage cases keep both listeners down for the configured
duration and require observed loss of work before restoring only primary or
fallback. Repeated cycles require stability after every transition. The silent
case keeps established TCP connections open while withholding replies and
jobs; it restores replies even on a failed assertion before normal cleanup.

## Failure and recovery

Uncertain writes are not retried. IDs are owned before creation is attempted,
so partially successful setup is cleaned. Cleanup is bounded and errors are
reported even if the test body passed. Server shutdown and transcripts still
run after restore failure.

Failure to establish initial mining is a setup error, not a completed firmware
regression. Later phase deadline failures are assertions with phase evidence.

The target must initially be hashing. After restoring settings, cleanup requires
fresh accepted shares within 90 seconds. A work-receiving device still at zero
hashrate after 30 seconds may receive one adapter-verified restart; original
settings are reread throughout. Safety faults forbid that restart. Recovery
is recorded separately, and needing a restart leaves an error even if the
device returns healthy. The entire restoration remains inside the runner's
configured cleanup timeout.

## Compatibility and migration

Existing Stratum regression work is unchanged. The new module defaults off.
API-only runs remain supported when no dashboard browser is supplied.
The pool-form case skips before hardware setup without browser configuration.

## Resource and operational constraints

Phase deadlines (5–300 seconds), polling cadence (0.25–5 seconds), 16 KiB client
lines, at most 64 accepted connections, 20,000 client requests, and
4,096 jobs per endpoint bound execution and evidence. Bind to a trusted
reachable lab interface.
The browser guard allows at most 1,024 API requests and eight saves, 32 KiB
write bodies, eight pending commands, and 32 guard acknowledgements. CDP
messages retain the 64 KiB limit; commands and form waits are bounded.

## Relationships to other feature slices

- [Lifecycle and cleanup](../lifecycle-and-cleanup/SPEC.md): final restoration.
- [ESP-Miner device adapters](../esp-miner-device-adapters/SPEC.md): native API.
- [Stratum V1 regression](../stratum-v1-regression/SPEC.md): reusable fake pool.
- [Configuration and selection](../configuration-and-selection/SPEC.md): opt-in.
- [Module catalog](../module-catalog/SPEC.md): discovery and bounded portable options.
- [Artifacts, privacy, and provenance](../artifacts-privacy-and-provenance/SPEC.md): evidence.
- [Transport interfaces](../transport-interfaces/SPEC.md): bounded I/O.

## Verification approach

Fake-device negative/cleanup checks and loopback SV1 tests precede HIL. Compare
phase decisions against both reconnecting and probing simulations. Identify
Gamma firmware before mutation and independently check post-run restoration.
