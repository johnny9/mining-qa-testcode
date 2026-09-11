# Pool fallback regression — risks

## Scope

### In

Manual/automatic pool transitions, repeated and full outages, silent endpoints,
active settings edits, optional dashboard and pool-form validation, bounded
evidence, and restoration on an authorized target.

### Out

Firmware deployment, public-pool outages, mining reward measurements, and lab
scheduling or lease ownership.

## Assumptions

The device can reach the local test host and exposes indexed pools with three
unused IDs. Only the authorized test owns the device during its execution.

## Open questions

Additional device families require separate HIL qualification; API-only runs
cannot prove a dashboard fix.
SV2 standard and extended channels require separate hardware results. This
module covers SV2-to-SV2 failover; mixed SV1/SV2 endpoint pairs and pools that
drip partial encrypted frames are outside this qualification.
Gamma-02 master `1df7ba1` passed both channel modes on 2026-09-11, including
complete-silence failover in approximately 225 seconds and automatic recovery.
The pool-form scenario does not validate password edits or every pool protocol
option. Its request guard intentionally narrows the write to disposable rows;
it validates real form behavior and firmware responses within that boundary.

An SV2 channel carries the worker identity established at channel open, not in
each share. Evidence must bind accepted shares to that connection and channel.
Each endpoint's distinct authority must follow endpoint corrections; otherwise
a test setup mistake can resemble a firmware recovery failure.

## Failure modes

Wrong advertised address causes timeout. A probe can resemble a mining
connection, so fresh submission and acceptance evidence is mandatory. A stale
share counter can survive a transition, so progression is checked per phase.
Partial writes and failed deletion must remain visible cleanup errors.

Some installed firmware may retain a pool-unavailable power shutdown after
restoring reachable pools. Configuration equality does not prove healthy
cleanup. Require new accepted shares, retain recovery evidence, and keep any
needed recovery restart visible as an error.

A TCP connection can remain open while the pool stops sending jobs and share
acknowledgements. Gamma firmware `ede6c13` did not fail over from that condition
within a 180-second phase deadline. The SV1 receive loop is unchanged between
PR #1962 and its parent; a source-derived reproduction confirms repeated empty
reads never expire. This is an observed firmware limitation, not a reason to skip or
weaken the regression. Recovery after the silent-primary failover assertion
was not reached; normal cleanup releases the injected silence first.

Firmware `8cdade8b` subsequently passed the full nine-case Gamma regression.
The receive deadline returned to the existing retry state machine: sustained
silence reached stable fallback mining after 732.392 seconds, then recovered
primary after replies resumed. Short silence preserved the same connection.
Older firmware remains subject to the observed unbounded wait; other firmware
retry policies may need a different bounded silent-phase setting.

## Security, privacy, and safety

Original credentials never leave original slots. Read-only/invalid baselines
fail before writes. CDP is optional, loopback-only, and targets the configured
device page. Private coordinates remain in ignored profiles and sanitized logs.
The browser guard rejects malformed or unexpected writes before forwarding.
It preserves the actual submitted edit and roles, and leaves the real response
unchanged. A disconnected guard fails the browser case; it cannot establish
successful UI validation. Silent fault injection is released before restoration.

## Performance and resource risks

Tests interrupt normal mining temporarily. Deadlines must cover real firmware
retry/heartbeat periods without requiring an exact timing policy.
The silent-primary budget defaults to 900 seconds because each existing retry
may consume a three-minute receive timeout. Ordinary phases retain their
shorter deadline. The separate 15-second silence case catches premature
disconnects caused by treating every transport poll timeout as a pool failure.

## Rollout and rollback

Enable the new module only in selected profiles, qualify on Gamma, and keep
the normal lifecycle cleanup. Disable the module to roll back test selection;
every run restores original pool entries, selection, and pause state.
