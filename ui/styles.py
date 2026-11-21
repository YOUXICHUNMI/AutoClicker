# -*- coding: utf-8 -*-
"""界面样式表 (QSS) - 支持深色 / 浅色 / 自动主题

颜色方案基于 Catppuccin Mocha (深色) 与 Catppuccin Latte (浅色)。
"""

import os
import sys

# winreg 只在 Windows 上存在；Linux / macOS 上 import 会失败，
# 所以用 try/except 包住，让本模块在任意平台都能被导入（非 Windows 走默认主题）。
try:
    import winreg
except ImportError:  # pragma: no cover - 仅非 Windows 平台走到这里
    winreg = None

IS_WINDOWS = sys.platform == "win32"


# ============================================================
# 颜色方案
# ============================================================

# Catppuccin Mocha (深色)
_DARK = {
    "base":          "#1e1e2e",
    "mantle":        "#181825",
    "surface0":      "#313244",
    "surface1":      "#45475a",
    "surface2":      "#585b70",
    "overlay0":      "#6c7086",
    "text":          "#cdd6f4",
    "blue":          "#89b4fa",
    "green":         "#a6e3a1",
    "green_hover":   "#94d389",
    "red":           "#f38ba8",
    "red_hover":     "#e07891",
}

# Catppuccin Latte (浅色)
_LIGHT = {
    "base":          "#eff1f5",
    "mantle":        "#e6e9ef",
    "surface0":      "#ccd0da",
    "surface1":      "#bcc0cc",
    "surface2":      "#acb0be",
    "overlay0":      "#6c6f85",
    "text":          "#4c4f69",
    "blue":          "#1e66f5",
    "green":         "#40a02b",
    "green_hover":   "#368a22",
    "red":           "#d20f39",
    "red_hover":     "#b30d31",
}


