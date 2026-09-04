# Lifecycle and cleanup — risks and scope

## Scope

### In

- Lifecycle ordering, mutable baseline ownership, restore verification, cleanup
  error semantics, and close/log attempts.

### Out

- Automatic firmware rollback and physical power recovery.
- Pool-account ownership or credentials.

## Assumptions

- The device API accurately reports writable pool and pause state except
  documented masked secrets.
- Restarting applies settings atomically enough for bounded verification.

## Open questions

- Future device families may need typed baseline objects rather than a generic
  mapping; that migration must preserve evidence-versus-input separation.

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Invalid/sanitized baseline | Placeholder written to device | Marker validator | Fail before mutation and repair from an operator-controlled source |
| Unknown write-only password | Cannot restore original | Configuration precondition | Refuse password mutation |
| Restart never returns | Device unavailable | Online timeout | Record cleanup error; operator recovery |
| Transient read looks like reboot | Test sends work to a stale session | Reboot generation and uptime-progress checks | Require two matching post-reboot observations |
| Partial restore | Wrong pool/pause state | Final reread mismatch | Fail test and preserve evidence |
| Close hides restore failure | False success | Independent cleanup aggregation | Report all errors |

## Security, privacy, and safety

- The in-memory baseline may contain a secret and must never be formatted or
  serialized unsanitized.
- HIL mutation requires explicit authorization and post-cleanup verification.

## Performance and resource risks

- Cleanup can extend failed runs through reboot timeout; bounds must allow real
  devices without becoming indefinite.

## Rollout and rollback

- Lifecycle changes should land with fake-device regressions first. If HIL
  exposes incompatibility, revert the write-path change and restore the device
  using operator-controlled known-good settings.
