@echo off
setlocal enabledelayedexpansion
title AutoClicker Installer

echo ============================================
echo        AutoClicker Environment Setup
echo ============================================
echo.

:: Switch to project root (parent of script dir)
cd /d "%~dp0.."
set "PROJECT_DIR=%CD%"
echo [INFO] Project: %PROJECT_DIR%
echo.

:: ========== 1. Detect Python ==========
echo [1/4] Detecting Python ...
set "PYTHON_CMD="
where python >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do set "PY_VER=%%i"
    echo       Found: %PY_VER%
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>&1
    if !errorlevel!==0 (
        for /f "tokens=*" %%i in ('py --version 2^>^&1') do set "PY_VER=%%i"
        echo       Found: %PY_VER%
        set "PYTHON_CMD=py"
    ) else (
        echo       [ERROR] Python not found. Please install Python 3.10+
        echo       Download: https://www.python.org/downloads/
        echo       Check "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
)
echo.

:: ========== 2. Create venv ==========
echo [2/4] Preparing virtual environment (.venv) ...
set "VENV_DIR=%PROJECT_DIR%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

set "VENV_OK=0"
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import sys" >nul 2>&1
    if !errorlevel!==0 set "VENV_OK=1"
)

if "%VENV_OK%"=="1" (
    echo       .venv 可用，跳过创建。
) else (
    if exist "%VENV_DIR%" (
        echo       .venv 已存在但解释器无法运行（base Python 可能已被卸载/移位）。
        echo       正在删除并重建 ...
        rmdir /s /q "%VENV_DIR%"
    )
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if !errorlevel! neq 0 (
        echo       [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo       .venv 已就绪: %VENV_DIR%
)
echo.

:: ========== 3. Install dependencies ==========
echo [3/4] Installing dependencies ...
echo       Upgrading pip ...
"%VENV_PYTHON%" -m pip install --upgrade pip >nul 2>&1

if not exist "%PROJECT_DIR%\requirements.txt" (
    echo       [WARN] requirements.txt not found, skipping dependencies.
) else (
    echo       Installing packages from requirements.txt ...
    "%VENV_PYTHON%" -m pip install -r "%PROJECT_DIR%\requirements.txt"
    if !errorlevel! neq 0 (
        echo       [ERROR] Dependency installation failed. Check network.
        pause
        exit /b 1
    )
    echo       Dependencies installed successfully.
)
echo.

:: ========== 4. Update run scripts ==========
echo [4/4] Updating run scripts ...
> "%PROJECT_DIR%\script\run.bat" (
    echo @echo off
    echo rem AutoClicker launcher ^(source run^)
    echo rem Data dir ^(config/ + log/^) is dist/, shared with the exe build.
    echo setlocal
    echo set "AUTOCLICKER_DATA_DIR=%%~dp0..\dist"
    echo if not exist "%%AUTOCLICKER_DATA_DIR%%" mkdir "%%AUTOCLICKER_DATA_DIR%%"
    echo cd /d "%%~dp0.."
    echo ".venv\Scripts\python.exe" main.py
    echo pause
    echo endlocal
)
echo       run.bat updated.

> "%PROJECT_DIR%\start.bat" (
    echo @echo off
    echo rem AutoClicker launcher ^(source run^)
    echo rem Data dir ^(config/ + log/^) is dist/, shared with the exe build.
    echo setlocal
    echo set "AUTOCLICKER_DATA_DIR=%%~dp0dist"
    echo if not exist "%%AUTOCLICKER_DATA_DIR%%" mkdir "%%AUTOCLICKER_DATA_DIR%%"
    echo cd /d "%%~dp0."
    echo ".venv\Scripts\python.exe" main.py
    echo if errorlevel 1 pause
    echo endlocal
)
echo       start.bat updated.

> "%PROJECT_DIR%\script\run.ps1" (
    echo # AutoClicker launcher ^(source run, auto-generated^)
    echo # Data dir ^(config/ + log/^) is dist/, shared with the exe build.
    echo $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    echo $ProjectDir = Split-Path -Parent $ScriptDir
    echo $env:AUTOCLICKER_DATA_DIR = Join-Path $ProjectDir "dist"
    echo if ^(-not ^(Test-Path -LiteralPath $env:AUTOCLICKER_DATA_DIR^)^) {
    echo     New-Item -ItemType Directory -Path $env:AUTOCLICKER_DATA_DIR -Force ^| Out-Null
    echo }
    echo Set-Location $ProjectDir
    echo ^& ^(Join-Path $ProjectDir ".venv\Scripts\python.exe"^) main.py
    echo Read-Host "Press Enter to exit"
)
echo       run.ps1 updated.
echo.

:: ========== Verify ==========
echo ============================================
echo              Setup Complete - Verifying...
echo ============================================
echo.

set "ALL_OK=1"

echo Testing PyQt6 import ...
"%VENV_PYTHON%" -c "import PyQt6.QtCore as c; print('  PyQt6 version:', c.PYQT_VERSION_STR)" 2>nul
if !errorlevel! neq 0 (
    echo       [WARN] PyQt6 import failed.
    set "ALL_OK=0"
) else (
    echo       PyQt6 OK.
)

echo Testing keyboard import ...
"%VENV_PYTHON%" -c "import keyboard; print('  keyboard version:', getattr(keyboard,'__version__','n/a'))" 2>nul
if !errorlevel! neq 0 (
    echo       [WARN] keyboard import failed.
    set "ALL_OK=0"
) else (
    echo       keyboard OK.
)

echo Testing project imports ...
"%VENV_PYTHON%" -c "import sys; sys.path.insert(0,'.'); import utils.app_paths, utils.config_manager, utils.logger, core.click_engine; print('  modules OK')" 2>nul
if !errorlevel! neq 0 (
    echo       [WARN] project module import failed.
    set "ALL_OK=0"
) else (
    echo       modules OK.
)

echo.
echo ============================================
if "%ALL_OK%"=="1" (
    echo  Setup complete. Double-click script\run.bat to start.
    echo  Package: script\package.cmd -BuildExe
) else (
    echo  Some checks failed, please review the [WARN] lines above.
)
echo ============================================
echo.
pause
