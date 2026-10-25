# Real dual-architecture QEMU firmware verification

The Stage 0 kernels have not yet been shown to boot in this public release.
These are instructions for running that test—not a claim of success.

Run from this repository:

```sh
cd kernel
sh scripts/build.sh
sh scripts/test_host.sh
sh scripts/test_qemu.sh --arch both
```

On Ubuntu/Debian, install `qemu-system-x86`, `qemu-system-arm`, `ovmf`,
`qemu-efi-aarch64`, `python3`, `clang` and `lld` if missing. The harness uses
TCG emulation, copies boot-media images and UEFI variables into a temporary
directory, disables networking and retains serial logs under `runtime-tests/`.
It does not expose your physical disks or require hardware virtualization.

Each architecture must produce the boot banner and correct responses to
`help`, `status`, `cpu`, `mem` and `universe`. The `universe` response is a
schema-validated `@LU1` JSON line with the matching architecture, firmware
handoff and explicit `user_space_isolation=false`. Parser-only or authored
fixture tests do not count as firmware execution.

Missing firmware or an emulator is a **not-run prerequisite**, not a PASS.
Do not disable Secure Boot or flash a production disk to run a preliminary
boot test. Preserve failures and report platform details without leaking
private device identifiers, paths or credentials.
