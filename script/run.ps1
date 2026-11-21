﻿# AutoClicker launcher (source run, auto-generated)
# Data dir (config/ + log/) is dist/, shared with the exe build.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$env:AUTOCLICKER_DATA_DIR = Join-Path $ProjectDir "dist"
if (-not (Test-Path -LiteralPath $env:AUTOCLICKER_DATA_DIR)) {
    New-Item -ItemType Directory -Path $env:AUTOCLICKER_DATA_DIR -Force | Out-Null
}
Set-Location $ProjectDir
& (Join-Path $ProjectDir ".venv\Scripts\python.exe") main.py
Read-Host "Press Enter to exit"
