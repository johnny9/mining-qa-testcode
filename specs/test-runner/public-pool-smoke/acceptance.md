# Public pool smoke — acceptance

## Functional behavior

- [x] **TR-POOL-SMOKE-AC-01:** The independent probe completes subscribe,
  authorize, and configured job reception within a timeout.
- [x] **TR-POOL-SMOKE-AC-02:** Observational mode verifies existing host/port
  and performs no device write.
- [x] **TR-POOL-SMOKE-AC-03:** Reconfiguration mode applies the configured
  host and port through adapter cleanup, preserves the device's current pool
  username when no replacement is supplied, and refuses unsafe write-only
  password mutation.
- [x] **TR-POOL-SMOKE-AC-04:** Share acceptance is recorded when available but
  is optional by default.

## Interfaces and compatibility

- [x] **TR-POOL-SMOKE-AC-05:** Pool/probe identities and passwords remain
  redacted from published evidence.
- [x] **TR-POOL-SMOKE-AC-06:** Stable-window criteria use normalized portable
  state rather than a model-specific lifecycle label.

## Quality attributes

- [x] **TR-POOL-SMOKE-AC-07:** Probe, readiness, work age, sample count, and
  cleanup are bounded.
- [x] **TR-POOL-SMOKE-AC-08:** A current authorized end-to-end run proves live
  public job reception, stable healthy device mining, and original pool restore.

## Verification evidence

- `tests.unit.test_stratum` — independent probe handshake/job protocol;
  reconciled 2026-08-10.
- `tests.unit.test_public_pool_smoke` covers explicit, environment, current
  device, and disposable probe identity selection; reconciled 2026-08-10.
- `tests.unit.test_bonanza_lifecycle` covers host/port configuration and full
  pool restoration; reconciled 2026-08-10.
- Authorized Bitaxe Gamma 602 HIL on firmware `f711cad` repaired a stale device
  port to the intended `public-pool.io:3333` baseline. The follow-up smoke
  received a Stratum job, observed stable healthy mining, retained port `3333`
  through cleanup, and passed independent post-cleanup state and
  artifact-privacy checks; run 2026-08-10.

## Acceptance rule

Protocol-only work may be accepted with loopback tests, but changes to device
reconfiguration or live health criteria require explicit target HIL and verified
post-test restoration before claiming end-to-end acceptance.
