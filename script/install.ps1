# ============================================================
#  AutoClicker Environment Setup (PowerShell)
#
#  创建 .venv、安装依赖、重写 run 脚本。
#  若 .venv 已存在但解释器无法运行（例如创建它的 Python 被卸载/移位），
#  会自动删除并重建 —— 旧的 "已存在就跳过" 逻辑无法修复这种情况。
# ============================================================
$ErrorActionPreference = "Stop"

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
Set-Location $ProjectDir

$VenvDir    = Join-Path $ProjectDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "       AutoClicker Environment Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[INFO] Project: $ProjectDir"
Write-Host ""

# ========== 工具函数 ==========
function Test-VenvUsable {
    if (-not (Test-Path -LiteralPath $VenvPython)) { return $false }
    try {
        $out = & $VenvPython -c "import sys;print(sys.version_info[0])" 2>$null
        return ($LASTEXITCODE -eq 0 -and "$out".Trim() -eq "3")
    } catch {
        return $false
    }
}

function Test-PythonCmd {
    param([string]$Cmd)
    if (-not $Cmd) { return $false }
    try {
        $out = & $Cmd -c "import sys;print(sys.version_info[0])" 2>$null
        return ($LASTEXITCODE -eq 0 -and "$out".Trim() -eq "3")
    } catch {
        return $false
    }
}

# ========== 1. 检测 Python ==========
Write-Host "[1/4] Detecting Python ..." -ForegroundColor Yellow
$pythonCmd = $null
foreach ($cand in @('python', 'python3', 'py')) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($cmd -and (Test-PythonCmd $cmd.Source)) {
        $ver = & $cmd.Source --version 2>&1
        Write-Host "      Found: $ver  ($($cmd.Source))"
        $pythonCmd = $cmd.Source
        break
    }
}

if (-not $pythonCmd) {
    Write-Host "      [ERROR] Python 3 not found. Please install Python 3.10+" -ForegroundColor Red
    Write-Host "      Download: https://www.python.org/downloads/"
    Write-Host "      Check 'Add Python to PATH' during installation."
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# ========== 2. 创建 venv ==========
Write-Host "[2/4] Preparing virtual environment (.venv) ..." -ForegroundColor Yellow
if (Test-Path -LiteralPath $VenvDir) {
    if (Test-VenvUsable) {
        Write-Host "      .venv 可用，跳过创建。" -ForegroundColor Green
    } else {
        Write-Host "      .venv 已存在但解释器无法运行（base Python 可能已被卸载/移位）。" -ForegroundColor DarkYellow
        Write-Host "      正在删除并重建 ..." -ForegroundColor DarkYellow
        Remove-Item -LiteralPath $VenvDir -Recurse -Force
        & $pythonCmd -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) {
            Write-Host "      [ERROR] Failed to create virtual environment." -ForegroundColor Red
            Read-Host "Press Enter to exit"
            exit 1
        }
        Write-Host "      .venv 已重建: $VenvDir" -ForegroundColor Green
    }
} else {
    & $pythonCmd -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "      [ERROR] Failed to create virtual environment." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "      .venv created: $VenvDir" -ForegroundColor Green
}
Write-Host ""

# ========== 3. 安装依赖 ==========
Write-Host "[3/4] Installing dependencies ..." -ForegroundColor Yellow
Write-Host "      Upgrading pip ..."
& $VenvPython -m pip install --upgrade pip *> $null

$reqFile = Join-Path $ProjectDir "requirements.txt"
if (-not (Test-Path -LiteralPath $reqFile)) {
    Write-Host "      [WARN] requirements.txt not found, skipping dependencies." -ForegroundColor DarkYellow
} else {
    Write-Host "      Installing packages from requirements.txt ..."
    & $VenvPython -m pip install -r $reqFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "      [ERROR] Dependency installation failed. Check network." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "      Dependencies installed successfully." -ForegroundColor Green
}
Write-Host ""

