#!/usr/bin/env python3
"""Deterministic GPT/FAT32 UEFI media, single- or dual-architecture.

Uses standard-library only. Each EFI image gets its architecture-defined
removable boot path. Never run this on a real block device: it writes an image.
"""
import argparse
import math
import pathlib
import struct
import uuid
import zlib

SECTOR = 512
DISK_SECTORS = 131072  # 64 MiB (whole image)
ESP_START = 2048
ESP_LAST = DISK_SECTORS - 34
ESP_SECTORS = ESP_LAST - ESP_START + 1
RESERVED_SECTORS = 32
FAT_COUNT = 2
FAT_SECTORS = 1024
SECTORS_PER_CLUSTER = 1
DATA_START = ESP_START + RESERVED_SECTORS + FAT_COUNT * FAT_SECTORS
CLUSTER_COUNT = (ESP_SECTORS - RESERVED_SECTORS - FAT_COUNT * FAT_SECTORS)
EFI_SYSTEM_PARTITION_TYPE = uuid.UUID('c12a7328-f81f-11d2-ba4b-00a0c93ec93b')
EFI_NAMES = {'x64': b'BOOTX64 EFI', 'arm64': b'BOOTAA64EFI'}


def boot_dir_entry(name11: bytes, attr: int, cluster: int, size: int = 0) -> bytes:
    assert len(name11) == 11
    ent = bytearray(32)
    ent[:11] = name11
    ent[11] = attr
    struct.pack_into('<H', ent, 20, cluster >> 16)
    struct.pack_into('<H', ent, 26, cluster & 0xffff)
    struct.pack_into('<I', ent, 28, size)
    return bytes(ent)


def gpt_header(current_lba, alternate_lba, partition_entries_lba,
               partitions_crc, disk_guid) -> bytes:
    h = bytearray(SECTOR)
    struct.pack_into('<8sIIIIQQQQ16sQIII', h, 0,
                     b'EFI PART', 0x10000, 92, 0, 0,
                     current_lba, alternate_lba, 34, DISK_SECTORS - 34,
                     disk_guid.bytes_le, partition_entries_lba,
                     128, 128, partitions_crc)
    struct.pack_into('<I', h, 16, zlib.crc32(h[:92]) & 0xffffffff)
    return bytes(h)


def volume_boot_sector() -> bytes:
    b = bytearray(SECTOR)
    b[:3] = b'\xeb\x58\x90'
    b[3:11] = b'CNATIVE '
    struct.pack_into('<H', b, 11, SECTOR)
    b[13] = SECTORS_PER_CLUSTER
    struct.pack_into('<H', b, 14, RESERVED_SECTORS)
    b[16] = FAT_COUNT
    struct.pack_into('<H', b, 17, 0)
    struct.pack_into('<H', b, 19, 0)
    b[21] = 0xf8
    struct.pack_into('<H', b, 22, 0)
    struct.pack_into('<H', b, 24, 63)
    struct.pack_into('<H', b, 26, 255)
    struct.pack_into('<I', b, 28, ESP_START)
    struct.pack_into('<I', b, 32, ESP_SECTORS)
    struct.pack_into('<I', b, 36, FAT_SECTORS)
    struct.pack_into('<H', b, 40, 0)
    struct.pack_into('<H', b, 42, 0)
    struct.pack_into('<I', b, 44, 2)
    struct.pack_into('<H', b, 48, 1)
    struct.pack_into('<H', b, 50, 6)
    b[64] = 0x80
    b[66] = 0x29
    struct.pack_into('<I', b, 67, 0x434e4154)
    b[71:82] = b'CNATIVE ESP'
    b[82:90] = b'FAT32   '
    b[510:512] = b'\x55\xaa'
    return bytes(b)


def fsinfo() -> bytes:
    b = bytearray(SECTOR)
    struct.pack_into('<I', b, 0, 0x41615252)
    struct.pack_into('<I', b, 484, 0x61417272)
    struct.pack_into('<I', b, 488, 0xffffffff)
    struct.pack_into('<I', b, 492, 0xffffffff)
    struct.pack_into('<I', b, 508, 0xaa550000)
    return bytes(b)


def cluster_lba(cluster: int) -> int:
    assert cluster >= 2
    return DATA_START + (cluster - 2) * SECTORS_PER_CLUSTER


