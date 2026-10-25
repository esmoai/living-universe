# Compatibility matrix — evidence, not promises

**Living Universe v0.3.0 Pre-Alpha**, 2026-10-25. Only status backed by the actual test is reported as verified.

| Component / target | Current evidence | Missing verification |
| --- | --- | --- |
| Portable HTML, supported modern desktop browser | Prior local Canvas2D fallback and record/bit/recall workflow checks | Fresh WebGL2 regression on supported GPU/browser |
| WebXR / immersive portal navigation | Original code included | Actual supported headset and secure-origin test |
| Linux x86-64 hosted C observer | Prior real loopback protocol tests and sanitizer checks | Adversarial review and deploy-hardening |
| Windows x64 hosted observer | Cross-compiled PE structure | Native Windows execution and smoke test |
| x86-64 UEFI C Stage 0 | Native compiled PE32+ and static GPT/FAT image validation | Actual OVMF, physical boot, independent MMU |
| ARM64 UEFI C Stage 0 | Native compiled PE32+ and static GPT/FAT image validation | Actual edk2/QEMU, physical board boot |
| ARM64 QEMU-virt profile | Target compiled, PL011 fallback included | Actual QEMU virt firmware execution |
| Linux ARM64 hosted observer | C source portable by design | Compile/test on Linux ARM64 host |
| Other x86/ARM boards, RISC-V, legacy BIOS | Not supported | Per-board/ISA ports and drivers |
| Native third-party app execution, OS sandbox | **Not implemented** | Hardware-enforced privilege separation, capabilities, loaders and negative tests |

Build success and a firmware image's checksum are not equivalent to successful boot or hardware support. Serial fixtures are explicitly marked simulated and cannot satisfy the dual QEMU gate. For new hardware, report the CPU, board, firmware revision, command, serial output and any failures—but not private serial numbers or keys.
