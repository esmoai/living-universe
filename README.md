# Living Universe

**An open-source spatial observatory and experimental C-native operating-system project.**

[Start here](START_HERE.md) · [Complete downloads](https://github.com/esmoai/living-universe/releases) · [Website / deployment](https://esmoai.github.io/living-universe/) · [Architecture](docs/ARCHITECTURE.md) · [Build and test](docs/BUILD_AND_TEST.md) · [Compatibility](docs/COMPATIBILITY.md) · [Contribute](CONTRIBUTING.md)

> **Pre-alpha.** The interface is a local data/bit inspector with recorded workspace history. The x86-64 and ARM64 C kernel remains **Stage 0**: independent page tables, task isolation, drivers and arbitrary native program execution are **not implemented**. Check the exact commit's CI for emulator results. Physical hardware and production security are not verified.

## Source, complete downloads and the website

The source repository and its automatic **Code > Download ZIP** contain maintained code, tests, documentation, sample data and standalone HTML. Generated executables and disk images are delivered separately, not lost or silently omitted.

**[Complete runnable releases](https://github.com/esmoai/living-universe/releases)** include editable source, offline HTML, Windows launchers and unsigned EXE, Linux observer, x86-64 and ARM64 EFI files, the ARM64 QEMU variant, all four boot images and checksums. A pre-alpha release is published only after that commit passes source checks, both actual QEMU boot gates, and a native Windows observer smoke test. If no release exists yet, inspect the failing or pending [Actions run](https://github.com/esmoai/living-universe/actions/workflows/ci.yml).

A source upload is **not** a deployed website. If the demo returns 404, select **Settings > Pages > Source > GitHub Actions**, then run **Deploy interactive demo**. [Publication instructions](docs/PUBLISHING.md) explain this one-time owner setting. The workflow verifies the published commit through `status.json`; no privileged backend is deployed.

[Coverage of the three supplied archives](docs/FILE_COVERAGE.md) documents the maintained sources, generated outputs and excluded private/historical references.

## The idea

What if a computer could be explored as a connected world rather than a stack of windows? Living Universe turns information into a traversable scene. **Peer, inspect, observe, recall, handle, curate, nourish and touch** are its guiding interactions.

The scene preserves the original spectral globe, cube, three portals and XR navigation path. Floating instruments expose 12 information channels, exact selected-file bytes and bits, provenance, annotations, local routing and read-only recall. Sample records are **simulated**; actual readings are **observed**; imported serial logs are **reported**, not authenticated.

```text
Browser / portable HTML                Bare-metal C kernel (Stage 0)
Spatial field, inspection, history      x86-64 UEFI + AArch64 UEFI
             |                                  |
Optional loopback C observer                @LU1 serial report
(hosted Windows/Linux tool)               (no task isolation yet)
```

The hosted observer reports its own process measurements and optionally reads one selected serial log. It binds to `127.0.0.1`, requires a random session key, and exposes no execution or host-write endpoint. It is not the eventual kernel capability broker and is not an OS sandbox.

## Run

Extract a complete release and open `LivingUniverse.html` or `Launch-LivingUniverse.bat`. The static browser experience needs no PHP, Node.js server or account. Initial records are simulated; no upload or scan happens by default.

Import `samples/precision.bin`: bytes `81 42 00 FF 80 41`; first byte bits `10000001`, most-significant bit first. Open **I / Instruments**, inspect Bits, annotate and visit Recall. Export before closing. Saved workspaces are plaintext and may contain private imported material.

Without WebGL2 a simpler Canvas2D spatial view operates; it does not provide VR. Detailed inspector cards are desktop UI, not a completed headset cockpit.

## Develop and verify

See [Build & Test](docs/BUILD_AND_TEST.md), [Codex handoff](docs/CODEX_HANDOFF.md), [Validation](docs/VALIDATION.md) and [Compatibility](docs/COMPATIBILITY.md). Source/model tests, real Linux API tests, cross-compilation, firmware emulation and physical hardware are different verification levels. Never report a fixture or a compiled image as a successful hardware boot.

The offline packager updates all standalone HTML copies together. CI installs compiler/linker prerequisites explicitly, builds both kernel architectures, collects diagnostics, tests the Windows executable, and packages release assets from the same commit. Native services remain local.

## Licensing and community

Original project code is under [Apache-2.0](LICENSE). Third-party libraries and bundled material retain their terms: [THIRD-PARTY-NOTICES](THIRD-PARTY-NOTICES.txt), [NOTICE](NOTICE.md), [Provenance](docs/PROVENANCE.md). Verify rights before adding new assets.

Read [Contributing](CONTRIBUTING.md), [Code of Conduct](CODE_OF_CONDUCT.md), [Security](SECURITY.md) and [Governance](GOVERNANCE.md). No contributor may claim a secure kernel from compilation alone.
