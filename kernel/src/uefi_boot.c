#include "uefi_min.h"
#include "kernel.h"
#include "arch.h"

/* A fixed early map buffer avoids firmware allocation between map and ExitBootServices. */
#define EARLY_MEMORY_MAP_BYTES (256U * 1024U)
static uint8_t g_memory_map[EARLY_MEMORY_MAP_BYTES] __attribute__((aligned(16)));
static kernel_boot_info_t g_boot_info;
/* Ensure a PE base-relocation entry exists for firmware relocation support. */
static void *volatile g_image_relocation_anchor = &g_boot_info;
static EFI_GUID g_gop_guid = {
    0x9042a9deU, 0x23dcU, 0x4a38U, {0x96U,0xfbU,0x7aU,0xdeU,0xd0U,0x80U,0x51U,0x6aU}
};

static void fw_print(EFI_SYSTEM_TABLE *system, CHAR16 *msg) {
    if (system && system->ConOut && system->ConOut->OutputString)
        (void)system->ConOut->OutputString(system->ConOut, msg);
}

EFI_STATUS EFIAPI efi_main(EFI_HANDLE image_handle, EFI_SYSTEM_TABLE *system) {
    if (!system || !system->BootServices) return EFI_INVALID_PARAMETER;
    if (g_image_relocation_anchor != &g_boot_info) return EFI_INVALID_PARAMETER;
    EFI_BOOT_SERVICES *bs = system->BootServices;
    arch_uefi_platform_init(system);
    serial_init();
    serial_write("\r\n[C kernel] UEFI firmware entry\r\n");
    fw_print(system, (CHAR16 *)L"Native C kernel: preparing firmware handoff...\r\n");

    g_boot_info.magic = KERNEL_BOOT_MAGIC;
    g_boot_info.version = KERNEL_BOOT_VERSION;
    g_boot_info.struct_size = (uint32_t)sizeof(g_boot_info);
    g_boot_info.memory_map_address = (uint64_t)(uintptr_t)g_memory_map;

    EFI_GRAPHICS_OUTPUT_PROTOCOL *gop = (void *)0;
    if (bs->LocateProtocol(&g_gop_guid, (void *)0, (void **)&gop) == EFI_SUCCESS
        && gop && gop->Mode && gop->Mode->Info) {
        EFI_GRAPHICS_OUTPUT_PROTOCOL_MODE *mode = gop->Mode;
        EFI_GRAPHICS_OUTPUT_MODE_INFORMATION *info = mode->Info;
        if (info->PixelFormat <= 1U && info->PixelsPerScanLine >= info->HorizontalResolution
            && info->HorizontalResolution > 0 && info->VerticalResolution > 0) {
            g_boot_info.framebuffer_address = mode->FrameBufferBase;
            g_boot_info.framebuffer_size = mode->FrameBufferSize;
            g_boot_info.framebuffer_width = info->HorizontalResolution;
            g_boot_info.framebuffer_height = info->VerticalResolution;
            g_boot_info.framebuffer_stride = info->PixelsPerScanLine;
            g_boot_info.framebuffer_pixel_format = info->PixelFormat;
        }
    }
    if (bs->SetWatchdogTimer)
        (void)bs->SetWatchdogTimer(0, 0, 0, (CHAR16 *)0);

    /* Do not allocate, print via UEFI or modify protocols between GetMemoryMap and ExitBootServices. */
    EFI_STATUS status = EFI_INVALID_PARAMETER;
    for (int attempt = 0; attempt < 4; attempt++) {
        UINTN map_size = sizeof(g_memory_map);
        UINTN map_key = 0;
        UINTN descriptor_size = 0;
        uint32_t descriptor_version = 0;
        status = bs->GetMemoryMap(&map_size, (EFI_MEMORY_DESCRIPTOR *)g_memory_map,
                                  &map_key, &descriptor_size, &descriptor_version);
        if (status != EFI_SUCCESS) break;
        if (descriptor_size < sizeof(EFI_MEMORY_DESCRIPTOR) || descriptor_size == 0
            || descriptor_version != EFI_MEMORY_DESCRIPTOR_VERSION) {
            status = EFI_INVALID_PARAMETER;
            break;
        }
        g_boot_info.memory_map_bytes = map_size;
        g_boot_info.memory_descriptor_size = descriptor_size;
        g_boot_info.memory_descriptor_version = descriptor_version;
        status = bs->ExitBootServices(image_handle, map_key);
        if (status == EFI_SUCCESS) {
            /* From here onward: no UEFI boot service calls. */
            arch_disable_interrupts();
            kernel_main(&g_boot_info);
            arch_halt_forever();
        }
        if (status != EFI_INVALID_PARAMETER) break;
    }
    serial_write("[C kernel] ERROR: firmware handoff unsuccessful\r\n");
    /* Firmware console may be unavailable after a failed ExitBootServices attempt. */
    return status;
}
