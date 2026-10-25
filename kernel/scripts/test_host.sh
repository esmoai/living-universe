#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
: "${CC:=clang}"
mkdir -p build/tests
"$CC" -std=c17 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
    -fno-omit-frame-pointer -DCNATIVE_TEST_BUILD=1 -Iinclude \
    src/arch/aarch64/serial.c tests/test_acpi_spcr.c -o build/tests/test_acpi_spcr
build/tests/test_acpi_spcr
