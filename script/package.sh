#!/usr/bin/env bash
# ============================================================
#  AutoClicker 打包脚本 (bash)
#
#  - 调用 script/gen_readme.py 生成 README.md（行数/目录树/git 版本）
#  - Windows 上（Git Bash / MSYS2）：用 PyInstaller 打两种形态（默认都打）
#      dist/AutoClicker.exe                                单文件 exe（--onefile）
#      dist/AutoClicker_v<版本>_<日期>_single_win64.exe    同一文件的带版本号副本
#      dist/AutoClicker_v<版本>_<日期>_win64.zip           绿色目录 zip（--onedir）
#  - 非 Windows：只能打源码归档（PyInstaller 不能跨平台交叉编译）
#
#  用法:
#    ./script/package.sh
#    ./script/package.sh --check-only     # 只检测 dist/ 产物是否最新，不打
#    ./script/package.sh --force          # 产物已最新也强制重新打包
#    ./script/package.sh --version 1.1.0
#    ./script/package.sh --skip-single    # 只打绿色目录 zip
#    ./script/package.sh --skip-green     # 只打单文件 exe
#    ./script/package.sh --no-exe         # 两种都不打，只做别的
#    ./script/package.sh --with-source    # Windows 上额外再打一份源码归档
#    ./script/package.sh --no-zip
#    ./script/package.sh --no-readme
#    ./script/package.sh --no-deps
#
#  注意:
#    Windows 上请用 Git Bash 或 MSYS2 的 bash，不要用 C:\Windows\System32\bash.exe
#    （那是 WSL 入口，对本机路径与代理的处理不一样，容易出问题）。
# ============================================================
set -euo pipefail

# ---------- 路径 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# ---------- 默认参数 ----------
VERSION="1.0.0"
BUILD_EXE=1      # 默认打程序（非 Windows 平台会自动跳过）
SKIP_SINGLE=0    # --skip-single：只打绿色目录
SKIP_GREEN=0     # --skip-green：只打单文件 exe
DO_ZIP=0        # 源码归档只在 --with-source 时打
DO_README=1
DO_DEPS=1
CHECK_ONLY=0
FORCE=0
WITH_SOURCE=0

# ---------- 排除规则 ----------
EXCLUDE_DIRS=(
  ".venv" "venv" "__pycache__" ".git" "dist" "build"
  ".idea" ".vscode" "log" ".pytest_cache" ".mypy_cache"
)
EXCLUDE_FILE_PATTERNS=(
  "*.pyc" "*.pyo" "*.pyd" "*.log" ".DS_Store" "Thumbs.db"
)
# 仅打包时排除: config/config.json 含本机窗口标题/句柄，程序首次运行会自动重建
ZIP_ONLY_EXCLUDE_FILES=("config.json")

# ---------- 颜色 ----------
if [ -t 1 ]; then
  C_STEP=$'\033[33m'; C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_ERR=$'\033[31m'; C_DIM=$'\033[90m'; C_OFF=$'\033[0m'
else
  C_STEP=''; C_OK=''; C_WARN=''; C_ERR=''; C_DIM=''; C_OFF=''
fi
step() { printf '%s%s%s\n' "$C_STEP" "$*" "$C_OFF"; }
ok()   { printf '%s%s%s\n' "$C_OK"   "$*" "$C_OFF"; }
warn() { printf '%s%s%s\n' "$C_WARN" "$*" "$C_OFF"; }
err()  { printf '%s%s%s\n' "$C_ERR"  "$*" "$C_OFF" >&2; }

usage() {
  # 只打印文件头注释块（第 2 行到 "set -euo" 之前），不要把代码行一起打出来
  awk 'NR>1 { if ($0 !~ /^#/) exit; print }' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

# ---------- 参数解析 ----------
while [ $# -gt 0 ]; do
  case "$1" in
    -v|--version)   VERSION="${2:?--version 需要一个值}"; shift 2 ;;
    -v=*|--version=*) VERSION="${1#*=}"; shift ;;
    -e|--build-exe) BUILD_EXE=1; shift ;;
    --no-exe)       BUILD_EXE=0; shift ;;
    --skip-single)  SKIP_SINGLE=1; shift ;;
    --skip-green)   SKIP_GREEN=1; shift ;;
    --with-source)  WITH_SOURCE=1; DO_ZIP=1; shift ;;
    --no-zip)       DO_ZIP=0; shift ;;
    --no-readme)    DO_README=0; shift ;;
    --no-deps)      DO_DEPS=0; shift ;;
    --check-only)   CHECK_ONLY=1; shift ;;
    -f|--force)     FORCE=1; shift ;;
    -h|--help)      usage 0 ;;
    *)              err "未知参数: $1"; usage 1 ;;
  esac
