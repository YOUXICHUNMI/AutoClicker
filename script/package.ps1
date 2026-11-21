# ============================================================
#  AutoClicker 打包脚本 (PowerShell)
#
#  - 调用 script/gen_readme.py 生成 README.md（行数/目录树/git 版本）
#  - 打包源码 zip 到 dist/，排除 .venv / __pycache__ / log / dist / build
#  - 可选 -BuildExe：用 PyInstaller 打单文件 exe
#
#  用法:
#    powershell -ExecutionPolicy Bypass -File script\package.ps1
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -CheckOnly
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -Version 1.1.0
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -BuildExe
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -SkipZip
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -SkipReadme
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -SkipDeps
# ============================================================
[CmdletBinding()]
param(
    [string]$Version = "1.0.0",
    [switch]$BuildExe,
    [switch]$SkipZip,
    [switch]$SkipReadme,
    [switch]$SkipDeps,
    # 只检查 dist/ 里的产物是不是最新的，检查完就退出，不打包
    [switch]$CheckOnly,
    # 产物已最新时也强制重新打包（跳过交互确认）
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# ---------- 路径 ----------
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
Set-Location $ProjectDir

# ---------- 排除规则 ----------
$ExcludeDirs  = @('.venv', 'venv', '__pycache__', '.git', 'dist', 'build',
                  '.idea', '.vscode', 'log', '.pytest_cache', '.mypy_cache')
$ExcludeFiles = @('*.pyc', '*.pyo', '*.pyd', '*.log', '.DS_Store', 'Thumbs.db')

# 仅打包时排除: config/config.json 是每台机器本地生成的状态文件(含窗口标题/句柄等本机信息),
# 不随发布包分发 —— 程序首次运行会自动以默认值重建。目录树里仍保留它以说明结构。
$ZipOnlyExcludeFiles = @('config.json')

function Write-Step([string]$Msg)  { Write-Host $Msg -ForegroundColor Yellow }
function Write-Ok([string]$Msg)    { Write-Host $Msg -ForegroundColor Green }
function Write-Warn2([string]$Msg) { Write-Host $Msg -ForegroundColor DarkYellow }
function Write-Err2([string]$Msg)  { Write-Host $Msg -ForegroundColor Red }

# ============================================================
#  0. 定位可用的 Python
# ============================================================
function Test-PythonExe {
    param([string]$Exe)
    if (-not $Exe) { return $false }
    if (-not (Test-Path -LiteralPath $Exe)) { return $false }
    try {
        $out = & $Exe -c "import sys;print(sys.version_info[0])" 2>$null
        return ($LASTEXITCODE -eq 0 -and "$out".Trim() -eq "3")
    } catch {
        return $false
    }
}

function Find-Python {
    # 1) 项目自带 venv（优先，依赖都在里面）
    $venvPy = Join-Path $ProjectDir '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPy) {
        if (Test-PythonExe $venvPy) {
            return @{ Exe = $venvPy; Kind = 'venv' }
        }
        Write-Warn2 "      .venv\Scripts\python.exe 无法运行（base 解释器可能已被卸载）"
        Write-Warn2 "      请删除 .venv 后重新执行 script\install.ps1，或改用系统 Python"
    }

    # 2) PATH 里的 python
    foreach ($name in @('python', 'python3')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and (Test-PythonExe $cmd.Source)) {
            return @{ Exe = $cmd.Source; Kind = 'system' }
        }
    }

    # 3) py launcher
    $pyCmd = Get-Command 'py' -ErrorAction SilentlyContinue
    if ($pyCmd) {
        try {
            $real = & py -c "import sys;print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and (Test-PythonExe "$real".Trim())) {
                return @{ Exe = "$real".Trim(); Kind = 'launcher' }
            }
        } catch { }
    }
    return $null
}

