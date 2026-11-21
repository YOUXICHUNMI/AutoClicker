#!/bin/bash
# AutoClicker launcher (source run, auto-generated)
# Data dir (config/ + log/) is dist/, shared with the exe build.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
export AUTOCLICKER_DATA_DIR="$PROJECT_DIR/dist"
mkdir -p "$AUTOCLICKER_DATA_DIR"
cd "$PROJECT_DIR"

# Pick the venv interpreter for this platform
if [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
elif [ -x "$PROJECT_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON="$PROJECT_DIR/.venv/Scripts/python.exe"
else
    echo "未找到 .venv，先运行 script/install.sh 安装依赖。" >&2
    exit 1
fi

"$PYTHON" main.py
