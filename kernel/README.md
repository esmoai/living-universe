# C-native kernel: shared Stage 0, x86-64 and AArch64

This is a freestanding C UEFI handoff prototype, not a completed OS or sandbox. It compiles natively for both ISAs; architecture-specific CPU/UART code is separated from shared boot, framebuffer, memory-map and command logic.

**Public emulator evidence now exists.** CI commit b1126982843b9ab51290fa3e935ad0ecafa13052 booted x86-64 with QEMU q35/OVMF and the AArch64 QEMU-virt profile with virt/cortex-a57/AAVMF. Both passed serial commands and valid @LU1 reports after ExitBootServices. See [current validation](../docs/VALIDATION.md). This supersedes the earlier static-build-only status. No physical hardware or hardware-enforced user-space isolation is claimed.

## Build and test

From the repository root, with clang and lld installed (versioned tool names may be set through CC and LINKER):

```sh
sh kernel/scripts/test_host.sh
sh kernel/scripts/build.sh
(cd kernel/build && sha256sum -c SHA256SUMS)
python3 kernel/scripts/boot_qemu.py --arch both
```

CI uses CC=clang-18 and LINKER=lld-link-18 explicitly. Commands are invoked via sh so executable checkout bits are not assumed. Python 3 builds/checks disk images without a third-party formatter.

## Generated deliverables

| Output under build/ | Purpose |
| --- | --- |
| x86_64/BOOTX64.EFI | Native x86-64 UEFI entry |
| aarch64/BOOTAA64.EFI | Generic AArch64 UEFI with firmware UART discovery |
| aarch64_virt/BOOTAA64.EFI | Explicit QEMU virt UART fallback; not arbitrary-board firmware |
| c-native-kernel-dual-uefi.img | 64 MiB GPT/FAT32 with both generic architecture boot paths |
| c-native-kernel-x86_64-uefi.img | 64 MiB x86-64 media |
| c-native-kernel-aarch64-uefi.img | 64 MiB generic ARM64 media |
| c-native-kernel-aarch64-qemu-virt.img | 64 MiB ARM64 emulator profile media |
| SHA256SUMS | Hashes of those seven artifacts |

These products are gitignored but included in the complete runnable release, together with the source and real CI serial logs. The generic ARM64 image is built but is not the profile exercised by the current QEMU gate.

## Implemented

UEFI PE32+ entry, final memory-map handoff, ExitBootServices, optional direct framebuffer, serial commands help/status/cpu/mem/universe/halt, and a common observation-only @LU1 line. Reports contain no arbitrary memory pointers or authority. Firmware conventional-page counts are not a live allocator.

The kernel still inherits firmware page tables, masks interrupts and polls an early console. It has no independent exception handling, scheduler, user processes, capability broker, native tool loader, filesystem/network drivers or signed update pipeline. No third-party code should execute in supervisor space.

## QEMU gate and safety

The runner finds installed matching OVMF/AAVMF firmware, copies disk/NVRAM to temporary storage, disables networking and uses TCG software emulation. It checks the architecture and actual command responses, not fixtures. It does not open a physical host drive. Results are in runtime-tests/.

x86 serial testing reported a 1280x800 framebuffer but did not visually test it. ARM64 used serial-only output. Broader CPU/memory layouts, generic firmware discovery, framebuffers, fault behavior and real boards require separate tests. The first two emulator passes do not complete the wider Gate 0 qualification plan.

Disk images overwrite partitions if deliberately flashed. Do not flash a production machine, weaken Secure Boot or assume USB boot on a locked device. AArch64 is an ISA family, not one board platform.

## Source layout

Shared headers and boot contract: include/. Common code: src/uefi_boot.c, src/kernel.c, src/framebuffer.c. CPU and UART implementations: src/arch/x86_64/ and src/arch/aarch64/. Disk creation/validation and emulator harness: scripts/. Host ACPI/SPCR tests: tests/.

The next foundational work remains independent paging, exceptions, memory allocation, interrupts, and user-space separation on both architectures. See [architecture](docs/ARCHITECTURE.md) and [roadmap](docs/ROADMAP.md).
