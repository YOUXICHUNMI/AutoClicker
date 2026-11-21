# -*- coding: utf-8 -*-
"""
自动点击器主窗口 - PyQt6 图形界面
"""

import json
import os
import sys

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QCheckBox,
    QSystemTrayIcon, QMenu, QMessageBox, QStatusBar, QAbstractItemView,
    QApplication, QStyle, QInputDialog, QCompleter, QLineEdit,
    QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QAction, QMovie

from core.click_engine import (
    ClickEngine, VK_MAP, enum_windows, enum_windows_detail,
    get_window_under_cursor, is_mouse_button_down,
    get_client_size, find_window_by_title, get_window_title,
    is_minimized, restore_window, is_window, IS_WINDOWS
)
from core.hotkey_listener import HotkeyListener
from utils.app_paths import resource_path
from utils.config_manager import ConfigManager
from ui.action_editor import ActionEditorDialog, KeyCaptureEdit
from ui.process_picker import ProcessPickerDialog
from ui.styles import get_style
from utils.logger import setup_logger, log_exception

logger = setup_logger("ui")

# 自定义 item data role：存储原始窗口标题（不含进程名后缀）
TITLE_ROLE = Qt.ItemDataRole.UserRole + 1


class MainWindow(QMainWindow):
    """主窗口"""

    # 信号：从热键线程安全地触发UI更新
    _start_signal = pyqtSignal()
    _stop_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoClicker - 自动连点器")
        # 最小尺寸比旧版（680x620）放宽：内容区已改为可滚动，
        # 窗口缩到多小都不会把控件挤变形，小屏幕也能完整操作
        self.setMinimumSize(560, 460)
        self.resize(820, 720)

        # 设置窗口图标
        icon_path = resource_path("utils", "static", "Ralsei.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.config_mgr = ConfigManager()
        self.engine = ClickEngine()
        self.hotkey = HotkeyListener()

        self._building_ui = False
        self._picking = False          # 是否正在拾取坐标
        self._pick_state = 0           # 0=等待释放初始点击 1=等待新点击
        self._pick_timer = None        # 拾取定时器

        self._init_ui()
        self._apply_default_size()
        self._init_tray()
        self._init_signals()
        self._load_profiles_to_ui()
        self._register_hotkeys()

    # ============================================================
    # UI 初始化
    # ============================================================
    def _init_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        # 窗口外层：上部是可滚动内容区，下部是常驻的控制栏。
        # 内容区放进 QScrollArea 的原因：窗口被拖窄时，若直接压缩布局，
        # 各控件的 minimumSizeHint 之和会超过可用宽度，Qt 只能让相邻控件重叠
        # （表现为按钮互相挤压、表格和按钮叠在一起）。加了滚动区以后，
        # 控件保持各自的最小尺寸，放不下就出现滚动条，永远不会互相压。
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("contentScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer_layout.addWidget(scroll, 1)

        content = QWidget()
        content.setObjectName("contentPane")
        # 内容最小宽度：窗口再窄也不压缩控件，改为出横向滚动条。
        # 这个值和下面各行控件的 minimumSizeHint 之和对应，调大控件时同步改。
        content.setMinimumWidth(510)
        scroll.setWidget(content)

        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(10)

        # --- 顶部运行状态栏（GIF 动画 + 状态文字）---
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        # Ralsei 运行 GIF
        self.run_gif_label = QLabel()
        self.run_gif_label.setFixedSize(48, 48)
        self.run_gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gif_path = resource_path("utils", "static", "Ralsei_Run.gif")
        self.run_movie = QMovie(gif_path)
        self.run_movie.setScaledSize(QSize(48, 48))
        self.run_movie.frameChanged.connect(
            lambda: self.run_gif_label.setMovie(self.run_movie)
        )
        # 未运行时显示静态图标
        icon_path = resource_path("utils", "static", "Ralsei.png")
        self._static_icon = QIcon(icon_path)
        self.run_gif_label.setPixmap(self._static_icon.pixmap(48, 48))
        top_bar.addWidget(self.run_gif_label)

        self.run_status_label = QLabel("待机中")
        self.run_status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #888;")
        top_bar.addWidget(self.run_status_label)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # --- 配置文件选择区 ---
        prof_group = QGroupBox("配置文件")
        prof_layout = QGridLayout(prof_group)
        prof_layout.setHorizontalSpacing(8)
        prof_layout.setVerticalSpacing(8)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(120)
        self.profile_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)

        self.add_prof_btn = QPushButton("新建")
        self.add_prof_btn.clicked.connect(self._add_profile)
        self.rename_prof_btn = QPushButton("重命名")
        self.rename_prof_btn.clicked.connect(self._rename_profile)
        self.del_prof_btn = QPushButton("删除")
        self.del_prof_btn.clicked.connect(self._del_profile)
        self.copy_prof_btn = QPushButton("复制")
        self.copy_prof_btn.clicked.connect(self._copy_profile)
        for b in (self.add_prof_btn, self.rename_prof_btn,
                  self.copy_prof_btn, self.del_prof_btn):
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 主题选择
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("深色", "dark")
        self.theme_combo.addItem("浅色", "light")
        self.theme_combo.addItem("自动 (跟随系统)", "auto")
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.theme_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 第 0 行：配置下拉占满剩余宽度 + 四个操作按钮
        prof_layout.addWidget(QLabel("当前配置:"), 0, 0)
        prof_layout.addWidget(self.profile_combo, 0, 1)
        prof_layout.addWidget(self.add_prof_btn, 0, 2)
        prof_layout.addWidget(self.rename_prof_btn, 0, 3)
        prof_layout.addWidget(self.copy_prof_btn, 0, 4)
        prof_layout.addWidget(self.del_prof_btn, 0, 5)
        prof_layout.setColumnStretch(1, 1)

        # 第 1 行：主题单独占一行，缩窄窗口时不会把配置行挤爆
        prof_layout.addWidget(QLabel("主题:"), 1, 0)
        prof_layout.addWidget(self.theme_combo, 1, 1,
                              Qt.AlignmentFlag.AlignLeft)
        prof_layout.setColumnStretch(1, 1)

        main_layout.addWidget(prof_group)

        # --- 动作序列表 ---
        action_group = QGroupBox("点击动作序列 (按顺序执行)")
        action_layout = QVBoxLayout(action_group)
        action_layout.setSpacing(8)

        self.action_table = QTableWidget(0, 5)
        self.action_table.setHorizontalHeaderLabels(["#", "类型", "按钮/按键", "模式", "参数"])
        self.action_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.action_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.action_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.action_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.action_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.action_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.action_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.action_table.setMinimumHeight(120)
        # 纵向可伸缩：窗口拉高时表格吃掉多余空间，按钮行保持原高
        self.action_table.setSizePolicy(QSizePolicy.Policy.Expanding,
                                        QSizePolicy.Policy.Expanding)
        self.action_table.verticalHeader().setDefaultSectionSize(28)
        action_layout.addWidget(self.action_table, 1)

        # 动作操作按钮（换行流式排列，窄窗口下不会被表格压住）
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.add_action_btn = QPushButton("+ 添加动作")
        self.add_action_btn.clicked.connect(self._add_action)
        self.edit_action_btn = QPushButton("编辑")
        self.edit_action_btn.clicked.connect(self._edit_action)
        self.del_action_btn = QPushButton("删除")
        self.del_action_btn.clicked.connect(self._del_action)
        self.up_btn = QPushButton("上移")
        self.up_btn.clicked.connect(self._move_up)
        self.down_btn = QPushButton("下移")
        self.down_btn.clicked.connect(self._move_down)
        for b in (self.add_action_btn, self.edit_action_btn, self.del_action_btn,
                  self.up_btn, self.down_btn):
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        action_layout.addLayout(btn_row)
        main_layout.addWidget(action_group, 1)

        # --- 参数设置区（两列网格，垂直更省空间）---
        param_group = QGroupBox("连点参数")
        param_layout = QGridLayout(param_group)
        param_layout.setHorizontalSpacing(10)
        param_layout.setVerticalSpacing(8)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(0, 100000)
        self.interval_spin.setSuffix(" ms  (0=最快)")
        self.interval_spin.setToolTip("每轮循环之间的间隔时间。设为0表示尽可能快地连点。")
        self.interval_spin.setSizePolicy(QSizePolicy.Policy.Expanding,
                                         QSizePolicy.Policy.Fixed)

        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(0, 999999)
        self.repeat_spin.setSuffix(" 次  (0=无限)")
        self.repeat_spin.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Fixed)

        self.loop_delay_spin = QSpinBox()
        self.loop_delay_spin.setRange(0, 100000)
        self.loop_delay_spin.setSuffix(" ms")
        self.loop_delay_spin.setSizePolicy(QSizePolicy.Policy.Expanding,
                                           QSizePolicy.Policy.Fixed)

        param_layout.addWidget(QLabel("循环间隔:"), 0, 0)
        param_layout.addWidget(self.interval_spin, 0, 1)
        param_layout.addWidget(QLabel("重复次数:"), 0, 2)
        param_layout.addWidget(self.repeat_spin, 0, 3)
        param_layout.addWidget(QLabel("循环间额外延迟:"), 1, 0)
        param_layout.addWidget(self.loop_delay_spin, 1, 1, 1, 3)
        param_layout.setColumnStretch(1, 1)
        param_layout.setColumnStretch(3, 1)
        main_layout.addWidget(param_group)

        # --- 目标窗口区 ---
        target_group = QGroupBox("目标窗口 (后台点击)")
        target_layout = QGridLayout(target_group)
        target_layout.setHorizontalSpacing(8)
        target_layout.setVerticalSpacing(8)

        self.target_mode_combo = QComboBox()
        self.target_mode_combo.addItem("前台模式 (SendInput)", "foreground")
        self.target_mode_combo.addItem("后台模式 (PostMessage)", "background")
        self.target_mode_combo.currentIndexChanged.connect(self._on_target_mode_changed)
        self.target_mode_combo.setSizePolicy(QSizePolicy.Policy.Fixed,
                                             QSizePolicy.Policy.Fixed)

        self.window_combo = QComboBox()
        # 只给一个很低的兜底宽度，真正的宽度由 Expanding 拿去，
        # 这样窄窗口下组合框会跟着变窄，而不是顶宽整行
        self.window_combo.setMinimumWidth(150)
        self.window_combo.setEnabled(False)
        # 可编辑 + 关键字搜索
        self.window_combo.setEditable(True)
        self.window_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = QCompleter()
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setModel(self.window_combo.model())
        self.window_combo.setCompleter(completer)
        # 占位提示
        edit = self.window_combo.lineEdit()
        if edit:
            edit.setPlaceholderText("输入关键字搜索窗口/进程...")
            edit.returnPressed.connect(self._on_window_search_enter)
        self.window_combo.currentIndexChanged.connect(lambda: self._update_pixel_display() if not self._building_ui else None)
        self.window_combo.setSizePolicy(QSizePolicy.Policy.Expanding,
                                        QSizePolicy.Policy.Fixed)

        self.refresh_win_btn = QPushButton("刷新")
        self.refresh_win_btn.setEnabled(False)
        self.refresh_win_btn.clicked.connect(self._refresh_windows)
        self.refresh_win_btn.setSizePolicy(QSizePolicy.Policy.Fixed,
                                           QSizePolicy.Policy.Fixed)

        self.process_btn = QPushButton("📋 进程")
        self.process_btn.setEnabled(False)
        self.process_btn.clicked.connect(self._on_pick_process)
        self.process_btn.setSizePolicy(QSizePolicy.Policy.Fixed,
                                       QSizePolicy.Policy.Fixed)

        # 第 0 行：模式（左）+ 刷新/进程两个按钮靠右
        # 拆成三行而不是挤一行：「模式 + 目标窗口 + 两个按钮 + 坐标」
        # 全在一条线上时整组最小宽度会到 730px，窄窗口必然溢出
        target_layout.addWidget(QLabel("模式:"), 0, 0)
        target_layout.addWidget(self.target_mode_combo, 0, 1,
                               Qt.AlignmentFlag.AlignLeft)
        target_layout.addWidget(self.refresh_win_btn, 0, 2)
        target_layout.addWidget(self.process_btn, 0, 3)
        # 末尾空列吃剩余宽度：两个按钮紧跟模式下拉，不会被推到窗口最右边
        target_layout.setColumnStretch(4, 1)

        # 第 1 行：目标窗口下拉单独占满整行（跨到最后的弹性列）
        target_layout.addWidget(QLabel("目标窗口:"), 1, 0)
        target_layout.addWidget(self.window_combo, 1, 1, 1, 4)

        # 第 2 行：固定点击坐标（仅后台模式可用）
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel("点击坐标:"))
        self.click_x_spin = QDoubleSpinBox()
        self.click_x_spin.setRange(0.0, 100.0)
        self.click_x_spin.setSingleStep(0.1)
        self.click_x_spin.setSuffix(" %")
        self.click_x_spin.setDecimals(1)
        self.click_x_spin.setValue(50.0)
        self.click_x_spin.setEnabled(False)
        self.click_x_spin.setMinimumWidth(90)
        self.click_x_spin.setSizePolicy(QSizePolicy.Policy.Fixed,
                                        QSizePolicy.Policy.Fixed)
        self.click_x_spin.valueChanged.connect(self._on_click_point_changed)
        row2.addWidget(QLabel("X:"))
        row2.addWidget(self.click_x_spin)

        self.click_y_spin = QDoubleSpinBox()
        self.click_y_spin.setRange(0.0, 100.0)
        self.click_y_spin.setSingleStep(0.1)
        self.click_y_spin.setSuffix(" %")
        self.click_y_spin.setDecimals(1)
        self.click_y_spin.setValue(50.0)
        self.click_y_spin.setEnabled(False)
        self.click_y_spin.setMinimumWidth(90)
        self.click_y_spin.setSizePolicy(QSizePolicy.Policy.Fixed,
                                        QSizePolicy.Policy.Fixed)
        self.click_y_spin.valueChanged.connect(self._on_click_point_changed)
        row2.addWidget(QLabel("Y:"))
        row2.addWidget(self.click_y_spin)

        self.pick_btn = QPushButton("🎯 拾取坐标")
        self.pick_btn.setEnabled(False)
        self.pick_btn.clicked.connect(self._start_pick_coordinate)
        self.pick_btn.setSizePolicy(QSizePolicy.Policy.Fixed,
                                    QSizePolicy.Policy.Fixed)
        row2.addWidget(self.pick_btn)

        self.pixel_label = QLabel("")
        self.pixel_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        row2.addStretch(1)
        target_layout.addLayout(row2, 2, 0, 1, 4)

        # 第 3 行：像素提示单独一行——它文字很长，混在坐标行里
        # 会把整组最小宽度顶到 550px，窄窗口就顶出去了
        target_layout.addWidget(self.pixel_label, 3, 0, 1, 4)
        main_layout.addWidget(target_group)

        # --- 热键设置区（两列网格，窄窗口也不挤）---
        hotkey_group = QGroupBox("热键设置 (后台生效)")
        hotkey_layout = QGridLayout(hotkey_group)
        hotkey_layout.setHorizontalSpacing(10)
        hotkey_layout.setVerticalSpacing(8)

        self.start_hotkey_edit = KeyCaptureEdit()
        self.start_hotkey_edit.setPlaceholderText("点击后按下热键...")
        self.start_hotkey_edit.setSizePolicy(QSizePolicy.Policy.Expanding,
                                             QSizePolicy.Policy.Fixed)

        self.stop_hotkey_edit = KeyCaptureEdit()
        self.stop_hotkey_edit.setPlaceholderText("点击后按下热键...")
        self.stop_hotkey_edit.setSizePolicy(QSizePolicy.Policy.Expanding,
                                            QSizePolicy.Policy.Fixed)

        apply_hk_btn = QPushButton("应用热键")
        apply_hk_btn.clicked.connect(self._apply_hotkeys)
        apply_hk_btn.setSizePolicy(QSizePolicy.Policy.Fixed,
                                   QSizePolicy.Policy.Fixed)

        hotkey_layout.addWidget(QLabel("启动热键:"), 0, 0)
        hotkey_layout.addWidget(self.start_hotkey_edit, 0, 1)
        hotkey_layout.addWidget(QLabel("停止热键:"), 0, 2)
        hotkey_layout.addWidget(self.stop_hotkey_edit, 0, 3)
        hotkey_layout.addWidget(apply_hk_btn, 0, 4)
        hotkey_layout.setColumnStretch(1, 1)
        hotkey_layout.setColumnStretch(3, 1)
        main_layout.addWidget(hotkey_group)

        # --- 控制按钮（常驻底部，不随内容滚动）---
        footer = QWidget()
        footer.setObjectName("footerBar")
        ctrl_row = QHBoxLayout(footer)
        ctrl_row.setContentsMargins(12, 8, 12, 8)
        ctrl_row.setSpacing(10)

        # 非 Windows 平台：输入模拟不可用，直接禁用「开始连点」并说明原因
        _start_hint = "▶  开始连点"
        if not IS_WINDOWS:
            _start_hint = "▶  开始连点 (仅 Windows 可用)"

        self.start_btn = QPushButton(_start_hint)
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.start_btn.clicked.connect(self._on_start)
        self.start_btn.setEnabled(IS_WINDOWS)
        if not IS_WINDOWS:
            self.start_btn.setToolTip(
                f"当前平台 ({sys.platform}) 不支持输入模拟。\n"
                "连点功能依赖 Windows 的 SendInput / PostMessage API。"
            )
        self.stop_btn = QPushButton("■  停止")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        ctrl_row.addWidget(self.start_btn)
        ctrl_row.addWidget(self.stop_btn)
        outer_layout.addWidget(footer, 0)

        # 内容放不下高度时向上收拢，避免控件被拉散
        main_layout.addStretch(1)

        # --- 状态栏 ---
        if IS_WINDOWS:
            self.statusBar().showMessage("就绪 | 热键启动/停止可后台使用")
        else:
            self.statusBar().showMessage(
                f"只读模式 | 当前平台 ({sys.platform}) 不支持输入模拟，仅可查看和编辑配置")

    def _apply_default_size(self):
        """按内容实际需要和屏幕大小决定初始窗口尺寸。

        内容区各分组的最小高度加起来约 840px（含边距）。屏幕够高就一次
        展开到能看全，屏幕不够就压到可用区域的 90%，剩下的交给滚动条——
        无论哪种，控件都不会被挤压变形。
        """
        self.resize(820, 720)
        self.layout().activate() if self.layout() else None

        content_h = 0
        scroll = self.findChild(QScrollArea, "contentScroll")
        if scroll is not None and scroll.widget() is not None:
            content_h = scroll.widget().minimumSizeHint().height()

        screen = QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        width = min(900, max(self.minimumWidth(), avail.width() - 120))
        # 内容高 + 底部控制栏(≈60) + 状态栏(≈24) + 标题栏(≈32)
        want_h = content_h + 116 if content_h else 720
        height = min(want_h, int(avail.height() * 0.9))
        self.resize(width, max(height, self.minimumHeight()))
    def _init_tray(self):
        """初始化系统托盘"""
        self.tray = QSystemTrayIcon(self)
        # 使用 Ralsei.png 作为托盘图标
        icon_path = resource_path("utils", "static", "Ralsei.png")
        if os.path.exists(icon_path):
            self.tray.setIcon(QIcon(icon_path))
        else:
            self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray.setToolTip("AutoClicker")
        tray_menu = QMenu()
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._on_quit)
        tray_menu.addAction(quit_action)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _init_signals(self):
        """连接跨线程信号"""
        self._start_signal.connect(self._on_start)
        self._stop_signal.connect(self._on_stop)
        self.engine.set_action_callback(self._on_action_callback)

        # 参数变化时自动保存
        for w in (self.interval_spin, self.repeat_spin, self.loop_delay_spin):
            w.valueChanged.connect(self._auto_save_profile)

    # ============================================================
    # 配置文件操作
    # ============================================================
    def _load_profiles_to_ui(self):
        """加载所有配置文件到下拉框"""
        self._building_ui = True
        self.profile_combo.clear()
        profiles = self.config_mgr.get_profiles()
        active = self.config_mgr.config.get("active_profile", 0)
        for p in profiles:
            self.profile_combo.addItem(p.get("name", "未命名"))
        if 0 <= active < len(profiles):
            self.profile_combo.setCurrentIndex(active)
        self._building_ui = False
        self._load_active_profile_to_ui()
        # 加载主题设置到 UI
        self._load_theme_to_ui()

    def _load_theme_to_ui(self):
        """从配置加载主题设置到下拉框"""
        theme = self.config_mgr.get_settings().get("theme", "auto")
        self._building_ui = True
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == theme:
                self.theme_combo.setCurrentIndex(i)
                break
        self._building_ui = False

    def _on_theme_changed(self, idx):
        """切换主题：重新应用样式并保存"""
        if self._building_ui:
            return
        theme = self.theme_combo.itemData(idx)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_style(theme))
        self.config_mgr.get_settings()["theme"] = theme
        self.config_mgr.save()

    def _load_active_profile_to_ui(self):
        """加载当前选中的配置到界面控件"""
        profile = self.config_mgr.get_active_profile()
        if not profile:
            return

        self._building_ui = True
        self.interval_spin.setValue(profile.get("interval", 1))
        self.repeat_spin.setValue(profile.get("repeat", 0))
        self.loop_delay_spin.setValue(profile.get("loop_delay", 0))
        self.start_hotkey_edit.setText(profile.get("start_hotkey", "F6"))
        self.stop_hotkey_edit.setText(profile.get("stop_hotkey", "F7"))

        # 目标窗口模式
        target_mode = profile.get("target_mode", "foreground")
        idx = 1 if target_mode == "background" else 0
        self.target_mode_combo.setCurrentIndex(idx)
        self._on_target_mode_changed(idx)

        # 点击坐标
        self.click_x_spin.setValue(profile.get("click_x", 0.5) * 100.0)
        self.click_y_spin.setValue(profile.get("click_y", 0.5) * 100.0)

        self._building_ui = False

        self._refresh_action_table(profile)
        self._refresh_windows()

    def _refresh_action_table(self, profile=None):
        """刷新动作表格"""
        if profile is None:
            profile = self.config_mgr.get_active_profile()
        if not profile:
            return
        actions = profile.get("actions", [])
        self.action_table.setRowCount(len(actions))
        for i, action in enumerate(actions):
            self.action_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            atype = action.get("type", "mouse")
            type_text = {"mouse": "鼠标", "keyboard": "键盘", "combo": "组合键"}.get(atype, atype)
            self.action_table.setItem(i, 1, QTableWidgetItem(type_text))

            if atype == "mouse":
                btn_text = action.get("button", "left")
            elif atype == "keyboard":
                btn_text = action.get("button", "")
            elif atype == "combo":
                btn_text = " + ".join(action.get("keys", []))
            else:
                btn_text = ""
            self.action_table.setItem(i, 2, QTableWidgetItem(btn_text))

            mode = action.get("mode", "click")
            self.action_table.setItem(i, 3, QTableWidgetItem("长按" if mode == "hold" else "单击"))

            if mode == "hold":
                hold_val = action.get("hold_duration", 0.05)
                params = "一直按" if hold_val <= 0 else f"长按 {hold_val:.3f}s"
            else:
                params = ""
            delay = action.get("delay_after", 0)
            if delay > 0:
                params += f" | 延迟 {delay:.3f}s" if params else f"延迟 {delay:.3f}s"
            self.action_table.setItem(i, 4, QTableWidgetItem(params))

    def _on_profile_changed(self, idx):
        if self._building_ui or idx < 0:
            return
        self.config_mgr.set_active_profile(idx)
        self._load_active_profile_to_ui()
        self._register_hotkeys()

    def _add_profile(self):
        name = f"配置 {len(self.config_mgr.get_profiles()) + 1}"
        new_prof = {
            "name": name,
            "actions": [],
            "interval": 1,
            "repeat": 0,
            "loop_delay": 0,
            "start_hotkey": "F6",
            "stop_hotkey": "F7",
            "enabled": True,
            "target_mode": "foreground",
            "target_title": "",
            "click_x": 0.5,
            "click_y": 0.5
        }
        self.config_mgr.get_profiles().append(new_prof)
        self.config_mgr.set_active_profile(len(self.config_mgr.get_profiles()) - 1)
        self.config_mgr.save()
        self._load_profiles_to_ui()

    def _rename_profile(self):
        prof = self._get_active_profile()
        if not prof:
            return
        old_name = prof.get("name", "")
        new_name, ok = QInputDialog.getText(
            self, "重命名配置", "配置名称:", text=old_name
        )
        if ok and new_name.strip():
            prof["name"] = new_name.strip()
            self.config_mgr.save()
            self._load_profiles_to_ui()

    def _del_profile(self):
        profiles = self.config_mgr.get_profiles()
        if len(profiles) <= 1:
            QMessageBox.warning(self, "提示", "至少需要保留一个配置文件")
            return
        idx = self.profile_combo.currentIndex()
        profiles.pop(idx)
        new_idx = max(0, idx - 1)
        self.config_mgr.set_active_profile(new_idx)
        self.config_mgr.save()
        self._load_profiles_to_ui()

    def _copy_profile(self):
        import copy
        profiles = self.config_mgr.get_profiles()
        idx = self.profile_combo.currentIndex()
        new_prof = copy.deepcopy(profiles[idx])
        new_prof["name"] = profiles[idx]["name"] + " (副本)"
        profiles.append(new_prof)
        self.config_mgr.set_active_profile(len(profiles) - 1)
        self.config_mgr.save()
        self._load_profiles_to_ui()

    # ============================================================
    # 动作序列操作
    # ============================================================
    def _get_active_profile(self):
        return self.config_mgr.get_active_profile()

    def _add_action(self):
        dlg = ActionEditorDialog(action={}, parent=self)
        if dlg.exec():
            result = dlg.get_result()
            if result:
                prof = self._get_active_profile()
                prof.setdefault("actions", []).append(result)
                self._auto_save_profile()
                self._refresh_action_table()

    def _edit_action(self):
        row = self.action_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一个动作")
            return
        prof = self._get_active_profile()
        actions = prof.get("actions", [])
        if row >= len(actions):
            return
        dlg = ActionEditorDialog(action=actions[row], parent=self)
        if dlg.exec():
            result = dlg.get_result()
            if result:
                actions[row] = result
                self._auto_save_profile()
                self._refresh_action_table()

    def _del_action(self):
        row = self.action_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一个动作")
            return
        prof = self._get_active_profile()
        actions = prof.get("actions", [])
        if row < len(actions):
            actions.pop(row)
            self._auto_save_profile()
            self._refresh_action_table()

    def _move_up(self):
        row = self.action_table.currentRow()
        if row <= 0:
            return
        prof = self._get_active_profile()
        actions = prof.get("actions", [])
        if row < len(actions):
            actions[row], actions[row - 1] = actions[row - 1], actions[row]
            self._auto_save_profile()
            self._refresh_action_table()
            self.action_table.selectRow(row - 1)

    def _move_down(self):
        row = self.action_table.currentRow()
        prof = self._get_active_profile()
        actions = prof.get("actions", [])
        if row < 0 or row >= len(actions) - 1:
            return
        actions[row], actions[row + 1] = actions[row + 1], actions[row]
        self._auto_save_profile()
        self._refresh_action_table()
        self.action_table.selectRow(row + 1)

    def _auto_save_profile(self):
        """自动保存当前界面的参数到配置"""
        if self._building_ui:
            return
        try:
            prof = self._get_active_profile()
            if not prof:
                return
            prof["interval"] = self.interval_spin.value()
            prof["repeat"] = self.repeat_spin.value()
            prof["loop_delay"] = self.loop_delay_spin.value()
            prof["start_hotkey"] = self.start_hotkey_edit.text().strip()
            prof["stop_hotkey"] = self.stop_hotkey_edit.text().strip()
            # 保存目标窗口设置
            prof["target_mode"] = self.target_mode_combo.currentData()
            if self.window_combo.isEnabled() and self.window_combo.currentIndex() >= 0:
                raw_title = self.window_combo.itemData(
                    self.window_combo.currentIndex(), TITLE_ROLE)
                prof["target_title"] = raw_title or self.window_combo.currentText()
            else:
                prof["target_title"] = ""
            # 保存点击坐标比例
            prof["click_x"] = round(self.click_x_spin.value() / 100.0, 4)
            prof["click_y"] = round(self.click_y_spin.value() / 100.0, 4)
            # 运行时缓存的目标句柄绝不能落盘：HWND 每次开机都会变，
            # 写进配置后下次启动会拿到一个指向别的窗口的陈旧句柄。
            prof.pop("target_hwnd", None)
            self.config_mgr.save()
        except Exception as e:
            log_exception(logger, e, "自动保存配置失败")

    # ============================================================
    # 目标窗口
    # ============================================================
    def _on_target_mode_changed(self, idx):
        """切换前台/后台模式"""
        is_bg = (idx == 1)
        self.window_combo.setEnabled(is_bg)
        self.refresh_win_btn.setEnabled(is_bg)
        self.process_btn.setEnabled(is_bg)
        self.click_x_spin.setEnabled(is_bg)
        self.click_y_spin.setEnabled(is_bg)
        self.pick_btn.setEnabled(is_bg)
        if is_bg:
            self._refresh_windows()
            # 尝试恢复之前选择的目标窗口
            prof = self._get_active_profile()
            if prof:
                saved_title = prof.get("target_title", "")
                if saved_title:
                    # 优先用 TITLE_ROLE 精确匹配原始标题
                    for i in range(self.window_combo.count()):
                        if self.window_combo.itemData(i, TITLE_ROLE) == saved_title:
                            self.window_combo.setCurrentIndex(i)
                            break
                    else:
                        # fallback: 显示文本包含匹配
                        i = self.window_combo.findText(saved_title, Qt.MatchFlag.MatchContains)
                        if i >= 0:
                            self.window_combo.setCurrentIndex(i)
            self._update_pixel_display()
        else:
            self.pixel_label.setText("")
        if not self._building_ui:
            self._auto_save_profile()

    def _refresh_windows(self):
        """刷新可用窗口列表（包含最小化的窗口），显示标题和进程名"""
        self.window_combo.clear()
        try:
            windows = enum_windows_detail()
            for hwnd, title, proc in windows:
                display = f"{title}  [{proc}]" if proc else title
                self.window_combo.addItem(display)
                idx = self.window_combo.count() - 1
                self.window_combo.setItemData(idx, hwnd)                        # UserRole: HWND
                self.window_combo.setItemData(idx, title, TITLE_ROLE)           # 原始标题
            logger.info(f"窗口列表已刷新，共 {len(windows)} 个窗口")
        except Exception as e:
            log_exception(logger, e, "刷新窗口列表失败")
            self.statusBar().showMessage(f"刷新窗口失败: {e}")

    def _on_window_search_enter(self):
        """用户在搜索框按回车：选中第一个匹配项"""
        text = self.window_combo.currentText().strip()
        if not text:
            return
        for i in range(self.window_combo.count()):
            item_text = self.window_combo.itemText(i)
            if text.lower() in item_text.lower():
                self.window_combo.setCurrentIndex(i)
                self._update_pixel_display()
                return

    def _on_pick_process(self):
        """打开进程选择对话框"""
        try:
            dlg = ProcessPickerDialog(self)
            if dlg.exec():
                hwnd = dlg.get_selected_hwnd()
                title = dlg.get_selected_title()
                if hwnd:
                    # 在下拉框中查找对应窗口
                    found = -1
                    for i in range(self.window_combo.count()):
                        if self.window_combo.itemData(i) == hwnd:
                            found = i
                            break
                    if found < 0:
                        # 窗口不在列表中，添加新项
                        proc = ""
                        for wh, wt, wp in enum_windows_detail():
                            if wh == hwnd:
                                proc = wp
                                break
                        display = f"{title}  [{proc}]" if proc else title
                        self.window_combo.addItem(display)
                        idx = self.window_combo.count() - 1
                        self.window_combo.setItemData(idx, hwnd)
                        self.window_combo.setItemData(idx, title, TITLE_ROLE)
                        found = idx
                    if found >= 0:
                        self.window_combo.setCurrentIndex(found)
                        self._auto_save_profile()
                        self._update_pixel_display()
                        self.statusBar().showMessage(
                            f"已选择: {title[:40]}" if len(title) > 40
                            else f"已选择: {title}")
        except Exception as e:
            log_exception(logger, e, "打开进程选择对话框失败")
            QMessageBox.warning(self, "错误", f"打开进程选择失败: {e}")

    def _on_click_point_changed(self):
        """坐标输入框变化时更新像素显示并自动保存"""
        if not self._building_ui:
            self._auto_save_profile()
        self._update_pixel_display()

    def _update_pixel_display(self):
        """根据当前选择的目标窗口和坐标比例，显示实际像素位置"""
        if self.target_mode_combo.currentData() != "background":
            self.pixel_label.setText("")
            return
        # 优先使用下拉框存储的 HWND
        hwnd = self.window_combo.currentData()
        if not hwnd or not is_window(hwnd):
            # fallback: 用原始标题查找
            title = self.window_combo.itemData(
                self.window_combo.currentIndex(), TITLE_ROLE)
            if not title:
                title = self.window_combo.currentText()
            if not title:
                self.pixel_label.setText("(请先选择目标窗口)")
                return
            hwnd = find_window_by_title(title)
        if not hwnd:
            self.pixel_label.setText("(未找到窗口，请刷新列表)")
            return
        w, h = get_client_size(hwnd)
        rel_x = self.click_x_spin.value() / 100.0
        rel_y = self.click_y_spin.value() / 100.0
        px = int(rel_x * w)
        py = int(rel_y * h)
        self.pixel_label.setText(f"→ 像素 ({px}, {py})  窗口 {w}x{h}")

    # ============================================================
    # 坐标拾取
    # ============================================================
    def _start_pick_coordinate(self):
        """开始拾取坐标：隐藏本窗口，等待用户在目标位置点击"""
        if self._picking:
            return
        self._picking = True
        self._pick_state = 0  # 先等待当前点击释放
        self.statusBar().showMessage("请在目标位置点击鼠标左键... (按 Esc 取消)")
        self.pick_btn.setText("取消拾取")
        # 隐藏本窗口以便用户点击目标
        self.hide()
        # 启动定时器轮询鼠标状态
        self._pick_timer = QTimer(self)
        self._pick_timer.timeout.connect(self._on_pick_timer)
        self._pick_timer.start(30)

    def _on_pick_timer(self):
        """拾取定时器回调"""
        if not self._picking:
            return

        if self._pick_state == 0:
            # 等待鼠标左键释放（排除点击拾取按钮的那次按下）
            if not is_mouse_button_down():
                self._pick_state = 1
        elif self._pick_state == 1:
            # 等待新的鼠标左键按下
            if is_mouse_button_down():
                # 捕获光标下的窗口和坐标
                hwnd, client_x, client_y = get_window_under_cursor()
                if hwnd:
                    # 获取窗口标题
                    title = get_window_title(hwnd)
                    w, h = get_client_size(hwnd)
                    if w > 0 and h > 0:
                        rel_x = client_x / w
                        rel_y = client_y / h
                        # 限制在 0~1 范围
                        rel_x = max(0.0, min(1.0, rel_x))
                        rel_y = max(0.0, min(1.0, rel_y))
                        # 更新 UI
                        self._building_ui = True
                        self.click_x_spin.setValue(rel_x * 100.0)
                        self.click_y_spin.setValue(rel_y * 100.0)
                        self._building_ui = False
                        # 自动选择目标窗口
                        if title:
                            # 优先在已有列表中按 HWND 查找
                            found = -1
                            for i in range(self.window_combo.count()):
                                if self.window_combo.itemData(i) == hwnd:
                                    found = i
                                    break
                            if found < 0:
                                # 按 TITLE_ROLE 匹配原始标题
                                for i in range(self.window_combo.count()):
                                    if self.window_combo.itemData(i, TITLE_ROLE) == title:
                                        found = i
                                        break
                            if found < 0:
                                # 窗口不在列表中，获取进程名后添加新项
                                proc = ""
                                for wh, wt, wp in enum_windows_detail():
                                    if wh == hwnd:
                                        proc = wp
                                        break
                                display = f"{title}  [{proc}]" if proc else title
                                self.window_combo.addItem(display)
                                idx = self.window_combo.count() - 1
                                self.window_combo.setItemData(idx, hwnd)
                                self.window_combo.setItemData(idx, title, TITLE_ROLE)
                                found = idx
                            if found >= 0:
                                self.window_combo.setCurrentIndex(found)
                        self._auto_save_profile()
                        self._update_pixel_display()
                        self.statusBar().showMessage(
                            f"已拾取: {title[:30]} ({int(rel_x*w)}, {int(rel_y*h)})")
                    else:
                        self.statusBar().showMessage("拾取失败: 窗口客户区为 0")
                else:
                    self.statusBar().showMessage("拾取失败: 未找到窗口")
                self._cancel_pick()

    def _cancel_pick(self):
        """取消拾取模式"""
        self._picking = False
        self._pick_state = 0
        if self._pick_timer:
            self._pick_timer.stop()
            self._pick_timer = None
        self.pick_btn.setText("🎯 拾取坐标")
        self.showNormal()
        self.activateWindow()

    def keyPressEvent(self, event):
        """全局按键事件：Esc 取消拾取"""
        if self._picking and event.key() == Qt.Key.Key_Escape:
            self._cancel_pick()
            self.statusBar().showMessage("已取消拾取")
            return
        super().keyPressEvent(event)

    # ============================================================
    # 连点控制
    # ============================================================
    def _on_start(self):
        if self.engine.is_running:
            return
        if not IS_WINDOWS:
            QMessageBox.information(
                self, "当前平台不支持",
                f"连点功能依赖 Windows 的 SendInput / PostMessage API，\n"
                f"当前平台 ({sys.platform}) 无法模拟鼠标键盘。\n\n"
                f"界面上的配置仍可正常查看和编辑。"
            )
            return
        try:
            prof = self._get_active_profile()
            if not prof or not prof.get("actions"):
                QMessageBox.warning(self, "提示", "请先添加至少一个点击动作")
                return

            # 后台模式：检查目标窗口
            target_hwnd = 0
            if prof.get("target_mode") == "background":
                # 优先使用下拉框存储的 HWND
                hwnd = self.window_combo.currentData()
                if not hwnd or not is_window(hwnd):
                    title = prof.get("target_title", "")
                    if title:
                        hwnd = find_window_by_title(title)
                if not hwnd:
                    title = prof.get("target_title", "")
                    QMessageBox.warning(self, "提示",
                        f"未找到目标窗口: {title}\n请刷新窗口列表并重新选择")
                    return
                if is_minimized(hwnd):
                    title = prof.get("target_title", "")
                    reply = QMessageBox.question(
                        self, "窗口已最小化",
                        f"目标窗口 \"{title}\" 当前已最小化。\n"
                        f"最小化窗口可能无法正确接收鼠标点击。\n\n"
                        f"是否自动还原窗口并继续？",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        restore_window(hwnd)
                        import time as _time
                        _time.sleep(0.3)
                    else:
                        return
                target_hwnd = hwnd

            self._auto_save_profile()
            # 保存后再设置运行时 HWND（不持久化到配置文件）
            if target_hwnd:
                prof["target_hwnd"] = target_hwnd
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.statusBar().showMessage("运行中...")

            # 启动 GIF 动画
            self.run_movie.start()
            self.run_status_label.setText("运行中...")
            self.run_status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #a6e3a1;")

            self.engine.start(prof)
            self.tray.showMessage("AutoClicker", "连点已启动", QSystemTrayIcon.MessageIcon.Information, 2000)
            logger.info(f"连点已启动: 配置={prof.get('name', '?')}")
        except Exception as e:
            log_exception(logger, e, "启动连点失败")
            QMessageBox.critical(self, "错误", f"启动失败: {e}")
            self.start_btn.setEnabled(IS_WINDOWS)
            self.stop_btn.setEnabled(False)

    def _on_stop(self):
        self.engine.stop()
        self.start_btn.setEnabled(IS_WINDOWS)
        self.stop_btn.setEnabled(False)
        self.statusBar().showMessage("已停止")

        # 停止 GIF 动画，恢复静态图标
        self.run_movie.stop()
        self.run_gif_label.setPixmap(self._static_icon.pixmap(48, 48))
        self.run_status_label.setText("已停止")
        self.run_status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f38ba8;")

        self.tray.showMessage("AutoClicker", "连点已停止", QSystemTrayIcon.MessageIcon.Information, 2000)

    def _on_action_callback(self, index):
        """引擎回调（在工作线程中调用，仅更新状态栏文字）"""
        if index < 0:
            # 循环结束：恢复 UI 状态
            def _on_finished():
                self.statusBar().showMessage("已完成")
                self.start_btn.setEnabled(IS_WINDOWS)
                self.stop_btn.setEnabled(False)
                self.run_movie.stop()
                self.run_gif_label.setPixmap(self._static_icon.pixmap(48, 48))
                self.run_status_label.setText("已完成")
                self.run_status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #89b4fa;")
            QTimer.singleShot(0, _on_finished)
        else:
            QTimer.singleShot(0, lambda i=index: self.statusBar().showMessage(f"运行中... 执行动作 #{i + 1}"))

    # ============================================================
    # 热键
    # ============================================================
    def _register_hotkeys(self):
        """注册当前配置的热键"""
        prof = self._get_active_profile()
        if not prof:
            return
        start_key = prof.get("start_hotkey", "F6")
        stop_key = prof.get("stop_hotkey", "F7")

        self.hotkey.set_callbacks(
            lambda: self._start_signal.emit(),
            lambda: self._stop_signal.emit()
        )
        if self.hotkey.available:
            self.hotkey.update_hotkeys(start_key, stop_key)
        else:
            # 非 Windows 下状态栏常驻"只读模式"提示，不要用它覆盖掉
            if IS_WINDOWS:
                self.statusBar().showMessage("警告: keyboard 库未安装，热键功能不可用")
            else:
                logger.warning("keyboard 不可用，全局热键已跳过注册")

    def _apply_hotkeys(self):
        self._auto_save_profile()
        self._register_hotkeys()
        self.statusBar().showMessage("热键已更新")

    # ============================================================
    # 托盘 & 关闭
    # ============================================================
    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def _on_quit(self):
        if self._picking:
            self._cancel_pick()
        self.engine.stop()
        self.hotkey.stop()
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        """关闭时保存配置，最小化到托盘"""
        try:
            if self._picking:
                self._cancel_pick()
            self._auto_save_profile()
            self.config_mgr.save()

            settings = self.config_mgr.get_settings()
            if settings.get("minimize_to_tray", False):
                event.ignore()
                self.hide()
                self.tray.showMessage("AutoClicker", "已最小化到托盘，双击图标恢复",
                                      QSystemTrayIcon.MessageIcon.Information, 2000)
            else:
                self.engine.stop()
                self.hotkey.stop()
                self.tray.hide()
                logger.info("窗口关闭，程序退出")
                event.accept()
        except Exception as e:
            log_exception(logger, e, "关闭窗口时出错")
            event.accept()

