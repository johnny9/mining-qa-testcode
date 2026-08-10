# Artifacts, privacy, and provenance — risks

## Scope

### In

- Artifact allocation, privacy transformation, trace policy, and provenance.

### Out

- Host filesystem security and third-party publisher data retention policy.

## Assumptions

- All first-party evidence crosses the shared artifact/privacy boundaries.
- Operators configure stable public labels that contain no sensitive data.

## Open questions

- Which artifact schemas require formal version numbers as external consumers
  grow?

## Failure modes

- A new field bypasses recursive sanitization.
- A secret appears inside an unexpected free-form error message.
- Dirty or mismatched source is presented as the requested revision.
- Orchestrator metadata is trusted without comparing it to the runner checkout.
- An unsafe filename escapes or collides with another run.
- A very large artifact set exhausts runner or lab resources, or changes after
  hashing and produces a misleading archive.

## Security, privacy, and safety

Privacy is fail-closed for remote publication. Tests must use synthetic canary
values, never real credentials, when proving absence.

## Performance and resource risks

Verbose traces, images, and telemetry can exhaust disk or make upload failure
more likely; manifest production fails at explicit count/per-file/total caps and
retention remains an operator responsibility outside the runner.

## Rollout and rollback

Introduce schema changes additively and audit generated artifacts. Roll back a
new field/publisher mapping without deleting local diagnostic evidence.
