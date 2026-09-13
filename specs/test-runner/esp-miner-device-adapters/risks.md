# ESP-Miner device adapters — risks and scope

## Scope

### In

- AxeOS behavior shared by Bonanza 1002 and Gamma 602 plus exact model identity
  and normalization differences.

### Out

- Other Bitaxe models until explicitly registered.
- ASIC-internal control and bridge-firmware implementation.

## Assumptions

- AxeOS endpoint behavior remains sufficiently compatible across supported
  versions for bounded feature detection.
- `boardVersion` and `ASICModel` are authoritative identity fields.

Network-only runs cannot collect early boot serial output or recover through
USB. An API failure remains a test/setup error; firmware recovery must use a
verified network-accessible partition or be reported as unavailable.

## Open questions

- If future ESP-Miner models diverge substantially, composition may replace the
  current subclass profile pattern.

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| API schema drift | Incorrect state/write payload | Fixture and HIL mismatch | Add versioned feature detection before support |
| Wrong board accepted | Unsafe firmware/test | Identity assertion | Exact board and ASIC match |
| Optional stream flaps | Evidence gaps | Connection warning/gaps | REST fallback and gap recording |
| Password mask sent as secret | Pool auth broken | Fake API payload assertion | Preserve existing masked value semantics |
| Gamma treated as bridge device | Invalid artifact requirement | Config/review tests | Keep application/web-only contract |

## Security, privacy, and safety

- Native fields may contain addresses, MACs, private IPs, and credentials;
  artifacts must pass privacy sanitation and must never feed cleanup writes.

## Performance and resource risks

- Aggressive concurrent polling can destabilize the embedded server; API
  serialization and bounded reconnect cadence are required.

## Rollout and rollback

- Land schema changes behind unit fixtures, then perform explicit target HIL.
  Keep known-good firmware/settings available for operator recovery.
