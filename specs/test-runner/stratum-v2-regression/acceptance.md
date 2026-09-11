# Stratum V2 regression — acceptance

## Functional behavior

- [x] **TR-STRATUM-V2-AC-01:** The fake server completes the ESP-Miner
  `Noise_NX_Secp256k1+EllSwift_ChaChaPoly_SHA256` responder handshake with an
  ephemeral, verifiable authority certificate.
- [x] **TR-STRATUM-V2-AC-02:** The server parses `SetupConnection` and standard
  or extended channel-open requests and returns matching success frames.
- [x] **TR-STRATUM-V2-AC-03:** Future jobs plus `SetNewPrevHash`, target
  changes, standard/extended submissions, accepted and rejected responses, and
  reconnection are independently observable.
- [x] **TR-STRATUM-V2-AC-04:** Device configuration selects SV2, the requested
  channel type, and the generated authority key through normal lifecycle
  cleanup.

## Interfaces and compatibility

- [x] **TR-STRATUM-V2-AC-05:** `test_stratum_v2_regression.py` is selectable
  through the packaged module catalog with bounded portable options while
  endpoint and identity values remain private profile settings.
- [x] **TR-STRATUM-V2-AC-06:** Existing `PoolSettings` callers retain SV1
  behavior by default, and flat and multi-pool ESP-Miner schemas restore all
  mutated SV2 fields.

## Quality attributes

- [x] **TR-STRATUM-V2-AC-07:** Frame payloads, event capture, client sessions,
  socket operations, handshake steps, scenario waits, and shutdown are bounded.
- [x] **TR-STRATUM-V2-AC-08:** Saved transcripts exclude raw encrypted bytes,
  device identifiers, endpoint coordinates, and mining identities.
- [x] **TR-STRATUM-V2-AC-09:** Loopback unit tests cover EllSwift compatibility,
  Noise authentication, both channel types, jobs, shares, rejection, malformed
  input, timeout, and shutdown behavior.
- [x] **TR-STRATUM-V2-AC-10:** A current authorized HIL run proves the selected
  target firmware passes the ordered suite and restores its original pool.

## Verification evidence

- 2026-09-11: The separate pool-fallback module reused this server in Gamma-02
  master `1df7ba1` HIL. All 18 cases passed across standard and extended channels,
  including complete silence, failover, recovery, and independent restoration.
  This qualifies the fallback scenarios; it is not a rerun of the original
  seven-case ordered protocol suite below.
- The complete Testcode unit suite passed all 103 tests on 2026-09-04. It
  includes official EllSwift/BIP340 vectors, authenticated loopback Noise,
  both channel types, job/target/share messages, rejection, reconnection,
  malformed input, transcript privacy, primary-pool schema fallback, and
  shutdown. The wheel and sdist built successfully with the fake server and
  packaged catalog.
- Authorized Gamma 602/BM1370 HIL against ESP-Miner PR 1897 CI firmware
  `1c44a87` passed all seven ordered cases in artifact
  `20260904T150741.490514Z`: authenticated Noise, setup, extended channel,
  future job and accepted share, target change, rejected share, and reconnect
  with fresh work. Cleanup reported success, and an independent API read
  confirmed both original SV1 pools, unpaused mining, and healthy hashrate.

## Acceptance rule

Server-only work may be accepted with official-vector and loopback tests.
Device-facing scenario changes require authorized HIL plus independent
verification that cleanup restored the original pool configuration.
