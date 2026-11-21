# ============================================================
#  AutoClicker 打包脚本 (PowerShell)
#
#  - 调用 script/gen_readme.py 生成 README.md（行数/目录树/git 版本）
#  - 用 PyInstaller 打两种形态（默认都打）:
#      dist/AutoClicker.exe                                单文件 exe（--onefile）
#      dist/AutoClicker_v<版本>_<日期>_single_win64.exe    同一文件的带版本号副本
#      dist/AutoClicker_v<版本>_<日期>_win64.zip           绿色目录 zip（--onedir）
#  - -WithSource 时额外打一份源码 zip
#
#  默认就是"编译成程序"，不需要任何额外开关。
#
#  用法:
#    powershell -ExecutionPolicy Bypass -File script\package.ps1
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -CheckOnly
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -Version 1.1.0
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -SkipSingle
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -SkipGreen
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -SkipExe
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -WithSource
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -SkipReadme
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -SkipDeps
#    powershell -ExecutionPolicy Bypass -File script\package.ps1 -Force
# ============================================================
[CmdletBinding()]
param(
    [string]$Version = "1.0.0",
    # 默认两种形态都打。只要一种时用下面两个开关。
    [switch]$SkipExe,      # 两种都不打（等价于旧语义）
    [switch]$SkipSingle,   # 不打单文件 exe，只打绿色目录 zip
    [switch]$SkipGreen,    # 不打绿色目录 zip，只打单文件 exe
    # 兼容旧用法：写了也等于"打 exe"（现在是默认行为，无需再传）
    [switch]$BuildExe,
    # 额外再打一个源码 zip（默认不打 —— 发布物是 exe，不是源码包）
    [switch]$WithSource,
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
    param([string]$PythonExe, [string]$Ver, [string]$Mode = 'onefile')

    $modeLabel = if ($Mode -eq 'onefile') { '单文件 exe' } else { '绿色目录' }
    Write-Step "[2/4] Building $modeLabel ..."

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
    # 两种形态用各自的 spec/work 目录，否则第二次跑会把第一次的中间产物当缓存复用
    $specDir = Join-Path $buildDir "pyinstaller-$Mode"
    $workDir = Join-Path $buildDir "pyinstaller-work-$Mode"
    # --onefile 直接吐到 dist/；--onedir 先吐到 build/green/（那是个文件夹，
    # 里面是 exe + 一堆依赖，不适合直接放 dist/，压完 zip 再说）
    $outDir = if ($Mode -eq 'onefile') { $distDir } else { Join-Path $buildDir 'green' }

    # ---- 版本信息（资源管理器「属性 → 详细信息」里看到的内容）
    # 不给这个文件，exe 的版本页是空的，右键属性一片空白，看着像没编译完整。
    # PyInstaller 要的不是 .rc，而是一个「Python 字面量」格式的文本。
    $verFile = Join-Path $buildDir "version_info_$Mode.txt"
    $verParts = @(1, 0, 0, 0)
    $verNums = $Ver -split '\.'
    for ($i = 0; $i -lt [Math]::Min(3, $verNums.Count); $i++) {
        $parsed = 0
        if ([int]::TryParse($verNums[$i], [ref]$parsed)) { $verParts[$i] = $parsed }
    }
    $verTuple = '(' + ($verParts -join ', ') + ')'
    $verText = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=$verTuple,
    prodvers=$verTuple,
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'080404B0',
        [StringStruct(u'CompanyName', u'YOUXICHUNMI'),
         StringStruct(u'FileDescription', u'AutoClicker - 自动连点器'),
         StringStruct(u'FileVersion', u'$Ver'),
         StringStruct(u'InternalName', u'AutoClicker'),
         StringStruct(u'LegalCopyright', u'MIT License'),
         StringStruct(u'OriginalFilename', u'AutoClicker.exe'),
         StringStruct(u'ProductName', u'AutoClicker'),
         StringStruct(u'ProductVersion', u'$Ver')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)
"@
    [System.IO.File]::WriteAllText($verFile, $verText, (New-Object System.Text.UTF8Encoding($false)))

    $pyArgs = @(
        '-m', 'PyInstaller',
        '--noconfirm',
        '--clean',
        "--$Mode",
        '--windowed',
        '--name', 'AutoClicker',
        '--version-file', $verFile,
        '--distpath', $outDir,
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

    # --onedir 的产物是个文件夹：$outDir\AutoClicker\AutoClicker.exe
    $exePath = if ($Mode -eq 'onefile') {
        Join-Path $outDir 'AutoClicker.exe'
    } else {
        Join-Path (Join-Path $outDir 'AutoClicker') 'AutoClicker.exe'
    }
    if (-not (Test-Path -LiteralPath $exePath)) {
        throw "构建结束但未找到 $exePath"
    }
    $sizeMB = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
    Write-Ok "      AutoClicker.exe  ($sizeMB MB)"

    if ($Mode -eq 'onefile') {
        # 单文件形态：dist/AutoClicker.exe 就是全部内容，
        # 再放一份带版本号的副本便于归档。
        $stamp = Get-Date -Format 'yyyyMMdd'
        $versioned = Join-Path $distDir "AutoClicker_v${Ver}_${stamp}_single_win64.exe"
        Copy-Item -LiteralPath $exePath -Destination $versioned -Force
        Write-Ok "      $(Split-Path -Leaf $versioned)"
        return $exePath
    }

    # 绿色目录形态：把整个 AutoClicker\ 文件夹压成 zip。
    # 注意压的是文件夹里的内容（exe 与依赖平铺在根），
    # 这样用户解压就能直接双击 exe，不用再进一层。
    if ($SkipZip) {
        Write-Host "      (跳过 zip 打包，绿色目录在 build\green\ 下)" -ForegroundColor DarkGray
        return $exePath
    }

    $srcDir  = Join-Path $outDir 'AutoClicker'
    $stamp   = Get-Date -Format 'yyyyMMdd'
    $zipName = "AutoClicker_v${Ver}_${stamp}_win64.zip"
    $zipPath = Join-Path $distDir $zipName

    $stage = Join-Path ([System.IO.Path]::GetTempPath()) ("AutoClicker_green_" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    try {
        Copy-Item -Path (Join-Path $srcDir '*') -Destination $stage -Recurse -Force
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
    param([string]$Ver, [bool]$ExpectSource = $false)

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
    # AutoClicker.exe 与 *_single_win64.exe 是两个文件，两个模式都要列出来
    $artifacts = @()
    foreach ($pat in @('*.zip', '*.tar.gz', 'AutoClicker.exe', '*_single_win64.exe')) {
        $items = Get-ChildItem -LiteralPath $distDir -Filter $pat -File -ErrorAction SilentlyContinue
        foreach ($i in $items) { $artifacts += $i }
    }
    $artifacts = $artifacts | Sort-Object FullName -Unique | Sort-Object LastWriteTime -Descending

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

        # 源码 zip（AutoClicker_vX_日期.zip，不带 _win64）现在只有 -WithSource 才产出。
        # 没要它就别拿它比时间，否则默认流程永远有一项"过期"。
        $isSourceZip = ($a.Name -match '^AutoClicker_v[^/]*_\d{8}\.zip$') -and ($a.Name -notlike '*_win64.zip')
        $skipSource  = $isSourceZip -and (-not $ExpectSource)
        # 日期戳不是今天的产物属于历史归档（同一天多次打包会覆盖同名文件，
        # 换了一天就留成旧文件）。它们不可能是本次打包的预期产物，
        # 拿它们跟今天的源码比 mtime 只会永远报过期，所以只展示不判定。
        $todayStamp = Get-Date -Format 'yyyyMMdd'
        $isOldDate  = ($a.Name -match '_(\d{8})') -and ($Matches[1] -ne $todayStamp)
        $stale = ($a.LastWriteTime -lt $src.Time)

        if ($isOldDate) {
            Write-Host  ("  [归档] {0}  ({1} MB, {2})  历史产物，不参与判定" -f $a.Name, $sizeMb, $ageStr) -ForegroundColor DarkGray
        } elseif ($skipSource) {
            Write-Host  ("  [跳过] {0}  ({1} MB, {2})  源码 zip，需 -WithSource 才会重建" -f $a.Name, $sizeMb, $ageStr) -ForegroundColor DarkGray
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

    # 该有的形态齐全吗？两种形态产出的文件名不一样，
    # 只按 mtime 判「过期」发现不了「这一种形态根本没打过」。
    $todayArtifacts = $artifacts | Where-Object { $_.Name -match "_$todayStamp" }
    if ($todayArtifacts) {
        $wantSingle = -not $SkipSingle -and -not $SkipExe
        $wantGreen  = -not $SkipGreen  -and -not $SkipExe
        if ($wantGreen) {
            if (-not ($todayArtifacts | Where-Object { $_.Name -like '*_win64.zip' })) {
                $allFresh = $false
                Write-Warn2 ("  今天还没有绿色目录 zip（AutoClicker_v{0}_{1}_win64.zip）" -f $Ver, $todayStamp)
            }
        }
        if ($wantSingle) {
            if (-not ($todayArtifacts | Where-Object { $_.Name -like '*_single_win64.exe' })) {
                $allFresh = $false
                Write-Warn2 ("  今天还没有带版本号的单文件 exe（AutoClicker_v{0}_{1}_single_win64.exe）" -f $Ver, $todayStamp)
            }
        }
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

# 默认两种形态都打。只要一种时用 -SkipSingle / -SkipGreen。
# -SkipExe 保留旧语义：两种都不打（只重生成 README 之类）。
$wantSingle = (-not $SkipExe) -and (-not $SkipGreen)
$wantGreen  = (-not $SkipExe) -and (-not $SkipSingle)
$forms = @()
if ($wantSingle) { $forms += '单文件 exe' }
if ($wantGreen)  { $forms += '绿色目录 zip' }
if ($forms.Count -eq 0) { $forms += '（不打可执行文件）' }
Write-Host "[INFO] Target  : $($forms -join ' + ')"
if ($WithSource) { Write-Host "[INFO] -WithSource 已指定，额外打源码 zip" -ForegroundColor DarkGray }
Write-Host ""

$results = @{ Readme = $null; Zip = $null; Exe = $null; Green = $null }

# 每次运行都先报一下 dist/ 里的产物是不是最新的
$fresh = Show-BuildStatus -Ver $Version -ExpectSource ([bool]$WithSource)
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
        Write-Warn2 "[1/4] Skip README generation."
    }

    # 两种形态各打一次。dist\ 先清空，免得上一轮的旧产物混进来。
    if ($wantSingle -or $wantGreen) {
        $distDir = Join-Path $ProjectDir 'dist'
        if (Test-Path -LiteralPath $distDir) {
            Remove-Item $distDir -Recurse -Force
        }
        New-Item -ItemType Directory -Path $distDir -Force | Out-Null
    }

    if ($wantSingle) {
        $results.Exe = Build-Exe -PythonExe $py.Exe -Ver $Version -Mode 'onefile'
    } else {
        Write-Warn2 "[2/4] Skip single exe (-SkipGreen / -SkipExe)."
    }

    if ($wantGreen) {
        $results.Green = Build-Exe -PythonExe $py.Exe -Ver $Version -Mode 'onedir'
    } else {
        Write-Warn2 "[3/4] Skip green dir zip (-SkipSingle / -SkipExe)."
    }

    # 源码 zip 只在显式 -WithSource 时打
    if ($WithSource -and -not $SkipZip) {
        $results.Zip = New-SourcePackage -Ver $Version
    } elseif ($WithSource) {
        Write-Warn2 "[4/4] Skip source zip (-SkipZip)."
    } else {
        Write-Host "[4/4] Skip source zip (用 -WithSource 可额外打一份)." -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Ok " Done!"
    if ($results.Readme) { Write-Host "   README : README.md" }
    $distAbs = Join-Path $ProjectDir 'dist'
    if (Test-Path -LiteralPath $distAbs) {
        Get-ChildItem -LiteralPath $distAbs -File | Where-Object {
            $_.Extension -in @('.exe', '.zip', '.gz')
        } | Sort-Object Name | ForEach-Object {
            $mb = [math]::Round($_.Length / 1MB, 2)
            Write-Host ("   {0,-46} {1,8} MB" -f $_.Name, $mb)
        }
    }
    if ($results.Zip)    { Write-Host "   Source : dist\$((Split-Path -Leaf $results.Zip))" }
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
} catch {
    Write-Err2 ""
    Write-Err2 "[ERROR] $($_.Exception.Message)"
    if ($_.ScriptStackTrace) { Write-Err2 $_.ScriptStackTrace }
    exit 1
}
