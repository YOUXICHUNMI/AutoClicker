# -*- coding: utf-8 -*-
"""
AutoClicker 日志模块
统一管理日志输出，按日期分文件，结构化格式
"""

import os
import sys
import logging
import threading
import traceback
from datetime import datetime

from utils.app_paths import app_path

# 日志目录（冻结运行时为 exe 同级的 log 文件夹）
LOG_DIR = app_path("log")

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
    # PyInstaller --noconsole 打包后 sys.stdout / sys.stderr 均为 None，
    # 此时挂 StreamHandler 会在每条日志上抛 AttributeError，直接跳过。
    if sys.stdout is not None:
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

    # 连点引擎跑在 threading.Thread 里，主线程钩子抓不到它的异常，
    # 必须单独挂 threading.excepthook，否则工作线程崩溃会静默死掉。
    def handle_thread_excepthook(args):
        if args.exc_type is SystemExit:
            return
        tb_text = "".join(
            traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        ).rstrip()
        separator = "=" * 60
        logger.error(separator)
        logger.error(
            f"[THREAD:{args.thread.name if args.thread else '?'}] "
            f"Unhandled exception: {args.exc_type.__name__}: {args.exc_value}"
        )
        logger.error(f"[TRACEBACK]\n{tb_text}")
        logger.error("-" * 60)

    threading.excepthook = handle_thread_excepthook
