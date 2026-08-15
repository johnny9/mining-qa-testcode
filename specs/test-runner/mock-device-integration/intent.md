# Mock-device integration — intent

## Problem

Unit fakes and a fake Stratum server validate isolated code, but no-device
integration also needs something to behave like the miner: expose native API
state/writes/restart/logs, connect to the fake pool, fail deterministically, and
prove cleanup ordering.

## Why it matters

The three-project workflow should be repeatable on a development/CI host
without risking a real miner. Using the real adapter against a process boundary
catches transport, lifecycle, and configuration drift that in-memory fakes
cannot.

## Stakeholders

- Testcode maintainers own native device/lifecycle fidelity.
- Status integration harness controls scenarios and asserts structured evidence.
- Lab process binds a private synthetic profile exactly as it would a real one.
- Hardware operators need simulation clearly separated from HIL.

## Desired outcome

A loopback-only process implements the required AxeOS Gamma API, minimal miner
Stratum behavior, deterministic fault controls, and bounded event ledger. The
real `bitaxe_602` adapter runs against it and every scenario terminates without
external network or physical-device access.

## Primary flow

1. Harness starts one isolated mock and fake pool per Lab, resets a named
   scenario, and generates a private synthetic Testcode profile.
2. The runner constructs the real Gamma adapter, drives native API lifecycle,
   and observes the mock's simulated Stratum behavior.
3. Harness verifies result/pointer plus structured mock events and final
   baseline, then terminates exact processes.

## Alternate and failure flows

- Identity mismatch fails before write.
- HTTP/restart/Stratum faults produce bounded explicit errors.
- Cleanup rejection/mismatch remains an error and preserves the attempted
  restore event.
- Privacy-canary logs publish only a separately sanitized copy containing no
  canary.

## Non-goals

- Claiming firmware, electrical, thermal, ASIC, timing, hashrate, or real
  miner-client conformance.
- Supporting OTA, serial, arbitrary commands, internet binding, or production
  use in version 1.
