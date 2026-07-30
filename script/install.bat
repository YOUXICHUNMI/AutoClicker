@echo off
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
where python >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do set "PY_VER=%%i"
    echo       Found: %PY_VER%
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>&1
    if %errorlevel%==0 (
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
echo [2/4] Creating virtual environment (venv) ...
set "VENV_DIR=%PROJECT_DIR%\.venv"
if exist "%VENV_DIR%" (
    echo       venv already exists, skipping creation.
) else (
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo       [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo       venv created: %VENV_DIR%
)
echo.

:: ========== 3. Install dependencies ==========
echo [3/4] Installing dependencies ...
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

echo       Upgrading pip ...
"%VENV_PYTHON%" -m pip install --upgrade pip >nul 2>&1

if not exist "%PROJECT_DIR%\requirements.txt" (
    echo       [WARN] requirements.txt not found, skipping dependencies.
) else (
    echo       Installing packages from requirements.txt ...
    "%VENV_PIP%" install -r "%PROJECT_DIR%\requirements.txt"
    if %errorlevel% neq 0 (
        echo       [ERROR] Dependency installation failed. Check network.
        pause
        exit /b 1
    )
    echo       Dependencies installed successfully.
)
echo.

:: ========== 4. Update run.bat ==========
echo [4/4] Updating run.bat ...
set "RUN_BAT=%PROJECT_DIR%\script\run.bat"
> "%RUN_BAT%" (
    echo @echo off
    echo cd /d "%%~dp0.."
    echo "%VENV_PYTHON%" main.py
    echo pause
)
echo       run.bat updated to use venv Python.
echo.

:: ========== Verify ==========
echo ============================================
echo              Setup Complete! Verifying...
echo ============================================
echo.
echo Testing PyQt6 import ...
"%VENV_PYTHON%" -c "import PyQt6; print('  PyQt6 version:', PyQt6.QtCore.PYQT_VERSION_STR)" 2>nul
if %errorlevel% neq 0 (
    echo       [WARN] PyQt6 import failed.
) else (
    echo       PyQt6 OK.
)
echo Testing keyboard import ...
"%VENV_PYTHON%" -c "import keyboard; print('  keyboard version:', keyboard.__version__)" 2>nul
if %errorlevel% neq 0 (
    echo       [WARN] keyboard import failed.
) else (
    echo       keyboard OK.
)
echo.
echo ============================================
echo  Done! Double-click script\run.bat to start.
echo ============================================
echo.
pause
