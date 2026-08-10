# Result model and publishing — risks

## Scope

### In

- Result aggregation, local reports, remote child publishers, and pointer.

### Out

- Parent gate aggregation, lab scheduling, and external service retention.

## Assumptions

- Publisher APIs provide stable identifiers/URLs or explicit failures.
- Orchestrator and runner agree on the pointer schema version.

## Open questions

- When external consumers expand, should the full run JSON receive a formal
  schema registry and migration tooling?

## Failure modes

- Remote success is mistaken for test success.
- Publisher retry creates duplicate children.
- Pointer is partial, oversized, or correlated to the wrong assignment.
- Pointer identifies a partial, tampered, or unbounded artifact manifest.
- Backend schema drift breaks publication after hardware work completes.

## Security, privacy, and safety

Authentication material stays in headers/environment boundaries and never in
results. Direct-upload URLs are temporary capabilities and must not be logged.

## Performance and resource risks

Large inline reports and excessive annotations can hit backend limits; keep
summaries compact and use bounded artifact uploads.

## Rollout and rollback

Add schema fields compatibly and deploy readers before required writers.
Rollback disables the affected remote publisher while retaining local results.
