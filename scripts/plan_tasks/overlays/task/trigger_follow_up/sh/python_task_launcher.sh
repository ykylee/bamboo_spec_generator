#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
echo "[trigger-follow-up] launching {{SCRIPT_NAME}}"
exec {{PYTHON_COMMAND}} "$SCRIPT_DIR/{{SCRIPT_NAME}}" "$@"