done

# ---------- 判定平台 ----------
case "$(uname -s 2>/dev/null || echo unknown)" in
  MINGW*|MSYS*|CYGWIN*) PLATFORM="windows" ;;
  Darwin)               PLATFORM="darwin"  ;;
  Linux)                PLATFORM="linux"   ;;
  *)                    PLATFORM="unknown" ;;
esac

# ---------- 定位 Python ----------
is_python3() {
  [ -n "${1:-}" ] && [ -x "$1" ] && "$1" -c 'import sys; sys.exit(0 if sys.version_info[0]==3 else 1)' 2>/dev/null
}

find_python() {
  local venv_py
  if [ "$PLATFORM" = "windows" ]; then
    venv_py="$PROJECT_DIR/.venv/Scripts/python.exe"
  else
    venv_py="$PROJECT_DIR/.venv/bin/python"
  fi

  if [ -e "$venv_py" ]; then
    if is_python3 "$venv_py"; then
      PY_EXE="$venv_py"; PY_KIND="venv"; return 0
    fi
    warn "      .venv 解释器无法运行（base Python 可能已被卸载）"
    warn "      请删除 .venv 后重新执行 script/install.sh，或改用系统 Python"
  fi

  local c
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
      local p; p="$(command -v "$c")"
      if is_python3 "$p"; then PY_EXE="$p"; PY_KIND="system"; return 0; fi
    fi
  done
  return 1
}

# ---------- 1. 生成 README ----------
gen_readme() {
  step "[1/4] Generating README.md ..."
  local gen="$SCRIPT_DIR/gen_readme.py"
  [ -f "$gen" ] || { err "缺少 README 生成器: $gen"; exit 1; }
  PYTHONIOENCODING=utf-8 "$PY_EXE" "$gen" --version "$VERSION" || {
    err "gen_readme.py 执行失败"
    exit 1
  }
}

# ---------- 构造 tar 排除参数 ----------
# GNU tar 的 --exclude 不含 '/' 时按「任一层级」匹配，所以目录名不要带前缀，
# 只有 config/config.json 这种带路径定位的才写全。
TAR_EXCLUDES=()
for _d in "${EXCLUDE_DIRS[@]}";        do TAR_EXCLUDES+=("--exclude=$_d"); done
for _p in "${EXCLUDE_FILE_PATTERNS[@]}"; do TAR_EXCLUDES+=("--exclude=$_p"); done
for _p in "${ZIP_ONLY_EXCLUDE_FILES[@]}"; do TAR_EXCLUDES+=("--exclude=./config/$_p"); done
unset _d _p

