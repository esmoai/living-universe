#!/bin/sh
set -eu
cd "$(dirname "$0")"
if ! command -v cc >/dev/null 2>&1; then
  printf 'A C compiler is required for the Linux native observer. The portable LivingUniverse.html needs no compiler.\n' >&2
  exit 2
fi
sh scripts/build_bridge.sh
exec ./bin/living-universe-observer-linux --web "$PWD/LivingUniverse.html" "$@"
