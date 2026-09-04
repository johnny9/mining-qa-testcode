# Stratum V2 regression — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Regression case | Own ordered hardware scenarios and temporary configuration | `tests/e2e/test_stratum_v2_regression.py` |
| Fake SV2 server | Terminate Noise, encode/decode the supported mining subset, and capture events | `src/miner_testcode/interfaces/fake_stratum_v2.py` |
| Device adapter | Select SV2/channel/auth settings and restore the baseline | `src/miner_testcode/devices/base.py` and `src/miner_testcode/devices/bitaxe.py` |
| Lifecycle | Guarantee cleanup after setup, test, or teardown failure | `src/miner_testcode/testcase.py:MinerTestCase` |

## Interfaces and contracts

### CLI

- Run through `miner-test`; `--pattern test_stratum_v2_regression.py` selects
  this slice.

### Configuration

- `[tests.stratum_v2_regression]` supplies enablement, bind/advertised host,
  port, username, channel type, initial/changed difficulty, and bounded waits.
- Endpoint and username settings remain private and are not portable catalog
  options. The advertised host must be reachable from the miner.

### Environment

- No secret environment value is required. The server generates authority and
  certificate keys per run and retains private key material only in memory.

### Python API

- `FakeStratumV2Server` exposes bounded start/stop, handshake/frame/share waits,
  target/job sends, session disconnect, and sanitized transcript output.
- `PoolSettings` defaults to SV1 and carries optional SV2 channel and authority
  settings only when its protocol is SV2.
- Restart readiness uses the selected primary `pools[]` value when a requested
  setting, such as SV2 authentication, has no flat AxeOS alias.

### HTTP or external protocols

- The supported wire subset is authenticated Noise NX plus Common
  `SetupConnection` and Mining Protocol open-channel, job, target, prev-hash,
  submit-success, and submit-error messages.

### Files, artifacts, payloads, and persistent state

- `fake-stratum-v2.jsonl` contains bounded event metadata and sanitized decoded
  fields. It never stores raw ciphertext, keys, device IDs, endpoint hosts, or
  mining identities.
- Sanitized baseline evidence redacts any pre-existing SV2 authority key; the
  authoritative in-memory baseline retains it only for cleanup.

## Contract constraints

### Required invariants

- One class-scoped server and temporary device configuration serve the ordered
  scenario sequence.
- Each encrypted header and payload is authenticated separately with monotonic
  Noise nonces and strict plaintext-size bounds.
- The first job is future work activated by a matching `SetNewPrevHash`.
- Cleanup owns restoration of every changed pool protocol/channel/auth field.
- Restart completion requires an observed reboot and a subsequent matching
  settings sample with uptime progress.

### Forbidden behavior

- Do not expose the fake listener beyond its configured lab interface by
  default or reuse its ephemeral authority as production trust material.
- Do not retain Noise private keys, raw traffic, private device metadata, pool
  identity, or network coordinates in artifacts.
- Do not accept unauthenticated, oversized, truncated, or structurally
  ambiguous frames as scenario evidence.
- Do not leave the device configured for the fake SV2 endpoint.

## Data and state

The server owns per-connection Noise keys/nonces, setup/channel state, target,
frames, and submissions. Cross-connection server authority is stable only for
one server run so reconnect authentication remains deterministic.

## Control and data flow

1. Start the fake listener and configure the device with its authority key.
2. Complete Noise, setup, and channel negotiation automatically.
3. The ordered tests send controlled target/job transitions and observe exact
   encrypted submissions/responses.
4. Stop the server, serialize bounded sanitized events, and restore the device.

## Failure and recovery

- Bind/start failure aborts before device mutation where possible.
- Noise authentication, framing, or protocol mismatch closes the affected
  client and records a bounded error class.
- Lost connection fails the current case unless it is the explicit reconnect
  stimulus; later dependent cases skip.
- Lifecycle cleanup still restores the baseline and reports cleanup errors.

## Compatibility and migration

The initial implementation follows the EllSwift/SHA-256 SV2 transport used by
current ESP-Miner. `PoolSettings.protocol` defaults to `SV1`, preserving every
existing caller. New SV2 message dialects require explicit codec/server cases.

## Resource and operational constraints

The fake server is single-run test infrastructure. Plaintext payloads are at
most 2 KiB, event counts and sessions are capped, and every network/scenario
wait and shutdown path is bounded.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Module catalog](../module-catalog/SPEC.md) | Publishes the selectable module and safe portable options. |
| [Device capability contract](../device-capability-contract/SPEC.md) | Supplies the distinct SV2 capability. |
| [ESP-Miner device adapters](../esp-miner-device-adapters/SPEC.md) | Owns native protocol/channel/auth fields. |
| [Transport interfaces](../transport-interfaces/SPEC.md) | Defines bounded protocol transport behavior. |
| [Lifecycle and cleanup](../lifecycle-and-cleanup/SPEC.md) | Restores temporary pool configuration. |
| [Artifacts, privacy, and provenance](../artifacts-privacy-and-provenance/SPEC.md) | Constrains transcript content. |
| [Stratum V1 regression](../stratum-v1-regression/SPEC.md) | Supplies the ordered-suite and fake-pool lifecycle pattern. |

## Verification approach

Unit-test primitives against official vectors, then exercise actual encrypted
loopback sockets through both channel modes and negative framing paths. Device
reactions and restoration require an explicitly authorized HIL run.
