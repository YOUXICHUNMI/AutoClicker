# -*- coding: utf-8 -*-
"""
全局热键监听模块 - 使用 keyboard 库实现后台热键响应
即使软件在后台/最小化，热键依然能触发。
"""

import sys
import threading

from utils.logger import setup_logger, log_exception

logger = setup_logger("hotkey")

IS_WINDOWS = sys.platform == "win32"

try:
    import keyboard
    _HAS_KEYBOARD = True
except ImportError:
    _HAS_KEYBOARD = False
    logger.warning("keyboard 库未安装，热键功能不可用")
except Exception as e:  # keyboard 在非 Windows 上可能因缺少 /dev/input 权限等报其它错
    _HAS_KEYBOARD = False
    logger.warning(f"keyboard 库初始化失败，热键功能不可用: {e}")

if _HAS_KEYBOARD and not IS_WINDOWS:
    logger.warning(
        "非 Windows 平台：keyboard 库需要 root 权限才能读取 /dev/input，"
        "全局热键通常不可用。"
    )


class HotkeyListener:
    """
    全局热键监听器
    在独立线程中运行，监听指定的热键并触发回调。
    """

    def __init__(self):
        self._start_hotkey = None
        self._stop_hotkey = None
        self._start_callback = None
        self._stop_callback = None
        self._registered = []
        self._lock = threading.Lock()

    @property
    def available(self):
        return _HAS_KEYBOARD

    def set_callbacks(self, start_cb, stop_cb):
        """设置启动和停止热键的回调函数"""
        self._start_callback = start_cb
        self._stop_callback = stop_cb

    def update_hotkeys(self, start_key, stop_key):
        """更新热键绑定（会先清除旧绑定）"""
        if not _HAS_KEYBOARD:
            return False

        with self._lock:
            self._unregister_all()

            self._start_hotkey = start_key
            self._stop_hotkey = stop_key

            try:
                if start_key:
                    keyboard.add_hotkey(start_key, self._on_start, suppress=False)
                    self._registered.append(("start", start_key))
                if stop_key:
                    keyboard.add_hotkey(stop_key, self._on_stop, suppress=False)
                    self._registered.append(("stop", stop_key))
                logger.info(f"热键已注册: 启动={start_key}, 停止={stop_key}")
                return True
            except Exception as e:
                log_exception(logger, e, f"注册热键失败: start={start_key}, stop={stop_key}")
                return False

    def _on_start(self):
        if self._start_callback:
            try:
                self._start_callback()
            except Exception as e:
                log_exception(logger, e, "启动回调异常")

    def _on_stop(self):
        if self._stop_callback:
            try:
                self._stop_callback()
            except Exception as e:
                log_exception(logger, e, "停止回调异常")

    def _unregister_all(self):
        """注销所有已注册的热键"""
        if not _HAS_KEYBOARD:
            return
        for tag, key in self._registered:
            try:
                keyboard.remove_hotkey(key)
            except Exception:
                pass
        if self._registered:
            logger.info(f"已注销 {len(self._registered)} 个热键")
        self._registered.clear()

    def stop(self):
        """停止监听，注销所有热键"""
        with self._lock:
            self._unregister_all()

    def capture_key(self, callback, timeout=None):
        """
        捕获下一次按键，用于界面上设置热键。
        callback(key_name) 在捕获到按键后调用。
        """
        if not _HAS_KEYBOARD:
            callback(None)
            return

        def _on_event(event):
            if event.event_type == keyboard.KEY_DOWN:
                key_name = event.name
                # 格式化修饰键
                if key_name in ("ctrl", "alt", "shift", "windows"):
                    return False  # 等待非修饰键
                # 组合键
                mods = []
                if keyboard.is_pressed("ctrl"):
                    mods.append("ctrl")
                if keyboard.is_pressed("alt"):
                    mods.append("alt")
                if keyboard.is_pressed("shift"):
                    mods.append("shift")
                if keyboard.is_pressed("windows"):
                    mods.append("windows")

                if mods:
                    full = "+".join(mods + [key_name])
                else:
                    full = key_name

                keyboard.unhook_all()
                callback(full)
                return False  # 阻止事件传播

            return False

        keyboard.hook(_on_event, suppress=False)
