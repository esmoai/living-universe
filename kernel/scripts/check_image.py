#!/usr/bin/env python3
"""Check PE32+ machine/EFI subsystem, GPT CRCs, FAT32 and both boot files.

Structural validation is NOT a firmware-boot test or security certification.
"""
import argparse
import pathlib
import struct
import zlib

EFI_NAMES = {'x64': b'BOOTX64 EFI', 'arm64': b'BOOTAA64EFI'}
MACHINES = {'x64': 0x8664, 'arm64': 0xAA64}


def u16(data, off): return struct.unpack_from('<H', data, off)[0]
def u32(data, off): return struct.unpack_from('<I', data, off)[0]
def u64(data, off): return struct.unpack_from('<Q', data, off)[0]


def validate_pe(efi, arch):
    assert efi[:2] == b'MZ', 'not a PE executable'
    pe = u32(efi, 0x3c)
    assert efi[pe:pe + 4] == b'PE\0\0', 'PE signature missing'
    assert u16(efi, pe + 4) == MACHINES[arch], f'wrong PE machine for {arch}'
    opt = pe + 24
    assert u16(efi, opt) == 0x20b, 'not PE32+'
    assert u16(efi, opt + 68) == 10, 'not UEFI application subsystem'
    assert u32(efi, opt + 16) != 0, 'zero entrypoint RVA'
    # A freestanding UEFI boot image does not import hosted runtime DLLs.
    assert u32(efi, opt + 112 + 8) == 0, 'unexpected imported runtime DLLs'
    assert u32(efi, opt + 112 + 12) == 0, 'unexpected import directory'
    reloc_rva = u32(efi, opt + 112 + 5 * 8)
    reloc_size = u32(efi, opt + 112 + 5 * 8 + 4)
    assert reloc_rva != 0 and reloc_size >= 8, 'missing EFI base relocations'


def check_image(path, binaries):
    data = pathlib.Path(path).read_bytes()
    assert data[510:512] == b'\x55\xaa' and data[450] == 0xee
    assert len(data) % 512 == 0 and len(data) >= 64 * 1024 * 1024
    sectors = len(data) // 512
    def sector(lba): return data[lba * 512:(lba + 1) * 512]
    entries = data[2*512:34*512]
    assert entries == data[(sectors - 33)*512:(sectors - 1)*512], 'GPT partition array mismatch'
    for lba, alternate, entry_lba in ((1, sectors-1, 2),
                                      (sectors-1, 1, sectors-33)):
        h = sector(lba)
        assert h[:8] == b'EFI PART'
        assert u64(h, 24) == lba and u64(h, 32) == alternate
        assert u64(h, 72) == entry_lba
        hsize = u32(h, 12)
        assert hsize == 92
        hc = bytearray(h[:hsize])
        header_crc = u32(h, 16)
        struct.pack_into('<I', hc, 16, 0)
        assert zlib.crc32(hc) & 0xffffffff == header_crc, 'GPT header CRC failed'
        assert zlib.crc32(entries) & 0xffffffff == u32(h, 88), 'GPT entry CRC failed'
    esp_start = u64(entries, 32)
    esp_end = u64(entries, 40)
    assert 0 < esp_start < esp_end < sectors
    vbr = sector(esp_start)
    assert vbr[510:512] == b'\x55\xaa'
    assert u16(vbr, 11) == 512 and vbr[13] == 1 and vbr[16] == 2
    assert u16(vbr, 14) == 32 and u16(vbr, 17) == 0
    assert u32(vbr, 44) == 2 and vbr[82:90] == b'FAT32   '
    assert u32(vbr, 32) == esp_end - esp_start + 1
    fat_start = esp_start + u16(vbr, 14)
    fat_sectors = u32(vbr, 36)
    data_start = fat_start + vbr[16] * fat_sectors
    fat = data[fat_start*512:(fat_start+fat_sectors)*512]
    assert fat == data[(fat_start+fat_sectors)*512:(fat_start+2*fat_sectors)*512]
    def cluster(n): return sector(data_start + n - 2)
    def find_entry(directory, name):
        raw = cluster(directory)
        for offset in range(0, 512, 32):
            item = raw[offset:offset+32]
            if item[:11] == name:
                return (u16(item, 26) | u16(item, 20) << 16), u32(item, 28)
        raise AssertionError(f'missing FAT entry {name!r}')
    efi_dir, _ = find_entry(2, b'EFI        ')
    boot_dir, _ = find_entry(efi_dir, b'BOOT       ')
    actual_names = {cluster(boot_dir)[i:i+11] for i in range(64,512,32)
                    if cluster(boot_dir)[i] not in (0, 0xe5)}
    assert actual_names == {EFI_NAMES[key] for key in binaries}, 'unexpected EFI entries'
    allocated = set()
    for key, image in binaries.items():
        validate_pe(image, key)
        start, size = find_entry(boot_dir, EFI_NAMES[key])
        assert size == len(image)
        recovered = bytearray()
        visited = set()
        current = start
        while current < 0x0ffffff8:
            assert current not in visited and current >= 5
            assert current not in allocated, 'FAT files have overlapping clusters'
            visited.add(current)
            allocated.add(current)
            recovered.extend(cluster(current))
            assert len(recovered) <= len(image) + 512
            current = u32(fat, current*4) & 0x0fffffff
        assert bytes(recovered[:size]) == image, f'{key} PE does not match ESP'
        print(f'PASS: {key}: PE32+ subsystem/machine/relocations and boot content')
    print('PASS: primary+backup GPT CRCs, FAT32, mirrored FATs, disk paths')
    print('NOTE: STATIC validation only. No firmware execution is established.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--image', type=pathlib.Path, required=True)
    ap.add_argument('--x64', type=pathlib.Path)
    ap.add_argument('--arm64', type=pathlib.Path)
    args = ap.parse_args()
    images = {}
    if args.x64: images['x64'] = args.x64.read_bytes()
    if args.arm64: images['arm64'] = args.arm64.read_bytes()
    if not images: ap.error('Provide --x64 and/or --arm64')
    check_image(args.image, images)


if __name__ == '__main__':
    main()
