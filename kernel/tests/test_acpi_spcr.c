#include "uefi_min.h"
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>

void arm64_early_uart_discover(EFI_SYSTEM_TABLE *system);
uintptr_t arm64_test_uart_base(void);
uint32_t arm64_test_uart_type(void);

static uint8_t rsdp[36];
static uint8_t xsdt[44];
static uint8_t spcr[80];
static EFI_CONFIGURATION_TABLE cfg;
static EFI_SYSTEM_TABLE system_table;

static void put32(uint8_t *p, uint32_t value) {
    for (int i = 0; i < 4; i++) p[i] = (uint8_t)(value >> (i * 8));
}
static void put64(uint8_t *p, uint64_t value) {
    for (int i = 0; i < 8; i++) p[i] = (uint8_t)(value >> (i * 8));
}
static void fix_checksum(uint8_t *p, unsigned count, unsigned check_idx) {
    unsigned sum = 0;
    p[check_idx] = 0;
    for (unsigned i = 0; i < count; i++) sum += p[i];
    p[check_idx] = (uint8_t)(0U - sum);
}
static void init_valid(void) {
    memset(rsdp, 0, sizeof(rsdp));
    memset(xsdt, 0, sizeof(xsdt));
    memset(spcr, 0, sizeof(spcr));
    memset(&cfg, 0, sizeof(cfg));
    memset(&system_table, 0, sizeof(system_table));
    memcpy(rsdp, "RSD PTR ", 8);
    rsdp[15] = 2;
    put32(rsdp + 20, (uint32_t)sizeof(rsdp));
    put64(rsdp + 24, (uintptr_t)xsdt);
    fix_checksum(rsdp, 20, 8);
    fix_checksum(rsdp, sizeof(rsdp), 32);
    memcpy(xsdt, "XSDT", 4);
    put32(xsdt + 4, sizeof(xsdt));
    put64(xsdt + 36, (uintptr_t)spcr);
    fix_checksum(xsdt, sizeof(xsdt), 9);
    memcpy(spcr, "SPCR", 4);
    put32(spcr + 4, sizeof(spcr));
    spcr[36] = 0x03;       /* PL011 */
    spcr[40] = 0;          /* MMIO */
    spcr[41] = 32;         /* register bit width */
    spcr[42] = 0;          /* bit offset */
    spcr[43] = 3;          /* dword access */
    put64(spcr + 44, 0x9000000ULL);
    fix_checksum(spcr, sizeof(spcr), 9);
    cfg.VendorGuid = (EFI_GUID){0x8868e871U, 0xe4f1U, 0x11d3U,
                                {0xbc,0x22,0x00,0x80,0xc7,0x3c,0x88,0x81}};
    cfg.VendorTable = rsdp;
    system_table.ConfigurationTable = &cfg;
    system_table.NumberOfTableEntries = 1;
}
int main(void) {
    init_valid();
    arm64_early_uart_discover(&system_table);
    assert(arm64_test_uart_base() == 0x9000000U);
    assert(arm64_test_uart_type() == 0x03U);
    spcr[36] = 0x0e;
    fix_checksum(spcr, sizeof(spcr), 9);
    arm64_early_uart_discover(&system_table);
    assert(arm64_test_uart_base() == 0x9000000U);
    assert(arm64_test_uart_type() == 0x0eU);
    spcr[36] = 0x01;
    fix_checksum(spcr, sizeof(spcr), 9);
    arm64_early_uart_discover(&system_table);
    assert(arm64_test_uart_base() == 0U); /* Not a supported UART */
    init_valid();
    spcr[56] ^= 1U;
    arm64_early_uart_discover(&system_table);
    assert(arm64_test_uart_base() == 0U); /* Bad SPCR checksum */
    init_valid();
    rsdp[32] ^= 1U;
    arm64_early_uart_discover(&system_table);
    assert(arm64_test_uart_base() == 0U); /* Bad extended RSDP checksum */
    init_valid();
    spcr[40] = 1;
    fix_checksum(spcr, sizeof(spcr), 9);
    arm64_early_uart_discover(&system_table);
    assert(arm64_test_uart_base() == 0U); /* Do not access port I/O on ARM64 */
    arm64_early_uart_discover(NULL);
    assert(arm64_test_uart_base() == 0U);
    puts("PASS: ARM64 ACPI SPCR: PL011/SBSA, absent, invalid checksum, ");
    puts("      unsupported UART, wrong address space, null firmware table.");
    return 0;
}
