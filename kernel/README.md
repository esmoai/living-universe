> Historical upstream baseline retained. For the v0.3 extension and actual current validation,
> see the project root START_HERE.md and docs/TESTING.md. Upstream claims below were not
> automatically revalidated by this release.

# C-Native Kernel — Stage 0 / v0.2 — x86-64 + AArch64 in parallel

**Native, freestanding C kernel bring-up for two processor architectures.**
This builds PE32+ UEFI boot applications for **x86-64** and **ARM64 (AArch64)**
from the **same kernel, framebuffer, UEFI handoff, and boot-info sources**.
Only CPU-specific instructions and early UART drivers are architecture adapters.

**This is NOT YET a general-purpose OS, secure microkernel, or universal program
launcher.** Both executables and the GPT/FAT32 boot images compile and pass
structural validation. **Neither has been runtime-tested under QEMU/UEFI or on
physical hardware in this delivery.** Treat as an early prototype only.

## What changed since Stage 0 / v0.1

- Retained existing x86-64 UEFI boot support with the same version-1 boot-info ABI.
- Added real **AArch64 machine-code** output, `EFI/BOOT/BOOTAA64.EFI`, not an
  x86 emulator or interpreted ARM target.
- Made `EFIAPI` architecture-aware: Microsoft x64 ABI for x86-64; AAPCS64 for ARM64.
- Factored ISA-dependent CPU reporting, interrupt masking, halt, and idle polling
  behind `include/arch.h`. Shared `src/kernel.c` contains no ISA instructions.
- Added ARM64 MIDR/MPIDR/CurrentEL discovery and a PL011/SBSA early serial driver.
- Added guarded ACPI 2.0 RSDP/XSDT/SPCR-based UART detection. An explicit
  QEMU `virt` build may use the documented PL011 address as an opt-in fallback;
  the general ARM64 build never assumes a QEMU-specific address.
- Added a **single removable-media image that carries both architecture boot
  files**, plus separate media for each architecture and QEMU `virt` testing.
- Added host-side sanitizers and negative tests for ACPI SPCR parser behavior.
- Preserved a fixed minimal trusted surface: no Node.js, PHP, Rust runtime,
  Linux/Windows syscalls, libc dependency, or downloaded executable support.

## Deliverables

| Path | Purpose |
|---|---|
| `build/x86_64/BOOTX64.EFI` | Native x86-64 UEFI application |
| `build/aarch64/BOOTAA64.EFI` | Native generic ARM64 UEFI application (ACPI/SPCR discovery) |
| `build/aarch64_virt/BOOTAA64.EFI` | ARM64-specific QEMU virt UART fallback; **not for arbitrary hardware** |
| `build/c-native-kernel-dual-uefi.img` | **64 MiB** GPT/FAT32 image with both standard boot paths |
| `build/c-native-kernel-x86_64-uefi.img` | 64 MiB x86-64-only image |
| `build/c-native-kernel-aarch64-uefi.img` | 64 MiB generic ARM64-only image |
| `build/c-native-kernel-aarch64-qemu-virt.img` | 64 MiB QEMU-virt-specific ARM64-only image |
| `build/SHA256SUMS` | Hashes for all seven release binaries/images |

UEFI firmware selects by architecture:

```
EFI/BOOT/BOOTX64.EFI     # x86-64 UEFI
EFI/BOOT/BOOTAA64.EFI    # AArch64 UEFI
```

The one combined image can be cloned to **one dedicated test USB** to serve both
kinds of UEFI firmware; that does **not** guarantee it will work on every board.
Each architecture has a different processor binary even though the disk image
contains both.

## Build

Requires Clang 17+, `lld-link` and Python 3 (standard library only for disk
creation and verification). From the project root:

```sh
./scripts/build.sh
./scripts/test_host.sh
(cd build && sha256sum -c SHA256SUMS)
```

The compiler targets `x86_64-pc-windows-msvc` and `aarch64-pc-windows-msvc`
only to generate PE/COFF for UEFI. These are *not Windows applications* and
have no Windows imports. The ARM64 build requires no ARM64 hardware to compile.

### Validation executed for this release

- Clang compiled both target ISAs with strict warning-as-error options.
- `lld-link` produced EFI application (PE32+) with the correct 0x8664 / 0xAA64
  machine identifiers, entrypoints, base relocations, and no runtime imports.
- Disk-image checker verified GPT primary/backup CRCs, partition-table mirrors,
  FAT32 FAT mirrors, boot-directory paths and binary content matches.
- The same shared boot-info structure compiles for both architectures.
- Host-side ASan + UBSan tested ARM64 ACPI/SPCR parsing, including rejected input.
- Builds were checked for determinism (see `build/VALIDATION.txt`).

**Not tested:** firmware executing the binaries, post-ExitBootServices memory
mapping, UART MMIO on actual hardware, GOP framebuffer access in firmware,
interrupt handling, user-space isolation, drivers, or Secure Boot signing.

