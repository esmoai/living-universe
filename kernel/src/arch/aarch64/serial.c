#include "kernel.h"
#include "uefi_min.h"

/* PL011 and SBSA UART: the shared DR/FR register subset. Firmware must have
 * configured the UART; we do not modify its baud rate or interrupt routing.
 * Unmapped/unknown MMIO is NEVER probed. No serial => framebuffer-only mode.
 * Stage 0 inherits firmware's page tables; physical-address MMIO visibility
 * must be validated with emulator/board tests before hardware support claims.
 */
static uintptr_t g_uart_base;
static uint32_t g_uart_type;

#define UART_DR 0x000U
#define UART_FR 0x018U
#define UART_FR_TXFF (1U << 5)
#define UART_FR_RXFE (1U << 4)

static uint8_t bytesum(const uint8_t *ptr, unsigned count) {
    unsigned sum = 0;
    for (unsigned i = 0; i < count; ++i) sum += ptr[i];
    return (uint8_t)sum;
}
static uint32_t le32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static uint64_t le64(const uint8_t *p) {
    return (uint64_t)le32(p) | ((uint64_t)le32(p+4) << 32);
}
static int fourcc(const uint8_t *p, char a, char b, char c, char d) {
    return p[0] == (uint8_t)a && p[1] == (uint8_t)b
        && p[2] == (uint8_t)c && p[3] == (uint8_t)d;
}
static int acpi_table_valid(const uint8_t *table) {
    if (!table) return 0;
    uint32_t length = le32(table + 4);
    if (length < 36U || length > 1024U * 1024U) return 0;
    return bytesum(table, length) == 0U;
}
static int acpi_guid_equal(EFI_GUID a, const EFI_GUID *b) {
    if (a.Data1 != b->Data1 || a.Data2 != b->Data2 || a.Data3 != b->Data3)
        return 0;
    for (unsigned i = 0; i < 8; i++) if (a.Data4[i] != b->Data4[i]) return 0;
    return 1;
}
static void parse_spcr(const uint8_t *spcr) {
    if (!acpi_table_valid(spcr) || !fourcc(spcr, 'S', 'P', 'C', 'R')) return;
    if (le32(spcr+4) < 80U) return;
    uint8_t type = spcr[36];
    if (type != 0x03U && type != 0x0dU && type != 0x0eU) return;
    /* SPCR base-address field is an ACPI Generic Address Structure (GAS). */
    if (spcr[40] != 0U || spcr[42] != 0U) return; /* MMIO, bit offset zero */
    if (spcr[41] && spcr[41] < 32U) return;
    if (spcr[43] && spcr[43] != 3U) return; /* 32-bit access or unspecified */
    uint64_t phys = le64(spcr + 44);
    if (!phys || (phys & 3U) || phys > UINTPTR_MAX - 0x20U) return;
    g_uart_base = (uintptr_t)phys;
    g_uart_type = type;
}
static void parse_acpi2_rsdp(const uint8_t *rsdp) {
    if (!rsdp) return;
    if (!fourcc(rsdp, 'R', 'S', 'D', ' ') ||
        rsdp[4] != 'P' || rsdp[5] != 'T' || rsdp[6] != 'R' || rsdp[7] != ' ')
        return;
    if (bytesum(rsdp, 20U) != 0U || rsdp[15] < 2U) return;
    uint32_t length = le32(rsdp + 20);
    if (length < 36U || length > 4096U || bytesum(rsdp, length) != 0U) return;
    uint64_t xsdt_address = le64(rsdp + 24);
    if (!xsdt_address || xsdt_address > UINTPTR_MAX) return;
    const uint8_t *xsdt = (const uint8_t *)(uintptr_t)xsdt_address;
    if (!acpi_table_valid(xsdt) || !fourcc(xsdt, 'X', 'S', 'D', 'T')) return;
    uint32_t length_xsdt = le32(xsdt + 4);
    if ((length_xsdt - 36U) % 8U != 0U) return;
    unsigned count = (length_xsdt - 36U) / 8U;
    if (count > 1024U) return; /* trust only bounded firmware metadata */
    for (unsigned i = 0; i < count; i++) {
        uint64_t table_address = le64(xsdt + 36U + 8U * i);
        if (!table_address || table_address > UINTPTR_MAX) continue;
        const uint8_t *table = (const uint8_t *)(uintptr_t)table_address;
        if (fourcc(table, 'S', 'P', 'C', 'R')) {
            parse_spcr(table);
            if (g_uart_base) return;
        }
    }
}

void arm64_early_uart_discover(EFI_SYSTEM_TABLE *system) {
    g_uart_base = 0;
    g_uart_type = 0;
    if (system && system->ConfigurationTable) {
        /* ACPI 2.0 configuration table GUID: 8868e871-e4f1-11d3-bc22-0080c73c8881 */
        static const EFI_GUID acpi2 = {
            0x8868e871U,0xe4f1U,0x11d3U,{0xbc,0x22,0x00,0x80,0xc7,0x3c,0x88,0x81}
        };
        const EFI_CONFIGURATION_TABLE *tables =
            (const EFI_CONFIGURATION_TABLE *)system->ConfigurationTable;
        UINTN count = system->NumberOfTableEntries;
        if (count > 256U) count = 256U;
        for (UINTN i = 0; i < count; i++) {
            if (acpi_guid_equal(tables[i].VendorGuid, &acpi2)) {
                parse_acpi2_rsdp((const uint8_t *)tables[i].VendorTable);
                if (g_uart_base) break;
            }
        }
    }
#if defined(CNATIVE_QEMU_VIRT_PL011_FALLBACK)
    /* Deliberately opt-in QEMU virt ONLY. Never assume 0x09000000 on real boards. */
    if (!g_uart_base) { g_uart_base = 0x09000000U; g_uart_type = 0x03U; }
#endif
}

void serial_init(void) { /* UEFI serial configuration is preserved. */ }
void serial_putc(char ch) {
    if (!g_uart_base || !g_uart_type) return;
    volatile uint32_t *fr = (volatile uint32_t *)(g_uart_base + UART_FR);
    volatile uint32_t *dr = (volatile uint32_t *)(g_uart_base + UART_DR);
    unsigned spins = 50000U;
    while (spins-- && (*fr & UART_FR_TXFF)) {
#if defined(__aarch64__)
        __asm__ __volatile__("yield" ::: "memory");
#else
        __asm__ __volatile__("" ::: "memory");
#endif
    }
    if (!(*fr & UART_FR_TXFF)) *dr = (uint32_t)(uint8_t)ch;
}
void serial_write(const char *str) {
    if (!str) return;
    while (*str) serial_putc(*str++);
}
int serial_getc_nonblocking(void) {
    if (!g_uart_base) return -1;
    volatile uint32_t *fr = (volatile uint32_t *)(g_uart_base + UART_FR);
    if (*fr & UART_FR_RXFE) return -1;
    return (int)(*(volatile uint32_t *)(g_uart_base + UART_DR) & 0xffU);
}

#if defined(CNATIVE_TEST_BUILD)
/* Test-only inspection is not linked into release firmware images. */
uintptr_t arm64_test_uart_base(void) { return g_uart_base; }
uint32_t arm64_test_uart_type(void) { return g_uart_type; }
#endif
