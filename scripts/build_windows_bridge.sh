#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
: "${CC:=clang}"
: "${LINKER:=lld-link}"
for tool in "$CC" "$LINKER"; do
  command -v "$tool" >/dev/null 2>&1 || { printf 'Missing tool: %s; install clang/lld or set CC and LINKER.\n' "$tool" >&2; exit 127; }
done
mkdir -p bridge/winbuild
for lib in kernel32 ws2_32 bcrypt shell32; do
  "$LINKER" /lib /def:"bridge/winbuild/$lib.def" /machine:x64 /out:"bridge/winbuild/$lib.lib"
done
"$CC" -target x86_64-pc-windows-msvc -std=c17 -O2 -ffreestanding -fno-builtin -fno-stack-protector -fno-unwind-tables -Wall -Wextra -Werror -c bridge/observer.c -o bridge/winbuild/observer.obj
"$LINKER" /nologo /machine:x64 /subsystem:console /entry:mainCRTStartup /nodefaultlib /Brepro /dynamicbase /highentropyva /nxcompat /out:LivingUniverse-Observer.exe bridge/winbuild/observer.obj bridge/winbuild/kernel32.lib bridge/winbuild/ws2_32.lib bridge/winbuild/bcrypt.lib bridge/winbuild/shell32.lib
printf 'Built Windows x86-64 PE executable. Runtime validation still required on Windows.\n'
