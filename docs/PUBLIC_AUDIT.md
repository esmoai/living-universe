# Public-release audit — 2026-10-25

## Publication policy

The repository was assembled using a **file allowlist**, not by uploading a 14 MiB private backup and hoping `.gitignore` would conceal its contents. The original user ZIPs, image/firmware disk artifacts, local log captures, exported workspace data, compiled Windows/Linux tools and private development notes are not tracked. The source tree is small, contains no git submodules or credential files, and has no untracked deployment backend required by the public demo.

## Source and third-party material

The standalone site is built from a hash-checked existing Source / Destination runtime plus six local JS modules. It retains the bundled third-party notices and publishes the original editable source. The static demo lives in `docs/index.html`, and an offline build regenerates identical bytes. This is not a claim that all original Three.js/WebXR paths were runtime-tested. The included license applies to code contributors own; externally sourced material retains its original notice/license.

## Automated checks performed during staging

- Scanned textual, generated HTML and bundled JavaScript for high-confidence GitHub, AWS, OpenAI, Google, private-PEM and bearer-token patterns; none matched. Reviewed project-owned text for employer/project-internal names and personal account paths; none matched. This is not a guarantee of no unknown secrets.
- Offline static HTML regenerated and matched `web/index.html` and `docs/index.html` byte-for-byte.
- 34 source/model unit tests passed; 123 real Linux hosted C loopback tests passed; 12 host telemetry/parser checks passed; ARM64 ACPI/SPCR host test passed.
- Compiled native x86-64, ARM64 and ARM64-QEMU UEFI binaries and verified generated GPT/FAT images and their SHA-256 checksums. **No actual firmware boot was conducted here.**
- 42 Playwright browser checks passed on the Canvas2D fallback; zero uncaught browser script exceptions. WebGL2, headset hardware and native Windows execution were not tested.
- Git tracked-file safety gate rejects large or forbidden artifacts and known secret formats. GitHub Actions default permission is read-only and action versions are pinned to commit hashes.

## Risks left open

Third-party upstream licenses should be rechecked before additional distribution or importing new assets. The hosted observer is not an OS sandbox. The pre-alpha kernel lacks memory isolation, drivers and any arbitrary tool executor. A new public repository needs additional GitHub settings: branch protection, private vulnerability reporting, appropriate contributor approval and Pages branch configuration. No person should interpret publication as production security validation.

This document is a reproducible preparation record, not a legal opinion or external security certification.
