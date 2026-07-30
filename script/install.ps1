# ============================================================
#  AutoClicker Environment Setup (PowerShell)
# ============================================================
$ErrorActionPreference = "Stop"

# Switch to project root (parent of script dir)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
Set-Location $ProjectDir

$VenvDir = Join-Path $ProjectDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "       AutoClicker Environment Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[INFO] Project: $ProjectDir"
Write-Host ""

# ========== 1. Detect Python ==========
Write-Host "[1/4] Detecting Python ..." -ForegroundColor Yellow
$pythonCmd = $null
try {
    $ver = & python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "      Found: $ver"
        $pythonCmd = "python"
    }
} catch {}

if (-not $pythonCmd) {
    try {
        $ver = & py --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "      Found: $ver"
            $pythonCmd = "py"
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Host "      [ERROR] Python not found. Please install Python 3.10+" -ForegroundColor Red
    Write-Host "      Download: https://www.python.org/downloads/"
    Write-Host "      Check 'Add Python to PATH' during installation."
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# ========== 2. Create venv ==========
Write-Host "[2/4] Creating virtual environment (.venv) ..." -ForegroundColor Yellow
if (Test-Path $VenvDir) {
    Write-Host "      .venv already exists, skipping creation."
} else {
    & $pythonCmd -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "      [ERROR] Failed to create virtual environment." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "      .venv created: $VenvDir"
}
Write-Host ""

# ========== 3. Install dependencies ==========
Write-Host "[3/4] Installing dependencies ..." -ForegroundColor Yellow
Write-Host "      Upgrading pip ..."
& $VenvPython -m pip install --upgrade pip *> $null

$reqFile = Join-Path $ProjectDir "requirements.txt"
if (-not (Test-Path $reqFile)) {
    Write-Host "      [WARN] requirements.txt not found, skipping dependencies." -ForegroundColor DarkYellow
} else {
    Write-Host "      Installing packages from requirements.txt ..."
    & $VenvPip install -r $reqFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "      [ERROR] Dependency installation failed. Check network." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "      Dependencies installed successfully." -ForegroundColor Green
}
Write-Host ""

# ========== 4. Update run.ps1 ==========
Write-Host "[4/4] Updating run.ps1 ..." -ForegroundColor Yellow
$runPs1 = Join-Path $ScriptDir "run.ps1"
$runContent = @"
# AutoClicker launcher (auto-generated)
`$ScriptDir = Split-Path -Parent `$MyInvocation.MyCommand.Path
`$ProjectDir = Split-Path -Parent `$ScriptDir
Set-Location `$ProjectDir
& (Join-Path `$ProjectDir ".venv\Scripts\python.exe") main.py
Read-Host "Press Enter to exit"
"@
Set-Content -Path $runPs1 -Value $runContent -Encoding UTF8
Write-Host "      run.ps1 updated."
Write-Host ""

# ========== Verify ==========
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "           Setup Complete! Verifying..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Testing PyQt6 import ..."
& $VenvPython -c "import PyQt6; print('  PyQt6 version:', PyQt6.QtCore.PYQT_VERSION_STR)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "      [WARN] PyQt6 import failed." -ForegroundColor Red
} else {
    Write-Host "      PyQt6 OK." -ForegroundColor Green
}

Write-Host "Testing keyboard import ..."
& $VenvPython -c "import keyboard; print('  keyboard version:', keyboard.__version__)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "      [WARN] keyboard import failed." -ForegroundColor Red
} else {
    Write-Host "      keyboard OK." -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Done! Run: powershell -File script\run.ps1" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
