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
