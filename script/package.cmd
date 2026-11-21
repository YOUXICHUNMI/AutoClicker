@echo off
rem ============================================================
rem  AutoClicker 打包脚本 (cmd)
rem
rem  这是 script\package.ps1 的薄包装：负责找到 PowerShell 并转调，
rem  真正的逻辑只有一份，避免 cmd 里重复实现模板替换与压缩。
rem  默认产出 dist\AutoClicker.exe（单文件 exe），无需额外开关。
rem
rem  用法:
rem    script\package.cmd
rem    script\package.cmd -Version 1.1.0
rem    script\package.cmd -Version 1.1.0
rem    script\package.cmd -SkipExe
rem    script\package.cmd -WithSource
rem    script\package.cmd -CheckOnly
rem    script\package.cmd -SkipZip
rem    script\package.cmd -SkipReadme
rem    script\package.cmd -SkipDeps
rem ============================================================
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "PROJECT_DIR=%SCRIPT_DIR%\.."
pushd "%PROJECT_DIR%" >nul 2>&1 || (echo [ERROR] 无法进入项目目录 & exit /b 1)
set "PROJECT_DIR=%CD%"
popd >nul

set "PS1=%SCRIPT_DIR%\package.ps1"
if not exist "%PS1%" (
    echo [ERROR] 找不到 %PS1%
    exit /b 1
)

rem 优先用 pwsh (PowerShell 7)，否则回退到 Windows PowerShell 5.1
set "PSEXE="
where pwsh >nul 2>&1 && set "PSEXE=pwsh"
if not defined PSEXE (
    where powershell >nul 2>&1 && set "PSEXE=powershell"
)
if not defined PSEXE (
    echo [ERROR] 未找到 PowerShell，请先安装 PowerShell 5.1 或更高版本
    exit /b 1
)

"%PSEXE%" -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
set "RC=%ERRORLEVEL%"

rem 退出码约定（与 ps1 一致）：
rem   0 = 成功 / 产物已是最新
rem   2 = 仅检测模式下发现产物过期（不是错误）
rem   其它 = 真失败
if "%RC%"=="2" (
    echo.
    echo [INFO] 检测结果：dist\ 里的产物已过期，需要重新打包。
    echo        去掉 -CheckOnly 再跑一次即可。
) else if not "%RC%"=="0" (
    echo.
    echo [ERROR] 打包失败，退出码 %RC%
)
endlocal & exit /b %RC%
