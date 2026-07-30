# AutoClicker launcher (PowerShell)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
Set-Location $ProjectDir
& (Join-Path $ProjectDir ".venv\Scripts\python.exe") main.py
Read-Host "Press Enter to exit"
