#!/bin/bash
# Cross-platform launcher (macOS / Linux). Starts the CML Tool in the
# foreground and opens your browser. Press Ctrl+C to stop.
#   Usage:  ./run.sh
cd "$(dirname "$0")" || exit 1

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "ERROR: Python 3 was not found. Install it from https://www.python.org/downloads/"
  exit 1
fi

exec "$PY" cml_tool.py
