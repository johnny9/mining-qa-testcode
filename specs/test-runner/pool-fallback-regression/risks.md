# Pool fallback regression — risks

## Scope

### In

Manual/automatic pool transitions, settings-save regression, optional dashboard
observation, bounded evidence, and restoration on an authorized target.

### Out

Firmware deployment, public-pool outages, mining reward measurements, and lab
scheduling or lease ownership.

## Assumptions

The device can reach the local test host and exposes indexed pools with three
unused IDs. Only the authorized test owns the device during its execution.

## Open questions

Additional device families require separate HIL qualification; API-only runs
cannot prove a dashboard fix.

## Failure modes

Wrong advertised address causes timeout. A probe can resemble a mining
connection, so fresh submission and acceptance evidence is mandatory. A stale
share counter can survive a transition, so progression is checked per phase.
Partial writes and failed deletion must remain visible cleanup errors.

Some installed firmware may retain a pool-unavailable power shutdown after
restoring reachable pools. Configuration equality does not prove healthy
cleanup. Require new accepted shares, retain recovery evidence, and keep any
needed recovery restart visible as an error.

## Security, privacy, and safety

Original credentials never leave original slots. Read-only/invalid baselines
fail before writes. CDP is optional, loopback-only, and targets the configured
device page. Private coordinates remain in ignored profiles and sanitized logs.

## Performance and resource risks

Tests interrupt normal mining temporarily. Deadlines must cover real firmware
retry/heartbeat periods without requiring an exact timing policy.

## Rollout and rollback

Enable the new module only in selected profiles, qualify on Gamma, and keep
the normal lifecycle cleanup. Disable the module to roll back test selection;
every run restores original pool entries, selection, and pause state.
