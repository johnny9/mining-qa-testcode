# Result model and publishing — acceptance

## Functional behavior

- [x] **TR-RESULTS-AC-01:** Native unittest outcomes and cleanup/infrastructure
  failures are represented without loss in the run summary.
- [x] **TR-RESULTS-AC-02:** Canonical local JSON and HTML are written even when
  remote publication fails.
- [x] **TR-RESULTS-AC-03:** Each publisher records its own status and required
  publishers affect final exit status while best-effort publishers do not.
- [x] **TR-RESULTS-AC-04:** An orchestrated run atomically writes a bounded
  contract-v1 child-result pointer with correlation and published child
  identity/link.

## Interfaces and compatibility

- [x] **TR-RESULTS-AC-05:** Publisher payloads use sanitized artifacts and
  direct uploads obey the server-issued target contract.
- [x] **TR-RESULTS-AC-06:** The runner never publishes aggregate parent-gate
  state.

## Quality attributes

- [x] **TR-RESULTS-AC-07:** Unit tests cover serialization, publisher success,
  timeout/error, required policy, and result-pointer behavior.
- [ ] **TR-RESULTS-AC-08:** Current staging/live publication has been verified
  end to end for every enabled remote backend.

## Verification evidence

- `tests.unit.test_publishers`, `tests.unit.test_runner`, and
  `tests.unit.test_config` cover the result model, local output, remote
  publishers, atomic 64-KiB-bounded contract-v1 pointer, legacy-v1 metadata,
  and non-integer/unsupported version rejection;
  reconciled 2026-08-10.
- No live remote publisher verification was performed for this documentation
  iteration.

## Acceptance rule

Local model/publisher changes require focused unit tests and inspection of
generated JSON. Backend or pointer contract changes also require a compatible
consumer test; live claims require an explicitly recorded staging/live run.