def _build_style(c):
    """根据颜色字典生成完整 QSS 样式表"""
    return f"""
QMainWindow, QDialog, QWidget#central {{
    background-color: {c['base']};
    color: {c['text']};
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}}

/* 可滚动内容区：窗口缩小时靠滚动条解决空间不足，
   而不是让控件互相挤压重叠 */
QScrollArea#contentScroll {{
    background-color: {c['base']};
    border: none;
}}
QWidget#contentPane {{
    background-color: {c['base']};
}}

/* 底部常驻控制栏：始终贴底，不随内容滚动 */
QWidget#footerBar {{
    background-color: {c['mantle']};
    border-top: 1px solid {c['surface1']};
}}

QScrollBar:horizontal {{
    background: {c['mantle']};
    height: 10px;
    border: none;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: {c['surface1']};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {c['surface2']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

QLabel {{
    color: {c['text']};
    background: transparent;
}}
QLabel:disabled {{
    color: {c['overlay0']};
}}

QGroupBox {{
    border: 1px solid {c['surface1']};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: bold;
    color: {c['blue']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}}

QPushButton {{
    background-color: {c['surface0']};
    border: 1px solid {c['surface1']};
    border-radius: 5px;
    padding: 6px 16px;
    color: {c['text']};
    min-height: 22px;
}}
QPushButton:hover {{
    background-color: {c['surface1']};
    border-color: {c['blue']};
}}
QPushButton:pressed {{
    background-color: {c['mantle']};
}}
QPushButton#startBtn {{
    background-color: {c['green']};
    color: {c['base']};
    font-weight: bold;
    font-size: 15px;
    min-height: 36px;
    border: none;
    border-radius: 8px;
}}
QPushButton#startBtn:hover {{
    background-color: {c['green_hover']};
}}
QPushButton#startBtn:disabled {{
    background-color: {c['surface1']};
    color: {c['overlay0']};
}}
QPushButton#stopBtn {{
    background-color: {c['red']};
    color: {c['base']};
    font-weight: bold;
    font-size: 15px;
    min-height: 36px;
    border: none;
    border-radius: 8px;
}}
QPushButton#stopBtn:hover {{
    background-color: {c['red_hover']};
}}

QComboBox {{
    background-color: {c['surface0']};
    border: 1px solid {c['surface1']};
    border-radius: 5px;
    padding: 4px 10px;
    color: {c['text']};
    min-height: 22px;
}}
QComboBox:hover {{
    border-color: {c['blue']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['surface0']};
    border: 1px solid {c['surface1']};
    selection-background-color: {c['blue']};
    color: {c['text']};
    outline: none;
}}

QSpinBox, QDoubleSpinBox, QLineEdit {{
    background-color: {c['surface0']};
    border: 1px solid {c['surface1']};
    border-radius: 5px;
    padding: 4px 8px;
    color: {c['text']};
    min-height: 22px;
}}
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{
    border-color: {c['blue']};
}}
QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled {{
    background-color: {c['mantle']};
    border: 1px solid {c['surface0']};
    color: {c['overlay0']};
}}

QTableWidget {{
    background-color: {c['mantle']};
    border: 1px solid {c['surface1']};
    border-radius: 5px;
    gridline-color: {c['surface0']};
    color: {c['text']};
    outline: none;
}}
QTableWidget::item {{
    padding: 4px 8px;
    min-height: 24px;
}}
QTableWidget::item:selected {{
    background-color: {c['surface0']};
    color: {c['blue']};
}}
QHeaderView::section {{
    background-color: {c['surface0']};
    border: none;
    border-right: 1px solid {c['surface1']};
    border-bottom: 1px solid {c['surface1']};
    padding: 6px 8px;
    color: {c['blue']};
    font-weight: bold;
}}

QListWidget, QListView {{
    background-color: {c['mantle']};
    border: 1px solid {c['surface1']};
    border-radius: 5px;
    color: {c['text']};
    outline: none;
}}
QListWidget::item, QListView::item {{
    padding: 4px 8px;
}}
QListWidget::item:selected, QListView::item:selected {{
    background-color: {c['surface0']};
    color: {c['blue']};
}}
QListWidget::item:disabled, QListView::item:disabled {{
    color: {c['overlay0']};
}}
QListWidget::item:alternate, QListView::item:alternate {{
    background-color: {c['base']};
}}

QCheckBox {{
    color: {c['text']};
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid {c['surface1']};
    background-color: {c['surface0']};
}}
QCheckBox::indicator:checked {{
    background-color: {c['blue']};
    border-color: {c['blue']};
}}

QStatusBar {{
    background-color: {c['mantle']};
    color: {c['overlay0']};
    border-top: 1px solid {c['surface0']};
}}

QScrollBar:vertical {{
    background: {c['mantle']};
    width: 10px;
    border: none;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {c['surface1']};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['surface2']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QToolTip {{
    background-color: {c['surface0']};
    color: {c['text']};
    border: 1px solid {c['surface1']};
    border-radius: 4px;
    padding: 4px;
}}

QMenu {{
    background-color: {c['surface0']};
    border: 1px solid {c['surface1']};
    color: {c['text']};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {c['blue']};
    color: {c['base']};
}}
"""


# 预生成两种主题样式表
DARK_STYLE = _build_style(_DARK)
LIGHT_STYLE = _build_style(_LIGHT)

# 向后兼容
MAIN_STYLE = DARK_STYLE


# ============================================================
# 系统主题检测
# ============================================================

def detect_system_dark():
    """检测系统是否使用暗色主题

    Windows 读注册表；其它平台按桌面环境的环境变量粗略判断，
    都判断不了时返回暗色（与 Windows 上的默认行为一致）。

    Returns:
        True 表示暗色模式，False 表示浅色模式
    """
    if IS_WINDOWS and winreg is not None:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            # AppsUseLightTheme: 0 = 暗色, 1 = 浅色
            return value == 0
        except Exception:
            return True  # 检测失败时默认暗色

    # 非 Windows：部分桌面环境会把当前配色方案导到环境变量里
    color_scheme = os.environ.get("COLORSCHEME", "").lower()
    if "dark" in color_scheme:
        return True
    if "light" in color_scheme:
        return False
    return True


# ============================================================
# 主题样式获取
# ============================================================

def get_style(theme="dark"):
    """根据主题名称返回对应 QSS 样式表

    Args:
        theme: "dark" | "light" | "auto"

    Returns:
        QSS 样式表字符串
    """
    if theme == "light":
        return LIGHT_STYLE
    elif theme == "auto":
        return DARK_STYLE if detect_system_dark() else LIGHT_STYLE
    else:
        return DARK_STYLE
