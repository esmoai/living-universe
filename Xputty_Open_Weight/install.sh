#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if command -v python3.11 >/dev/null 2>&1; then
  exec python3.11 tools/bootstrap.py
fi
exec python3 tools/bootstrap.py