## Emulator testing instructions — x86-64

Install a QEMU x86-64 system emulator and OVMF UEFI firmware on a test machine.
Use the actual firmware filenames for your distribution (some require 2 MiB vs
4 MiB variable-store format). Example:

```sh
cp /path/to/OVMF_VARS.fd /tmp/CNATIVE_OVMF_VARS.fd
qemu-system-x86_64 -machine q35 -m 512M \
  -drive if=pflash,format=raw,readonly=on,file=/path/to/OVMF_CODE.fd \
  -drive if=pflash,format=raw,file=/tmp/CNATIVE_OVMF_VARS.fd \
  -drive if=virtio,format=raw,file=build/c-native-kernel-dual-uefi.img \
  -serial stdio
```

Serial commands expected after successful firmware handoff: `help`, `status`,
`cpu`, `mem`, `halt` followed by Return. The port is legacy COM1 on x86.

## Emulator testing instructions — AArch64

Install an AArch64 QEMU system emulator and edk2/QEMU EFI firmware (for example,
a compatible `QEMU_EFI.fd`). Firmware layout varies by distribution; consult
its QEMU ARM64 instructions. In a lab VM:

```sh
qemu-system-aarch64 -machine virt,gic-version=3 -cpu cortex-a57 -m 1024 \
  -bios /path/to/QEMU_EFI.fd -monitor none -display none -serial stdio \
  -drive if=none,format=raw,id=disk,file=build/c-native-kernel-aarch64-qemu-virt.img \
  -device virtio-blk-device,drive=disk
```

If the firmware requires separate flash images for CODE and writable variable
storage, replace `-bios` with the correct `-drive if=pflash` configuration.
The QEMU `virt` disk image opts into PL011 `0x09000000` as an emulator-only UART
fallback. The generic ARM64 binary instead uses firmware ACPI SPCR discovery.

Where GOP is available, the shared framebuffer shows a boot screen. The ARM64
serial console operates using the common PL011/SBSA register subset when the
UART is identified. **An arbitrary ARM64 board need not have a compatible UART,
ACPI tables, GOP graphics, or usable UEFI boot firmware.**

## Hardware testing and safety

- **Do not flash a production disk.** A `.img` is a complete disk image and
  overwrites the selected removable drive's partition table and contents.
- Use expendable USB media and test in QEMU/OVMF before noncritical lab hardware.
- These EFI applications are **unsigned**; firmware Secure Boot may refuse them.
  There is no signed update or verified boot pipeline yet.
- ARM64 is a CPU family, **not a single motherboard platform**. ARM devices may
  boot via UEFI, vendor chain, or specialized SoC firmware. Generic ARM64 UEFI
  support is not equivalent to Raspberry Pi, Apple Silicon, or phone support.
- The kernel still inherits **firmware page tables** after `ExitBootServices`
  and has **no fault recovery**. MMIO accessibility must be checked per platform.
- If serial and GOP are unavailable, Stage 0 may appear to hang silently.

## Source structure

```
include/kernel.h                 shared boot-info ABI v1
include/uefi_min.h               common UEFI structures + EFIAPI by architecture
include/arch.h                   portable architecture-operation contract
src/uefi_boot.c                  shared UEFI entry/ExitBootServices
src/kernel.c                     shared command loop, memory-map scan, status
src/framebuffer.c                shared GOP framebuffer painter
src/arch/x86_64/arch.c           CPUID, CLI, PAUSE, HLT
src/arch/x86_64/serial.c         legacy x86 COM1 serial driver
src/arch/aarch64/arch.c          system registers, DAIF, YIELD, WFI
src/arch/aarch64/serial.c        PL011/SBSA, ACPI SPCR discovery
scripts/build.sh                 build both CPU targets and 4 disk images
scripts/make_disk.py             deterministic GPT/FAT32 image composer
scripts/check_image.py           static PE/GPT/FAT checker for both architectures
scripts/test_host.sh             UBSan/ASan ACPI parser tests
tests/test_acpi_spcr.c            valid and rejected platform metadata fixtures
```

### References

- UEFI Architecture-specific removable file naming:
  https://uefi.org/specs/UEFI/2.11/03_Boot_Manager.html
- QEMU AArch64 `virt` machine:
  https://www.qemu.org/docs/master/system/arm/virt.html
- Arm SystemReady documentation (ACPI/SPCR board examples):
  https://developer.arm.com/architectures/architecture-exploration/systemready

Next milestone stays **Gate 0 runtime verification on x86-64 and ARM64**. Only
then should the project progress toward independent page tables, interrupt
controllers and kernel privilege boundaries on both architectures.

## Local QEMU runtime gate (Windows/WSL/Linux development)

This source package adds a QEMU UEFI boot smoke-test runner to verify both
architectures on the same laptop. Refer to `docs/QEMU_TESTING.md`.
Run `./scripts/test_qemu.sh --arch both` after installing QEMU/UEFI firmware.
The release's earlier static validation does not establish runtime boot.
