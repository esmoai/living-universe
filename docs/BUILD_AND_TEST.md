# Build and test

## Requirements

For the source/test workflow: Python 3.11+, Node.js 22+, a C17 compiler; Clang and `lld-link` for UEFI/Windows cross-builds. GitHub CI will use pinned actions and explicit read-only permissions. Running the standalone HTML needs only a modern browser.

## Offline web build

```bash
python3 scripts/build_web.py
node --check validation/extension-syntax.js
node --test source/tests/data.test.js source/tests/universe.test.js
```

The packager checks SHA-256 of the retained original Source / Destination runtime in `vendor/` and embeds the added instruments without downloading npm packages. It writes `LivingUniverse.html` and `web/index.html`; publication uses the identical `docs/index.html` after an explicit copy/check. This is a **narrow extension packager**, not a general replacement for Vite. Changing the original Three.js scene requires a full source build and review of the adapter.

## Editable Vite source

```bash
cd source
npm ci
npm test
npm run build
```

Node.js is a build tool, not a dependency of the deployed static HTML. The dependency lockfile is checked in. Avoid silently upgrading packages when reproducing an issue.

## Native hosted observer

```bash
sh scripts/build_bridge.sh
python3 tests/test_bridge.py
# Cross-build Windows x64 binary on a machine with clang and lld-link
sh scripts/build_windows_bridge.sh
```

The Windows executable is unsigned and has not been verified by running it on Windows in the previous release. Do not disable security protections to run it. The C observer runs as a normal user-space application on Windows/Linux, **not inside the bare-metal kernel**. Its loopback-only API is documented in [Protocol](PROTOCOL.md).

## Kernel build and QEMU validation

```bash
cd kernel
sh scripts/test_host.sh
sh scripts/build.sh
sh scripts/test_qemu.sh --arch both
```

`build.sh` creates **generated** x86-64, generic AArch64, QEMU-virt AArch64, and dual-UEFI boot media under `kernel/build/`. This directory is deliberately gitignored. The QEMU runner makes temporary disk/NVRAM copies, runs without networking, and requires real `@LU1` output from each architecture. Do not pass test fixtures off as firmware output. No user data drive should be touched.

Host prerequisites on Ubuntu/Debian include `qemu-system-x86`, `qemu-system-arm`, `ovmf` and `qemu-efi-aarch64` for the real firmware gate. The QEMU gate remains **not yet confirmed** on this public release; firmware or physical hardware execution is not established by static builds.

## Automated tests

The root `scripts/test_all.sh` checks offline web, JavaScript tests, C observer, telemetry formatter and dual-architecture kernel build. Browser integration tests in `tests/test_browser.py` require Playwright/Chromium (not part of normal production dependencies). They previously ran in Canvas2D fallback mode, not WebGL or XR. The optional QEMU workflow is a **real runtime gate**, not a substitute for physical target testing.

## Podman lab

See `Containerfile` for a replaceable development environment. It is **not the kernel**. Start rootless, without `--privileged` or host device mounts, and build with pinned base-image digests for a production CI baseline. Podman test setup is a proposed workflow rather than a previously validated artifact.
