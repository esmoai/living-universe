#include "arch.h"
#include "kernel.h"
#include "uefi_min.h"

void arch_uefi_platform_init(EFI_SYSTEM_TABLE *system) { (void)system; }
void arch_disable_interrupts(void) { __asm__ __volatile__("cli" ::: "memory"); }
void arch_pause(void) { __asm__ __volatile__("pause" ::: "memory"); }
_Noreturn void arch_halt_forever(void) {
    arch_disable_interrupts();
    for (;;) __asm__ __volatile__("hlt" ::: "memory");
}
const char *arch_name(void) { return "x86-64"; }
void arch_print_cpu(void) {
    uint32_t eax, ebx, ecx, edx;
    __asm__ __volatile__("cpuid" : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx)
                       : "a"(0U), "c"(0U));
    char vendor[13];
    uint32_t registers[3] = {ebx, edx, ecx};
    for (unsigned i = 0; i < 3; i++)
        for (unsigned j = 0; j < 4; j++)
            vendor[4U * i + j] = (char)((registers[i] >> (8U * j)) & 0xffU);
    vendor[12] = 0;
    serial_write("architecture: x86-64; cpu vendor: ");
    serial_write(vendor);
    serial_write("\r\n");
}