# ---------- 2. 打包源码 ----------
pack_source() {
  step "[2/3] Packaging source archive ..."

  local dist="$PROJECT_DIR/dist"
  mkdir -p "$dist"
  local stamp; stamp="$(date +%Y%m%d)"
  local base="AutoClicker_v${VERSION}_${stamp}"

  local made=()

  # --- tar.gz：三个平台都有 tar，作为保底格式 ---
  local tarball="$dist/${base}.tar.gz"
  rm -f "$tarball"
  tar "${TAR_EXCLUDES[@]}" -czf "$tarball" . 2>/dev/null
  made+=("$tarball")

  # --- zip：有 zip 命令时才做，方便 Windows 用户直接解压 ---
  if command -v zip >/dev/null 2>&1; then
    local zipfile="$dist/${base}.zip"
    rm -f "$zipfile"
    # 收集要打包的文件清单，避开 GNU/BSD find 语法差异
    local tmpdir; tmpdir="$(mktemp -d)"
    local stage="$tmpdir/stage"
    mkdir -p "$stage"
    copy_tree "$stage"
    ( cd "$stage" && zip -q -r -X "$zipfile" . ) || warn "      zip 打包失败，已跳过"
    rm -rf "$tmpdir"
    [ -f "$zipfile" ] && made+=("$zipfile")
  else
    warn "      系统没有 zip 命令，跳过 .zip（tar.gz 已生成）"
  fi

  local f size
  for f in "${made[@]}"; do
    [ -f "$f" ] || continue
    size="$(du -k "$f" | cut -f1)"
    ok "      $(basename "$f")  (${size} KB)"
  done

  if [ ${#made[@]} -eq 0 ]; then
    err "没有生成任何归档"
    exit 1
  fi
}

# 把项目复制到暂存目录（带排除），供 zip 使用
copy_tree() {
  local dest="$1"
  local d p
  local rsync_args=()
  if command -v rsync >/dev/null 2>&1; then
    for d in "${EXCLUDE_DIRS[@]}";    do rsync_args+=("--exclude=$d/"); done
    for p in "${EXCLUDE_FILE_PATTERNS[@]}"; do rsync_args+=("--exclude=$p"); done
    for p in "${ZIP_ONLY_EXCLUDE_FILES[@]}"; do rsync_args+=("--exclude=$p"); done
    rsync -a "${rsync_args[@]}" "$PROJECT_DIR"/ "$dest"/
    return
  fi
  # 无 rsync 时用 tar 管道
  tar "${TAR_EXCLUDES[@]}" -cf - . 2>/dev/null | ( cd "$dest" && tar -xf - )
  # 排除后 config/ 可能变空
  [ -d "$dest/config" ] && [ -z "$(ls -A "$dest/config" 2>/dev/null)" ] && rmdir "$dest/config"
}

# ---------- 3. 打 exe ----------
# $1 = onefile | onedir
#   onefile → dist/AutoClicker.exe（单文件）+ 带版本号副本
#   onedir  → build/green/AutoClicker/ 整个文件夹压成 dist/AutoClicker_v*_win64.zip
build_exe() {
  local mode="${1:-onefile}"
  local label
  [ "$mode" = "onefile" ] && label="单文件 exe" || label="绿色目录"

  if [ "$PLATFORM" != "windows" ]; then
    warn "[2/4] 跳过 $label：PyInstaller 不能跨平台交叉编译（当前平台: $PLATFORM）"
    warn "      本平台只能打源码归档；要程序请到 Windows 上执行 package.ps1"
    return 0
  fi

  step "[2/4] Building $label ..."

  if [ "$DO_DEPS" -eq 1 ]; then
    if ! "$PY_EXE" -c 'import PyInstaller' 2>/dev/null; then
      warn "      未安装 PyInstaller，正在安装 ..."
      "$PY_EXE" -m pip install --upgrade pyinstaller || { err "PyInstaller 安装失败"; exit 1; }
    fi
  fi

  local dist="$PROJECT_DIR/dist"
  local build="$PROJECT_DIR/build"
  mkdir -p "$dist" "$build"
  # 两种形态用各自的 spec/work 目录，否则第二次跑会复用第一次的中间产物
  local specdir="$build/pyinstaller-$mode"
  local workdir="$build/pyinstaller-work-$mode"
  # --onedir 的产物是文件夹，先吐到 build/green/
  local outdir="$dist"
  [ "$mode" = "onedir" ] && outdir="$build/green"

  # Windows 路径必须用反斜杠给 PyInstaller 的 --add-data 分隔符
  local add_data="$PROJECT_DIR/utils/static;utils/static"
  case "$PLATFORM" in
    windows) add_data="$(cygpath -w "$PROJECT_DIR/utils/static" 2>/dev/null || echo "$PROJECT_DIR/utils/static");utils/static" ;;
  esac

  local icon="$PROJECT_DIR/utils/static/Ralsei.ico"

  # 版本信息：PyInstaller 要的是 Python 字面量，不是 .rc。
  # 不给的话 exe 右键属性 → 详细信息 是空的，看着像没编完整。
  local verfile="$build/version_info_$mode.txt"
  local v1=0 v2=0 v3=0 rest
  rest="$VERSION"
  v1="$(printf '%s' "$rest" | cut -d. -f1)"; v2="$(printf '%s' "$rest" | cut -d. -f2)"; v3="$(printf '%s' "$rest" | cut -d. -f3)"
  case "$v1" in ''|*[!0-9]*) v1=1 ;; esac
  case "$v2" in ''|*[!0-9]*) v2=0 ;; esac
  case "$v3" in ''|*[!0-9]*) v3=0 ;; esac
  cat > "$verfile" <<VEREOF
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($v1, $v2, $v3, 0),
    prodvers=($v1, $v2, $v3, 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'080404B0',
        [StringStruct(u'CompanyName', u'YOUXICHUNMI'),
         StringStruct(u'FileDescription', u'AutoClicker - 自动连点器'),
         StringStruct(u'FileVersion', u'$VERSION'),
         StringStruct(u'InternalName', u'AutoClicker'),
         StringStruct(u'LegalCopyright', u'MIT License'),
         StringStruct(u'OriginalFilename', u'AutoClicker.exe'),
         StringStruct(u'ProductName', u'AutoClicker'),
         StringStruct(u'ProductVersion', u'$VERSION')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)
VEREOF

  local pyargs=(
    -m PyInstaller
    --noconfirm --clean "--$mode" --windowed
    --name AutoClicker
    --distpath "$outdir"
    --workpath "$workdir"
    --specpath "$specdir"
    --add-data "$add_data"
  )
  # 版本资源是 PE 专有的，非 Windows 传了反而可能让 PyInstaller 报错
  case "$PLATFORM" in
    windows) pyargs+=(--version-file "$verfile") ;;
  esac
  [ -f "$icon" ] && pyargs+=(--icon "$icon")
  local m
  for m in PyQt6.QtWebEngineCore PyQt6.QtWebEngineWidgets PyQt6.QtMultimedia \
           PyQt6.QtQuick PyQt6.QtQml PyQt6.QtBluetooth PyQt6.QtDesigner \
           PyQt6.QtHelp PyQt6.QtNetworkAuth PyQt6.Qt3DCore PyQt6.QtCharts; do
    pyargs+=(--exclude-module "$m")
  done
  pyargs+=("$PROJECT_DIR/main.py")

  printf '%s      pyinstaller %s%s\n' "$C_DIM" "${pyargs[*]}" "$C_OFF"
  "$PY_EXE" "${pyargs[@]}" || { err "PyInstaller 构建失败"; exit 1; }

  local exe
  if [ "$mode" = "onefile" ]; then
    exe="$dist/AutoClicker.exe"
  else
    exe="$outdir/AutoClicker/AutoClicker.exe"
  fi
  [ -f "$exe" ] || { err "构建结束但未找到 $exe"; exit 1; }
  ok "      AutoClicker.exe  ($(( $(stat -c%s "$exe" 2>/dev/null || echo 0) / 1048576 )) MB)"

  local stamp; stamp="$(date +%Y%m%d)"

  # 单文件形态：再放一份带版本号的副本便于归档，没有 zip 可打。
  if [ "$mode" = "onefile" ]; then
    local versioned="$dist/AutoClicker_v${VERSION}_${stamp}_single_win64.exe"
    cp "$exe" "$versioned"
    ok "      $(basename "$versioned")"
    return 0
  fi


  # exe + 依赖 + 文档 + 配置说明 打成一个发布包
  local relbase="AutoClicker_v${VERSION}_${stamp}_win64"
  local tmpdir; tmpdir="$(mktemp -d)"
  cp -r "$outdir/AutoClicker/." "$tmpdir/"
  [ -f "$PROJECT_DIR/README.md" ] && cp "$PROJECT_DIR/README.md" "$tmpdir/"
  [ -f "$PROJECT_DIR/LICENSE" ]   && cp "$PROJECT_DIR/LICENSE"   "$tmpdir/"
  mkdir -p "$tmpdir/config"
  cat > "$tmpdir/config/说明.txt" <<'EOF'
