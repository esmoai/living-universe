#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p validation
python3 scripts/build_web.py
node --check validation/extension-syntax.js
node --test source/tests/data.test.js source/tests/universe.test.js
sh scripts/build_bridge.sh
python3 tests/test_bridge.py
python3 tests/test_kernel_telemetry.py
(cd kernel && sh scripts/test_host.sh && sh scripts/build.sh)
printf '\nHost and build checks complete. No firmware boot was performed.\n'
if [ "${1:-}" = "--qemu" ]; then
  (cd kernel && sh scripts/test_qemu.sh --arch both)
else
  printf 'Actual firmware gate: sh scripts/test_all.sh --qemu\n'
fi
