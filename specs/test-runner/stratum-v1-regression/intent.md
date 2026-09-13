# Stratum V1 regression — intent

## Problem

Public pools cannot deterministically produce malformed jobs, duplicate work,
or exact share responses, so they cannot isolate miner-client regressions.

## Why it matters

A miner may appear reachable while mishandling job changes, extranonces,
difficulty, extension negotiation, submit responses, or reconnect behavior.
Controlled protocol stimuli make those failures repeatable and diagnosable.

## Stakeholders

- Firmware developers changing the mining client.
- Lab operators validating a board/firmware combination.
- Maintainers diagnosing a failed child result.

## Desired outcome

The target miner connects to a local fake pool and passes an ordered,
bounded set of protocol scenarios with a sanitized transcript. Opt-in
pull-request validation can exercise high-risk protocol transitions without
widening the normal qualification suite.

## Primary flow

Start the fake server, temporarily point the device at it, wait for the client,
run ordered scenarios, retain evidence, and restore the original pool.

## Alternate and failure flows

- A server or client timeout fails the current scenario with bounded evidence.
- A failed prerequisite skips later scenarios that would produce misleading
  secondary failures.
- Cleanup restores the original device configuration after any outcome.

## Non-goals

- Replacing public-pool interoperability tests.
- Acting as a production pool or implementing every Stratum extension.
- Measuring payout, long-duration stability, or absolute hashrate.
