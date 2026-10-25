#!/bin/sh
set -u
printf 'Living Universe development environment (inspection only)\n'
uname -srm
for tool in cc clang lld-link python3 node qemu-system-x86_64 qemu-system-aarch64 podman; do
  if command -v "$tool" >/dev/null 2>&1; then printf 'FOUND  %s: %s\n' "$tool" "$(command -v "$tool")"; else printf 'MISSING %s\n' "$tool"; fi
done
printf '\nFirmware candidates:\n'
for path in /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd /usr/share/AAVMF/AAVMF_CODE.fd /usr/share/qemu-efi-aarch64/QEMU_EFI.fd; do
  if [ -f "$path" ]; then printf 'FOUND %s\n' "$path"; fi
done
printf '\nThis script installs nothing and changes no host settings.\n'