AutoClicker 首次运行时会在本目录生成 config.json。
删掉 config.json 即可恢复默认配置。
日志写在同级的 log/ 目录，按日期滚动。
EOF

  local rel="$dist/${relbase}.zip"
  rm -f "$rel"
  if command -v zip >/dev/null 2>&1; then
    ( cd "$tmpdir" && zip -q -r -X "$rel" . )
  else
    # 无 zip 时用 PowerShell 兜底（Windows 上必然可用）
    local win_tmp win_rel
    win_tmp="$(cygpath -w "$tmpdir" 2>/dev/null || echo "$tmpdir")"
    win_rel="$(cygpath -w "$rel" 2>/dev/null || echo "$rel")"
    powershell.exe -NoProfile -Command \
      "Compress-Archive -Path '$win_tmp\*' -DestinationPath '$win_rel' -CompressionLevel Optimal -Force" \
      || { rm -rf "$tmpdir"; err "创建 $rel 失败"; exit 1; }
  fi
  rm -rf "$tmpdir"
  ok "      ${relbase}.zip  ($(( $(stat -c%s "$rel" 2>/dev/null || echo 0) / 1024 )) KB)"
}

# ============================================================
#  0. 检测 dist/ 里的产物是否比源码新
# ============================================================
newest_source() {
  # 输出: "<epoch>\t<相对路径>"，只看会进包的文件
  local newest=0 newestf=""
  while IFS= read -r f; do
    local t
    t=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || echo 0)
    if [ "$t" -gt "$newest" ]; then
      newest="$t"
      newestf="${f#$PROJECT_DIR/}"
    fi
  done < <(find "$PROJECT_DIR" \
      \( -name .venv -o -name venv -o -name __pycache__ -o -name .git \
         -o -name dist -o -name build -o -name log -o -name .idea \
         -o -name .vscode -o -name node_modules -o -name .pytest_cache \
         -o -name .mypy_cache \) -prune -o -type f -print 2>/dev/null \
    | grep -Ev '\.(pyc|pyo|pyd|log)$|/(\.DS_Store|Thumbs\.db)$' \
    | grep -E '^'"$PROJECT_DIR"'/(main\.py|core/|ui/|utils/|script/|README\.md$|requirements\.txt$)')

  printf '%s\t%s\n' "$newest" "$newestf"
}

