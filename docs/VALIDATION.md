# Validation evidence and remaining limits

## First public runtime evidence

Commit `b1126982843b9ab51290fa3e935ad0ecafa13052`, [CI run 40170436898](https://github.com/esmoai/living-universe/actions/runs/40170436898), established:

- Offline model tests and the complete npm editable-source tests/build passed.
- Real Linux observer protocol tests and the shared-C telemetry tests passed.
- x86-64, generic AArch64 and AArch64 QEMU-variant native files compiled; image checks passed.
- The **actual x86-64 QEMU q35/qemu64 boot with OVMF** passed help, status, cpu, mem and schema-validated universe commands after ExitBootServices.
- The **actual AArch64 QEMU virt/cortex-a57 boot with AAVMF**, using the explicit QEMU UART profile, passed those same commands. It ran at EL1 with a serial-only console.

The run's native-validation artifact and complete kit contain the actual serial logs, not authored fixtures. x86 reported a framebuffer but the headless test did not visually validate it. Generic ARM64 board firmware, generic ARM64 image boot and physical machines are not covered by the QEMU-specific profile.

That first overall run was not green: the Windows smoke test compared a raw CRLF log with a newline-normalized Python text read. The observer had started and served requests. The test was corrected to use explicit CRLF bytes and require exact preservation. This is a test-correctness fix, not removal of the requirement. Consult the subsequent windows-observer and publish-prealpha jobs for full Windows/release status.

## Per-commit release gate

[Current CI runs](https://github.com/esmoai/living-universe/actions/workflows/ci.yml) are the authoritative status for a new commit. A complete pre-alpha release is created only after source/model checks, the native/dual-QEMU job, Windows runtime smoke and source-safety checks succeed. Do not infer green CI merely from this file or from the existence of an intermediate artifact.

## Earlier local evidence

The supplied v0.3 archive reported 34 model tests, 123 Linux bridge checks repeated under sanitizers, 42 browser interactions under Canvas2D fallback, and 12 telemetry/parser checks. Those were local development results, not original WebGL or headset verification. Repeated sanitizer runs are not distinct test cases. The new public runtime evidence above supersedes earlier statements that neither architecture had ever booted in QEMU.

## Still not established

Physical hardware compatibility, generic ARM board boot, independent MMU/user-task isolation, native tool execution, a kernel-hosted renderer, actual WebGL/WebXR/headset behavior, broad browser-to-native HTTP integration, and security certification remain unverified or unimplemented. Source builds, runtime emulation, endpoint smoke tests and hardware tests remain separate claims.

Pages is independent of native tests. Its build passed, but activation/deployment requires the owner's Pages setting. A successful pages.yml deployment and matching public status.json commit are required before calling the site live.
