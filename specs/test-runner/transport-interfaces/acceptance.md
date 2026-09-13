# Transport interfaces — acceptance

## Functional behavior

- [x] **TR-IO-AC-01:** Read-only mode blocks HTTP writes before opening a
  connection.
- [x] **TR-IO-AC-02:** HTTP reads retry only transient transport failures;
  writes and uploads execute at most once automatically.
- [x] **TR-IO-AC-03:** Stratum probe subscribes, authorizes, and receives at
  least the configured number of jobs within a bound.
- [x] **TR-IO-AC-04:** WebSocket updates can merge into native state while an
  outage permits REST fallback.

## Interfaces and compatibility

- [x] **TR-IO-AC-05:** HTTP traces contain method/path/status/timing/size/error
  metadata and no bodies.
- [x] **TR-IO-AC-06:** Serial flash commands remain shell-free and resolve named
  artifact/port placeholders.

## Quality attributes

- [x] **TR-IO-AC-07:** Responses, messages, logs, retries, and timeouts are
  bounded and invalid limits fail configuration.
- [ ] **TR-IO-AC-08:** Current target validation confirms the configured stable
  serial path, permissions, capture, and recovery through a real reboot.

- [x] **TR-IO-AC-09:** Omitted or explicitly disabled serial permits a
  network-only lifecycle without serial construction or USB capabilities;
  legacy serial tables remain enabled and USB upgrades fail while disabled.

## Verification evidence

- `tests.unit.test_network_only` — disabled/omitted serial lifecycle, capability
  exclusion, USB upgrade rejection, legacy compatibility, and invalid option;
  reconciled 2026-09-13.

- `tests.unit.test_api` — read-only transport boundary; reconciled 2026-08-10.
- `tests.unit.test_stratum` — real loopback Stratum handshake/job behavior;
  reconciled 2026-08-10.
- `tests.unit.test_fake_stratum_v2` — official-vector crypto compatibility and
  bounded authenticated loopback framing, channel, job, share, rejection,
  reconnect, malformed-input, privacy, and shutdown behavior; reconciled
  2026-09-04.
- `tests.unit.test_bitaxe_state` — WebSocket diff and fallback normalization;
  reconciled 2026-08-10.
- Live serial criterion is unchecked for this documentation iteration.

## Acceptance rule

Transport changes are acceptable only with explicit bounds, timeout and retry
semantics, body/secret-free evidence, negative error tests, and a clear report
of any unperformed live-interface validation.
