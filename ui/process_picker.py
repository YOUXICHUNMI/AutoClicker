# -*- coding: utf-8 -*-
"""
进程选择对话框 - 浏览所有进程并选择目标窗口
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton
)
from PyQt6.QtCore import Qt

from core.click_engine import get_process_window_list
from utils.logger import setup_logger, log_exception

logger = setup_logger("process_picker")

# 复用 main_window 中的 TITLE_ROLE 定义
TITLE_ROLE = Qt.ItemDataRole.UserRole + 1


class ProcessPickerDialog(QDialog):
    """进程选择对话框：显示所有进程及其窗口，支持关键字搜索"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择进程")
        self.setMinimumSize(520, 520)
        self.resize(520, 600)
        self._selected_hwnd = 0
        self._selected_title = ""
        self._init_ui()
        self._load_processes()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # --- 搜索框 ---
        layout.addWidget(QLabel("输入关键字搜索进程名或窗口标题:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("例如: chrome、记事本、explorer...")
        self.search_edit.textChanged.connect(self._on_search)
        self.search_edit.returnPressed.connect(self._on_search_enter)
        layout.addWidget(self.search_edit)

        # --- 进程列表 ---
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)

        # --- 底部状态 + 按钮 ---
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.count_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self._on_ok)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.ok_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

    def _load_processes(self):
        """加载所有进程和窗口到列表"""
        self.list_widget.clear()
        try:
            data = get_process_window_list()
            total_with_window = 0
            for pid, proc_name, windows in data:
                if windows:
                    for hwnd, title in windows:
                        display = f"{proc_name}  [{pid}]  —  {title}"
                        item = QListWidgetItem(display)
                        item.setData(Qt.ItemDataRole.UserRole, hwnd)
                        item.setData(TITLE_ROLE, title)
                        self.list_widget.addItem(item)
                        total_with_window += 1
                else:
                    display = f"{proc_name}  [{pid}]  (无窗口)"
                    item = QListWidgetItem(display)
                    item.setData(Qt.ItemDataRole.UserRole, 0)
                    # 禁用无窗口的进程项
                    flags = item.flags()
                    flags &= ~Qt.ItemFlag.ItemIsSelectable
                    flags &= ~Qt.ItemFlag.ItemIsEnabled
                    item.setFlags(flags)
                    self.list_widget.addItem(item)

            self.count_label.setText(
                f"共 {self.list_widget.count()} 个进程，"
                f"其中 {total_with_window} 个有窗口")
            logger.info(f"进程列表已加载: {self.list_widget.count()} 个进程")
        except Exception as e:
            log_exception(logger, e, "加载进程列表失败")

    def _on_search(self, text):
        """实时搜索过滤"""
        text = text.strip().lower()
        visible = 0
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            match = (text == "") or (text in item.text().lower())
            item.setHidden(not match)
            if match:
                visible += 1
        self.count_label.setText(f"匹配 {visible} 项")

    def _on_search_enter(self):
        """搜索框按回车：选中第一个可选项"""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.isHidden():
                continue
            if not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
                continue
            self.list_widget.setCurrentRow(i)
            return

    def _on_item_double_clicked(self, item):
        """双击选择"""
        hwnd = item.data(Qt.ItemDataRole.UserRole)
        if hwnd:
            self._selected_hwnd = hwnd
            self._selected_title = item.data(TITLE_ROLE) or ""
            self.accept()

    def _on_ok(self):
        """确定按钮"""
        item = self.list_widget.currentItem()
        if not item:
            return
        hwnd = item.data(Qt.ItemDataRole.UserRole)
        if hwnd:
            self._selected_hwnd = hwnd
            self._selected_title = item.data(TITLE_ROLE) or ""
            self.accept()

    def get_selected_hwnd(self):
        """返回选中的窗口句柄"""
        return self._selected_hwnd

    def get_selected_title(self):
        """返回选中的窗口标题"""
        return self._selected_title