show_build_status() {
  echo ""
  echo "------------- 打包产物检测 -------------"

  local dist_dir="$PROJECT_DIR/dist"
  if [ ! -d "$dist_dir" ]; then
    warn "  dist/ 目录不存在 —— 还没打过包。"
    echo "----------------------------------------"
    return 1
  fi

  local src_line src_time src_file
  src_line=$(newest_source)
  src_time="${src_line%%$'\t'*}"
  src_file="${src_line#*$'\t'}"

  if [ "${src_time:-0}" -gt 0 ]; then
    echo "  源码最新改动: $(date -d "@$src_time" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -r "$src_time" '+%Y-%m-%d %H:%M:%S')  ($src_file)"
  fi

  local artifacts n=0 all_fresh=1 today_count=0
  local TODAY_STAMP
  TODAY_STAMP=$(date '+%Y%m%d')
  artifacts=$(find "$dist_dir" -maxdepth 1 -type f \
      \( -name '*.zip' -o -name '*.tar.gz' -o -name 'AutoClicker.exe' \
         -o -name '*_single_win64.exe' \) -print 2>/dev/null)

  if [ -z "$artifacts" ]; then
    warn "  dist/ 里没有任何产物 —— 需要打包。"
    echo "----------------------------------------"
    return 1
  fi

  while IFS= read -r a; do
    [ -n "$a" ] || continue
    n=$((n + 1))
    local at asize amtime size_mb
    at=$(stat -c %Y "$a" 2>/dev/null || stat -f %m "$a" 2>/dev/null || echo 0)
    asize=$(stat -c %s "$a" 2>/dev/null || stat -f %z "$a" 2>/dev/null || echo 0)
    size_mb=$(awk -v s="$asize" 'BEGIN{printf "%.2f", s/1048576}')

    local now age age_h age_d age_str
    now=$(date +%s)
    age=$((now - at))
    age_h=$((age / 3600))
    age_d=$((age / 86400))
    if [ "$age" -lt 3600 ]; then
      age_str="$((age / 60)) 分钟前"
    elif [ "$age_h" -lt 24 ]; then
      age_str="${age_h} 小时前"
    else
      age_str="${age_d} 天前"
    fi

    # 日期戳不是今天的产物属于历史归档（同一天多次打包会覆盖同名文件，
    # 换了一天就留成旧文件）。它们不可能是本次打包的预期产物，
    # 拿它们跟今天的源码比 mtime 只会永远报过期，所以只展示不判定。
    amonth_stamp=$(basename "$a" | sed -n 's/.*_\([0-9]\{8\}\)[_.].*/\1/p')
    is_old_date=0
    if [ -n "$amonth_stamp" ] && [ "$amonth_stamp" != "$TODAY_STAMP" ]; then
      is_old_date=1
    fi

    # 源码 zip（AutoClicker_vX_日期.zip，不带 _win64）只在 --with-source 时产出
    local abase; abase=$(basename "$a")
    local is_src_zip=0
    case "$abase" in
      AutoClicker_v*_win64.zip) is_src_zip=0 ;;
      AutoClicker_v*_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].zip) is_src_zip=1 ;;
    esac

    if [ "$is_old_date" -eq 1 ]; then
      printf '  [归档] %s  (%s MB, %s)  历史产物，不参与判定\n' "$abase" "$size_mb" "$age_str"
    elif [ "$is_src_zip" -eq 1 ] && [ "${WITH_SOURCE:-0}" -eq 0 ]; then
      printf '  [跳过] %s  (%s MB, %s)  源码 zip，需 --with-source 才会重建\n' "$abase" "$size_mb" "$age_str"
    elif [ "${a%.tar.gz}" != "$a" ]; then
      printf '  [跳过] %s  (%s MB, %s)  package.sh 的产物\n' "$abase" "$size_mb" "$age_str"
    elif [ "$at" -lt "${src_time:-0}" ]; then
      # AutoClicker.exe 是 package.ps1 的产物，非 Windows 上不算它
      if [ "$(basename "$a")" = "AutoClicker.exe" ] && [ "$PLATFORM" != "windows" ]; then
        printf '  [跳过] %s  (%s MB, %s)  仅 Windows 产物\n' "$(basename "$a")" "$size_mb" "$age_str"
      else
        all_fresh=0
        warn "  [过期] $(basename "$a")  (${size_mb} MB, ${age_str})"
      fi
    else
      ok   "  [最新] $(basename "$a")  (${size_mb} MB, ${age_str})"
    fi
    if [ "$is_old_date" -eq 0 ]; then today_count=$((today_count + 1)); fi
  done <<< "$artifacts"

  if [ "$today_count" -eq 0 ]; then
    all_fresh=0
    warn "  dist/ 里没有今天（$TODAY_STAMP）的产物 —— 需要打包。"
  else
    # 两种形态都要有：绿色目录 zip 与单文件 exe。缺哪个都算需要重新打包。
    if [ "$BUILD_EXE" -eq 1 ] && [ "$PLATFORM" = "windows" ]; then
      if [ "$SKIP_SINGLE" -eq 0 ]; then
        if ! find "$dist_dir" -maxdepth 1 -type f -name "*_${TODAY_STAMP}_single_win64.exe" | grep -q .; then
          all_fresh=0
          warn "  缺少今天的单文件 exe（*_${TODAY_STAMP}_single_win64.exe）—— 需要打包。"
        fi
      fi
      if [ "$SKIP_GREEN" -eq 0 ]; then
        if ! find "$dist_dir" -maxdepth 1 -type f -name "*_${TODAY_STAMP}_win64.zip" | grep -q .; then
          all_fresh=0
          warn "  缺少今天的绿色目录 zip（*_${TODAY_STAMP}_win64.zip）—— 需要打包。"
        fi
      fi
    fi
  fi

  echo "----------------------------------------"
  if [ "$all_fresh" -eq 1 ]; then
    ok "  结论: 产物已是最新，无需重新打包。"
    return 0
  else
    warn "  结论: 源码比产物新，建议重新打包。"
    return 1
  fi
}

