# -*- coding: utf-8 -*-
"""
AutoClicker - 自动连点器
入口文件
"""

import sys
import os

# 将项目根目录加入 sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from ui.main_window import MainWindow
from ui.styles import get_style
from utils.app_paths import resource_path
from utils.config_manager import ConfigManager
from utils.logger import setup_logger, install_global_handler, log_exception

# 初始化日志
logger = setup_logger("main")

# 静态资源路径（冻结运行时从 PyInstaller 的解压目录取）
ICON_PATH = resource_path("utils", "static", "Ralsei.png")


def main():
    logger.info("=" * 60)
    logger.info("AutoClicker 启动")
    logger.info(f"项目目录: {PROJECT_ROOT}")

    # 安装全局异常钩子
    install_global_handler(logger)

    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("AutoClicker")

    # 设置应用程序图标
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))
    else:
        logger.warning(f"图标文件不存在: {ICON_PATH}")

    # 读取配置中的主题设置并应用样式
    try:
        cfg = ConfigManager()
        theme = cfg.get_settings().get("theme", "auto")
        app.setStyleSheet(get_style(theme))
        logger.info(f"主题: {theme}")
    except Exception as e:
        log_exception(logger, e, "加载配置或主题失败")

    # 确保全局热键库可用
    try:
        import keyboard
        logger.info("keyboard 库加载成功")
    except ImportError:
        logger.warning("未安装 keyboard 库，全局热键功能将不可用")
        logger.warning("请运行: pip install keyboard")

    try:
        window = MainWindow()
        window.show()
        logger.info("主窗口已显示，进入事件循环")
        sys.exit(app.exec())
    except Exception as e:
        log_exception(logger, e, "主窗口启动失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
