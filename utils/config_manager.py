# -*- coding: utf-8 -*-
"""配置文件管理模块 - 使用 JSON 保存/加载连点器配置"""

import json
import os
from copy import deepcopy

from utils.app_paths import app_path

# 配置文件目录（冻结运行时为 exe 同级的 config 文件夹）
CONFIG_DIR = app_path("config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# 默认配置
DEFAULT_CONFIG = {
    "profiles": [
        {
            "name": "默认配置",
            "actions": [
                {
                    "type": "mouse",
                    "button": "left",
                    "mode": "click",        # click | hold
                    "hold_duration": 0.05,  # 长按时长（秒），仅 hold 模式生效
                    "delay_after": 0.001    # 执行后等待（秒）
                }
            ],
            "interval": 1,           # 循环间隔（毫秒），0 表示尽可能快
            "repeat": 0,             # 重复次数，0 表示无限
            "loop_delay": 0,         # 每轮循环之间的额外延迟（毫秒）
            "start_hotkey": "F6",
            "stop_hotkey": "F7",
            "enabled": True,
            "target_mode": "foreground",  # foreground | background
            "target_title": "",           # 后台模式目标窗口标题
            "click_x": 0.5,               # 后台点击 X 比例 (0.0~1.0)
            "click_y": 0.5                # 后台点击 Y 比例 (0.0~1.0)
        }
    ],
    "active_profile": 0,
    "settings": {
        "minimize_to_tray": False,
        "start_minimized": False,
        "high_precision": True,   # 使用高精度计时器
        "theme": "auto"           # dark | light | auto
    }
}


class ConfigManager:
    """配置管理器：负责读取、保存、重置配置"""

    def __init__(self):
        self._config = deepcopy(DEFAULT_CONFIG)
        self.load()

    # ---- 读写 ----
    def load(self):
        """从磁盘加载配置，文件不存在时自动创建默认配置"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # 合并：以加载值为准，但保证默认键存在
                self._merge(loaded)
        except Exception as e:
            print(f"[ConfigManager] 加载配置失败，使用默认配置: {e}")
            self._config = deepcopy(DEFAULT_CONFIG)
        return self._config

    def save(self):
        """保存配置到磁盘"""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[ConfigManager] 保存配置失败: {e}")
            return False

    def reset(self):
        """重置为默认配置"""
        self._config = deepcopy(DEFAULT_CONFIG)
        self.save()

    # ---- 访问 ----
    @property
    def config(self):
        return self._config

    def get_profiles(self):
        return self._config.get("profiles", [])

    def get_active_profile(self):
        profiles = self.get_profiles()
        idx = self._config.get("active_profile", 0)
        if 0 <= idx < len(profiles):
            return profiles[idx]
        return profiles[0] if profiles else None

    def set_active_profile(self, idx):
        self._config["active_profile"] = idx

    def get_settings(self):
        return self._config.get("settings", {})

    # ---- 内部 ----
    def _merge(self, loaded):
        """将加载的配置与默认配置合并，保证结构完整"""
        for key in DEFAULT_CONFIG:
            if key not in loaded:
                loaded[key] = deepcopy(DEFAULT_CONFIG[key])
        # 确保每个 profile 都有新增字段
        default_prof = DEFAULT_CONFIG["profiles"][0]
        for prof in loaded.get("profiles", []):
            for k, v in default_prof.items():
                if k not in prof:
                    prof[k] = deepcopy(v)
        # 确保 settings 有所有默认字段
        default_settings = DEFAULT_CONFIG["settings"]
        loaded_settings = loaded.get("settings", {})
        for k, v in default_settings.items():
            if k not in loaded_settings:
                loaded_settings[k] = deepcopy(v)
        loaded["settings"] = loaded_settings
        self._config = loaded
