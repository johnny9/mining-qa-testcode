# Orchestration v2 — intent

## Problem

A distributed gate adds global run, Lab execution, local run, assignment, and
attempt identities that version 1 cannot distinguish. Propagating them through
generic artifacts risks publishing private Lab paths/bindings or accepting
misattributed work after hardware access begins.

## Why it matters

Detailed evidence must link unambiguously to one frozen distributed execution
without weakening exact-source checks, cleanup, result truth, or privacy.
Contract drift must fail before a device or transport is created.

## Stakeholders

- Lab orchestrator supplies immutable invocation metadata and consumes the
  private pointer.
- Status verifies the public child correlation against frozen global state.
- Testcode maintainers evolve parsers, results, publishers, and privacy.
- Lab operators retain private local evidence and device authority.

## Desired outcome

The runner reads v1 and strict v2, validates v2 plus exact source/Testcode
provenance before artifact/device/network work, echoes immutable private
correlation in a bounded pointer, and publishes only the allowlisted public
subset in detailed child evidence.

## Primary flow

1. Parse environment and validate every v2 field/cross-field equality plus the
   executing Testcode checkout.
2. Run the existing Testcode lifecycle, construct detailed results, sanitize
   evidence/logs, and publish a child containing public v2 correlation.
3. Write a required bounded manifest and atomic private v2 result pointer with
   exact echoed correlation and child identity.

## Alternate and failure flows

- Unknown, mixed, incomplete, mismatched, or oversized v2 fails before artifact
  allocation, device construction, network, or publication.
- Pointer, manifest, required publisher, cleanup, or privacy failure remains an
  error and cannot become pass.
- Direct and version-1 invocations preserve their existing behavior.

## Non-goals

- Accepting Status work directly, registering Labs, leasing hardware, or
  aggregating a parent/global gate.
- Publishing private local run identity, profile/setup/device identity, paths,
  credentials, pool/payout identity, or raw logs.