# ============================================================
#  主流程
# ============================================================
echo ""
echo "============================================"
echo "        AutoClicker Package Builder"
echo "============================================"
echo "[INFO] Project : $PROJECT_DIR"
echo "[INFO] Version : $VERSION"
echo "[INFO] Platform: $PLATFORM"
echo "[INFO] BuildExe: $BUILD_EXE"
echo ""

if show_build_status; then BUILD_FRESH=1; else BUILD_FRESH=0; fi
echo ""

if [ "$CHECK_ONLY" -eq 1 ]; then
  echo "[INFO] --check-only 模式：仅检测，不执行打包。"
  echo ""
  [ "$BUILD_FRESH" -eq 1 ] && exit 0 || exit 2
fi

# 产物已是最新时，先问一句要不要白打一遍（非交互场景自动继续）
if [ "$BUILD_FRESH" -eq 1 ] && [ "$FORCE" -eq 0 ]; then
  if [ -t 0 ]; then
    echo ""
    printf '产物已是最新，仍要重新打包吗？[y/N] '
    read -r ans
    case "$ans" in
      y|Y|yes|YES)
        echo ""
        ;;
      *)
        echo ""
        ok "已跳过打包。"
        echo ""
        exit 0
        ;;
    esac
  else
    warn "[INFO] 非交互环境，继续打包（用 --check-only 可只检测）。"
    echo ""
  fi
