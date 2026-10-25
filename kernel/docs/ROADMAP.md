# Dual-architecture roadmap (gated)

## Gate 0A — x86-64 firmware handoff

- Native `BOOTX64.EFI` with UEFI entry, final memory map, serial diagnostics,
  and direct GOP framebuffer drawing.
- GPT/FAT32 removable disk image, structural validation, deterministic builds.

**Current:** Compiled and statically validated. Not emulator/hardware tested.

## Gate 0B — ARM64 firmware handoff (new, parallel)

- Native `BOOTAA64.EFI` with the *same* kernel/firmware-handoff code.
- ARM64 CPU/interrupt/poll primitives; PL011/SBSA early console via SPCR.
- QEMU `virt`-only UART fallback as an explicit separate test build.
- ARM64 and dual-architecture GPT/FAT32 boot images; static checks.
- Negative unit tests for SPCR parser with ASan/UBSan.

**Current:** Compiled and statically validated; host parser tests pass.
Not emulator/hardware tested.

### Gate 0 exit requirements BEFORE advancing either architecture

1. Execute `BOOTX64.EFI` under UEFI/OVMF in at least two virtual configurations.
2. Execute `BOOTAA64.EFI` under AArch64 QEMU/edk2 with serial diagnostics and
   `help`, `status`, `mem`, `cpu`, and `halt` commands.
3. Validate framebuffer on an emulator model with an actual GOP device.
4. Confirm `ExitBootServices` succeeds under several memory-map layouts.
5. Boot both on a documented, noncritical physical UEFI machine/board.
6. Record firmware versions, hardware capabilities, and serial output in tests.

These tests have **not been performed** in this delivery.

## Gate 1 — MMU/interrupt control on both ISAs

- Shared physical page-frame allocator using boot memory map and reservation.
- x86-64 GDT/IDT/TSS, paging, NX, APIC and exception diagnostics.
- ARM64 VBAR, ESR/FAR, TTBR/TCR/MAIR, supported granules, GIC and arch timer.
- No return to firmware page tables, correct cache/device memory attributes,
  shootdowns, invalid-mapping rejection and safe fault reporting.

Exit: verified page isolation and repeatable exception/fault tests on both ISAs.

## Gate 2 — isolated microkernel primitives on both ISAs

- Ring 3 / EL0 user processes, address spaces and privilege transitions.
- Versioned capability table, delegation/revocation, safe syscalls and IPC.
- Preemptive scheduling and process lifetime/resource enforcement.
- Memory and privilege adversarial tests, including malicious user programs.

Exit: process-to-process and process-to-kernel memory isolation demonstrated.

## Gate 3 — minimum independently useful OS services

- PCIe, storage, USB/HID, filesystems, network, graphics, entropy and crypto.
- User-space driver services and device DMA/IOMMU policy.
- Install/recovery pipeline with signed, verifiable updates.

## Gate 4 — permissioned tool ecosystem

- Native loaders for supported ABI targets, isolated WASM host and interpreters.
- User-verified tool manifests, resource metering and auditability.
- Foreign OS/ISA virtual machines and emulators as constrained services.

## Platform policy

Every architecture milestone must have its own compatible boot image and
hardware tests. AArch64 UEFI support does not imply compatibility with locked
phones, Apple Silicon, vendor-boot-only ARM boards, or every new motherboard.
No claims of universally executing any executable format until demonstrated.
