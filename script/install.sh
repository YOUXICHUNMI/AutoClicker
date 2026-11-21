#!/bin/bash
# ============================================================
#  AutoClicker Environment Setup (Bash / Linux / macOS / Git Bash)
#
#  创建 .venv、安装依赖、重写 run 脚本。
#  若 .venv 已存在但解释器无法运行（例如创建它的 Python 被卸载/移位），
#  会自动删除并重建。
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

VENV_DIR="$PROJECT_DIR/.venv"

# Windows(Git Bash/MSYS2) 用 Scripts/，其他平台用 bin/
case "$(uname -s 2>/dev/null || echo unknown)" in
    MINGW*|MSYS*|CYGWIN*) VENV_PYTHON="$VENV_DIR/Scripts/python.exe" ;;
    *)                     VENV_PYTHON="$VENV_DIR/bin/python" ;;
esac
VENV_DIRNAME="$(dirname "$(dirname "$VENV_PYTHON")")"

echo "============================================"
echo "       AutoClicker Environment Setup"
echo "============================================"
echo ""
echo "[INFO] Project: $PROJECT_DIR"
echo ""

# ========== 工具函数 ==========
venv_usable() {
    [ -x "$VENV_PYTHON" ] || return 1
    "$VENV_PYTHON" -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" >/dev/null 2>&1
}

is_python3() {
    "$1" -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" >/dev/null 2>&1
}

# ========== 1. 检测 Python ==========
echo "[1/4] Detecting Python ..."
PYTHON_CMD=""
for cand in python3 python; do
    if command -v "$cand" &>/dev/null && is_python3 "$cand"; then
        echo "      Found: $("$cand" --version 2>&1)  ($(command -v "$cand"))"
        PYTHON_CMD="$cand"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "      [ERROR] Python 3 not found. Please install Python 3.10+"
    echo "      Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "      macOS:         brew install python3"
    exit 1
fi
echo ""

# ========== 2. 创建 venv ==========
echo "[2/4] Preparing virtual environment (.venv) ..."
if [ -d "$VENV_DIR" ]; then
    if venv_usable; then
        echo "      .venv 可用，跳过创建。"
    else
        echo "      .venv 已存在但解释器无法运行（base Python 可能已被卸载/移位）。"
        echo "      正在删除并重建 ..."
        rm -rf "$VENV_DIR"
        if ! "$PYTHON_CMD" -m venv "$VENV_DIR"; then
            echo "      [ERROR] Failed to create virtual environment."
            echo "      On Ubuntu/Debian: sudo apt install python3-venv"
            exit 1
        fi
        # 重建后重新确认解释器路径存在
        if [ ! -x "$VENV_PYTHON" ]; then
            echo "      [ERROR] venv 创建后未找到解释器: $VENV_PYTHON"
            exit 1
        fi
        echo "      .venv 已重建: $VENV_DIR"
    fi
else
    if ! "$PYTHON_CMD" -m venv "$VENV_DIR"; then
        echo "      [ERROR] Failed to create virtual environment."
        echo "      On Ubuntu/Debian: sudo apt install python3-venv"
        exit 1
    fi
    echo "      .venv created: $VENV_DIR"
fi
echo ""

# ========== 3. 安装依赖 ==========
echo "[3/4] Installing dependencies ..."
echo "      Upgrading pip ..."
"$VENV_PYTHON" -m pip install --upgrade pip >/dev/null 2>&1 || true

REQ_FILE="$PROJECT_DIR/requirements.txt"
if [ ! -f "$REQ_FILE" ]; then
    echo "      [WARN] requirements.txt not found, skipping dependencies."
else
    echo "      Installing packages from requirements.txt ..."
    if ! "$VENV_PYTHON" -m pip install -r "$REQ_FILE"; then
        echo "      [ERROR] Dependency installation failed. Check network."
        exit 1
    fi
    echo "      Dependencies installed successfully."
fi
echo ""

# ========== 4. 重写 run 脚本 ==========
echo "[4/4] Updating launcher scripts ..."
RUN_SH="$SCRIPT_DIR/run.sh"
cat > "$RUN_SH" << 'RUNEOF'
#!/bin/bash
# AutoClicker launcher (source run, auto-generated)
# Data dir (config/ + log/) is dist/, shared with the exe build.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
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
RUNEOF
chmod +x "$RUN_SH"
echo "      run.sh updated."

START_SH="$PROJECT_DIR/start.sh"
cat > "$START_SH" << 'STARTEOF'
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
STARTEOF
chmod +x "$START_SH"
echo "      start.sh updated."
echo ""

# ========== 验证 ==========
echo "============================================"
echo "           Setup Complete - Verifying..."
echo "============================================"
echo ""

ALL_OK=1

echo "Testing PyQt6 import ..."
if "$VENV_PYTHON" -c "import PyQt6.QtCore as c; print('  PyQt6 version:', c.PYQT_VERSION_STR)" 2>/dev/null; then
    echo "      PyQt6 OK."
else
    echo "      [WARN] PyQt6 import failed."
    echo "      On Linux: sudo apt install libgl1 libegl1"
    ALL_OK=0
fi

echo "Testing keyboard import ..."
if "$VENV_PYTHON" -c "import keyboard; print('  keyboard version:', getattr(keyboard,'__version__','n/a'))" 2>/dev/null; then
    echo "      keyboard OK."
else
    echo "      [WARN] keyboard import failed."
    echo "      On Linux: sudo pip install keyboard (needs root for /dev/input)"
    ALL_OK=0
fi

echo "Testing project imports ..."
if "$VENV_PYTHON" -c "import sys; sys.path.insert(0,'.'); import utils.app_paths, utils.config_manager, utils.logger, core.click_engine; print('  modules OK')" 2>/dev/null; then
    echo "      modules OK."
else
    echo "      [WARN] project module import failed."
    ALL_OK=0
fi

echo ""
echo "============================================"
if [ "$ALL_OK" -eq 1 ]; then
    echo " Done! Run: ./start.sh  (or ./script/run.sh)"
    echo " Package: ./script/package.sh"
else
    echo " Some checks failed, please review the [WARN] lines above."
fi
echo "============================================"
