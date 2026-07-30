@echo off
cd /d "%~dp0.."
set "VENV_DIR=%~dp0..\.venv"
echo %VENV_DIR%
"%VENV_DIR%\Scripts\python.exe" main.py 
pause
