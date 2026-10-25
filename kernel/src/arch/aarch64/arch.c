#include "arch.h"
#include "kernel.h"
#include "uefi_min.h"

/* Firmware-assisted serial discovery is separate from the CPU adapter. */
void arm64_early_uart_discover(EFI_SYSTEM_TABLE *system);

void arch_uefi_platform_init(EFI_SYSTEM_TABLE *system) {
    arm64_early_uart_discover(system);
}
void arch_disable_interrupts(void) {
    __asm__ __volatile__("msr daifset, #0xf" ::: "memory");
}
void arch_pause(void) { __asm__ __volatile__("yield" ::: "memory"); }
_Noreturn void arch_halt_forever(void) {
    arch_disable_interrupts();
    for (;;) __asm__ __volatile__("wfi" ::: "memory");
}
const char *arch_name(void) { return "AArch64"; }

static void print_hex64(uint64_t number) {
    static const char digits[] = "0123456789ABCDEF";
    for (int nibble = 15; nibble >= 0; nibble--)
        serial_putc(digits[(unsigned)((number >> (nibble * 4)) & 0xfU)]);
}
void arch_print_cpu(void) {
    uint64_t midr, mpidr, currentel;
    __asm__ __volatile__("mrs %0, midr_el1" : "=r"(midr));
    __asm__ __volatile__("mrs %0, mpidr_el1" : "=r"(mpidr));
    __asm__ __volatile__("mrs %0, CurrentEL" : "=r"(currentel));
    serial_write("architecture: AArch64; MIDR_EL1=0x");
    print_hex64(midr);
    serial_write("; MPIDR_EL1=0x");
    print_hex64(mpidr);
    serial_write("; EL=");
    serial_putc((char)('0' + ((currentel >> 2) & 3U)));
    serial_write("\r\n");
}
