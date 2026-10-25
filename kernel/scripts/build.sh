#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
: "${CC:=clang}"
: "${LINKER:=lld-link}"
mkdir -p build/x86_64 build/aarch64 build/aarch64_virt
COMMON="-std=c17 -O2 -ffreestanding -fno-builtin -fno-stack-protector -fno-asynchronous-unwind-tables -fno-unwind-tables -fno-ident -fshort-wchar -Wall -Wextra -Werror -Iinclude"

compile_target() {
    target="$1"
    triple="$2"
    arch="$3"
    platform_flag="$4"
    extra="$5"
    objects=""
    for item in src/uefi_boot.c src/kernel.c src/framebuffer.c "src/arch/$arch/arch.c" "src/arch/$arch/serial.c"; do
        obj="build/$target/$(basename "${item%.c}").obj"
        "$CC" -target "$triple" $COMMON $platform_flag $extra -c "$item" -o "$obj"
        objects="$objects $obj"
    done
    if [ "$arch" = x86_64 ]; then
        machine=x64; filename=BOOTX64.EFI
    else
        machine=arm64; filename=BOOTAA64.EFI
    fi
    # shellcheck disable=SC2086
    "$LINKER" /nologo /machine:"$machine" /subsystem:efi_application /entry:efi_main \
        /nodefaultlib /Brepro /dynamicbase /nxcompat \
        /out:"build/$target/$filename" $objects
}
compile_target x86_64 x86_64-pc-windows-msvc x86_64 -mno-red-zone ""
compile_target aarch64 aarch64-pc-windows-msvc aarch64 "" ""
compile_target aarch64_virt aarch64-pc-windows-msvc aarch64 "" "-DCNATIVE_QEMU_VIRT_PL011_FALLBACK=1"

python3 scripts/make_disk.py --output build/c-native-kernel-x86_64-uefi.img --x64 build/x86_64/BOOTX64.EFI
python3 scripts/make_disk.py --output build/c-native-kernel-aarch64-uefi.img --arm64 build/aarch64/BOOTAA64.EFI
python3 scripts/make_disk.py --output build/c-native-kernel-aarch64-qemu-virt.img --arm64 build/aarch64_virt/BOOTAA64.EFI
python3 scripts/make_disk.py --output build/c-native-kernel-dual-uefi.img --x64 build/x86_64/BOOTX64.EFI --arm64 build/aarch64/BOOTAA64.EFI

python3 scripts/check_image.py --image build/c-native-kernel-x86_64-uefi.img --x64 build/x86_64/BOOTX64.EFI
python3 scripts/check_image.py --image build/c-native-kernel-aarch64-uefi.img --arm64 build/aarch64/BOOTAA64.EFI
python3 scripts/check_image.py --image build/c-native-kernel-aarch64-qemu-virt.img --arm64 build/aarch64_virt/BOOTAA64.EFI
python3 scripts/check_image.py --image build/c-native-kernel-dual-uefi.img --x64 build/x86_64/BOOTX64.EFI --arm64 build/aarch64/BOOTAA64.EFI
(cd build && sha256sum x86_64/BOOTX64.EFI aarch64/BOOTAA64.EFI aarch64_virt/BOOTAA64.EFI \
    c-native-kernel-x86_64-uefi.img c-native-kernel-aarch64-uefi.img \
    c-native-kernel-aarch64-qemu-virt.img c-native-kernel-dual-uefi.img > SHA256SUMS)
printf '\nBuild complete: x86-64, ARM64 UEFI, ARM64 QEMU virt, dual-architecture UEFI media.\n'
