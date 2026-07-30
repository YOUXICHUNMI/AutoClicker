#!/bin/bash
# AutoClicker launcher (Bash / Linux / macOS)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"
"$PROJECT_DIR/.venv/bin/python" main.py
