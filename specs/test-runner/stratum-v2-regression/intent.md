# Stratum V2 regression — intent

## Problem

Public SV2 pools cannot deterministically provide target changes, exact share
responses, future-job ordering, transport failures, or stable protocol traces.
The existing local regression server implements only Stratum V1.

## Why it matters

An SV2 miner can complete TCP setup while failing Noise authentication,
channel negotiation, binary framing, job activation, or encrypted share
submission. Public-pool observation cannot reliably isolate those failures.

## Stakeholders

- **Firmware developers** — need repeatable evidence for the ESP-Miner SV2
  client.
- **Lab operators** — need bounded execution and verified pool restoration.
- **Test maintainers** — need a scriptable pool with sanitized protocol
  evidence.

## Desired outcome

The target miner establishes authenticated Noise, negotiates the selected SV2
channel type, consumes controlled jobs and targets, submits shares, handles
exact acknowledgements, and returns to its captured pool configuration.

## Primary flow

1. Start an ephemeral-authority fake server and capture the device baseline.
2. Temporarily configure the miner for SV2 and the server authority key.
3. Run ordered negotiation, job, target, share-response, and reconnect cases.
4. Save a sanitized transcript and restore the complete original pool state.

## Alternate and failure flows

- Noise, frame, setup, channel, share, and reconnect waits fail within explicit
  bounds.
- A failed prerequisite skips later ordered cases without bypassing cleanup.
- Unsupported or malformed encrypted input closes only that client session.

## Non-goals

- Operating a production pool or implementing Job Declaration/Template
  Distribution protocols.
- Certifying every SV2 implementation or replacing public-pool interoperability
  tests.
- Treating local protocol simulation as physical-hardware validation.
