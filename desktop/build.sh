#!/usr/bin/env bash
# OneASR Desktop Quick Build Entry
set -e

export PATH="$HOME/.cargo/bin:$HOME/.local/bin:/opt/homebrew/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="python3"

# Prefer python from uv or venv if available
if command -v uv >/dev/null 2>&1; then
    exec uv run python "${SCRIPT_DIR}/scripts/build.py" "$@"
else
    exec "${PYTHON_BIN}" "${SCRIPT_DIR}/scripts/build.py" "$@"
fi
