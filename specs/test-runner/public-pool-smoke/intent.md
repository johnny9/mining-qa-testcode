# Public pool smoke — intent

## Problem

A miner can appear healthy locally while its configured pool is unreachable,
its Stratum handshake is broken, or its work is stale. Conversely, short tests
cannot assume public pool difficulty will produce an accepted share.

## Why it matters

The smoke test needs independent protocol evidence and device health without
making external share timing a false hard requirement or unnecessarily changing
a correctly configured device.

## Stakeholders

- **Firmware developer/reviewer** — needs live pool and mining evidence.
- **Lab operator** — chooses observational or temporary reconfiguration mode.
- **Public pool** — is an external dependency with variable difficulty and
  availability.
- **Publisher consumer** — needs clear probe and stability results.

## Desired outcome

The independent client completes subscribe/authorize/job reception and the
device shows consecutive fresh healthy-mining observations against the expected
pool. Any temporary pool change is restored.

## Primary flow

1. Resolve pool/probe settings and launch an independent bounded Stratum probe.
2. Optionally configure/restart the device, preserving its current payout
   identity when no replacement is supplied, or verify its existing pool in
   read-only observational mode.
3. Require protocol job evidence and a stable device window with hashrate and
   fresh work; record a share when available without requiring it by default.

## Alternate and failure flows

- Missing identity fails before configuration.
- Observational mode rejects host/port mismatch.
- Probe, readiness, stale work, fault, or low-hashrate timeout fails with local
  evidence, then cleanup still runs.

## Non-goals

- Benchmarking pool latency or miner hashrate.
- Requiring an accepted share at arbitrary public difficulty by default.
- Publishing a private payout identity.
