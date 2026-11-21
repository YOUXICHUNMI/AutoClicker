#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
README 生成器

由 package.ps1 / package.sh / package.cmd 共同调用，负责：

1. 扫描源码，统计每个模块的有效行数（去掉末尾空行）
2. 递归生成目录树（排除 .venv / __pycache__ / log / dist 等）
3. 读取 git 最近一次提交信息
4. 把上述内容代入 script/README.template.md 的占位符，写出 README.md

为什么用 Python 而不是在各脚本里各写一份：
    模板有 478 行、7 个占位符，PowerShell / bash / cmd 三套实现必然发散。
    本项目本身就依赖 Python，把这段逻辑集中到一处，三个打包脚本只做
    "找 Python → 调用本文件 → 打包" 三件事，不会走样。

用法:
    python script/gen_readme.py [--version 1.0.0] [--quiet]
    python script/gen_readme.py --check          # 只算不写，打印统计
"""

import argparse
import os
import subprocess
import sys

# Windows 控制台默认 GBK，中文输出会变乱码；统一切到 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ---------- 路径 ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "README.template.md")
README_PATH = os.path.join(PROJECT_DIR, "README.md")

# ---------- 打包/打包树排除规则 ----------
EXCLUDE_DIRS = {
    ".venv", "venv", "__pycache__", ".git", "dist", "build",
    ".idea", ".vscode", "log", ".pytest_cache", ".mypy_cache",
}
EXCLUDE_FILE_SUFFIXES = (".pyc", ".pyo", ".pyd", ".log")
EXCLUDE_FILE_NAMES = {".DS_Store", "Thumbs.db"}

# ---------- 模块职责表（顺序即 README 表格顺序）----------
MODULE_DESC = [
    ("main.py", "程序入口：创建 QApplication、装载主题、初始化日志与主窗口"),
    ("core/click_engine.py", "核心引擎：Win32 输入模拟、窗口/进程枚举、连点循环调度"),
    ("core/hotkey_listener.py", "全局热键注册与回调（依赖 keyboard 库）"),
    ("ui/main_window.py", "主窗口：配置管理、动作表格、目标窗口、坐标拾取、热键、托盘、启停控制"),
    ("ui/action_editor.py", "动作编辑对话框 + KeyCaptureEdit 按键捕获控件"),
    ("ui/process_picker.py", "进程选择对话框"),
    ("ui/styles.py", "Catppuccin 深/浅色主题与系统暗色检测"),
    ("utils/app_paths.py", "路径解析：统一源码运行与 PyInstaller 冻结运行下的目录定位"),
    ("utils/config_manager.py", "配置读写、默认值合并、多配置管理"),
    ("utils/logger.py", "日志初始化、全局/线程异常钩子"),
]


def _is_excluded_dir(name):
    return name in EXCLUDE_DIRS


def _is_excluded_file(name):
    if name in EXCLUDE_FILE_NAMES:
        return True
    return name.endswith(EXCLUDE_FILE_SUFFIXES)


def count_lines(path):
    """有效行数：去掉文件末尾的连续空行"""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return 0
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    n = len(lines)
    while n > 0 and not lines[n - 1].strip():
        n -= 1
    return n


def collect_stats():
    """返回 [(相对路径, 行数, 说明), ...]，只含实际存在的文件"""
    rows = []
    for rel, desc in MODULE_DESC:
        full = os.path.join(PROJECT_DIR, rel)
        if os.path.isfile(full):
            rows.append((rel, count_lines(full), desc))
    return rows


def build_tree(root, prefix="", rel=""):
    """
    递归生成目录树文本行。

    Args:
        root: 当前遍历的绝对路径
        prefix: 前面累积的缩进串（'│   ' / '    '）
        rel:  相对项目根的前缀路径，仅用于 debug
    """
    try:
        entries = [e for e in os.scandir(root)]
    except OSError:
        return []

    def keep(entry):
        if entry.is_dir(follow_symlinks=False):
            return not _is_excluded_dir(entry.name)
        return not _is_excluded_file(entry.name)

    entries = [e for e in entries if keep(e)]
    # 目录在前、文件在后，各自按名称排序（不区分大小写，跨平台更稳）
    dirs = sorted([e for e in entries if e.is_dir(follow_symlinks=False)],
                  key=lambda e: e.name.lower())
    files = sorted([e for e in entries if not e.is_dir(follow_symlinks=False)],
                   key=lambda e: e.name.lower())
    ordered = dirs + files

    out = []
    for idx, entry in enumerate(ordered):
        is_last = idx == len(ordered) - 1
        branch = "└── " if is_last else "├── "
        next_pad = "    " if is_last else "│   "
        if entry.is_dir(follow_symlinks=False):
            out.append(prefix + branch + entry.name + "/")
            out.extend(build_tree(entry.path, prefix + next_pad,
                                  rel + entry.name + "/"))
        else:
            out.append(prefix + branch + entry.name)
    return out


def get_git_info():
    """返回 'hash (date) subject'，无 git 或失败时返回 None"""
    try:
        r = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                           cwd=PROJECT_DIR, capture_output=True, text=True,
                           timeout=10)
        if r.returncode != 0:
            return None

        def one(*args):
            p = subprocess.run(["git"] + list(args), cwd=PROJECT_DIR,
                               capture_output=True, text=True, timeout=10)
            return p.stdout.strip() if p.returncode == 0 else ""

        h = one("log", "-1", "--format=%h")
        d = one("log", "-1", "--format=%ad", "--date=short")
        s = one("log", "-1", "--format=%s")
        if not h:
            return None
        return f"{h} ({d}) {s}"
    except (OSError, subprocess.SubprocessError):
        return None


def render(version, today):
    """生成 README 文本；模板缺失时抛 FileNotFoundError"""
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        tpl = f.read()

    stats = collect_stats()
    total_lines = sum(r[1] for r in stats)
    loc_table = "\n".join(
        f"| `{rel}` | {n} | {desc} |" for rel, n, desc in stats
    )
    tree = "\n".join(build_tree(PROJECT_DIR))

    git_info = get_git_info()
    git_line = f"> 最近提交：`{git_info}`" if git_info else ""

    text = tpl
    text = text.replace("TREE_PLACEHOLDER", tree)
    text = text.replace("LOC_PLACEHOLDER", loc_table)
    text = text.replace("FILE_COUNT_PLACEHOLDER", str(len(stats)))
    text = text.replace("TOTAL_LINES_PLACEHOLDER", str(total_lines))
    text = text.replace("GENERATED_DATE_PLACEHOLDER", today)
    text = text.replace("VERSION_PLACEHOLDER", version)
    if git_line:
        text = text.replace("GIT_INFO_PLACEHOLDER", git_line)
    else:
        # 整行删掉，避免留下空引用块
        text = text.replace("GIT_INFO_PLACEHOLDER\r\n", "")
        text = text.replace("GIT_INFO_PLACEHOLDER\n", "")

    # 统一换行符，保证跨平台产出逐字节一致
    return text.replace("\r\n", "\n"), stats, total_lines


def write_if_changed(path, text):
    """内容未变则不写，保持 mtime 稳定 —— 让 zip 可复现"""
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            if f.read() == text:
                return False
    except OSError:
        pass
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate README.md from template")
    ap.add_argument("--version", default="1.0.0", help="版本号，写入页脚")
    ap.add_argument("--date", default=None, help="生成日期，默认今天")
    ap.add_argument("--check", action="store_true",
                    help="只统计并打印，不写文件")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if args.date:
        today = args.date
    else:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")

    def say(msg=""):
        if not args.quiet:
            print(msg)

    if not os.path.isfile(TEMPLATE_PATH):
        print(f"[ERROR] 模板不存在: {TEMPLATE_PATH}", file=sys.stderr)
        return 2

    try:
        text, stats, total_lines = render(args.version, today)
    except OSError as e:
        print(f"[ERROR] 读取模板失败: {e}", file=sys.stderr)
        return 2

    if args.check:
        say(f"模块数  : {len(stats)}")
        say(f"总行数  : {total_lines}")
        say("")
        for rel, n, _ in stats:
            say(f"  {rel:<28} {n:>5}")
        return 0

    changed = write_if_changed(README_PATH, text)
    if changed:
        say(f"[OK] README.md 已更新  ({len(text)} 字符 / "
            f"{len(stats)} 模块 / {total_lines} 行)")
    else:
        say(f"[--] README.md 无变化，跳过写入  ({len(text)} 字符)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
