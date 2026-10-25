# Compatibility: evidence, not promises

See [Validation](VALIDATION.md) for the exact public run and the distinction between a component pass and overall CI success.

| Target | Established evidence | Not established |
| --- | --- | --- |
| Portable browser UI | Earlier local Canvas2D interaction tests; public offline model and full editable-source builds pass | Fresh WebGL2 and real touch-device regression |
| WebXR | Original navigation source retained | Actual headset validation; immersive detailed inspector cards |
| Linux x86-64 observer | Real loopback tests, process smoke and earlier sanitizer checks | Independent security audit; complete sandboxing |
| Windows x64 observer | Actual startup and requests exercised; dedicated Windows CI gate tests complete behavior | Check the exact subsequent job for full smoke success; independent hardening |
| x86-64 UEFI Stage 0 | Actual QEMU q35/qemu64 + OVMF boot and command checks passed | Physical PC boot, own MMU, interrupts/task isolation |
| AArch64 QEMU-virt profile | Actual virt/cortex-a57 + AAVMF boot, EL1 and command checks passed | Physical ARM board and visual framebuffer validation |
| Generic AArch64 UEFI image | Native cross-build and static image checks | Generic-image runtime boot on declared board configurations |
| Linux ARM64 hosted observer | Shared C source available | Actual ARM64 host build/runtime test |
| RISC-V, legacy BIOS, other/locked boards | Not supported by this release | Explicit ports, boot-chain support and drivers |
| Arbitrary native tools and secure kernel sandbox | Not implemented | Hardware-enforced separation, capabilities and adversarial tests |

A QEMU success is specific to the recorded firmware, CPU and machine configuration. The universal-hardware ambition is not current support. All released kernel images remain experimental and unsigned. Start with emulation, never a production disk.
