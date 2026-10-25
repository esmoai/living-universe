#include "kernel.h"

/* Early framebuffer only: no fonts, terminal dependencies, firmware calls or heap. */
static const kernel_boot_info_t *g_boot;
static uint32_t g_status_row;

/* Tiny 5x7 glyphs (space, digits, uppercase ASCII and punctuation). */
static const uint8_t FONT_DIGITS[10][7] = {
 {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},
 {30,1,1,14,1,1,30},{2,6,10,18,31,2,2},{31,16,16,30,1,1,30},
 {14,16,16,30,17,17,14},{31,1,2,4,8,8,8},{14,17,17,14,17,17,14},
 {14,17,17,15,1,1,14}
};
static const uint8_t FONT_UPPER[26][7] = {
 {14,17,17,31,17,17,17},{30,17,17,30,17,17,30},{15,16,16,16,16,16,15},
 {30,17,17,17,17,17,30},{31,16,16,30,16,16,31},{31,16,16,30,16,16,16},
 {15,16,16,23,17,17,15},{17,17,17,31,17,17,17},{14,4,4,4,4,4,14},
 {7,2,2,2,18,18,12},{17,18,20,24,20,18,17},{16,16,16,16,16,16,31},
 {17,27,21,21,17,17,17},{17,25,21,19,17,17,17},{14,17,17,17,17,17,14},
 {30,17,17,30,16,16,16},{14,17,17,17,21,18,13},{30,17,17,30,20,18,17},
 {15,16,16,14,1,1,30},{31,4,4,4,4,4,4},{17,17,17,17,17,17,14},
 {17,17,17,17,17,10,4},{17,17,17,21,21,21,10},{17,17,10,4,10,17,17},
 {17,17,10,4,4,4,4},{31,1,2,4,8,16,31}
};
static const uint8_t FONT_PUNCT[5][7] = {
 {0,0,0,0,0,0,0}, /* space */
 {0,4,4,0,4,4,0}, /* colon */
 {0,0,0,31,0,0,0}, /* dash */
 {0,0,0,0,0,12,12}, /* dot */
 {1,2,2,4,8,8,16} /* slash */
};

static uint32_t rgb(uint8_t r, uint8_t g, uint8_t b) {
    /* GOP format 0: RGB byte order. GOP format 1: BGR byte order. */
    if (g_boot && g_boot->framebuffer_pixel_format == 0U)
        return (uint32_t)r | ((uint32_t)g << 8) | ((uint32_t)b << 16);
    return (uint32_t)b | ((uint32_t)g << 8) | ((uint32_t)r << 16);
}

static void pixel(uint32_t x, uint32_t y, uint32_t color) {
    if (!g_boot || !g_boot->framebuffer_address) return;
    if (x >= g_boot->framebuffer_width || y >= g_boot->framebuffer_height) return;
    uint64_t index = (uint64_t)y * g_boot->framebuffer_stride + x;
    if (index >= g_boot->framebuffer_size / 4U) return;
    ((volatile uint32_t *)(uintptr_t)g_boot->framebuffer_address)[index] = color;
}

static void fill(uint32_t x, uint32_t y, uint32_t w, uint32_t h, uint32_t color) {
    if (!g_boot || !g_boot->framebuffer_address) return;
    uint32_t maxx = g_boot->framebuffer_width;
    uint32_t maxy = g_boot->framebuffer_height;
    if (x >= maxx || y >= maxy) return;
    uint32_t endx = (w > maxx - x) ? maxx : x + w;
    uint32_t endy = (h > maxy - y) ? maxy : y + h;
    for (uint32_t py = y; py < endy; py++)
        for (uint32_t px = x; px < endx; px++) pixel(px, py, color);
}

static const uint8_t *glyph(char c) {
    if (c >= '0' && c <= '9') return FONT_DIGITS[(unsigned)(c - '0')];
    if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');
    if (c >= 'A' && c <= 'Z') return FONT_UPPER[(unsigned)(c - 'A')];
    if (c == ':') return FONT_PUNCT[1];
    if (c == '-') return FONT_PUNCT[2];
    if (c == '.') return FONT_PUNCT[3];
    if (c == '/') return FONT_PUNCT[4];
    return FONT_PUNCT[0];
}

static void text(uint32_t x, uint32_t y, const char *message, uint32_t scale, uint32_t color) {
    if (!message || scale == 0) return;
    for (size_t i = 0; message[i] && i < 112; i++) {
        if (x + 6U * scale >= (g_boot ? g_boot->framebuffer_width : 0)) break;
        const uint8_t *shape = glyph(message[i]);
        for (uint32_t row = 0; row < 7; row++) {
            for (uint32_t col = 0; col < 5; col++) {
                if (shape[row] & (1U << (4U - col)))
                    fill(x + col * scale, y + row * scale, scale, scale, color);
            }
        }
        x += 6U * scale;
    }
}

void framebuffer_boot_screen(const kernel_boot_info_t *boot) {
    g_boot = boot;
    if (!boot || !boot->framebuffer_address) return;
    uint32_t bg = rgb(10, 17, 32);
    uint32_t accent = rgb(52, 211, 187);
    uint32_t body = rgb(205, 222, 242);
    fill(0, 0, boot->framebuffer_width, boot->framebuffer_height, bg);
    fill(0, 0, boot->framebuffer_width, 7U, accent);
    uint32_t scale = boot->framebuffer_width >= 820 ? 3U : 2U;
    text(36, 46, "C NATIVE KERNEL", scale, accent);
    text(36, 102, "BARE METAL BOOT CONFIRMED", 2, body);
    text(36, 144, "UEFI BOOT SERVICES EXITED", 2, body);
    text(36, 186, "NO WINDOWS OR LINUX HOST", 2, body);
    fill(36, 240, (boot->framebuffer_width > 100 ? boot->framebuffer_width - 72 : 0), 2, rgb(42, 75, 94));
    text(36, 260, "STAGE ZERO - HARDWARE BRINGUP", 2, accent);
    text(36, 300, "COM1 SERIAL CONSOLE ENABLED", 2, body);
    text(36, 340, "TYPE HELP ON SERIAL PORT", 2, body);
    text(36, 398, "NOT YET A GENERAL PURPOSE OS", 1, rgb(137, 158, 179));
    g_status_row = 443;
}

void framebuffer_status(const char *message) {
    if (!g_boot || !g_boot->framebuffer_address || !message) return;
    if (g_status_row + 20 >= g_boot->framebuffer_height) g_status_row = 443;
    fill(36, g_status_row, (g_boot->framebuffer_width > 90 ? g_boot->framebuffer_width - 72 : 0), 14,
         rgb(10, 17, 32));
    text(36, g_status_row, message, 1, rgb(200, 212, 230));
    g_status_row += 17;
}
