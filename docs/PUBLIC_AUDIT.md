# Public source and delivery audit

## Scope and provenance

The public source was assembled from an explicit allowlist, not by dumping private backup ZIPs into Git history. All three supplied archives were inventoried; [File coverage](FILE_COVERAGE.md) records their identities and dispositions. No runtime source was missing. Original reference media, chat notes, authoring host settings, nested backups and personal workspaces are not public runtime dependencies.

Editable visual sources, the retained hash-checked production runtime, native C observer, both kernel architecture ports, tests, licenses and documentation are present. Original third-party terms are preserved. The license covers project code with publication authorization, not ownership of arbitrary third-party material. Automated scans are not legal clearance or proof that unknown secrets cannot exist.

## Repair from source-only publication

The initial main CI failed because its runner lacked lld-link. The repair explicitly installs and selects Clang/LLVM, synchronizes all standalone HTML outputs and creates complete release kits. Generated Windows/Linux tools, three EFI executables and four disk images are included in release downloads rather than Git history. Packaging rejects missing required artifacts and includes a file hash inventory.

The publication pipeline now runs actual x86-64 and AArch64 QEMU firmware tests, a real Windows EXE smoke test, full editable-source tests/build, model tests and native API checks before releasing. Read-only jobs have no publishing authority; deployment/release rights are scoped to dedicated jobs. Existing versioned releases are not overwritten by the workflow. This policy is not a claim that GitHub's optional immutable-release administrative setting is enabled.

## Verified public milestone

[Run 40170633060](https://github.com/esmoai/living-universe/actions/runs/40170633060), commit 10272c09f668cd528b182b5f912dd369b823a2c5, passed every source/native/release job and published v0.3.1-prealpha. The Windows smoke test explicitly preserved CRLF bytes. Both QEMU tests used actual firmware and commands, not substituted fixtures. Physical machines, generic ARM board boot, WebGL/headsets and kernel isolation remain outside this verified milestone.

Earlier 34-model / 123-native / 42-Canvas2D local counts describe the original staging environment, not new hardware certification. Current CI and its exact commit are authoritative for a release. The v0.3.2 refresh corrects inherited status wording after the public runtime milestone.

## Website remains a separate deployment

The static Pages build passes and stages only public HTML, notices, sample bytes and status metadata. The last deployment check failed because the repository had no enabled Pages site. Owner activation at Settings > Pages > Source > GitHub Actions remains necessary. A successful deploy job and matching public status.json are required before claiming the website is live. No native service is deployed to the public site.

## Remaining owner safeguards

Review private vulnerability reporting, branch rules, outside-contributor approvals and dependency changes. These settings are not claimed enabled without evidence. Do not treat a green build, public source, cryptographic checksum or unsigned pre-alpha download as a production security guarantee.
