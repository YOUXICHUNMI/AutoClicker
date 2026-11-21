#!/bin/bash
# AutoClicker launcher (source run, auto-generated)
# Data dir (config/ + log/) is dist/, shared with the exe build.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export AUTOCLICKER_DATA_DIR="$PROJECT_DIR/dist"
mkdir -p "$AUTOCLICKER_DATA_DIR"
cd "$PROJECT_DIR"
"$PROJECT_DIR/.venv/bin/python" main.py
