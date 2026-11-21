# AutoClicker

![Ralsei](./utils/static/Ralsei.png)

**一个用纯 Win32 消息实现「后台点击」的 Windows 自动连点器。**

基于 PyQt6，支持鼠标/键盘动作序列编排、HWND 级后台点击、多配置管理、全局热键控制。
输入模拟全部走 `ctypes` 直接调用 Win32 API，**不依赖 pywin32 / pynput 等任何第三方 Win32 封装库**。

> 最初的需求很朴素：在 CookieClicker 网页版挂机时，不喜欢鼠大侠，而且想要一个能后台跑、不抢占鼠标的连点器。

---

## 目录

- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [架构说明](#架构说明)
- [使用说明](#使用说明)
- [动作类型详解](#动作类型详解)
- [配置说明](#配置说明)
- [故障排查](#故障排查)
- [已知问题](#已知问题)
- [开发说明](#开发说明)
- [许可证](#许可证)

---

## 功能特性

### 输入能力

- **多动作类型**：鼠标点击、键盘按键、组合键（多键序列，按下顺序执行、逆序释放）
- **两种点击模式**：单击（带动作后延迟）、长按（可设为「一直按」，启动即按住、停止时才松开）
- **五个鼠标按钮**：左键、右键、中键、X1（侧键后退）、X2（侧键前进）
- **完整虚拟键表**：字母、数字、F1–F16、修饰键（含左右区分）、方向键、小键盘、Oem 系列、CapsLock、PrintScreen、Pause

### 双模式输入

| 模式 | 实现 | 适用场景 | 特点 |
|------|------|----------|------|
| **前台模式** | `SendInput` | 普通桌面程序 | 走系统输入队列，兼容性最好，但会抢占鼠标焦点 |
| **后台模式** | `PostMessage` + HWND | 挂机、边点边干别的 | 直接向目标窗口投递消息，**不影响前台操作**，可最小化运行 |

后台模式的点击坐标用**相对比例**（0–100%）而非绝对像素，因此目标窗口移动、改变大小时点击位置依然正确。

### 目标窗口选择

三种方式任选：

1. **关键字搜索**：下拉框输入窗口标题或进程名，`MatchContains` 模糊匹配
2. **进程列表**：点「📋 进程」从所有进程及其窗口中选择
3. **鼠标拾取**：点「🎯 拾取坐标」后，鼠标点击目标窗口，自动识别窗口 + 记录相对坐标

### 其它

- **多配置管理**：新建、重命名、复制、删除，切换即生效，改动自动保存
- **全局热键**：启动/停止热键可自定义（默认 `F6` / `F7`），最小化到托盘后依然生效
- **三主题系统**：深色（Catppuccin Mocha）、浅色（Catppuccin Latte）、自动跟随系统
- **日志系统**：按日期分文件（`dist/log/app_YYYY-MM-DD.log`），未捕获异常经全局钩子记录完整堆栈
- **精细计时**：`_precise_sleep` 混合 `time.sleep` 与忙等，间隔可低至 0 ms（极限连点模式）

---

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | **Windows 10 / 11**（连点功能必需）；Linux / macOS 仅可查看和编辑配置 |
| Python | >= 3.10 |
| 依赖 | PyQt6 >= 6.6.0、keyboard >= 0.13.5 |

> ⚠️ **`keyboard` 库注册全局热键需要管理员权限。** 非管理员运行时程序不会报错，但热键会静默失效。建议始终以管理员身份运行。

### 跨平台支持程度

连点依赖 Win32 的 `SendInput`（前台）与 `PostMessage`（后台），这是 Windows 独有的，无法在其它系统上复现。
因此本项目在非 Windows 平台上**降级为只读模式**：

| 能力 | Windows | Linux / macOS |
|------|---------|---------------|
| 查看 / 新建 / 编辑 / 复制配置 | ✅ | ✅ |
| 编辑动作序列、连点参数、热键 | ✅ | ✅ |
| 目标窗口列表、进程选择 | ✅ | ⬜ 返回空列表 |
| 坐标拾取 | ✅ | ⬜ 不可用 |
| **开始连点** | ✅ | ❌ 按钮禁用，点击会弹窗说明原因 |
| 全局热键 | ✅ | ❌（`keyboard` 需 root 读 `/dev/input`） |

非 Windows 启动时，状态栏会显示：

```
只读模式 | 当前平台 (linux) 不支持输入模拟，仅可查看和编辑配置
```

技术上由 `core/click_engine.py` 的 `IS_WINDOWS` 守卫实现：非 Windows 下 `ctypes.windll` /
`ctypes.wintypes` / `ctypes.WINFUNCTYPE` 都不存在，模块会用具名空间造出等价的最小类型，
把各输入函数降级为空操作（返回 `False` / `(1, 1)` / 空列表），因此**整个程序仍能正常导入和启动**。
`ui/styles.py` 的 `winreg` 同样做了 `ImportError` 保护（非 Windows 改读 `COLORSCHEME` 环境变量）。

---

## 快速开始

### 方式一：uv（推荐，最快）

```bash
pip install uv
uv venv .venv
uv pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

### 方式二：pip + venv

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 方式三：一键脚本

Windows（批处理）：

```bat
script\install.bat
script\run.bat
```

Windows（PowerShell）：

```powershell
powershell -ExecutionPolicy Bypass -File script\install.ps1
powershell -ExecutionPolicy Bypass -File script\run.ps1
```

Linux / macOS：

```bash
./script/install.sh
./start.sh          # 或 ./script/run.sh
```

> 📌 **`install` 脚本带自愈能力**：若 `.venv` 存在但解释器已无法运行（例如创建它的 Python 被卸载或移位），脚本会自动删除并重建，无需你手动清理。

### 打包发布

**打包的产物是可执行文件，不是源码压缩包**。默认一次跑完，**两种形态都产**，不需要额外开关：

| 产物 | 说明 |
|------|------|
| `dist/AutoClicker.exe` | 单文件 exe（onefile，约 33.7 MB），拷一个文件就能跑 |
| `dist/AutoClicker_v{版本}_{日期}_single_win64.exe` | 上面那份的带版本号副本，便于归档与分发 |
| `dist/AutoClicker_v{版本}_{日期}_win64.zip` | 绿色目录包（onedir，33.7 MB），解压后是 `AutoClicker.exe` + `_internal/` 依赖目录，启动快、便于排障 |

**单文件适合发给别人**（对方什么都不用装）；**绿色目录适合自己留着排障**（依赖都在 `_internal/` 里一眼可见，启动也更快）。

三个脚本按你手边的 shell 任选其一：

| 脚本 | 运行环境 | 产物 |
|------|----------|------|
| `script/package.ps1` | Windows PowerShell 5.1+ / PowerShell 7 | 上面三份全产 |
| `script/package.cmd` | Windows 命令提示符（cmd.exe） | 同上（内部转调 PowerShell） |
| `script/package.sh` | Linux / macOS / Git Bash / MSYS2 | Windows 上同上；非 Windows 上只能打源码归档（PyInstaller 不能交叉编译） |

三个脚本在打包前都会先检测 `dist/` 里的产物是否最新（见下面的「打包结果自检」）。

```powershell
# PowerShell（Windows 主用）
powershell -ExecutionPolicy Bypass -File script\package.ps1
```

```bat
:: cmd，参数与 ps1 完全一致
script\package.cmd
```

```bash
# bash / Git Bash / MSYS2  （Windows 上请用 Git Bash，不要用 WSL 的 bash）
./script/package.sh
```

主流程四件事：

1. 调用 `script/gen_readme.py` —— 扫描源码统计行数、生成目录树、读取 git 版本，**重新生成 `README.md`**（模板在 `script/README.template.md`，改文档请改模板，不要直接改 README）
2. **用 PyInstaller 打单文件 exe**（`--onefile`）到 `dist/AutoClicker.exe`，并复制一份带版本号的副本
3. **用 PyInstaller 打绿色目录**（`--onedir`）到临时目录，再压成 `dist/AutoClicker_v{版本}_{日期}_win64.zip`
4. 若额外传 `--with-source` / `-WithSource`，再打一份源码归档（排除 `.venv` / `__pycache__` / `log` / `dist` / `build`，并剔除 `config/config.json` —— 含本机窗口标题与句柄，首次运行会自动重建）

常用开关：

| PowerShell | bash | 作用 |
|---|---|---|
| `-Version 1.1.0` | `--version 1.1.0` | 指定版本号 |
| `-SkipSingle` | `--skip-single` | 只打绿色目录 zip，不打单文件 exe |
| `-SkipGreen` | `--skip-green` | 只打单文件 exe，不打绿色目录 zip |
| `-SkipExe` | `--no-exe` | 两种都不打（只跑 README 与可选源码归档） |
| `-WithSource` | `--with-source` | 额外打一份源码归档 |
| `-SkipZip` | `--no-zip` | 单文件 exe 不再压进发布 zip |
| `-SkipReadme` | `--no-readme` | 不重新生成 README |
| `-SkipDeps` | `--no-deps` | 不自动装 PyInstaller |
| `-CheckOnly` | `--check-only` | 只检测产物是否最新 |
| `-Force` | `--force` | 跳过交互确认，强制重打 |

#### 打包结果自检

**每次运行打包脚本，第一件事都是检查 `dist/` 里现有的产物是不是最新的**，然后再决定要不要打包：

```
------------- 打包产物检测 -------------
  源码最新改动: 2026-11-21 19:20:25  (README.md)
  [最新] AutoClicker.exe  (33.68 MB, 1 分钟前)
  [最新] AutoClicker_v1.0.0_20261121_single_win64.exe  (33.68 MB, 1 分钟前)
  [最新] AutoClicker_v1.0.0_20261121_win64.zip  (33.72 MB, 1 分钟前)
  [归档] AutoClicker_v1.0.0_20261120_win64.zip  (33.38 MB, 16 小时前)  历史产物，不参与判定
----------------------------------------
  结论: 产物已是最新，无需重新打包。
```

判定规则：

- 取源码里最新修改的那个文件的时间（只看 `main.py` / `core/` / `ui/` / `utils/` / `script/` / `README.md` / `requirements.txt`，自动跳过 `.venv`、`__pycache__`、`log`、`dist`、`build`；`config/` 与 `log/` 是运行期数据，现在落在 `dist/` 下，不算源码）
- `dist/` 里每个产物与这个时间比对：更早的标 `[过期]`，更晚的标 `[最新]`
- **文件名日期戳不是今天的标 `[归档]`，不参与判定**。同一天重复打包会覆盖同名文件，换了一天旧文件就留在 `dist/` 里；它们不可能是本次打包的预期产物，拿它们比时间只会永远报过期。
- `.tar.gz` 只由 `package.sh` 产出，在 ps1 里只显示 `[跳过]`，不参与判定（反之 `.exe` 在非 Windows 平台也不参与）
- 源码 zip（`AutoClicker_v{版本}_{日期}.zip`，不带 `_win64`）现在只在显式 `-WithSource` / `--with-source` 时产出，默认流程里显示 `[跳过]`，不参与判定
- **形态齐全检查**：默认要产两种形态，所以今天缺 `*_win64.zip`（绿色目录）或缺 `*_single_win64.exe`（单文件带版本号副本）都判定为需要打包
- `dist/` 里一个今天的产物都没有（只剩归档），也判定为需要打包
- 有任何一个**今天的**产物过期，结论就是「建议重新打包」

三种用法：

| 参数 | 行为 |
|------|------|
| （不加） | 先检测，再打包。若产物已最新且是交互终端，会问一句「仍要重新打包吗？[y/N]」，回车即跳过 |
| `--check-only` / `-CheckOnly` | 只检测，检测完就退出。已最新 `exit 0`，有过期 `exit 2`，可直接用在 CI 里做判断 |
| `--force` / `-Force` | 跳过那句确认，无论如何都打一遍 |

> 三个脚本的自检结论必须一致：同一份 `dist/` 分别用 `package.ps1 -CheckOnly`、
> `package.cmd -CheckOnly`、`package.sh --check-only` 跑，输出和退出码要相同。

```powershell
powershell -ExecutionPolicy Bypass -File script\package.ps1 -CheckOnly
```

```bash
./script/package.sh --check-only
```

非交互环境（输出被管道重定向、CI 里跑）不会卡在确认上，会直接打印一行提示然后继续打包。

#### 打 exe 说明

```powershell
# 默认就打，两种形态都产
powershell -ExecutionPolicy Bypass -File script\package.ps1

# 只想要单文件
powershell -ExecutionPolicy Bypass -File script\package.ps1 -SkipGreen

# 只想要绿色目录
powershell -ExecutionPolicy Bypass -File script\package.ps1 -SkipSingle
```

产物：

- `dist/AutoClicker.exe` —— 单文件，实测约 33.7 MB
- `dist/AutoClicker_v{版本}_{日期}_single_win64.exe` —— 同上，带版本号，便于归档
- `dist/AutoClicker_v{版本}_{日期}_win64.zip` —— 绿色目录，解压后是 `AutoClicker.exe` + `_internal/`，附 `README.md`、`LICENSE`、`config/说明.txt`

单文件是 **onefile** 模式，启动时会把自己解压到 `%TEMP%\_MEIxxxxxx\` 再运行。因此：

- `config/` 和 `log/` 落在 **exe 所在目录**（不是临时目录），配置和日志不会丢 —— 这由 `utils/app_paths.py` 的 `app_root()` 保证
- 图标、GIF 等只读资源打进包里，由 `resource_path()` 从 `sys._MEIPASS` 读取
- 首次运行 exe 时若同目录没有 `config/config.json`，会以默认值自动创建
- 全局热键仍需管理员权限：右键 exe →「以管理员身份运行」
- **onefile 对临时目录有要求**：它要在 `%TEMP%` 下建目录解压。如果 `%TEMP%` 因为权限、完整性级别（Low Integrity）、杀软或磁盘策略而不可写，会弹出 `Could not create temporary directory!` 的错误框 —— 此时换 `TMP`/`TEMP` 环境变量指向可写目录，或改用绿色目录版即可。绿色目录版不做解压，没有这个约束。

### 用 GitHub Actions 自动打包

仓库里带了一份 `.github/workflows/build.yml`，推到 GitHub 就会自动编译并打包出 **Windows 和 Linux** 两套产物，不用在自己机器上装任何东西。

触发方式：

| 事件 | 行为 |
|------|------|
| push 到 `main` | 编译 + 打包，产物作为 workflow artifact 保留 30 天 |
| `pull_request` | 同上（只构建，不发版） |
| push 形如 `v1.2.0` 的 tag | 额外自动建 GitHub Release，把两平台产物挂上去 |
| 手动 `workflow_dispatch` | 在 Actions 页面点「Run workflow」 |

两个 job：

- **windows** —— 装 Python 3.12 + 依赖 + PyInstaller，然后**直接调用仓库自己的 `script/package.ps1 -Force -SkipReadme`**，所以 CI 产出的东西和你本机跑出来的完全一致；上传 `dist/*.exe` 与 `dist/*.zip`
- **linux** —— 先 `apt-get` 装 PyQt6 在无显示环境必需的系统库（`libgl1`、`libegl1`、`libxkbcommon-x11-0`、`libxcb-*` 一族），再跑两次 PyInstaller（onefile + onedir），产出 `AutoClicker_v{版本}_{日期}_single_linux64` 与 `AutoClicker_v{版本}_{日期}_linux64.tar.gz`

> Linux 那边 PyInstaller 不能交叉编译出 Windows 产物，反之亦然 —— 所以两个 job 各在各自的原生 runner 上跑。

本地等价命令（想手动模拟 CI 的处理）：

```bash
# Linux
python -m PyInstaller --noconfirm --clean --onefile --name AutoClicker \
  --add-data "$PWD/utils/static:utils/static" main.py
```

### 数据目录：源码运行与 exe 运行共用 `dist/`

`start.bat` / `start.sh` 和 `script/run.bat` / `run.ps1` / `run.sh` 都会先设置环境变量
`AUTOCLICKER_DATA_DIR=<项目根>/dist`，再由 `utils/app_paths.py` 的 `app_root()` 优先读取它。

所以无论你是双击 `start.bat`（或跑 `./start.sh`）跑源码，还是双击 `dist/AutoClicker.exe`，读写的都是同一份
`dist/config/config.json` 与 `dist/log/`：

| 运行方式 | 配置 | 日志 |
|----------|------|------|
| `start.bat` / `start.sh` / `script\run.*` | `dist/config/config.json` | `dist/log/app_YYYY-MM-DD.log` |
| `dist/AutoClicker.exe` | `dist/config/config.json` | `dist/log/app_YYYY-MM-DD.log` |
| `.venv\Scripts\python.exe main.py`（不设环境变量） | `config/config.json` | `log/app_YYYY-MM-DD.log` |

要换数据目录，启动前设 `AUTOCLICKER_DATA_DIR` 指向任意目录即可，三种方式都遵循同一个优先级：
环境变量 → 冻结运行取 exe 同级 → 源码运行取项目根。

打包机需要 Python 3.10+ 与 PyInstaller；脚本会先探测 `.venv` 是否可用，缺失 PyInstaller 时会自动 `pip install`（用 `-SkipDeps` / `--no-deps` 可跳过）。构建日志在成功时只显示末尾几行，失败时完整日志保存到 `build/pyinstaller-error.log`。


---

## 项目结构

```
AutoClicker/
├── .github/
│   └── workflows/
│       └── build.yml
├── core/
│   ├── __init__.py
│   ├── click_engine.py
│   └── hotkey_listener.py
├── script/
│   ├── gen_readme.py
│   ├── install.bat
│   ├── install.ps1
│   ├── install.sh
│   ├── package.cmd
│   ├── package.ps1
│   ├── package.sh
│   ├── README.template.md
│   ├── run.bat
│   ├── run.ps1
│   └── run.sh
├── ui/
│   ├── __init__.py
│   ├── action_editor.py
│   ├── main_window.py
│   ├── process_picker.py
│   └── styles.py
├── utils/
│   ├── static/
│   │   ├── Ralsei.ico
│   │   ├── Ralsei.png
│   │   └── Ralsei_Run.gif
│   ├── __init__.py
│   ├── app_paths.py
│   ├── config_manager.py
│   └── logger.py
├── .gitattributes
├── .gitignore
├── main.py
├── README.md
├── requirements.txt
├── start.bat
└── start.sh
```

自动生成（首次运行时创建，均位于数据目录）：

- `dist/config/config.json` — 配置文件，缺失时自动以默认值重建
- `dist/log/app_YYYY-MM-DD.log` — 日志，按日期滚动

> 直接跑 `.venv\Scripts\python.exe main.py`（不经启动脚本）时，这两个目录会落在项目根，而不是 `dist/`。

### 代码规模

共 **10** 个 Python 模块，**3489** 行代码（不含空行尾部）。

| 文件 | 行数 | 职责 |
|------|------|------|
| `main.py` | 92 | 程序入口：创建 QApplication、装载主题、初始化日志与主窗口 |
| `core/click_engine.py` | 909 | 核心引擎：Win32 输入模拟、窗口/进程枚举、连点循环调度 |
| `core/hotkey_listener.py` | 149 | 全局热键注册与回调（依赖 keyboard 库） |
| `ui/main_window.py` | 1180 | 主窗口：配置管理、动作表格、目标窗口、坐标拾取、热键、托盘、启停控制 |
| `ui/action_editor.py` | 309 | 动作编辑对话框 + KeyCaptureEdit 按键捕获控件 |
| `ui/process_picker.py` | 148 | 进程选择对话框 |
| `ui/styles.py` | 380 | Catppuccin 深/浅色主题与系统暗色检测 |
| `utils/app_paths.py` | 68 | 路径解析：统一源码运行与 PyInstaller 冻结运行下的目录定位 |
| `utils/config_manager.py` | 127 | 配置读写、默认值合并、多配置管理 |
| `utils/logger.py` | 127 | 日志初始化、全局/线程异常钩子 |

---

## 架构说明

项目按三层拆分，**核心层不依赖 UI**，可单独复用：

```
┌─────────────────────────────────────────┐
│  main.py          创建应用、装载主题      │
├─────────────────────────────────────────┤
│  ui/              界面层                  │
│    main_window.py    主窗口（编排）       │
│    action_editor.py  动作编辑对话框       │
│    process_picker.py 进程选择对话框       │
│    styles.py         主题样式表           │
├─────────────────────────────────────────┤
│  core/            核心层（无 UI 依赖）     │
│    click_engine.py   Win32 输入 + 调度    │
│    hotkey_listener.py 全局热键            │
├─────────────────────────────────────────┤
│  utils/           基础设施                │
│    app_paths.py       源码/冻结路径解析   │
│    config_manager.py  配置持久化          │
│    logger.py          日志 + 异常钩子     │
├─────────────────────────────────────────┤
│  script/          构建与文档              │
│    gen_readme.py      README 生成器       │
│    README.template.md README 模板(占位符) │
│    package.ps1/.cmd/.sh  三平台打包脚本   │
└─────────────────────────────────────────┘
```

### 关键设计

**1. Win32 调用集中在 `core/click_engine.py` 的模块级纯函数里**

`is_window()` / `get_window_title()` / `get_client_size()` / `restore_window()` /
`get_window_under_cursor()` / `is_mouse_button_down()` / `get_top_level_window()`
都是无状态的纯函数，`ClickEngine` 只负责编排线程与循环。想单独测试某个 Win32 行为，不需要构造引擎对象。

**2. 连点跑在独立线程里，UI 通过回调更新**

`ClickEngine.start()` 起一个 `threading.Thread` 跑 `_run_loop`，每执行一个动作就通过
`_action_callback(index)` 通知 UI；UI 侧用 `QTimer.singleShot(0, ...)` 把回调弹回主线程，
避免跨线程直接操作控件。

**3. 相对坐标而非绝对像素**

`click_x` / `click_y` 存 0.0–1.0 的比例。后台点击时用 `get_client_size(hwnd)` 换算成
当前客户区像素坐标再交给 `PostMessage`，窗口挪位置也不会点偏。

**4. 「一直按」的 hold 语义**

`mode == "hold"` 且 `hold_duration <= 0` 时，动作会按下但不松开，并被记入 `held_indices`
跳过后续重复执行；直到停止时才由 `_release_held_keys()` 统一释放。适合需要持续按住
某键的场景（游戏里连续前进等）。

**5. 可滚动的内容区，窗口缩放时控件不会互相挤压**

界面最外层是「可滚动内容区 + 常驻底部控制栏」两段式布局：

- 内容（配置、动作表、连点参数、目标窗口、热键）整体放进 `QScrollArea`
  （objectName `contentScroll`），里面的 `contentPane` 设了 `minimumWidth`，
  控件因此**永远不会被压到低于自身最小尺寸**；
- 「▶ 开始连点 / ■ 停止」两个主按钮放在滚动区外的常驻底栏（objectName `footerBar`），
  窗口拉得再矮也够得到，不用先滚到底；
- 各分组用 `QGridLayout` 分行排列（早期是一条 `QHBoxLayout` 长龙，宽度不够时
  Qt 只能让相邻控件重叠，表现为按钮互相压）。分组最小宽度实测：
  配置文件 484 / 动作序列 379 / 连点参数 440 / 目标窗口 416 / 热键 320。
- 窗口最小尺寸 560×460，初始尺寸按内容高度自动决定（内容区最小高约 838px，
  屏幕放得下就一次展开到 900×928，放不下就取可用区域 90%，其余交给纵向滚动条）。

---

## 使用说明

### 1. 编排动作序列

点「+ 添加动作」打开编辑器，选类型后填写参数。表格列出所有动作，**按从上到下的顺序执行**：

| 列 | 含义 |
|----|------|
| # | 执行序号 |
| 类型 | 鼠标 / 键盘 / 组合键 |
| 按钮/按键 | 具体按钮或按键名 |
| 模式 | 单击 / 长按（一直按时显示「一直按」） |
| 参数 | 长按时长或动作后延迟 |

用「上移 / 下移」调整顺序，「编辑」「删除」修改。

### 2. 设置连点参数

| 参数 | 范围 | 说明 |
|------|------|------|
| 循环间隔 | 0–100000 ms | 每轮动作序列之间的间隔，**0 = 极限速度** |
| 重复次数 | 0–999999 | 0 = 无限循环 |
| 循环间额外延迟 | 0–100000 ms | 与循环间隔叠加，用于更粗的节奏控制 |

### 3. 选择目标窗口（后台模式）

1. 「模式」切到 **后台模式 (PostMessage)**
2. 「目标窗口」下拉框输入关键字筛选，或点「📋 进程」浏览，或点「🎯 拾取坐标」直接点目标窗口
3. 用 X / Y 微调点击位置（相对客户区的百分比），下方会实时显示换算后的像素值

### 4. 设置热键

在「热键设置」的两个输入框里点击，然后直接按下想要的键，会显示键名。点「应用热键」生效。
热键在窗口最小化或失焦时依然有效（**需管理员权限**）。

### 5. 开始 / 停止

点「▶ 开始连点」或用启动热键。运行时顶部会显示 Ralsei 跑步动画和当前执行状态。

### 6. 托盘

程序启动时即创建系统托盘图标（不是开关项）：双击图标恢复窗口，右键菜单可显示窗口或退出。

关闭主窗口时的行为由配置文件里的 `settings.minimize_to_tray` 决定：

- `false`（默认）：**直接退出**，停止连点并注销热键
- `true`：隐藏到托盘继续后台运行

> ⚠️ 这个选项目前**没有界面开关**，需要手动编辑数据目录下的 `config.json`（经启动脚本运行时是 `dist/config/config.json`）。

---

## 动作类型详解

### 鼠标点击

```json
{
  "type": "mouse",
  "button": "left",
  "mode": "click",
  "delay_after": 0.001
}
```

`button` 可选：`left` / `right` / `middle` / `x1` / `x2`。
前台模式走 `SendInput` 的 `MOUSEEVENTF_*`，后台模式走 `WM_LBUTTONDOWN/UP` 系列消息（X 键额外带 `mouseData`）。

### 键盘按键

```json
{
  "type": "keyboard",
  "button": "F5",
  "mode": "click",
  "delay_after": 0.0
}
```

按键名经 `VK_MAP` 查表转虚拟键码，支持 `a`–`z`、`0`–`9`、`F1`–`F16`、`Space`、`Enter`、
`Tab`、`Escape`、`Delete`、方向键、`Num0`–`Num9`、`Oem*` 系列等。

### 组合键

```json
{
  "type": "combo",
  "vk_list": ["ctrl", "shift", "s"],
  "mode": "click",
  "delay_after": 0.0
}
```

按顺序逐个按下，结束后**逆序释放**，保证修饰键状态正确。

### 长按 / 一直按

```json
{
  "type": "mouse",
  "button": "left",
  "mode": "hold",
  "hold_duration": 0
}
```

`hold_duration > 0`：按住指定秒数后自动松开。
`hold_duration == 0`：**一直按住**，直到点击「停止」才释放，且该动作在后续循环中被跳过。

---

## 配置说明

配置存放于数据目录下的 `config/config.json`（经启动脚本或 exe 运行时是 `dist/config/config.json`），程序运行时会自动创建和更新。完整结构：

```json
{
  "profiles": [
    {
      "name": "配置名",
      "actions": [
        { "type": "mouse", "button": "left", "mode": "click", "delay_after": 0.0 }
      ],
      "interval": 2,
      "repeat": 0,
      "loop_delay": 0,
      "start_hotkey": "F6",
      "stop_hotkey": "F7",
      "enabled": true,
      "target_mode": "background",
      "target_title": "目标窗口标题",
      "click_x": 0.279,
      "click_y": 0.478
    }
  ],
  "active_profile": 0,
  "settings": {
    "minimize_to_tray": false,
    "start_minimized": false,
    "high_precision": true,
    "theme": "dark"
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `profiles[].name` | string | 配置名 |
| `profiles[].actions` | array | 动作序列，按数组顺序执行 |
| `profiles[].interval` | int | 循环间隔（ms），0 = 最快 |
| `profiles[].repeat` | int | 重复次数，0 = 无限 |
| `profiles[].loop_delay` | int | 循环间额外延迟（ms） |
| `profiles[].start_hotkey` | string | 启动热键，如 `F6`、`ctrl+F1` |
| `profiles[].stop_hotkey` | string | 停止热键 |
| `profiles[].target_mode` | string | `foreground` 或 `background` |
| `profiles[].target_title` | string | 目标窗口标题（用于重连时查找） |
| `profiles[].click_x` / `click_y` | float | 相对客户区的点击位置，0.0–1.0 |
| `profiles[].enabled` | bool | **已定义但当前版本未读取**（无启用/禁用功能），保留供后续扩展 |
| `active_profile` | int | 当前激活配置的索引 |
| `settings.theme` | string | `dark` / `light` / `auto` |
| `settings.minimize_to_tray` | bool | 关闭窗口时是否最小化到托盘（**无界面开关**） |
| `settings.start_minimized` | bool | **已定义但从未被读取**（启动即最小化未实现） |
| `settings.high_precision` | bool | **已定义但从未被读取**（精细计时始终启用） |

> 💡 配置里如果出现 `target_hwnd` 字段，那是运行时缓存的窗口句柄，**每次开机都会变**，程序会校验有效性并自动回退到按标题查找。手改配置时可以直接删掉它。

### 手动编辑

可以直接编辑 JSON（程序关闭时），或删除整个文件让程序以默认值重建。

---

## 故障排查

### 程序起不来 / 提示找不到 Python

`.venv` 的 `pyvenv.cfg` 记录了创建它的基础解释器路径（`home = ...`）。**如果那个 Python 被卸载或移动**，
虚拟环境里的 `python.exe` 就只是个失效的存根，会报：

```
did not find executable at 'C:\PythonXXX\python.exe'
```

同时 `script\run.*`、`start.bat` 全部失效，因为它们都硬编码了 `.venv\Scripts\python.exe`。

**解决**：删掉整个 `.venv` 目录，重新跑 `script\install.bat`（或按下文手建）。

```bat
rmdir /s /q .venv
script\install.bat
```

### 热键按了没反应

1. **是否以管理员身份运行？** `keyboard` 库注册全局热键必须有管理员权限，否则静默失败
2. 热键是否被其它程序占用（如录屏软件、游戏加速器）
3. 点「应用热键」后是否看到键名正确显示

### 后台点击没反应

1. 确认目标窗口句柄有效（点「刷新」重新选择）
2. 目标窗口最小化时，部分程序不处理投递的消息 —— 尝试先还原窗口
3. **某些程序（尤其是游戏）只接受真实硬件输入**，会主动丢弃 `PostMessage` 消息。这类程序必须用前台模式
4. 部分网页控件依赖鼠标移动事件更新 hover 状态，纯点击消息可能不触发响应

### 点击位置偏了

- 确认 X / Y 是**相对客户区的百分比**，不是屏幕绝对坐标
- 高分屏（125% / 150% 缩放）下，最小化窗口的客户区尺寸是估算值，可能有个位数像素偏差 —— 尽量在窗口正常显示时拾取坐标

### 全局异常看不到

日志在数据目录下的 `log/app_YYYY-MM-DD.log`（经启动脚本或 exe 运行时是 `dist/log/`）。
主线程异常由 `sys.excepthook` 记录，工作线程（连点引擎、热键）异常由 `threading.excepthook`
记录，日志行前缀为 `[THREAD:线程名]`。

### 在 Linux / macOS 上跑不起来

界面能起，但「开始连点」是灰的 —— 这**不是 bug**，是设计如此（见上文「跨平台支持程度」）。

常见的启动失败与原因：

| 现象 | 原因 | 处理 |
|------|------|------|
| `ModuleNotFoundError: No module named 'PyQt6.QtWidgets'` | 缺 Qt 运行库 | `sudo apt install libgl1 libegl1`（Debian/Ubuntu） |
| `ImportError: libGL.so.1` | 同上，缺 OpenGL | `sudo apt install libgl1` |
| `keyboard` 导入报 `Unsupported platform` | `keyboard` 依赖 Windows API | 属正常，热键在非 Windows 上不可用 |
| `./script/install.sh: Permission denied` | 文件没有可执行位 | `bash script/install.sh`，或 `chmod +x script/*.sh` |
| `$'\r': command not found` | 脚本被 CRLF 换行污染 | `sed -i 's/\r$//' script/*.sh && sed -i 's/\r$//' start.sh` |

> 📌 仓库已通过 `.gitattributes` 固定换行：`.sh` 检出为 LF、`.bat`/`.cmd`/`.ps1` 检出为 CRLF，
> 并给三个 `.sh` 脚本登记了可执行位（`100755`）。所以正常 `git clone` 下来不会出现上面后两条。

---

## 已知问题

以下是当前版本已知的、尚未修复的问题，供二次开发参考：

| 严重度 | 问题 | 位置 |
|--------|------|------|
| 中 | 最小化窗口的客户区尺寸靠硬编码减 16px/46px 估算，高 DPI 下会偏 | `core/click_engine.py` `get_client_size` |
| 低 | `SendInput` 返回值从不检查，被 UIPI 拦截时静默失败 | `core/click_engine.py` `_send_mouse` / `_send_keyboard` |
| 低 | `settings.start_minimized` 与 `settings.high_precision` 已定义但**从未被读取** | `utils/config_manager.py` |
| 低 | `HotkeyListener.capture_key()` 未被调用（UI 用 `KeyCaptureEdit` 自行实现） | `core/hotkey_listener.py` |
| 低 | 主题只在启动时读取，运行中切换系统主题不生效 | `ui/styles.py` |

> 已修复：
> - `target_hwnd` 会污染配置文件 —— 现在 `_auto_save_profile()` 保存前会 `pop` 掉它
> - 工作线程崩溃不入日志 —— 现在挂了 `threading.excepthook`，前缀 `[THREAD:线程名]`
> - 后台点击不发 `WM_MOUSEMOVE` —— 现在点击前会先补一条移动消息，X1/X2 的
>   `wParam` 高字也按 Windows 约定填了 `XBUTTON1` / `XBUTTON2`
> - 进程列表按进程名去重导致多进程应用丢窗口 —— 现在按 `(pid, 进程名)` 去重，
>   Chrome / Edge / VS Code 的每个进程窗口都能选到（无窗口进程仍按名字去重，避免列表变噪音）

### 一个曾被误判为 bug 的点

早期报告认为「后台键盘只发 `WM_KEYDOWN/KEYUP`、不发 `WM_CHAR`，所以输入框不会产生字符」。
实测（`QLineEdit` 接收 `PostMessage`）发现恰恰相反：

| 发送内容 | 输入框结果 |
|----------|-----------|
| 只发 `WM_KEYDOWN` + `WM_KEYUP` | `'aa'` —— 已经产生了字符，而且是两个 |
| 只发 `WM_CHAR` | `'A'` |
| `WM_KEYDOWN` + `WM_CHAR` + `WM_KEYUP` | `'Aaa'` —— 重复了 |

原因：目标窗口的消息循环会对收到的 `WM_KEYDOWN` 调 `TranslateMessage` 自动生成
`WM_CHAR`（Qt 这类框架还会额外处理一次，所以是两条）。**再手动补 `WM_CHAR` 只会让字符翻倍**，
所以代码保持只发 `WM_KEYDOWN/KEYUP`，这是正确行为。

---

## 开发说明

### 修改主题

主题色集中定义在 `ui/styles.py` 顶部两个字典 `_DARK` / `_LIGHT` 里，
`_build_style(color_dict)` 会把它们套进 QSS 模板。加新控件时同步给两个字典补色即可。

### 添加新的按键映射

在 `core/click_engine.py` 的 `VK_MAP` 字典里加 `"键名": 虚拟键码`。
虚拟键码查[微软官方文档](https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes)。

### 添加新动作类型

1. `ui/action_editor.py`：在 `type_combo` 加一项，`QStackedWidget` 加一页，`_on_ok` 里补分支
2. `core/click_engine.py`：`_execute_action` 里补 `action_type` 分支
3. `ui/main_window.py`：`_refresh_action_table` 里补类型的中文显示名

### 代码风格

- Win32 常量用全大写并附注释说明取值来源
- ctypes 结构体字段名保持与 MSDN 一致，方便对照文档
- 任何跨线程的 UI 更新必须经过信号或 `QTimer.singleShot`

> 最近提交：`dd8def4 (2026-11-21) feat: 打包默认产出 exe，源码 zip 改为可选`

---

## 许可证

本项目仅供学习和个人使用。

---

*本文档由 `script/package.ps1` / `package.sh` / `package.cmd` 任一脚本生成于 2026-11-21，版本 1.0.0。*
*手工修改会被下次打包覆盖 —— 请改 `script/README.template.md`。*
