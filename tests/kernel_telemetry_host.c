/* Host-side wire-format test of the actual shared kernel function.
 * This does NOT boot firmware or execute either target ISA. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../kernel/src/kernel.c"
static const char *test_arch = "x86-64";
void serial_putc(char c) { putchar(c); }
void serial_write(const char *s) { fputs(s, stdout); }
int serial_getc_nonblocking(void) { return -1; }
void serial_init(void) {}
void framebuffer_boot_screen(const kernel_boot_info_t *b) { (void)b; }
void framebuffer_status(const char *s) { (void)s; }
void arch_print_cpu(void) {}
void arch_pause(void) {}
_Noreturn void arch_halt_forever(void) { abort(); }
const char *arch_name(void) { return test_arch; }
int main(void) {
    EFI_MEMORY_DESCRIPTOR map[3]; memset(map, 0, sizeof map);
    map[0].Type=EFI_CONVENTIONAL_MEMORY; map[0].NumberOfPages=4096;
    map[1].Type=EFI_CONVENTIONAL_MEMORY; map[1].NumberOfPages=17;
    map[2].Type=0; map[2].NumberOfPages=999;
    kernel_boot_info_t boot; memset(&boot,0,sizeof boot);
    boot.memory_map_address=(uintptr_t)map; boot.memory_map_bytes=sizeof map;
    boot.memory_descriptor_size=sizeof map[0]; g_boot=&boot;
    if (conventional_pages()!=4113) return 1;
    puts("# LU_TEST_FIXTURE - host execution of telemetry formatter, NOT firmware boot");
    show_universe(); test_arch="AArch64"; show_universe();
    boot.memory_descriptor_size=0;
    if (conventional_pages()!=0) return 2;
    return 0;
}
