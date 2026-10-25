# Compatibility: evidence, not promises

The fully successful public baseline is release v0.3.1-prealpha, commit 10272c09f668cd528b182b5f912dd369b823a2c5, CI run 40170633060. Consult each newer release's exact validation run. See [Validation](VALIDATION.md).

| Target | Established evidence | Not established |
| --- | --- | --- |
| Portable browser UI | Earlier local Canvas2D interaction tests; public model and complete editable-source builds pass | Fresh WebGL2 and physical touch-device regression |
| WebXR | Original navigation source retained | Actual headset validation; immersive detailed inspector cards |
| Linux x86-64 observer | Real loopback/API tests, process smoke and earlier sanitizer checks | Independent audit or complete OS sandboxing |
| Windows x64 observer | Actual windows-2022 execution and all 11 smoke checks passed | All Windows versions, code signing and independent hardening |
| x86-64 UEFI Stage 0 | Actual QEMU q35/qemu64 + OVMF handoff and command checks passed | Physical PC boot, own MMU, interrupts/task isolation |
| AArch64 QEMU-virt profile | Actual virt/cortex-a57 + AAVMF boot, EL1 and commands passed | Physical ARM board and visual framebuffer behavior |
| Generic AArch64 UEFI image | Cross-build and static disk-image checks | Runtime boot on declared generic/physical platforms |
| Linux ARM64 hosted observer | Shared C source | Actual ARM64 host build/runtime test |
| RISC-V, BIOS and other/locked boards | Not supported by this release | Explicit ports, firmware paths and drivers |
| Arbitrary native tool execution and secure kernel sandbox | Not implemented | Hardware-enforced separation, capabilities and adversarial tests |

QEMU results apply only to the recorded machine, CPU and firmware configuration. The universal-hardware ambition is not current support. All kernel images and the Windows EXE remain unsigned development builds. Start with emulation, never a production disk.
