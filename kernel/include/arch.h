#ifndef CNATIVE_ARCH_H
#define CNATIVE_ARCH_H

/* Architecture-port boundary. Shared core knows no ISA-specific instructions. */
struct EFI_SYSTEM_TABLE;
void arch_uefi_platform_init(struct EFI_SYSTEM_TABLE *system);
void arch_disable_interrupts(void);
void arch_pause(void);
_Noreturn void arch_halt_forever(void);
void arch_print_cpu(void);
const char *arch_name(void);

#endif
