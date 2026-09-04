# Stratum V1 regression — risks

## Scope

### In

- Supported fake-server messages, scenario control, evidence, and restoration.

### Out

- Production pool operation and exhaustive Stratum conformance certification.

## Assumptions

- The lab host is reachable from the miner on the advertised endpoint.
- Device adapters can safely snapshot and restore pool configuration.

## Open questions

- Which optional Stratum extensions deserve portable scenarios as firmware
  support expands?

## Failure modes

- Wrong advertised address produces a misleading client timeout.
- Scenario state leaks into a later case.
- A malformed-frame disconnect leaves stale writes alive or delays the new
  connection beyond the recovery bound.
- Server teardown races with transcript collection.
- A failed run leaves the miner attached to the fake pool.

## Security, privacy, and safety

Bind narrowly, treat identities/passwords as sensitive, and never expose the
fake server as a general-purpose unauthenticated service.

## Performance and resource risks

Unbounded client input or transcript capture can consume memory; message sizes,
queues, and capture volume must remain limited.

## Rollout and rollback

Add scenarios disabled or narrowly selected first. Roll back by removing the
new scenario while retaining lifecycle restoration and its regression test.
