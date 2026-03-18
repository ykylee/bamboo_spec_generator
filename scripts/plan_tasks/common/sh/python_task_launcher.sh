#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
exec {{PYTHON_COMMAND}} "$SCRIPT_DIR/{{SCRIPT_NAME}}" "$@"
