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
- A positive fixture retains the old scriptSig length after extranonce sizes
  change, turning an intended valid-work check into a malformed-coinbase test.
- With no extranonce or version rolling, a random job's finite search space
  may contain no qualifying share; the zero-length case preserves a proven
  solution instead of lowering difficulty or increasing the timeout.
- A malformed large suffix is mistaken for evidence that all large suffixes
  should be rejected, breaking valid multi-payout pools.
- Deferred negotiation is answered too late or on the wrong connection.
- A pre-reboot socket remains apparently open and receives work meant for the
  current boot; a fresh protocol response is required before selecting it.
- An unbounded job burst overloads the device or test host.
- A malformed-frame disconnect leaves stale writes alive or delays the new
  connection beyond the recovery bound.
- Server teardown races with transcript collection.
- A failed run leaves the miner attached to the fake pool.

## Security, privacy, and safety

Bind narrowly, treat identities/passwords as sensitive, and never expose the
fake server as a general-purpose unauthenticated service.

## Performance and resource risks

Unbounded client input, job bursts, or transcript capture can consume memory;
message sizes, burst counts, queues, and capture volume must remain limited.

## Rollout and rollback

Add scenarios disabled or narrowly selected first. PR 1897 cases are selected
only by `--validation-pr 1897`. Roll back by removing the new scenario while
retaining lifecycle restoration and fake-server unit coverage.
