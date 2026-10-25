#include "kernel.h"
#include "uefi_min.h"
#include "arch.h"

static const kernel_boot_info_t *g_boot;
static char g_command[64];
static unsigned g_command_used;

static int equal(const char *a, const char *b) {
    while (*a && *b && *a == *b) { ++a; ++b; }
    return *a == *b;
}

static void print_uint(uint64_t n) {
    char buf[24];
    unsigned used = 0;
    do {
        buf[used++] = (char)('0' + n % 10ULL);
        n /= 10ULL;
    } while (n && used < sizeof(buf));
    while (used) serial_putc(buf[--used]);
}

static uint64_t conventional_pages(void) {
    if (!g_boot || g_boot->memory_descriptor_size < sizeof(EFI_MEMORY_DESCRIPTOR)) return 0;
    uint64_t result = 0;
    uint64_t stride = g_boot->memory_descriptor_size;
    const uint8_t *map = (const uint8_t *)(uintptr_t)g_boot->memory_map_address;
    for (uint64_t offset = 0; offset + sizeof(EFI_MEMORY_DESCRIPTOR) <= g_boot->memory_map_bytes;
         offset += stride) {
        const EFI_MEMORY_DESCRIPTOR *entry = (const EFI_MEMORY_DESCRIPTOR *)(const void *)(map + offset);
        if (entry->Type == EFI_CONVENTIONAL_MEMORY
            && result <= UINT64_MAX - entry->NumberOfPages)
            result += entry->NumberOfPages;
    }
    return result;
}

static void show_cpu(void) {
    arch_print_cpu();
}

static void show_status(void) {
    serial_write("C kernel prototype stage 0; firmware boot services exited.\r\n");
    serial_write("kernel: privileged firmware handoff; user-space isolation: NOT IMPLEMENTED.\r\n");
    serial_write("native tool execution: NOT IMPLEMENTED.\r\n");
    serial_write("framebuffer: ");
    if (g_boot->framebuffer_address) {
        print_uint(g_boot->framebuffer_width);
        serial_putc('x');
        print_uint(g_boot->framebuffer_height);
        serial_write("\r\n");
    } else serial_write("unavailable (serial-only)\r\n");
}

static void show_memory(void) {
    uint64_t pages = conventional_pages();
    serial_write("UEFI conventional RAM remaining: ");
    print_uint(pages);
    serial_write(" pages; ");
    print_uint(pages / 256ULL);
    serial_write(" MiB (approximately).\r\n");
    serial_write("This is firmware's final map, not a live allocator.\r\n");
}

/* Observation-only wire contract. No pointers, write commands or authority. */
static void show_universe(void) {
    static uint64_t sequence;
    serial_write("@LU1 {\"v\":1,\"source\":\"c-native-kernel\",\"event\":\"boot.snapshot\",\"stage\":0,\"arch\":\"");
    serial_write(arch_name());
    serial_write("\",\"sequence\":"); print_uint(++sequence);
    serial_write(",\"firmware_exited\":true,\"user_space_isolation\":false,\"native_tool_execution\":false,\"conventional_pages\":");
    print_uint(conventional_pages());
    serial_write(",\"memory_map_bytes\":"); print_uint(g_boot->memory_map_bytes);
    serial_write(",\"descriptor_size\":"); print_uint(g_boot->memory_descriptor_size);
    serial_write("}\r\n");
}

static void execute_command(const char *command) {
    if (equal(command, "help")) {
        serial_write("commands: help status mem cpu universe halt\r\n");
    } else if (equal(command, "status")) {
        show_status();
        framebuffer_status("STATUS REQUEST RECEIVED");
    } else if (equal(command, "mem")) {
        show_memory();
        framebuffer_status("MEMORY MAP INSPECTED");
    } else if (equal(command, "cpu")) {
        show_cpu();
        framebuffer_status("CPU CAPABILITIES INSPECTED");
    } else if (equal(command, "universe")) {
        show_universe();
    } else if (equal(command, "halt")) {
        serial_write("Halting CPU. Power-cycle to restart.\r\n");
        framebuffer_status("CPU HALTED");
        arch_halt_forever();
    } else if (command[0] != '\0') {
        serial_write("unknown command; type help\r\n");
    }
    serial_write("kernel> ");
}

void kernel_main(const kernel_boot_info_t *boot) {
    if (!boot || boot->magic != KERNEL_BOOT_MAGIC || boot->version != KERNEL_BOOT_VERSION
        || boot->struct_size != sizeof(kernel_boot_info_t)) {
        serial_write("KERNEL PANIC: invalid boot contract\r\n");
        arch_halt_forever();
    }
    g_boot = boot;
    framebuffer_boot_screen(boot);
    serial_write("\r\n=====================================\r\n");
    serial_write("  C-NATIVE BARE-METAL KERNEL v0.2\r\n");
    serial_write("=====================================\r\n");
    show_status();
    show_cpu();
    show_memory();
    show_universe();
    serial_write("Type help. Commands use the detected early serial console.\r\n");
    serial_write("kernel> ");

    /* Stage zero has no IDT, interrupt controller or scheduler yet. Poll COM1 only.
       Not a production idle loop; next milestone implements interrupts + HLT idle. */
    for (;;) {
        int input = serial_getc_nonblocking();
        if (input < 0) { arch_pause(); continue; }
        char ch = (char)input;
        if (ch == '\r' || ch == '\n') {
            serial_write("\r\n");
            g_command[g_command_used] = 0;
            execute_command(g_command);
            g_command_used = 0;
            continue;
        }
        if (ch == 8 || ch == 127) {
            if (g_command_used) {
                --g_command_used;
                serial_write("\b \b");
            }
            continue;
        }
        if (ch >= 32 && ch <= 126 && g_command_used + 1 < sizeof(g_command)) {
            if (ch >= 'A' && ch <= 'Z') ch = (char)(ch - 'A' + 'a');
            g_command[g_command_used++] = ch;
            serial_putc(ch);
        }
    }
}
