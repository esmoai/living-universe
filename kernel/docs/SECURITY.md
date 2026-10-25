# Security charter — dual-architecture Stage 0

## Do not infer sandboxing from bare-metal execution

This build has **no secure user-process isolation**. It is a privileged firmware
handoff experiment. The C code has privileged CPU access and inherits
firmware-created memory mappings. It must not load or execute third-party code.
A separate ELF/PE/WASM loader and safe tooling environment are intentionally
NOT included until later gates.

## Trust model

- The device firmware, its ACPI tables and its initial page tables are trusted
  inputs at Stage 0; malicious firmware is outside current protection.
- ARM64 ACPI SPCR is checksum-validated, bounded in length and constrained to
  known UART interface types. These checks improve robustness but do not turn
  firmware data into a fully untrusted-memory-safe interface.
- x86-64 COM1 and ARM64 PL011/SBSA console are early diagnostics only.
  ARM64's MMIO access assumes the relevant firmware mapping remains valid
  after `ExitBootServices`, which must be tested for each supported platform.
- Signed boot media, kernel image signature checks, IOMMU isolation,
  authentication, user authorization and permission enforcement are FUTURE WORK.

## Required later invariants

1. Ring 3 (x86-64) / EL0 (AArch64) separation from the supervisor kernel.
2. CPU page tables deny ungranted memory; W^X execution policy where supported.
3. Bounds-validated IPC and revocable unforgeable resource handles.
4. Drivers and external runtimes kept out of privileged kernel address space.
5. Explicit per-tool CPU/memory/time/I/O/resource budgets.
6. Verified package/boot signatures, rollback protections and recoverability.
7. Per-architecture exception/fault and DMA isolation tests.
8. Never silently weaken required isolation when a hardware feature is missing.

## Stage 0 tests done

- Cross-compile x86-64 and AArch64 as freestanding UEFI PE32+.
- Validate PE headers, entrypoints and relocation directory.
- Validate GPT primary/backup checksums, dual ESP boot files and FAT32 chains.
- Run host sanitizer unit tests exercising valid and invalid ACPI SPCR metadata.
- Check deterministic outputs from repeated builds.

## Stage 0 tests NOT done

- No QEMU/OVMF or physical firmware boot execution has been completed here.
- No coverage of actual ARM hardware MMIO mappings or GOP.
- No independent MMU/page-table ownership or exception vectors.
- No isolation, hardware access controls or execution of untrusted programs.
