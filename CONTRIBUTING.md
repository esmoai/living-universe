# Contributing

Thank you for helping make the project technically rigorous and accessible.

## Working agreements

- Keep x86-64 and AArch64 in parallel: a shared-kernel change requires both compile targets and tests.
- The visual field should remain primary; use dismissible instruments instead of replacing it with a conventional dashboard.
- Distinguish `simulated`, `observed`, `reported`, `derived`, and `recorded` evidence. Never present fixtures as real boot logs.
- No third-party runtime or native application is granted kernel privilege. New capability enforcement belongs in the verified native boundary, never merely in the UI.
- Do not submit private logs, tokens, proprietary corporate material, personal data, executable ZIP blobs, or unlicensed assets.
- Avoid speculative security claims. Provide exact reproduction commands, platform/firmware versions and observed behavior.

## Suggested workflow

1. Check open issues for a small scoped task, or open an issue explaining your approach.
2. Work on a branch. Keep commits focused and explain tradeoffs.
3. Run `sh scripts/test_all.sh`; additionally run QEMU or browser tests if your change affects those surfaces. Mark skipped checks accurately.
4. Include relevant tests, documentation and a note describing compatibility and security impact.
5. Open a pull request using the checklist template. Maintainers review before merging.

Large architecture changes should start with a design issue including threat boundaries, ABI changes, performance measures, rollback and cross-architecture validation. Comments, bug reports, accessibility feedback, board-compatibility data, and self-contained tests are all valuable.

By submitting a contribution, you represent that you have the right to contribute it under the repository's applicable open-source terms, including Apache 2.0 for original project code. Please disclose additional licensing requirements before merging. No CLA is required at this time; maintainers can adopt a formal DCO policy later after discussion.
