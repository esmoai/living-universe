# Instructions for Codex and other contributors

Before changing code, read README.md, docs/ARCHITECTURE.md, docs/BUILD_AND_TEST.md, SECURITY.md and CONTRIBUTING.md.

Preserve the C-first, dual-architecture kernel roadmap. Native executable runtimes must not run in the privileged kernel; capabilities require checked hardware/OS enforcement and adversarial tests. Stage 0 UEFI images cannot run arbitrary tools or promise universal hardware support.

The browser field is the visual primary experience. Keep colored record markers separate from decorative stars. Preserve exact original bytes and provenance. No autonomous privileged repair and no collection of local data by default.

Run model tests, native tests, two-architecture build checks and an actual firmware boot gate when testing boot behavior. Do not use fixture output as a substitute for QEMU. Do not introduce hidden analytics, external runtime downloads, credentials or unlicensed assets into the public repo.

The static demo is `docs/index.html`, a copy of the offline bundle. `scripts/build_web.py` checks vendor hashes and regenerates the main app. Update the Pages demo only after verifying that the rebuilt output contains no secrets or external privilege-bearing endpoints. Do not commit generated binaries, kernel/build, raw input archives, captured private logs or personal workspace exports.
