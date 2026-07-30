# -*- coding: utf-8 -*-
"""
AutoClicker 日志模块
统一管理日志输出，按日期分文件，结构化格式
"""

import os
import sys
import logging
import traceback
from datetime import datetime

# 日志目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(PROJECT_ROOT, "log")

# 日志格式
LOG_FORMAT = "[%(asctime)s] [%(levelname)-7s] [%(name)-14s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S.%f"[:-3]  # 毫秒精度


def _get_log_file():
    """返回今天的日志文件路径: log/app_YYYY-MM-DD.log"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(LOG_DIR, f"app_{today}.log")


def setup_logger(name="app", level=logging.DEBUG):
    """
    设置并返回一个 logger，同时输出到文件和控制台

    Args:
        name: 模块名称 (如 'main', 'click_engine', 'ui')
        level: 日志级别
    Returns:
        logging.Logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # 文件 handler
    file_handler = logging.FileHandler(_get_log_file(), encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def log_exception(logger, exc, context=""):
    """
    以结构化格式记录异常（含完整 traceback）

    Args:
        logger: logging.Logger 实例
        exc: 异常对象
        context: 额外上下文描述
    """
    tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    tb_text = "".join(tb_lines).rstrip()

    separator = "=" * 60
    logger.error(separator)
    if context:
        logger.error(f"[CONTEXT] {context}")
    logger.error(f"[EXCEPTION] {type(exc).__name__}: {exc}")
    logger.error(f"[TRACEBACK]\n{tb_text}")
    logger.error("-" * 60)


def install_global_handler(logger):
    """
    安装全局异常钩子，捕获未处理的异常并写入日志

    Args:
        logger: 主 logger 实例
    """
    def handle_excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb)).rstrip()
        separator = "=" * 60
        logger.error(separator)
        logger.error(f"[GLOBAL] Unhandled exception: {exc_type.__name__}: {exc_value}")
        logger.error(f"[TRACEBACK]\n{tb_text}")
        logger.error("-" * 60)

    sys.excepthook = handle_excepthook