def make_media(target: pathlib.Path, binaries: dict[str, bytes]):
    if not binaries or any(k not in EFI_NAMES for k in binaries):
        raise ValueError('Expected x64 and/or arm64 EFI images')
    disk_tag = '+'.join(sorted(binaries))
    disk_guid = uuid.uuid5(uuid.NAMESPACE_DNS, 'c-native-kernel-stage0-v02-' + disk_tag)
    part_guid = uuid.uuid5(disk_guid, 'efi-system-partition')

    starts = {}
    next_cluster = 5
    fat = bytearray(FAT_SECTORS * SECTOR)
    struct.pack_into('<I', fat, 0, 0x0ffffff8)
    struct.pack_into('<I', fat, 4, 0x0fffffff)
    for cluster in (2, 3, 4):
        struct.pack_into('<I', fat, cluster * 4, 0x0fffffff)
    for name in sorted(binaries):
        data = binaries[name]
        if not data:
            raise ValueError('Zero-length EFI application')
        count = math.ceil(len(data) / SECTOR)
        if count + next_cluster - 2 >= CLUSTER_COUNT:
            raise ValueError('EFI images exceed ESP capacity')
        starts[name] = next_cluster
        for i in range(count):
            cluster = next_cluster + i
            struct.pack_into('<I', fat, cluster * 4,
                             (cluster + 1) if i + 1 < count else 0x0fffffff)
        next_cluster += count
    if (CLUSTER_COUNT + 2) * 4 > len(fat):
        raise ValueError('FAT too small for volume')

    partition_entries = bytearray(128 * 128)
    entry = bytearray(128)
    struct.pack_into('<16s16sQQQ', entry, 0,
                     EFI_SYSTEM_PARTITION_TYPE.bytes_le, part_guid.bytes_le,
                     ESP_START, ESP_LAST, 0)
    name_bytes = 'C Native ESP'.encode('utf-16le')
    entry[56:56 + len(name_bytes)] = name_bytes
    partition_entries[:128] = entry
    part_crc = zlib.crc32(partition_entries) & 0xffffffff

    protective_mbr = bytearray(SECTOR)
    protective_mbr[446 + 4] = 0xee
    struct.pack_into('<I', protective_mbr, 446 + 8, 1)
    struct.pack_into('<I', protective_mbr, 446 + 12, DISK_SECTORS - 1)
    protective_mbr[510:512] = b'\x55\xaa'

    def write_sector(f, lba, data):
        assert len(data) <= SECTOR
        f.seek(lba * SECTOR)
        f.write(data)

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('wb') as f:
        f.truncate(SECTOR * DISK_SECTORS)
        write_sector(f, 0, protective_mbr)
        write_sector(f, 1, gpt_header(1, DISK_SECTORS - 1, 2,
                                       part_crc, disk_guid))
        f.seek(2 * SECTOR)
        f.write(partition_entries)
        f.seek((DISK_SECTORS - 33) * SECTOR)
        f.write(partition_entries)
        write_sector(f, DISK_SECTORS - 1,
                     gpt_header(DISK_SECTORS - 1, 1, DISK_SECTORS - 33,
                                part_crc, disk_guid))
        boot = volume_boot_sector()
        info = fsinfo()
        for off, data in ((0, boot), (1, info), (6, boot), (7, info)):
            write_sector(f, ESP_START + off, data)
        for copy in range(FAT_COUNT):
            f.seek((ESP_START + RESERVED_SECTORS + copy * FAT_SECTORS) * SECTOR)
            f.write(fat)
        write_sector(f, cluster_lba(2), boot_dir_entry(b'EFI        ', 0x10, 3))
        write_sector(f, cluster_lba(3),
                     boot_dir_entry(b'.          ', 0x10, 3)
                     + boot_dir_entry(b'..         ', 0x10, 2)
                     + boot_dir_entry(b'BOOT       ', 0x10, 4))
        entries = (boot_dir_entry(b'.          ', 0x10, 4)
                   + boot_dir_entry(b'..         ', 0x10, 3))
        for name in sorted(binaries):
            entries += boot_dir_entry(EFI_NAMES[name], 0x20,
                                      starts[name], len(binaries[name]))
        write_sector(f, cluster_lba(4), entries)
        for name in sorted(binaries):
            f.seek(cluster_lba(starts[name]) * SECTOR)
            f.write(binaries[name])
    print(f'Created {target} ({SECTOR * DISK_SECTORS} bytes)')
    for name in sorted(binaries):
        print(f'  EFI/BOOT/{EFI_NAMES[name][:8].rstrip().decode()}.EFI: '
              f'{len(binaries[name])} bytes [{name}]')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    parser.add_argument('--x64', type=pathlib.Path)
    parser.add_argument('--arm64', type=pathlib.Path)
    args = parser.parse_args()
    images = {}
    if args.x64:
        images['x64'] = args.x64.read_bytes()
    if args.arm64:
        images['arm64'] = args.arm64.read_bytes()
    make_media(args.output, images)


if __name__ == '__main__':
    main()
