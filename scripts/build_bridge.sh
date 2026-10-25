#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p bin validation
cc -std=c17 -D_GNU_SOURCE -O2 -fno-builtin -Wall -Wextra -Werror -fstack-protector-strong -D_FORTIFY_SOURCE=2 -fPIE -pie -Wl,-z,relro,-z,now bridge/observer.c -o bin/living-universe-observer-linux
printf 'Built native hosted observer for this Linux architecture.\n'
