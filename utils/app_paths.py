# -*- coding: utf-8 -*-
"""
应用路径解析

统一处理「源码运行」与「PyInstaller 冻结运行」两种情况下的目录定位。

- 源码运行：应用根目录 = 项目根目录（main.py 所在目录）
- 冻结运行：应用根目录 = exe 所在目录

为什么不能直接用 __file__ 推导：
    PyInstaller onefile 模式会把整个包解压到 %TEMP%\\_MEIxxxxxx\\ 再运行，
    此时模块的 __file__ 指向那个临时目录。若用它存放 config/ 和 log/，
    程序退出后临时目录被删除，用户的配置和日志会全部丢失。
    静态资源（只读）倒是可以放在临时目录里，用 resource_path() 取。
"""

import os
import sys

# 数据目录环境变量：由启动脚本设置，让源码运行与 exe 运行共用同一个数据目录
DATA_DIR_ENV = "AUTOCLICKER_DATA_DIR"


def is_frozen() -> bool:
    """是否运行在 PyInstaller 等冻结环境中"""
    return getattr(sys, "frozen", False)


def app_root() -> str:
    """
    可写的应用根目录：配置文件、日志放这里。

    优先级：
    1. 环境变量 AUTOCLICKER_DATA_DIR（start.bat / script/run.* 会设为项目下的
       dist/，这样源码运行与 exe 运行读写的是同一份配置和日志）
    2. 冻结运行：exe 所在目录（用户能看到、能备份）
    3. 源码运行：项目根目录
    """
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return os.path.abspath(override)

    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_root() -> str:
    """
    只读资源根目录：图标、GIF 等打进包里的静态文件。

    - 冻结运行：sys._MEIPASS（解压出的临时目录）
    - 源码运行：项目根目录
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return meipass
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts) -> str:
    """拼接只读资源路径，例如 resource_path('utils', 'static', 'Ralsei.png')"""
    return os.path.join(resource_root(), *parts)


def app_path(*parts) -> str:
    """拼接可写路径，例如 app_path('config', 'config.json')"""
    return os.path.join(app_root(), *parts)