# ============================================================
#  1. 生成 README.md
# ============================================================
function New-Readme {
    param([string]$PythonExe)

    Write-Step "[1/3] Generating README.md ..."

    $gen = Join-Path $ScriptDir 'gen_readme.py'
    if (-not (Test-Path -LiteralPath $gen)) {
        throw "缺少 README 生成器: $gen"
    }

    # 用文件重定向而非 2>&1：避免 stderr 被 PowerShell 转成 ErrorRecord 打印
    # "NativeCommandError"，也避免子进程 stdout 被调用方当作函数返回值收集。
    $genLog = Join-Path ([System.IO.Path]::GetTempPath()) ("gen_readme_" + [guid]::NewGuid().ToString('N') + ".log")
    $genRc = 1
    try {
        & $PythonExe $gen --version $Version *> $genLog
        $genRc = $LASTEXITCODE
        if (Test-Path -LiteralPath $genLog) {
            Get-Content -LiteralPath $genLog | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
        }
    } finally {
        if (Test-Path -LiteralPath $genLog) { Remove-Item -LiteralPath $genLog -Force -ErrorAction SilentlyContinue }
    }
    if ($genRc -ne 0) {
        throw "gen_readme.py 执行失败 (exit $genRc)"
    }
}

# ============================================================
#  2. 打包源码 zip
# ============================================================
function New-SourcePackage {
    param([string]$Ver)

    Write-Step "[2/3] Packaging source zip ..."

    $distDir = Join-Path $ProjectDir 'dist'
    if (-not (Test-Path -LiteralPath $distDir)) {
        New-Item -ItemType Directory -Path $distDir -Force | Out-Null
    }

    $stamp   = Get-Date -Format 'yyyyMMdd'
    $zipName = "AutoClicker_v${Ver}_$stamp.zip"
    $zipPath = Join-Path $distDir $zipName

    # 用临时暂存目录，先复制（带排除），再压缩 —— 比逐文件 Add 更可靠
    $stage = Join-Path ([System.IO.Path]::GetTempPath()) ("AutoClicker_pkg_" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage -Force | Out-Null

    try {
        $xdArgs = @()
        foreach ($d in $ExcludeDirs) { $xdArgs += $d }
        $xfArgs = @()
        foreach ($f in $ExcludeFiles) { $xfArgs += $f }
        foreach ($f in $ZipOnlyExcludeFiles) { $xfArgs += $f }

        $roboLog = Join-Path $stage '_robocopy.log'
        & robocopy $ProjectDir $stage /E /NFL /NDL /NJH /NJS /NP /XD @xdArgs /XF @xfArgs *> $roboLog
        $rc = $LASTEXITCODE
        Remove-Item $roboLog -Force -ErrorAction SilentlyContinue
        if ($rc -ge 8) {
            throw "robocopy failed with exit code $rc"
        }

        # 排除后 config/ 可能变成空目录，删掉以免误导
        $cfgStage = Join-Path $stage 'config'
        if ((Test-Path -LiteralPath $cfgStage) -and -not (Get-ChildItem $cfgStage -Force)) {
            Remove-Item $cfgStage -Recurse -Force
        }

        if (Test-Path -LiteralPath $zipPath) { Remove-Item $zipPath -Force }
        Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath -CompressionLevel Optimal -Force

        $sizeKB = [math]::Round((Get-Item $zipPath).Length / 1KB, 1)
        Write-Ok  "      $zipName  ($sizeKB KB)"
        return $zipPath
    } finally {
        if (Test-Path -LiteralPath $stage) {
            Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# ============================================================
#  3. 打 exe (PyInstaller)
# ============================================================
function Build-Exe {
    param([string]$PythonExe, [string]$Ver)

    Write-Step "[3/3] Building standalone exe ..."

    # 依赖自检
    # 注意: $ErrorActionPreference = "Stop" 下对原生命令用 2>$null 会抛
    # NativeCommandError（stderr 被当作终止性错误）。这里必须用 try/catch 包住。
    if (-not $SkipDeps) {
        $hasPyInstaller = $false
        try {
            & $PythonExe -c "import PyInstaller" 2>&1 | Out-Null
            $hasPyInstaller = ($LASTEXITCODE -eq 0)
        } catch {
            $hasPyInstaller = $false
        }
        if (-not $hasPyInstaller) {
            Write-Warn2 "      未安装 PyInstaller，正在安装 ..."
            # 必须重定向到文件：pip 的输出若走管道会被当作本函数的返回值收集，
            # Build-Exe 就变成返回「一堆 pip 日志 + zip 路径」的数组，主流程
            # Split-Path -Leaf 收到数组即报 Cannot bind argument to parameter Path。
            $pipLog = Join-Path ([System.IO.Path]::GetTempPath()) ("pip_" + [guid]::NewGuid().ToString('N') + ".log")
            $pipRc = 1
            $prevEap2 = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            try {
                & $PythonExe -m pip install --upgrade pyinstaller *> $pipLog
                $pipRc = $LASTEXITCODE
                if (Test-Path -LiteralPath $pipLog) {
                    Get-Content -LiteralPath $pipLog -Tail 3 |
                        ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
                }
            } finally {
                $ErrorActionPreference = $prevEap2
                if (Test-Path -LiteralPath $pipLog) { Remove-Item -LiteralPath $pipLog -Force -ErrorAction SilentlyContinue }
            }
            if ($pipRc -ne 0) { throw "PyInstaller 安装失败 (exit $pipRc)" }
        }
    }

    $distDir = Join-Path $ProjectDir 'dist'
    $buildDir = Join-Path $ProjectDir 'build'
    foreach ($d in @($distDir, $buildDir)) {
        if (-not (Test-Path -LiteralPath $d)) {
            New-Item -ItemType Directory -Path $d -Force | Out-Null
        }
    }

    $icon = Join-Path $ProjectDir 'utils\static\Ralsei.ico'
    $addData = Join-Path $ProjectDir 'utils\static'
    $specDir = Join-Path $buildDir 'pyinstaller'
    $workDir = Join-Path $buildDir 'pyinstaller-work'

    $pyArgs = @(
        '-m', 'PyInstaller',
        '--noconfirm',
        '--clean',
        '--onefile',
        '--windowed',
        '--name', 'AutoClicker',
        '--distpath', $distDir,
        '--workpath', $workDir,
        '--specpath', $specDir,
        # 只读资源：整个 utils/static 打进包，运行时用 resource_path() 取
        '--add-data', "$addData;utils/static"
    )
    if (Test-Path -LiteralPath $icon) {
        $pyArgs += @('--icon', $icon)
    }
    # 明显用不到的 Qt 大模块，显式排掉能省十几 MB
    foreach ($mod in @('PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets',
                       'PyQt6.QtMultimedia', 'PyQt6.QtQuick', 'PyQt6.QtQml',
                       'PyQt6.QtBluetooth', 'PyQt6.QtDesigner', 'PyQt6.QtHelp',
                       'PyQt6.QtNetworkAuth', 'PyQt6.Qt3DCore', 'PyQt6.QtCharts')) {
        $pyArgs += @('--exclude-module', $mod)
    }
    $pyArgs += @((Join-Path $ProjectDir 'main.py'))

    Write-Host ("      pyinstaller " + ($pyArgs -join ' ')) -ForegroundColor DarkGray
    # PyInstaller 把所有 INFO 日志写到 stderr。PowerShell 5.1 在
    # $ErrorActionPreference='Stop' 下会把原生命令的每条 stderr 转成终止性
    # ErrorRecord（NativeCommandError），即使已经重定向到文件也会中断。
    # 解决：临时把 EAP 调回 Continue，并 *> 重定向到文件，退出码单独判断。
    $pyLog = Join-Path ([System.IO.Path]::GetTempPath()) ("pyinstaller_" + [guid]::NewGuid().ToString('N') + ".log")
    $pyRc = 1
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $PythonExe @pyArgs *> $pyLog
        $pyRc = $LASTEXITCODE
        if (Test-Path -LiteralPath $pyLog) {
            $tailCount = if ($pyRc -eq 0) { 10 } else { 60 }
            Get-Content -LiteralPath $pyLog -Tail $tailCount |
                ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
        }
    } finally {
        $ErrorActionPreference = $prevEap
        if (Test-Path -LiteralPath $pyLog) {
            if ($pyRc -ne 0) {
                $keep = Join-Path $buildDir 'pyinstaller-error.log'
                Move-Item -LiteralPath $pyLog -Destination $keep -Force -ErrorAction SilentlyContinue
                Write-Warn2 "      完整日志已保存: $keep"
            } else {
                Remove-Item -LiteralPath $pyLog -Force -ErrorAction SilentlyContinue
            }
        }
    }
    if ($pyRc -ne 0) {
        throw "PyInstaller 构建失败 (exit $pyRc)"
    }

    $exePath = Join-Path $distDir 'AutoClicker.exe'
    if (-not (Test-Path -LiteralPath $exePath)) {
        throw "构建结束但未找到 $exePath"
    }
    $sizeMB = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
    Write-Ok "      AutoClicker.exe  ($sizeMB MB)"

    # 把 exe + 文档 + 一份默认配置说明打成一个发布包
    $stamp   = Get-Date -Format 'yyyyMMdd'
    $zipName = "AutoClicker_v${Ver}_${stamp}_win64.zip"
    $zipPath = Join-Path $distDir $zipName

    $stage = Join-Path ([System.IO.Path]::GetTempPath()) ("AutoClicker_exe_" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    try {
        Copy-Item -LiteralPath $exePath -Destination $stage -Force
        $readme = Join-Path $ProjectDir 'README.md'
        if (Test-Path -LiteralPath $readme) {
            Copy-Item -LiteralPath $readme -Destination $stage -Force
        }
        $lic = Join-Path $ProjectDir 'LICENSE'
        if (Test-Path -LiteralPath $lic) {
            Copy-Item -LiteralPath $lic -Destination $stage -Force
        }
        # 附一个空 config 目录，暗示用户配置会落在 exe 同级
        $cfg = Join-Path $stage 'config'
        New-Item -ItemType Directory -Path $cfg -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $cfg '说明.txt') -Encoding UTF8 -Value @"
AutoClicker 首次运行时会在本目录生成 config.json。
删掉 config.json 即可恢复默认配置。
日志写在同级的 log/ 目录，按日期滚动。
"@

        if (Test-Path -LiteralPath $zipPath) { Remove-Item $zipPath -Force }
        Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath -CompressionLevel Optimal -Force
        $zipKB = [math]::Round((Get-Item $zipPath).Length / 1KB, 1)
        Write-Ok "      $zipName  ($zipKB KB)"
        return $zipPath
    } finally {
        if (Test-Path -LiteralPath $stage) {
            Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# ============================================================
#  检测：dist/ 里的产物是否比源码新
# ============================================================
function Get-SourceStamp {
    # 返回项目源码中最新修改时间（只看会进包的文件，排除 .venv / dist / build / log 等）
    $root = $ProjectDir
    $newest = [datetime]::MinValue
    $newestFile = ''

    $skipDirs = @('.venv', 'venv', '__pycache__', '.git', 'dist', 'build',
                  '.idea', '.vscode', 'log', '.pytest_cache', '.mypy_cache',
                  'node_modules')

    # 只统计这些顶层目录下的源码/脚本/资源，避免全盘递归扫描
    # 注意：config/ 与 log/ 是运行期数据（现在默认落在 dist/ 下），不属于源码，不参与判断
    $roots = @('main.py', 'core', 'ui', 'utils', 'script', 'README.md', 'requirements.txt')

    $files = @()
    foreach ($r in $roots) {
        $p = Join-Path $root $r
        if (-not (Test-Path -LiteralPath $p)) { continue }
        if (Test-Path -LiteralPath $p -PathType Leaf) {
            $files += Get-Item -LiteralPath $p
        } else {
            $files += Get-ChildItem -LiteralPath $p -Recurse -File -ErrorAction SilentlyContinue
        }
    }

    foreach ($f in $files) {
        # 跳过被排除目录下的文件
        $rel = $f.FullName.Substring($root.Length).TrimStart('\', '/')
        $skip = $false
        foreach ($d in $skipDirs) {
            if ($rel -match "(^|[\\/])$([regex]::Escape($d))([\\/]|$)") { $skip = $true; break }
        }
        if ($skip) { continue }
        if ($ExcludeFiles -contains $f.Name) { continue }
        if ($f.LastWriteTime -gt $newest) {
            $newest = $f.LastWriteTime
            $newestFile = $rel
        }
    }

    return [pscustomobject]@{
        Time  = $newest
        File  = $newestFile
        Count = $files.Count
    }
}

function Show-BuildStatus {
    param([string]$Ver)

    Write-Host ""
    Write-Host "------------- 打包产物检测 -------------" -ForegroundColor Cyan

    $distDir = Join-Path $ProjectDir 'dist'
    if (-not (Test-Path -LiteralPath $distDir)) {
        Write-Warn2 "  dist/ 目录不存在 —— 还没打过包。"
        Write-Host "----------------------------------------" -ForegroundColor Cyan
        return $false
    }

    $src = Get-SourceStamp
    Write-Host ("  源码最新改动: {0}  ({1})" -f $src.Time.ToString('yyyy-MM-dd HH:mm:ss'), $src.File)

    # 收集 dist 里的产物；.tar.gz 是 package.sh 的产物，只展示不参与判定，
    # 否则用 ps1 的人会永远看到「过期」。
    $artifacts = @()
    foreach ($pat in @('*.zip', '*.tar.gz', 'AutoClicker.exe')) {
        $items = Get-ChildItem -LiteralPath $distDir -Filter $pat -File -ErrorAction SilentlyContinue
        foreach ($i in $items) { $artifacts += $i }
    }
    $artifacts = $artifacts | Sort-Object LastWriteTime -Descending

    if ($artifacts.Count -eq 0) {
        Write-Warn2 "  dist/ 里没有任何产物 —— 需要打包。"
        Write-Host "----------------------------------------" -ForegroundColor Cyan
        return $false
    }

    $allFresh = $true
    $todayCount = 0
    foreach ($a in $artifacts) {
        $sizeMb = [math]::Round($a.Length / 1MB, 2)
        $age    = (Get-Date) - $a.LastWriteTime
        $ageStr = if ($age.TotalHours -lt 1) {
            '{0} 分钟前' -f [math]::Max(1, [int]$age.TotalMinutes)
        } elseif ($age.TotalDays -lt 1) {
            '{0} 小时前' -f [int]$age.TotalHours
        } else {
            '{0} 天前' -f [int]$age.TotalDays
        }

        # .tar.gz 归 package.sh 管，不参与本地判定
        $other = $a.Name -like '*.tar.gz'
        # 日期戳不是今天的产物属于历史归档（同一天多次打包会覆盖同名文件，
        # 换了一天就留成旧文件）。它们不可能是本次打包的预期产物，
        # 拿它们跟今天的源码比 mtime 只会永远报过期，所以只展示不判定。
        $todayStamp = Get-Date -Format 'yyyyMMdd'
        $isOldDate  = ($a.Name -match '_(\d{8})') -and ($Matches[1] -ne $todayStamp)
        $stale = ($a.LastWriteTime -lt $src.Time)

        if ($isOldDate) {
            Write-Host  ("  [归档] {0}  ({1} MB, {2})  历史产物，不参与判定" -f $a.Name, $sizeMb, $ageStr) -ForegroundColor DarkGray
        } elseif ($stale -and -not $other) {
            $allFresh = $false
            Write-Warn2 ("  [过期] {0}  ({1} MB, {2})" -f $a.Name, $sizeMb, $ageStr)
        } elseif ($stale) {
            Write-Host  ("  [跳过] {0}  ({1} MB, {2})  package.sh 的产物" -f $a.Name, $sizeMb, $ageStr) -ForegroundColor DarkGray
        } else {
            Write-Ok   ("  [最新] {0}  ({1} MB, {2})" -f $a.Name, $sizeMb, $ageStr)
        }

        if (-not $isOldDate) { $todayCount++ }
    }

    # 全是历史归档、今天一个产物都没有，同样算需要打包
    if ($todayCount -eq 0) {
        $allFresh = $false
        Write-Warn2 "  dist/ 里没有今天（$((Get-Date).ToString('yyyy-MM-dd'))）的产物 —— 需要打包。"
    }

    # 版本号一致性提醒
    $zipNames = $artifacts | Where-Object { $_.Name -like 'AutoClicker_v*' }
    if ($zipNames) {
        $mismatch = $zipNames | Where-Object { $_.Name -notlike "*v$Ver*" }
        if ($mismatch) {
            Write-Warn2 ("  注意: 现有产物的版本号不是当前的 $Ver")
        }
    }

    Write-Host "----------------------------------------" -ForegroundColor Cyan
    if ($allFresh) {
        Write-Ok "  结论: 产物已是最新，无需重新打包。"
    } else {
        Write-Warn2 "  结论: 源码比产物新，建议重新打包。"
    }
    return $allFresh
}

# ============================================================
#  主流程
# ============================================================
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "        AutoClicker Package Builder" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "[INFO] Project : $ProjectDir"
Write-Host "[INFO] Version : $Version"
Write-Host "[INFO] BuildExe: $BuildExe"
Write-Host ""

$results = @{ Readme = $null; Zip = $null; Exe = $null }

# 每次运行都先报一下 dist/ 里的产物是不是最新的
$fresh = Show-BuildStatus -Ver $Version
Write-Host ""

if ($CheckOnly) {
    Write-Host "[INFO] -CheckOnly 模式：仅检测，不执行打包。" -ForegroundColor DarkGray
    Write-Host ""
    if ($fresh) { exit 0 } else { exit 2 }
}

# 产物已是最新时，先问一句要不要白打一遍（管道/非交互场景自动跳过）
if ($fresh -and -not $Force) {
    $interactive = $true
    try { $interactive = -not [Console]::IsInputRedirected } catch { $interactive = $false }

    if ($interactive) {
        Write-Host ""
        $ans = Read-Host "产物已是最新，仍要重新打包吗？[y/N]"
        if ($ans -notmatch '^[yY]') {
            Write-Ok ""
            Write-Ok "已跳过打包。"
            Write-Host ""
            exit 0
        }
        Write-Host ""
    } else {
        Write-Warn2 "[INFO] 非交互环境，继续打包（用 -CheckOnly 可只检测）。"
        Write-Host ""
    }
}

try {
    $py = Find-Python
    if (-not $py) {
        throw "未找到可用的 Python 3，请安装 Python 3.10+ 或先运行 script\install.ps1"
    }
    Write-Host "[INFO] Python  : $($py.Exe)  [$($py.Kind)]"
    Write-Host ""

    if (-not $SkipReadme) {
        New-Readme -PythonExe $py.Exe
        $results.Readme = Join-Path $ProjectDir 'README.md'
    } else {
        Write-Warn2 "[1/3] Skip README generation."
    }

    if (-not $SkipZip) {
        $results.Zip = New-SourcePackage -Ver $Version
    } else {
        Write-Warn2 "[2/3] Skip source zip."
    }

    if ($BuildExe) {
        $results.Exe = Build-Exe -PythonExe $py.Exe -Ver $Version
    } else {
        Write-Warn2 "[3/3] Skip exe build (use -BuildExe to enable)."
    }

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Ok " Done!"
    if ($results.Readme) { Write-Host "   README : README.md" }
    if ($results.Zip)    { Write-Host "   Source : dist\$((Split-Path -Leaf $results.Zip))" }
    if ($results.Exe)    { Write-Host "   Release: dist\$((Split-Path -Leaf $results.Exe))" }
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
} catch {
    Write-Err2 ""
    Write-Err2 "[ERROR] $($_.Exception.Message)"
    if ($_.ScriptStackTrace) { Write-Err2 $_.ScriptStackTrace }
    exit 1
}
