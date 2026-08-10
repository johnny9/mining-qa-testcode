---
name: run-mining-device-test
description: Preflight, execute, monitor, and verify an authorized mining-qa-testcode hardware test against one or more configured local devices. Use when a user wants to run a local smoke, regression, validation-PR, read-only, firmware-upgrade, or other E2E mining-device test and needs exact selection, safety checks, cleanup verification, artifact review, or publication-status reporting.
---

# Run a mining device test

Run the narrowest intended test and prove the final device state. Adapt to the
profile, registered adapter, and discovered tests; do not assume a device model
or test module.

## Establish authorization and scope

Identify the local profile, device names, test pattern, validation PRs, artifact
handoff, and intended publisher destinations. A request to run a test authorizes
the hardware actions already made explicit in that profile, but not an
unmentioned firmware change, different device, different test, or new remote
publication destination.

If no valid profile exists, use `$configure-mining-test-device`. If required
firmware artifacts are missing or lack immutable provenance, use
`$build-github-test-artifact` before proceeding.

## Preflight before hardware creation

1. Read `AGENTS.md`, the selected profile without exposing resolved secrets,
   the matching test module, adapter, and relevant current specs.
2. Resolve testcode provenance and record the current commit/dirty state. Remote
   publication requires published, exact testcode provenance.
3. Confirm the physical target's current identity and firmware with safe reads.
   Confirm stable serial resolution and permissions when serial is required.
4. Confirm required environment variables are set without printing values.
5. For upgrades, recheck every path, role, SHA-256, expected version, target
   identity, method, and recovery plan against the artifact handoff.
6. For mutable tests, capture the operator-visible pool, pause/mining state, and
   other adapter-owned mutable baseline independently. Never derive restore
   input from redacted artifacts.
7. Confirm the device can reach any configured local server and that ports are
   available.
8. State remote publisher side effects before execution. Use a local-only
   profile when the requested run is local-only; do not silently publish.

Stop before writes when identity, artifact role, baseline, credentials,
recovery, or authorization is ambiguous.

## Execute the narrow command

Prefer the installed repository environment:

```bash
.venv/bin/miner-test --config <local-toml> --device <name> --pattern '<test-file>'
```

Add repeatable `--validation-pr <number>` only for explicitly intended opt-in
cases. Without installation, use:

```bash
PYTHONPATH=src python3 -m miner_testcode --config <local-toml> \
  --device <name> --pattern '<test-file>'
```

Do not broaden a narrow request to every enabled device or every test. Stream
progress and preserve the run directory on failure. Do not retry uncertain
writes or flash operations automatically.

Interpret exit status precisely:

- `0`: tests and all required publishers succeeded.
- `1`: executed tests, cleanup, or required publishing was unsuccessful.
- `2`: configuration or local I/O failed before a valid run completed.

An exit status alone does not prove cleanup or healthy mining.

## Verify after the runner exits

1. Locate the exact timestamped artifact directory and inspect `result.json`,
   `runner.log`, per-test logs, telemetry/state, serial evidence, and publisher
   records as applicable.
2. Re-read the live device independently. Compare identity, pool settings,
   pause state, mining state, and other mutable fields to the preflight
   baseline. Treat cleanup mismatch as failure even if assertions passed.
3. Confirm the device is online and reaches the expected steady state. Do not
   claim accepted shares, hashrate stability, serial capture, or recovery unless
   evidence shows it.
4. Remember that target firmware persists by design; distinguish restored
   mutable settings from firmware rollback.
5. Check published output for private hostnames, addresses, pool identities,
   credentials, absolute paths, or other leaked local data. Never paste secrets
   into the report.
6. For remote publishers, verify the returned result/check URL and whether
   artifact upload completed. Distinguish local test success from publication
   success.

## Report the result

Lead with pass, fail, or blocked and include:

- Exact command, testcode repository/SHA, target publication label, firmware
  version, artifact SHA(s), selected test/PR cases, and elapsed time.
- Counts for run, pass, failure, error, and skip, plus required publisher state.
- Artifact directory and remote result links when publication was authorized.
- Independent cleanup comparison and final mining/device health.
- Any unverified physical behavior, recovery action, privacy concern, or next
  narrow diagnostic step.

Never claim a build, HIL run, publication, or restoration that was not actually
performed and observed.
