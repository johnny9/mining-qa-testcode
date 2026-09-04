# Stratum V2 regression — risks and scope

## Scope

### In

- ESP-Miner-compatible Noise transport, standard/extended mining channels,
  controlled jobs/targets/share responses, evidence, and restoration.

### Out

- Production pool operation, Job Declaration, Template Distribution, and
  exhaustive conformance or cryptographic certification.

## Assumptions

- Target firmware implements the current EllSwift/SHA-256 ESP-Miner SV2
  transport and its AxeOS pool fields.
- The lab host address is reachable from the miner.
- The device can find a configured low-difficulty share within the bound.

## Open questions

- Which protocol-negative HIL cases should become permanently enabled after
  representative firmware branches demonstrate consistent recovery?

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Crypto dialect drift | Handshake timeout mistaken for mining failure | Official vectors and transcript error class | Version the transport implementation and report the mismatch |
| Wrong advertised address | Device never reaches the server | No TCP session before timeout | Keep bind and advertised addresses distinct |
| Invalid job/target encoding | No share and misleading ASIC suspicion | Loopback codec tests and device work counters | Pin field byte order and valid templates |
| Transcript exposes identity | Privacy loss | Canary/sanitization assertions | Store only allowlisted decoded metadata |
| Restore omits SV2 field | Miner remains on wrong trust/channel settings | Full baseline comparison | Capture and restore complete pool objects/fields |

## Security, privacy, and safety

- The generated authority authenticates only this ephemeral test server. Its
  private keys are neither persisted nor reusable.
- Pool identities, device IDs, and network coordinates are sensitive even
  though SV2 encrypts them on the wire.
- Device mutation requires an authorized non-read-only profile and verified
  lifecycle cleanup.

## Performance and resource risks

Pure-Python EllSwift encoding is setup-only but must remain bounded. Ciphertext
lengths, decrypted payloads, events, sessions, tasks, and waits all have hard
limits to prevent a malformed client from consuming unbounded resources.

## Rollout and rollback

Ship the new module independently from SV1. Rollback removes the SV2 catalog
entry/scenarios and protocol-specific fake server while retaining the generic
protocol-aware pool configuration and its restoration tests if already used by
other modules.
