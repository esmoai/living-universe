#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then sh install.sh; fi
exec .venv/bin/python -u launch.py "$@"