# ========== 4. 重写 run 脚本 ==========
Write-Host "[4/4] Updating run scripts ..." -ForegroundColor Yellow
$runPs1 = Join-Path $ScriptDir "run.ps1"
$runContent = @"
# AutoClicker launcher (source run, auto-generated)
# Data dir (config/ + log/) is dist/, shared with the exe build.
`$ScriptDir = Split-Path -Parent `$MyInvocation.MyCommand.Path
`$ProjectDir = Split-Path -Parent `$ScriptDir
`$env:AUTOCLICKER_DATA_DIR = Join-Path `$ProjectDir "dist"
if (-not (Test-Path -LiteralPath `$env:AUTOCLICKER_DATA_DIR)) {
    New-Item -ItemType Directory -Path `$env:AUTOCLICKER_DATA_DIR -Force | Out-Null
}
Set-Location `$ProjectDir
& (Join-Path `$ProjectDir ".venv\Scripts\python.exe") main.py
Read-Host "Press Enter to exit"
"@
Set-Content -Path $runPs1 -Value $runContent -Encoding UTF8
Write-Host "      run.ps1 updated."

$runBat = Join-Path $ScriptDir "run.bat"
$batContent = @"
@echo off
rem AutoClicker launcher (source run)
rem Data dir (config/ + log/) is dist/, shared with the exe build.
setlocal
set "AUTOCLICKER_DATA_DIR=%~dp0..\dist"
if not exist "%AUTOCLICKER_DATA_DIR%" mkdir "%AUTOCLICKER_DATA_DIR%"
cd /d "%~dp0.."
".venv\Scripts\python.exe" main.py
pause
endlocal
"@
Set-Content -Path $runBat -Value $batContent -Encoding ASCII
Write-Host "      run.bat updated."

# 顶层 start.bat：与 script/run.bat 等价，方便双击仓库根目录
$startBat = Join-Path $ProjectDir "start.bat"
$startContent = @"
@echo off
rem AutoClicker launcher (source run)
rem Data dir (config/ + log/) is dist/, shared with the exe build.
setlocal
set "AUTOCLICKER_DATA_DIR=%~dp0dist"
if not exist "%AUTOCLICKER_DATA_DIR%" mkdir "%AUTOCLICKER_DATA_DIR%"
cd /d "%~dp0."
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
endlocal
"@
Set-Content -Path $startBat -Value $startContent -Encoding ASCII
Write-Host "      start.bat updated."
Write-Host ""

# ========== 验证 ==========
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "           Setup Complete! Verifying..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$allOk = $true

Write-Host "Testing PyQt6 import ..."
& $VenvPython -c "import PyQt6.QtCore as c; print('  PyQt6 version:', c.PYQT_VERSION_STR)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "      [WARN] PyQt6 import failed." -ForegroundColor Red
    $allOk = $false
} else {
    Write-Host "      PyQt6 OK." -ForegroundColor Green
}

Write-Host "Testing keyboard import ..."
& $VenvPython -c "import keyboard; print('  keyboard version:', getattr(keyboard,'__version__','n/a'))" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "      [WARN] keyboard import failed." -ForegroundColor Red
    $allOk = $false
} else {
    Write-Host "      keyboard OK." -ForegroundColor Green
}

Write-Host "Testing project imports ..."
& $VenvPython -c "import sys; sys.path.insert(0,'.'); import utils.app_paths, utils.config_manager, utils.logger, core.click_engine; print('  modules OK')" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "      [WARN] project module import failed." -ForegroundColor Red
    $allOk = $false
} else {
    Write-Host "      modules OK." -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
if ($allOk) {
    Write-Host " Done! Run: powershell -File script\run.ps1" -ForegroundColor Green
    Write-Host " Package: powershell -File script\package.ps1 -BuildExe" -ForegroundColor Green
} else {
    Write-Host " 部分检查未通过，请查看上方 [WARN]。" -ForegroundColor DarkYellow
}
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
