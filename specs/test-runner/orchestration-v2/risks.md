# Orchestration v2 — risks and scope

## Scope

### In

- Strict v2 metadata, correlation, exact-source validation, pointer, manifest,
  public child section, sanitized log boundary, and v1 compatibility.

### Out

- Status/Lab coordination, local scheduling/leases, global aggregation,
  physical-device selection, and parent publication.

## Assumptions

- Lab supplies exact immutable values and consumes the matching pointer.
- Status validates child correlation against server-owned frozen state.
- Existing privacy boundaries see every first-party public field/artifact.

## Open questions

- None blocking v2. Retirement criteria for v1 require later usage evidence.

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Correlation copied from mutable state | Cross-run child attribution | mismatch/concurrency tests | immutable per-invocation model |
| Private pointer serialized publicly | Lab privacy leak | canary payload tests | separate allowlist serializer |
| Writer enabled before Lab reader | Lost child evidence | compatibility matrix | reader-first staged rollout |
| Cleanup error hidden by publication | False pass | outcome matrix tests | cleanup remains authoritative |
| Raw log used after sanitizer failure | Secret/device leak | failure-path tests | no public log and no fallback |

## Security, privacy, and safety

Reject malformed work before hardware/network, never broaden device authority,
and keep private fields in the bounded pointer only. Simulation uses synthetic
canaries, not real credentials or coordinates.

## Performance and resource risks

Additional metadata, scanning, and artifacts increase CPU/disk/upload work.
Retain strict caps and fail explicitly rather than truncating authoritative
identity or scan coverage.

## Rollout and rollback

Add readers first, keep writer dormant, exercise simulation, and preserve v1.
Rollback disables new v2 invocations without deleting v2 evidence or changing
v1 meaning.
