#!/bin/bash
# ============================================================
#  AutoClicker Environment Setup (Bash / Linux / macOS)
# ============================================================
set -e

# Switch to project root (parent of script dir)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

VENV_DIR="$PROJECT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

echo "============================================"
echo "       AutoClicker Environment Setup"
echo "============================================"
echo ""
echo "[INFO] Project: $PROJECT_DIR"
echo ""

# ========== 1. Detect Python ==========
echo "[1/4] Detecting Python ..."
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    echo "      Found: $PY_VER"
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PY_VER=$(python --version 2>&1)
    echo "      Found: $PY_VER"
    PYTHON_CMD="python"
else
    echo "      [ERROR] Python not found. Please install Python 3.10+"
    echo "      Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "      macOS:         brew install python3"
    exit 1
fi
echo ""

# ========== 2. Create venv ==========
echo "[2/4] Creating virtual environment (.venv) ..."
if [ -d "$VENV_DIR" ]; then
    echo "      .venv already exists, skipping creation."
else
    $PYTHON_CMD -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "      [ERROR] Failed to create virtual environment."
        echo "      On Ubuntu/Debian: sudo apt install python3-venv"
        exit 1
    fi
    echo "      .venv created: $VENV_DIR"
fi
echo ""

# ========== 3. Install dependencies ==========
echo "[3/4] Installing dependencies ..."
echo "      Upgrading pip ..."
$VENV_PYTHON -m pip install --upgrade pip >/dev/null 2>&1

REQ_FILE="$PROJECT_DIR/requirements.txt"
if [ ! -f "$REQ_FILE" ]; then
    echo "      [WARN] requirements.txt not found, skipping dependencies."
else
    echo "      Installing packages from requirements.txt ..."
    $VENV_PIP install -r "$REQ_FILE"
    if [ $? -ne 0 ]; then
        echo "      [ERROR] Dependency installation failed. Check network."
        exit 1
    fi
    echo "      Dependencies installed successfully."
fi
echo ""

# ========== 4. Update run.sh ==========
echo "[4/4] Updating run.sh ..."
RUN_SH="$SCRIPT_DIR/run.sh"
cat > "$RUN_SH" << 'RUNEOF'
#!/bin/bash
# AutoClicker launcher (auto-generated)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"
"$PROJECT_DIR/.venv/bin/python" main.py
RUNEOF
chmod +x "$RUN_SH"
echo "      run.sh updated."
echo ""

# ========== Verify ==========
echo "============================================"
echo "           Setup Complete! Verifying..."
echo "============================================"
echo ""

echo "Testing PyQt6 import ..."
$VENV_PYTHON -c "import PyQt6; print('  PyQt6 version:', PyQt6.QtCore.PYQT_VERSION_STR)" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "      [WARN] PyQt6 import failed."
    echo "      On Linux: sudo apt install libgl1-mesa-glx libegl1-mesa"
else
    echo "      PyQt6 OK."
fi

echo "Testing keyboard import ..."
$VENV_PYTHON -c "import keyboard; print('  keyboard version:', keyboard.__version__)" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "      [WARN] keyboard import failed."
    echo "      On Linux: sudo pip install keyboard (needs root for /dev/input)"
else
    echo "      keyboard OK."
fi

echo ""
echo "============================================"
echo " Done! Run: ./script/run.sh"
echo "============================================"