fi

if ! find_python; then
  err "[ERROR] 未找到可用的 Python 3，请安装 Python 3.10+ 或先运行 script/install.sh"
  exit 1
fi
echo "[INFO] Python  : $PY_EXE  [$PY_KIND]"
echo ""

[ "$DO_README" -eq 1 ] && gen_readme || warn "[1/4] Skip README generation."

# 两种形态默认都打。只要一种用 --skip-single / --skip-green。
WANT_SINGLE=$(( BUILD_EXE == 1 && SKIP_SINGLE == 0 ? 1 : 0 ))
WANT_GREEN=$((  BUILD_EXE == 1 && SKIP_GREEN  == 0 ? 1 : 0 ))

if [ "$BUILD_EXE" -eq 1 ]; then
  # dist/ 先清空，免得上一轮的旧产物混进来
  rm -rf "$PROJECT_DIR/dist"
  mkdir -p "$PROJECT_DIR/dist"

  if [ "$WANT_SINGLE" -eq 1 ]; then
    build_exe onefile
  else
    warn "[2/4] Skip single exe (--skip-single / --no-exe)."
  fi

  if [ "$WANT_GREEN" -eq 1 ]; then
    build_exe onedir
  else
    warn "[3/4] Skip green dir zip (--skip-green / --no-exe)."
  fi
else
  warn "[2/4] [3/4] Skip both forms (--no-exe)."
fi

# 源码归档只在 --with-source 时打
if [ "$WITH_SOURCE" -eq 1 ] && [ "$DO_ZIP" -eq 1 ]; then
  pack_source
elif [ "$WITH_SOURCE" -eq 1 ]; then
  warn "[4/4] Skip source archive (--no-zip)."
else
  printf '%s[4/4] Skip source archive (用 --with-source 可额外打一份).%s\n' "$C_DIM" "$C_OFF"
fi

echo ""
echo "============================================"
ok " Done!"
[ "$DO_README" -eq 1 ] && echo "   README : README.md"
if [ -d "$PROJECT_DIR/dist" ]; then
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    printf '   %-46s %5d MB\n' "$(basename "$f")" \
      "$(( $(stat -c%s "$f" 2>/dev/null || echo 0) / 1048576 ))"
  done <<EOF
$(find "$PROJECT_DIR/dist" -maxdepth 1 -type f \( -name '*.exe' -o -name '*.zip' -o -name '*.gz' \) 2>/dev/null | sort)
EOF
fi
[ "$WITH_SOURCE" -eq 1 ] && [ "$DO_ZIP" -eq 1 ] && echo "   Archive: dist/"
echo "============================================"
echo ""
