#ifndef NATIVE_C_KERNEL_H
#define NATIVE_C_KERNEL_H
#include <stdint.h>
#include <stddef.h>

#define KERNEL_BOOT_MAGIC 0x434b45524e454c31ULL
#define KERNEL_BOOT_VERSION 1U

/* Boot contract: all pointers valid only on the boot platform at kernel entry. */
typedef struct {
    uint64_t magic;
    uint32_t version;
    uint32_t struct_size;
    uint64_t framebuffer_address;
    uint64_t framebuffer_size;
    uint32_t framebuffer_width;
    uint32_t framebuffer_height;
    uint32_t framebuffer_stride;
    uint32_t framebuffer_pixel_format;
    uint64_t memory_map_address;
    uint64_t memory_map_bytes;
    uint64_t memory_descriptor_size;
    uint32_t memory_descriptor_version;
    uint32_t reserved;
} kernel_boot_info_t;

void kernel_main(const kernel_boot_info_t *boot);
void serial_init(void);
void serial_putc(char c);
void serial_write(const char *s);
int serial_getc_nonblocking(void);
void framebuffer_boot_screen(const kernel_boot_info_t *boot);
void framebuffer_status(const char *text);

#endif
