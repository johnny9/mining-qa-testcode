# Transport interfaces — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| HTTP API | Serialize operations, bound responses/uploads, enforce read-only, safe-read retries | `src/miner_testcode/interfaces/api.py` |
| WebSocket | Bound connection and messages, ping, expose parsed JSON stream | `src/miner_testcode/interfaces/websocket.py` |
| ESP serial | Resolve stable paths, capture bounded lifecycle evidence, optional shell-free flash | `src/miner_testcode/interfaces/serial.py` |
| Stratum probe | Bounded subscribe/authorize/job observation | `src/miner_testcode/interfaces/stratum.py` |
| Stratum V2 fake server | Terminate authenticated Noise and exchange bounded encrypted mining frames | `src/miner_testcode/interfaces/fake_stratum_v2.py` |

## Interfaces and contracts

### CLI

- None directly; interfaces are adapter-owned.

### Configuration

- API: base URL, timeout, safe-read retries/backoff, polling, online timeout,
  log bound.
- WebSocket: enabled/required, URL or derived URL, connect/reconnect/ping, max
  message, max samples.
- Serial: path/glob, baud rate, capture/required, optional flash command.

### Environment

- None directly. Protocol credentials are supplied by higher feature slices
  and must not enter traces.

### Python API

- `HttpApiInterface`, `JsonWebSocketInterface`, `EspSerialInterface`,
  `StratumV1Probe`, and `FakeStratumV2Server` expose bounded async operations.

### HTTP or external protocols

- HTTP(S) JSON and binary upload; WebSocket JSON messages; USB serial byte
  stream; Stratum V1 newline-delimited JSON-RPC over TCP/TLS; authenticated
  Stratum V2 binary mining frames over Noise.

### Files, artifacts, payloads, and persistent state

- `api.jsonl` records timing/status/size/path/error metadata, not bodies.
- `serial.log` and serial events remain test artifacts and are sanitized before
  publication.
- Stratum probe output records bounded protocol outcomes without passwords.

## Contract constraints

### Required invariants

- All HTTP operations on one embedded API interface are serialized.
- Every response/message/upload has a configured or hard maximum.
- Only GET/HEAD transient transport failures receive automatic retry.
- Read-only rejects any non-GET/HEAD operation before connection creation.
- Serial commands use argument arrays and named substitutions, never a shell.

### Forbidden behavior

- No automatic write retry after an uncertain response.
- No request/response bodies or credentials in generic API traces.
- No ambiguous serial wildcard selection.
- No unbounded WebSocket/Stratum line or message accumulation.
- No unauthenticated, oversized, or truncated SV2 frame may become protocol
  evidence.

## Data and state

- HTTP lock serializes operations for one device.
- WebSocket reconnect state is transient; normalized telemetry owns durable
  in-run observations.
- Serial capture task owns the file handle and is closed during lifecycle.

## Control and data flow

1. Validate/normalize endpoint and limits at interface construction.
2. Execute bounded operation in async wrapper or background task.
3. Emit body-free trace and return parsed data or typed interface error.

## Failure and recovery

- Oversized response/message → truncate only for evidence, fail operation.
- Transient safe read → bounded retry/backoff.
- Interrupted write → surface uncertainty; caller verifies device state.
- WebSocket outage → adapter records gap/fallback or fails if required.
- Serial path/permission failure → error when required, warning when optional.

## Compatibility and migration

- Protocol-specific behavior remains behind interfaces. New endpoints must not
  weaken bounds or tracing privacy.

## Resource and operational constraints

- Defaults bound HTTP to 8 MiB, WebSocket messages to configured maximum, logs
  to adapter limits, and structured telemetry separately.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [ESP-Miner device adapters](../esp-miner-device-adapters/SPEC.md) | Main consumer and fallback/restart coordinator. |
| [Firmware lifecycle](../firmware-lifecycle/SPEC.md) | Uses bounded binary upload or serial command. |
| [State, telemetry, and charting](../state-telemetry-and-charting/SPEC.md) | Consumes API/WebSocket observations and gaps. |
| [Public pool smoke](../public-pool-smoke/SPEC.md) | Uses independent Stratum probe. |
| [Stratum V2 regression](../stratum-v2-regression/SPEC.md) | Owns the authenticated fake-server scenarios and transcript contract. |

## Verification approach

- Unit tests exercise read-only preconnection rejection, transient/error bounds,
  WebSocket diff consumers, Stratum V1 handshake/job behavior, and encrypted
  SV2 authentication/framing. Live serial and embedded-device behavior require
  explicit target checks.
