#include "kernel.h"

#define COM1 0x3f8U
static inline void outb(uint16_t port, uint8_t value) {
    __asm__ __volatile__("outb %0, %1" : : "a"(value), "Nd"(port));
}
static inline uint8_t inb(uint16_t port) {
    uint8_t value;
    __asm__ __volatile__("inb %1, %0" : "=a"(value) : "Nd"(port));
    return value;
}

void serial_init(void) {
    outb(COM1 + 1U, 0x00);
    outb(COM1 + 3U, 0x80);
    outb(COM1 + 0U, 0x03);
    outb(COM1 + 1U, 0x00);
    outb(COM1 + 3U, 0x03);
    outb(COM1 + 2U, 0xc7);
    outb(COM1 + 4U, 0x0b);
}

void serial_putc(char ch) {
    /* A missing serial device must not hang the kernel forever. */
    uint32_t spins = 50000U;
    while (spins-- && !(inb(COM1 + 5U) & 0x20U))
        __asm__ __volatile__("pause");
    if (inb(COM1 + 5U) & 0x20U) outb(COM1, (uint8_t)ch);
}

void serial_write(const char *s) {
    if (!s) return;
    while (*s) serial_putc(*s++);
}

int serial_getc_nonblocking(void) {
    if ((inb(COM1 + 5U) & 0x01U) == 0U) return -1;
    return (int)inb(COM1);
}
