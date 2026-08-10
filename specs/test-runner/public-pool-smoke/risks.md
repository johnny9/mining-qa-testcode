# Public pool smoke — risks and scope

## Scope

### In

- Independent public Stratum handshake/job evidence, optional device pool
  configuration, normalized stable mining window, and share observation.

### Out

- Pool SLA, payout/account correctness, hashrate benchmarking, and guaranteed
  share discovery.

## Assumptions

- The configured host permits the disposable/public probe identity.
- Device/pool work age and normalized state are sufficiently current.

## Open questions

- Additional pool protocols or authentication schemes need separate capability
  and privacy design.

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Public pool unavailable | False hardware suspicion | Independent probe failure | Report external dependency; retry only in a new run |
| Low difficulty/share randomness | No accepted share | Optional share policy | Require jobs and health, not share by default |
| Private identity published | Privacy loss | Redaction tests | Separate probe identity and final sanitation |
| Disposable probe identity written to device | Payouts use the wrong identity | Username-resolution regression | Preserve current device identity unless an explicit replacement is supplied |
| Temporary pool not restored | Mining redirected | Cleanup final-state check | Fail run and operator recovery |
| Read-only mode writes | Unauthorized mutation | Transport guard | Pair observational config and negative tests |

## Security, privacy, and safety

- Payout identities and passwords are sensitive. Use disposable probe identity
  and environment-only credentials.

## Performance and resource risks

- Stable sample windows lengthen HIL but prevent single-sample false positives.
  Bounds must remain operationally reasonable.

## Rollout and rollback

- Change protocol and health criteria separately where possible. Restore the
  original pool and verify mining before ending any mutating rollout.
