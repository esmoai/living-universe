# Living Universe

**An open-source spatial observatory and experimental C-native operating-system project.**

[Explore the interactive demo](https://esmoai.github.io/living-universe/) · [Architecture](docs/ARCHITECTURE.md) · [Build and test](docs/BUILD_AND_TEST.md) · [Compatibility](docs/COMPATIBILITY.md) · [Contribute](CONTRIBUTING.md) · [Security](SECURITY.md)

> **Pre-alpha, version 0.3.0.** The interactive interface is a real local data/bit inspector with recorded workspace history. The freestanding x86-64 and ARM64 C kernel remains **Stage 0**: independent page tables, task isolation, drivers and arbitrary program execution are **not implemented**. Dual-architecture firmware boots and hardware testing are **not yet verified**. Do not use this kernel on production devices.

### The idea

What if a computer could be explored as a connected world rather than a stack of windows? *Living Universe* turns information into a traversable scene. **Peer, inspect, observe, recall, handle, curate, nourish and touch** are its guiding interactions.

The current scene preserves the original spectral globe, cube, three portals and XR navigation path. Optional floating instruments allow navigation through 12 information channels, exact selected-file bytes and bit positions, provenance, local annotations, and read-only recall of recorded states. Sample records are labeled **simulated**; actual measurements are **observed**; imported serial logs are **reported** rather than authenticated.

### Architecture — today vs. goal

```text
Browser / portable HTML (runs now)      Kernel / bare-metal C (Stage 0)
    Spatial field, 12 channels           x86-64 UEFI      AArch64 UEFI
    Inspect, bits, recorded history          |                |
                 |                          +--- shared C ---+
     OPTIONAL read-only bridge                      |
       Linux / Windows C user tool             @LU1 serial report
         (not the kernel)                     (no user-space isolation)
```

**Runtime boundary:** a hosted local C observer can report its own process readings and optionally import one selected kernel serial log. It binds to `127.0.0.1`, uses a random session key, and exposes **no execution or host-write endpoint**. The eventual C microkernel capability broker is design work, not a deployed security guarantee.

### Run the demo

Open [LivingUniverse.html](LivingUniverse.html) in a modern browser or use `Launch-LivingUniverse.bat` on Windows. The public [GitHub Pages demo](https://esmoai.github.io/living-universe/) hosts the same standalone static experience **once Pages is enabled**. No server, PHP, Node.js, or account is required to explore or import a local sample.

Try `samples/precision.bin`: bytes `81 42 00 FF 80 41`; first byte bits `10000001` (MSB first). Use **I → Instruments**, import the file, inspect Bits, add a local note and visit Recall. Initial records are simulated. No uploads or scans occur by default. Exported workspaces are plaintext—do not publish them casually.

On a browser without WebGL2, a simpler Canvas2D spatial view operates; it **does not provide VR**. XR and real-hardware behavior still need independent testing.

### Develop

See [Build & Test](docs/BUILD_AND_TEST.md). The public source, offline runtime packager, Linux C observer, Windows cross-build scripts, kernel source, QEMU test runner, unit tests and examples are included. **Generated executables, boot disk images, personal reference archives, saved workspaces and runtime logs are deliberately not committed.**

### Status

| Workstream | What is verified | Still open |
| --- | --- | --- |
| Visual interface | Prior local model + Canvas2D workflow tests | WebGL/WebXR regression on compatible hardware |
| Linux C observer | Prior local loopback/API and sanitizer checks | External security review; production hardening |
| Windows C observer | Cross-compiled PE structure | Runtime smoke test on Windows |
| x86-64 + ARM64 C kernel | Both targets compile and pass static image checks | Actual UEFI/QEMU and physical boot, MMU/interrupts/isolation |
| Open-source publication | Sanitized source and static site prepared | Pages activation and public CI results |

Read [Validation](docs/VALIDATION.md) for the provenance and limitations of previous tests. Tests have not been silently upgraded to hardware verification.

### Licensing

Original project code contributed with publication authorization is provided under the [Apache License 2.0](LICENSE). Third-party libraries and generated bundled material retain their existing terms; see [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt) and [NOTICE.md](NOTICE.md). Please verify rights before introducing new assets or dependencies.

### Community

Pull requests and reproducible issue reports are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [SECURITY.md](SECURITY.md) and [GOVERNANCE.md](GOVERNANCE.md). **No contributor can claim a secure kernel from source compilation alone.**

Source and disclosure: [Provenance](docs/PROVENANCE.md) · [Public-release audit](docs/PUBLIC_AUDIT.md).
