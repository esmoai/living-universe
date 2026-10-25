# Validation evidence and remaining limits

## Fully successful public runtime milestone

Release [v0.3.1-prealpha](https://github.com/esmoai/living-universe/releases/tag/v0.3.1-prealpha) comes from commit `10272c09f668cd528b182b5f912dd369b823a2c5`, [CI run 40170633060](https://github.com/esmoai/living-universe/actions/runs/40170633060). All five jobs succeeded: web-and-model, native-and-kernel, release-safety, windows-observer and publish-prealpha.

Verified in that run:

- Offline model tests and complete npm editable-source tests/build.
- Real Linux observer API checks, hosted process smoke and shared-C telemetry tests.
- Three native UEFI targets, their four GPT/FAT boot images and checksums.
- Actual x86-64 q35/qemu64 + OVMF boot, followed by help/status/cpu/mem/universe checks and validated @LU1 output after ExitBootServices.
- Actual AArch64 virt/cortex-a57 + AAVMF boot, EL1 and the same command checks using the explicit QEMU UART profile. It was serial-only.
- Actual Windows x64 observer execution on windows-2022: 11 endpoint/process checks, including precise CRLF log-byte preservation.
- Creation of the complete runnable pre-alpha release only after these gates passed.

Real serial logs accompany the kit and native-validation artifact. x86 reported a framebuffer but the headless test did not visually validate it. The generic ARM64 image is compiled but is not the QEMU-specific profile tested at runtime. Linux ARM64 observer execution and physical-board boot are not covered.

The preceding b112698 run first demonstrated both emulator boots but failed its Windows test because a Python text read normalized CRLF. The test was corrected to compare exact bytes, not removed. The subsequent complete pass above supersedes that failure while keeping its diagnostic history.

## Per-commit gate

[Current CI runs](https://github.com/esmoai/living-universe/actions/workflows/ci.yml) are authoritative for any newer commit. Do not infer success from a document or an intermediate artifact. The v0.3.2 publication refresh updates status documents; its own workflow must also pass before that version is released. A green emulator test is not a physical compatibility or security certification.

## Earlier local evidence

The supplied v0.3 kit recorded 34 model tests, 123 Linux protocol checks repeated under sanitizers, 42 browser interactions in the Canvas2D fallback, and 12 telemetry/parser checks. Those are local development results. The browser document was injected for that test; real WebGL, headset operation and public HTTP-native integration were not established. Repeating a suite under sanitizers does not create additional distinct cases.

## Remaining boundaries

Independent kernel MMU ownership, user-task isolation, arbitrary native tool execution, hardware drivers and kernel-hosted rendering are not implemented. Physical hardware, generic ARM board boot, broad OS/browser compatibility, actual WebXR and independent security review remain open.

Pages is independent of native CI. Its static build passes, but no enabled site was found at the last deployment attempt. Owner activation and a successful deploy with matching public status.json are required before claiming the website is live.
