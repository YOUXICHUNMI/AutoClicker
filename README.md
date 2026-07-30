# AutoClicker
![](./utils/static/Ralsei.png)  

基于 PyQt6 的 Windows 自动连点器，支持鼠标/键盘动作录制与回放、后台窗口点击、多配置管理、全局热键控制。  

在CookieClickWeb端时，不喜欢鼠大侠而且想要后台挂机的连点器，突发奇想让AI随便写了一个。

## 功能特性

- **多动作类型**：鼠标点击、键盘按键、组合键序列
- **点击模式**：单击（含动作后延迟）、长按（可设为一直按）
- **后台模式**：通过窗口句柄（HWND）对后台窗口发送点击，不影响前台操作
- **进程选择**：关键字搜索窗口、进程列表选择目标窗口
- **多配置管理**：支持多套配置切换、重命名、自动保存
- **全局热键**：启动/停止热键自定义，托盘最小化
- **三主题系统**：深色（Catppuccin Mocha）、浅色（Catppuccin Latte）、自动跟随系统
- **日志系统**：异常自动记录到 `log/` 目录，按日期分文件

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 |
| Python | >= 3.10 |
| 依赖 | PyQt6 >= 6.6.0, keyboard >= 0.13.5 |

> `keyboard` 库需要管理员权限才能注册全局热键。建议以管理员身份运行。

## 项目结构

```
AutoClicker/
├── main.py                  # 程序入口
├── requirements.txt         # 依赖列表
├── start.bat               # 快捷启动脚本
├── config/
│   └── config.json         # 配置文件（自动生成）
├── core/
│   └── click_engine.py     # 核心引擎（窗口枚举、进程枚举、点击执行）
├── ui/
│   ├── main_window.py      # 主窗口
│   ├── action_editor.py    # 动作编辑对话框
│   ├── process_picker.py   # 进程选择对话框
│   └── styles.py           # 主题样式（深色/浅色/自动）
├── utils/
│   ├── config_manager.py   # 配置管理器
│   ├── logger.py           # 日志模块
│   └── static/
│       ├── Ralsei.png      # 应用图标
│       └── Ralsei_Run.gif  # 运行动画
├── script/
│   ├── install.bat         # Windows 安装脚本
│   ├── install.ps1         # PowerShell 安装脚本
│   ├── install.sh          # Bash 安装脚本
│   ├── run.bat             # Windows 启动脚本
│   ├── run.ps1             # PowerShell 启动脚本
│   └── run.sh              # Bash 启动脚本
└── log/                    # 日志目录（自动生成）
```

## 安装与运行

### 方式一：uv（推荐）

[uv](https://github.com/astral-sh/uv) 是高性能的 Python 包管理器，安装速度快、自带虚拟环境管理。

```bash
# 1. 安装 uv
pip install uv

# 2. 创建虚拟环境
uv venv .venv

# 3. 安装依赖
uv pip install -r requirements.txt

# 4. 运行
.venv\Scripts\python.exe main.py
```

### 方式二：pip + venv

```bash
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活虚拟环境
.venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行
python main.py
```

### 方式三：一键脚本

项目提供了多平台安装和运行脚本，位于 `script/` 目录：

**Windows (CMD):**
```bat
script\install.bat
script\run.bat
```

**Windows (PowerShell):**
```powershell
.\script\install.ps1
.\script\run.ps1
```

**Linux / Git Bash:**
```bash
chmod +x script/install.sh script/run.sh
./script/install.sh
./script/run.sh
```

脚本会自动创建 `.venv` 虚拟环境、安装依赖，并使用虚拟环境中的 Python 启动程序。

## 依赖列表

```
PyQt6>=6.6.0
keyboard>=0.13.5
```

| 依赖 | 用途 |
|------|------|
| [PyQt6](https://pypi.org/project/PyQt6/) | GUI 框架，提供窗口、控件、样式表 |
| [keyboard](https://pypi.org/project/keyboard/) | 全局热键注册与监听 |

## 使用说明

1. **添加动作**：点击"添加动作"按钮，选择动作类型（鼠标/键盘/组合键），设置按钮或按键、点击模式
2. **前台/后台模式**：
   - 前台模式：直接在当前光标位置执行点击
   - 后台模式：选择目标窗口后，对指定窗口发送后台点击消息
3. **选择目标窗口**：
   - 下拉框支持关键字搜索（匹配窗口标题和进程名）
   - 点击"进程"按钮从进程列表中选择
   - 点击"拾取"按钮后鼠标点击目标窗口自动选中
4. **启动/停止**：点击"开始"按钮或使用全局热键
5. **托盘最小化**：关闭窗口时最小化到系统托盘，右键托盘图标可退出

## 配置说明

配置文件位于 `config/config.json`，程序运行时自动创建和更新。支持多配置切换，每个配置独立保存动作列表、目标窗口、热键等设置。

## 日志

程序运行日志自动写入 `log/` 目录，按日期命名（`app_YYYY-MM-DD.log`）。未捕获的异常会通过全局异常钩子自动记录，包含完整的堆栈信息。

## 许可

本项目仅供学习和个人使用。
