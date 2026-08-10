---
name: build-github-test-artifact
description: Resolve an exact GitHub revision and obtain or build target-appropriate, checksum-verified firmware or software artifacts for hardware testing. Use when a user wants an artifact from a repository, branch, tag, commit, pull request, release, or GitHub Actions run; needs help choosing factory, application, web/filesystem, bridge, or other artifact roles; or needs a reproducible artifact handoff for mining-qa-testcode or another local test runner.
---

# Build a GitHub test artifact

Produce an immutable, target-specific artifact handoff. Adapt to the requested
repository and device; do not assume ESP-Miner, Bitaxe, or one build system.

## Establish the request

Determine, from the request and available checkouts:

- GitHub repository and requested branch, tag, commit, PR, release, or run.
- Exact hardware/model/revision and installation method.
- Artifact roles the consumer accepts and whether recovery media is needed.
- Whether the user wants a source build, an existing CI/release artifact, or
  whichever can be verified most strongly.

Ask only for information that cannot be discovered safely. Do not guess a
hardware revision, artifact role, flash offset, partition layout, or signing
requirement.

## Resolve immutable provenance

1. Inspect the repository's build documentation, workflows, manifests,
   submodules, release metadata, and target definitions.
2. Resolve mutable input to an exact commit SHA. For a PR, distinguish head SHA
   from GitHub's synthetic merge SHA and use the one the requested test means.
3. Prefer the canonical upstream remote. Record repository URL, SHA, ref or PR,
   submodule SHAs, and whether the source tree is clean.
4. Use an isolated clean checkout or worktree. Preserve unrelated and dirty
   work; never present a dirty build as reproducible.
5. Reject a CI artifact unless its workflow run is successful, belongs to the
   exact intended SHA, and identifies the correct target. Treat checksums from
   the same untrusted bundle as integrity metadata, not independent authenticity.

Do not substitute a nearby branch tip, rebuild a different SHA, or reuse a
stale build directory across revisions or toolchain changes.

## Select source build or published artifact

Prefer an existing GitHub Actions or release artifact when its exact source,
target, contents, and integrity can be verified. Otherwise build from the clean
resolved source using repository-owned instructions.

Before building:

- Read the actual workflow or build scripts rather than inventing commands.
- Verify required toolchain versions, lockfiles, submodules, target flags, and
  generated assets.
- Confirm which output maps to each consumer role. Names alone are insufficient.
- Separate manufacturer/factory images, application OTA images,
  filesystem/web OTA images, bridge/controller firmware, and host executables.

Run proportionate build and non-hardware validation. Capture the exact commands
and relevant versions. Never claim HIL, boot, flashing, or device compatibility
that was not observed.

## Validate outputs

For every selected artifact:

1. Confirm it is a regular file produced by or attached to the resolved source.
2. Identify its role from build configuration, manifest, partition data, or
   documented workflow—not just its filename.
3. Check target identifiers, embedded version/manifest, format, size bounds,
   signing metadata, and flash/OTA compatibility when the project exposes them.
4. Compute SHA-256 and byte size locally.
5. Retain a known-good recovery artifact and procedure before recommending a
   device write when the platform needs one.

Do not combine images, change offsets, sign, publish, or flash unless the user
explicitly requested that separate action.

## Hand off

Report a compact artifact handoff containing:

- Repository URL, immutable commit SHA, requested ref/PR/run, and source state.
- Target hardware and intended installation method.
- One row per artifact: role, absolute local path, byte size, SHA-256, version or
  manifest identity, and why it is the correct role.
- Build/download commands and validation actually run.
- Recovery artifact/procedure and any unresolved compatibility or physical-test
  limitation.

If the artifact will feed `mining-qa-testcode`, make the role names match the
selected adapter's `devices.interfaces.upgrade` contract. Pass this handoff to
`$configure-mining-test-device`; do not edit a local profile merely because an
artifact was built.
