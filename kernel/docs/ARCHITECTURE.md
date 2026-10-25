# Architecture — one C kernel, multiple independent ISA ports

## Purpose

Stage 0 v0.2 supports freestanding **x86-64 UEFI** and **AArch64 UEFI** side by
side. It is still **firmware handoff**, not a working secure operating system.
Later kernel milestones will establish privilege-separated processes, scheduling,
capabilities and IPC before external code is ever executed.

```
                   SHARED KERNEL CODE (freestanding C)
                src/kernel.c | src/framebuffer.c
                            |
                  boot_info ABI v1 (stable)
                            |
                   include/arch.h adapter
                  /                        \
       x86_64 (UEFI)                       AArch64 (UEFI)
       CPUID, CLI, HLT                      MIDR, DAIF, WFI
       COM1 port I/O                       PL011/SBSA MMIO (SPCR)
       EFIAPI ms_abi                       EFIAPI AAPCS64
                 \                        /
               SAME UEFI HANDOFF (src/uefi_boot.c)
                              |
         GPT/FAT32 ESP: BOOTX64.EFI and BOOTAA64.EFI
```

The standard UEFI boot path is architecture-selected by firmware. ARM64 and x86
binaries share semantics and versioned in-memory contracts but do not share
instructions. Each **must be compiled for its own ISA**.

## Shared Stage 0 boot contract

- UEFI entry: obtain GOP framebuffer if available; disable UEFI watchdog;
  acquire final memory map; call `ExitBootServices` with an accepted map key.
- Kernel entry: validate the magic/version/size of `kernel_boot_info_t`;
  render a framebuffer boot screen; report platform CPU and available memory.
- Memory map sizes are in the EFI convention (4 KiB pages) irrespective of
  later ARM64 translation-granule support (4/16/64 KiB on some processors).
- Serial functionality is optional. x86 assumes the traditional COM1 device;
  ARM64 accepts only firmware-declared PL011/SBSA UART or an **explicitly
  requested** QEMU-virt test profile.
- AArch64 UEFI firmware calling convention uses AAPCS64; x86-64 UEFI uses
  Microsoft x64. `uefi_min.h` selects the correct ABI at compile time.

## ARM64 bring-up details

- The generic ARM64 adapter reads `MIDR_EL1`, `MPIDR_EL1` and `CurrentEL`.
- Interrupt masking uses DAIF; spin uses YIELD; halt uses WFI. No scheduler,
  vector table, or interrupt controller is installed yet.
- UART discovery traverses UEFI ACPI 2.0 configuration, validates RSDP/XSDT/
  SPCR checksums and lengths, and accepts only PL011/Arm SBSA MMIO UARTs.
- Boards advertising no supported UART can still reach kernel C execution,
  but commands are unavailable without a console until later input drivers.
- The QEMU-only variant can fall back to PL011 at `0x09000000`; **never** use
  that fallback on unknown real ARM64 hardware.
- No Device Tree parsing, EFI Runtime Services, or EL2/EL1 transitions are
  implemented. No attempt to access arbitrary board registers is made.

## Hardware independence caveats

Bare metal is not firmware-free. UEFI has to initialize enough of the hardware
and CPU to reach the EFI application. Board-specific firmware/boot straps remain
necessary. AArch64 is particularly platform-diverse: SoC/vendor variants require
independent board validation and, eventually, dedicated platform drivers.

## Kernel target architecture — later gates, not delivered

**Gate 1, in parallel on both ISAs:**

| Responsibility | x86-64 planned implementation | AArch64 planned implementation |
|---|---|---|
| Exceptions | IDT/GDT/TSS | vector table via `VBAR_EL1`, ESR/FAR diagnostics |
| Virtual memory | CR3, x86 page tables, NX | TTBR/TCR/MAIR, supported translation granules, execute-never |
| Timers | APIC / TSC and calibrated clock | architected Generic Timer |
| Interrupt controller | LAPIC / IOAPIC or x2APIC | GICv2/v3 depending on platform |
| Topology | ACPI, CPUID | ACPI or Device Tree, MPIDR |
| DMA isolation | VT-d / AMD-Vi | Arm SMMU/IOMMU |
| Preemption | ring 0 to ring 3 | EL1 to EL0 |

**Gate 2:** native user-space process isolation, object-capability handles,
resource budgets, verified IPC, safe recovery. Drivers and language engines
run outside the kernel; never load untrusted modules into supervisor memory.

**Gate 3:** storage, USB/HID, networking, displays, filesystems, crypto and
installation on a documented hardware support matrix.

**Gate 4:** isolated native app, WASM/WASI and interpreted-tool execution;
foreign-ISA emulators and guest OS virtualization.

## CPU execution and security principle

This kernel will run **natively** on each supported architecture. Universal
tool support is a later *OS compatibility and isolation* problem, not a property
conferred by C. A Windows EXE, Linux ELF, or downloaded file cannot currently
be run by Stage 0 on either CPU.
