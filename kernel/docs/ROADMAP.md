# Dual-architecture kernel roadmap

## Stage 0 evidence

The shared C core and both native UEFI ports compile. Public CI commit b1126982843b9ab51290fa3e935ad0ecafa13052 performed actual x86-64 q35/OVMF and AArch64 virt/AAVMF boots. Both passed help/status/cpu/mem/universe and schema/architecture validation. ARM used the explicit QEMU UART profile. See ../../docs/VALIDATION.md and the real serial logs.

This is the first emulator smoke gate, not complete hardware qualification. Wider memory-map configurations, the generic ARM64 image and firmware discovery, visual framebuffer tests, faults and physical machines remain open. No test fixture may substitute for a real boot.

## Gate 1: independent hardware control on both ISAs

Implement physical allocation, reserved-memory accounting, controlled page tables, W^X/NX attributes, exception handling and recoverable diagnostics. x86 needs GDT/IDT/TSS and APIC/timers; ARM64 needs vectors/ESR/FAR, TTBR/TCR/MAIR, GIC and architected timers. Validate mapping, caches, TLB behavior and fault tests per platform.

## Gate 2: isolated microkernel tasks

Add ring 3 / EL0 transitions, separated address spaces, capability handles with delegation and revocation, checked syscalls/IPC, preemption and budgets. Demonstrate containment of malformed messages, forged handles, memory violations, exhaustion and crashes before executing external programs.

## Gate 3: independently useful services

Drivers for declared hardware, storage/filesystems, USB/HID, networking, graphics, entropy and cryptography. Keep most complex services outside privileged kernel memory. Validate DMA/IOMMU policy and a verified recoverable update chain.

## Gate 4: permissioned tools

Native loaders for explicit ABIs, isolated WASM and interpreter hosts, monitored resource limits and authentic package provenance. Foreign OS/ISA compatibility needs a declared VM/emulator path, not an assertion that C executes any binary.

Every claim must name its tested configuration. ARM64 does not imply phones, Apple Silicon or all vendor boards. RISC-V and other architectures require separate ports.
