# Transport interfaces — risks and scope

## Scope

### In

- HTTP, WebSocket, serial, and Stratum transport mechanics, limits, tracing,
  retry, and read-only enforcement.

### Out

- Device-specific semantic validation and test-level pass criteria.

## Assumptions

- GET/HEAD operations are safe to retry; device writes are not assumed
  idempotent.
- Stable serial identifiers are provided by the host's udev environment.

Network-only runs cannot collect early boot serial output or recover through
USB. An API failure remains a test/setup error; firmware recovery must use a
verified network-accessible partition or be reported as unavailable.

## Open questions

- Future protocols may require explicit idempotency keys before safe write
  retries can be introduced.

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Duplicate write | Double restart/configuration | Write count tests | Never auto-retry writes |
| Oversized payload | Memory exhaustion | Limit breach | Abort and surface interface error |
| Concurrent API calls | Embedded server instability | Flaky timeouts | Per-interface operation lock |
| Ambiguous serial glob | Wrong device capture/flash | Multiple match error | Require unique resolution |
| Credential in trace | Privacy compromise | Redaction/privacy tests | Never trace bodies |

## Security, privacy, and safety

- Protocol data may contain pool identities, credentials, MACs, paths, and
  private addresses; collection and publication are separate trust boundaries.

## Performance and resource risks

- Too-frequent polling or reconnect can overload embedded hardware; cadence and
  sample limits are configuration constraints.

## Rollout and rollback

- Tightening limits may break real firmware and needs representative evidence.
  Revert to last known-safe bounds if target validation shows incompatibility.
