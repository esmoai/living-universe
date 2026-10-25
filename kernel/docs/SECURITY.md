# Kernel security charter: dual-architecture Stage 0

## Present boundary

The kernel has no secure user-process isolation. It is a privileged UEFI handoff experiment using firmware-created page tables and early serial/framebuffer access. It must not load or execute untrusted third-party code. Native binary compatibility, a task scheduler, capability enforcement, independent exception handling, IOMMU policy and safe tooling are not implemented.

The firmware, ACPI pointers and initial page tables are trusted inputs. ARM64 SPCR metadata is bounded/checksummed and restricted to known UART types, but that does not make malicious firmware safe. The QEMU-only PL011 fallback must not be used as an arbitrary-board hardware address. MMIO mappings and cache/device attributes require validation for every real platform.

## Runtime evidence now available

Public CI run 40170633060 at commit 10272c09f668cd528b182b5f912dd369b823a2c5 successfully executed:

- x86-64 QEMU q35/qemu64 with OVMF: actual firmware handoff, serial commands and valid architecture-specific @LU1 response.
- AArch64 QEMU virt/cortex-a57 with AAVMF: actual EL1 entry, serial commands and valid @LU1 response using the explicit emulator UART profile.

Both executions reported isolation and native-tool execution as false. This supersedes original static-only staging status; it does not establish generic ARM64-image boot, physical hardware safety, independent MMU control or a working sandbox. The generic ARM64 UEFI image is cross-built and statically checked, not the runtime-tested emulator profile. Visual framebuffer behavior and headset interaction are separate tests.

## Implemented checks versus unproven properties

Compilation and PE/GPT/FAT integrity checks cover all built images. Host ASan/UBSan tests cover the ACPI/SPCR parser and shared C observation formatter. Actual serial logs are retained as CI evidence; authored fixtures cannot satisfy the boot gate. These checks do not prove C memory safety, absence of privilege bugs or universal hardware support.

## Mandatory later invariants

1. Separate ring 3 / EL0 programs from the supervisor address space.
2. Enforce page permissions, execute-never/W^X policy and safe sharing.
3. Validate pointer ranges, arithmetic, message lengths and capability generations.
4. Keep third-party runtimes and most complex services outside kernel memory.
5. Enforce time, CPU, memory, I/O and process budgets below the UI.
6. Verify packages and boot/update chains with recoverable, authenticated state.
7. Test privilege misuse, malformed IPC, crashes and DMA boundaries per architecture.
8. Refuse unsupported isolation requirements instead of silently weakening them.

The current images are unsigned development builds. Begin in QEMU; never flash a production disk or disable platform protections based on an assumption that bare-metal C implies security.
