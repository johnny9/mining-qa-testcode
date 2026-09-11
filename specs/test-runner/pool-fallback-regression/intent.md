# Pool fallback regression — intent

## Problem

Pool-selection state can disagree with the pool actually receiving work, and
settings changes can strand mining after failover or recovery.

## Why it matters

Regression checks must prove mining resumes on the correct pool without making
one reconnect or probing policy a correctness requirement.

## Stakeholders

Firmware reviewers, test maintainers, and operators of shared mining hardware.

## Desired outcome

A reusable module records manual selection, automatic fallback and recovery,
and settings-save outcomes with sustained fresh share evidence and verified
cleanup. It exercises the real form's edit history and persistence, active
edits without role changes, repeated transitions, silent endpoints, and
recovery after both pools lose connectivity.

## Primary flow

Capture the normal device baseline; allocate three unused pool slots; exercise
two controlled SV1 endpoints; restore selection; delete temporary entries;
verify original settings and resumed mining.

## Alternate and failure flows

Absent enablement skips before hardware setup. Unsupported indexed pools,
insufficient free slots, invalid configuration, and read-only devices never
receive test writes. Cleanup runs after partial setup and failed assertions.

## Non-goals

Requiring uninterrupted mining during settings saves, prescribing probes,
installing firmware, verifying proof of work cryptographically, or scheduling
lab leases. API-only runs do not validate rendered frontend behavior.
