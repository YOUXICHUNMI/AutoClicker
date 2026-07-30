# -*- coding: utf-8 -*-
"""动作编辑对话框 - 用于添加/编辑单个点击动作"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem,
    QStackedWidget, QGroupBox, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal


class KeyCaptureEdit(QLineEdit):
    """支持捕获按键的输入框 - 点击后按下任意键自动填入键名

    支持单独修饰键（Ctrl/Shift/Alt/Win）以及组合键（Ctrl+F6 等）。
    """

    # 修饰键 -> keyboard 库识别的名称
    MODIFIER_KEYS = {
        Qt.Key.Key_Control: "ctrl",
        Qt.Key.Key_Shift: "shift",
        Qt.Key.Key_Alt: "alt",
        Qt.Key.Key_Meta: "win",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("点击此处后按下按键...")
        self.setReadOnly(False)

    def keyPressEvent(self, event):
        """拦截按键事件，转换为键名"""
        key = event.key()
        text = event.text()
        mods = event.modifiers()

        # 单独按下修饰键 -> 直接返回修饰键名
        if key in self.MODIFIER_KEYS:
            self.setText(self.MODIFIER_KEYS[key])
            return

        # 忽略 CapsLock / NumLock / ScrollLock 等切换键
        if key in (Qt.Key.Key_CapsLock, Qt.Key.Key_NumLock, Qt.Key.Key_ScrollLock):
            return

        # 收集当前按住的修饰键
        mod_parts = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            mod_parts.append("ctrl")
        if mods & Qt.KeyboardModifier.AltModifier:
            mod_parts.append("alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            mod_parts.append("shift")
        if mods & Qt.KeyboardModifier.MetaModifier:
            mod_parts.append("win")

        key_name = self._key_to_name(key, mods, text)
        if key_name:
            if mod_parts:
                self.setText("+".join(mod_parts + [key_name]))
            else:
                self.setText(key_name)

    def _key_to_name(self, key, modifiers, text):
        """将 Qt 按键转换为键名"""
        # 特殊键映射
        special = {
            Qt.Key.Key_Space: "Space",
            Qt.Key.Key_Return: "Enter",
            Qt.Key.Key_Enter: "Enter",
            Qt.Key.Key_Tab: "Tab",
            Qt.Key.Key_Escape: "Escape",
            Qt.Key.Key_Backspace: "Backspace",
            Qt.Key.Key_Delete: "Delete",
            Qt.Key.Key_Insert: "Insert",
            Qt.Key.Key_Home: "Home",
            Qt.Key.Key_End: "End",
            Qt.Key.Key_PageUp: "PageUp",
            Qt.Key.Key_PageDown: "PageDown",
            Qt.Key.Key_Up: "Up",
            Qt.Key.Key_Down: "Down",
            Qt.Key.Key_Left: "Left",
            Qt.Key.Key_Right: "Right",
            Qt.Key.Key_CapsLock: "CapsLock",
            Qt.Key.Key_NumLock: "NumLock",
            Qt.Key.Key_ScrollLock: "ScrollLock",
            Qt.Key.Key_Print: "PrintScreen",
            Qt.Key.Key_Pause: "Pause",
        }

        # 功能键
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F16:
            return f"F{key - Qt.Key.Key_F1 + 1}"

        # 数字小键盘
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            if modifiers & Qt.KeyboardModifier.KeypadModifier:
                return f"Num{key - Qt.Key.Key_0}"
            return str(key - Qt.Key.Key_0)

        # 字母
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return chr(key - Qt.Key.Key_A + ord('A'))

        # 特殊键
        if key in special:
            return special[key]

        # 符号键
        if text and text.isprintable():
            return text.upper()

        return None


class ActionEditorDialog(QDialog):
    """动作编辑对话框"""

    def __init__(self, action=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑动作")
        self.setMinimumWidth(420)
        self._action = action or {}
        self._result = None
        self._init_ui()
        self._load_action()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 动作类型
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("动作类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["鼠标点击", "键盘按键", "组合键"])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        # 堆叠区域：根据类型显示不同配置
        self.stack = QStackedWidget()

        # --- 鼠标配置页 ---
        mouse_page = QWidget()
        mouse_layout = QFormLayout(mouse_page)
        self.mouse_btn_combo = QComboBox()
        self.mouse_btn_combo.addItems(["left", "right", "middle", "x1", "x2"])
        mouse_layout.addRow("鼠标按钮:", self.mouse_btn_combo)
        self.stack.addWidget(mouse_page)

        # --- 键盘配置页 ---
        kb_page = QWidget()
        kb_layout = QFormLayout(kb_page)
        self.key_edit = KeyCaptureEdit()
        kb_layout.addRow("按键:", self.key_edit)
        hint = QLabel("提示: 点击输入框后直接按下要绑定的按键")
        hint.setStyleSheet("color: #6c7086; font-size: 11px;")
        kb_layout.addRow(hint)
        self.stack.addWidget(kb_page)

        # --- 组合键配置页 ---
        combo_page = QWidget()
        combo_layout = QVBoxLayout(combo_page)
        combo_form = QFormLayout()
        self.combo_key_edit = KeyCaptureEdit()
        combo_form.addRow("添加按键:", self.combo_key_edit)
        combo_layout.addLayout(combo_form)

        add_btn_row = QHBoxLayout()
        self.add_key_btn = QPushButton("+ 添加到组合")
        self.add_key_btn.clicked.connect(self._add_combo_key)
        add_btn_row.addWidget(self.add_key_btn)
        add_btn_row.addStretch()
        combo_layout.addLayout(add_btn_row)

        self.combo_list = QListWidget()
        self.combo_list.setMinimumHeight(100)
        combo_layout.addWidget(QLabel("组合键序列 (按下顺序):"))
        combo_layout.addWidget(self.combo_list)

        del_row = QHBoxLayout()
        self.del_key_btn = QPushButton("- 删除选中")
        self.del_key_btn.clicked.connect(self._del_combo_key)
        del_row.addWidget(self.del_key_btn)
        del_row.addStretch()
        combo_layout.addLayout(del_row)
        self.stack.addWidget(combo_page)

        layout.addWidget(self.stack)

        # 模式设置
        mode_group = QGroupBox("点击模式")
        mode_layout = QFormLayout(mode_group)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["单击 (Click)", "长按 (Hold)"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addRow("模式:", self.mode_combo)

        self.hold_label = QLabel("长按时长:")
        self.hold_spin = QDoubleSpinBox()
        self.hold_spin.setRange(0.0, 10.0)
        self.hold_spin.setSingleStep(0.01)
        self.hold_spin.setSuffix(" 秒")
        self.hold_spin.setDecimals(3)
        self.hold_spin.setSpecialValueText("一直按 (0s)")
        mode_layout.addRow(self.hold_label, self.hold_spin)

        self.delay_label = QLabel("动作后延迟:")
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.0, 10.0)
        self.delay_spin.setSingleStep(0.001)
        self.delay_spin.setSuffix(" 秒")
        self.delay_spin.setDecimals(3)
        mode_layout.addRow(self.delay_label, self.delay_spin)
        layout.addWidget(mode_group)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _on_type_changed(self, idx):
        self.stack.setCurrentIndex(idx)

    def _on_mode_changed(self, idx):
        is_hold = (idx == 1)
        # 两个字段始终保持可见，非当前模式的字段灰显禁用
        self.hold_label.setEnabled(is_hold)
        self.hold_spin.setEnabled(is_hold)
        self.delay_label.setEnabled(not is_hold)
        self.delay_spin.setEnabled(not is_hold)

    def _add_combo_key(self):
        key = self.combo_key_edit.text().strip()
        if key:
            self.combo_list.addItem(key)
            self.combo_key_edit.clear()

    def _del_combo_key(self):
        row = self.combo_list.currentRow()
        if row >= 0:
            self.combo_list.takeItem(row)

    def _load_action(self):
        """加载已有动作到界面"""
        a = self._action
        atype = a.get("type", "mouse")

        if atype == "mouse":
            self.type_combo.setCurrentIndex(0)
            self.mouse_btn_combo.setCurrentText(a.get("button", "left"))
        elif atype == "keyboard":
            self.type_combo.setCurrentIndex(1)
            self.key_edit.setText(a.get("button", ""))
        elif atype == "combo":
            self.type_combo.setCurrentIndex(2)
            for k in a.get("keys", []):
                self.combo_list.addItem(k)

        mode = a.get("mode", "click")
        self.mode_combo.setCurrentIndex(1 if mode == "hold" else 0)
        self.hold_spin.setValue(a.get("hold_duration", 0.05))
        self.delay_spin.setValue(a.get("delay_after", 0.001))
        self._on_mode_changed(self.mode_combo.currentIndex())

    def _on_ok(self):
        """构建结果动作并关闭"""
        idx = self.type_combo.currentIndex()

        mode = "hold" if self.mode_combo.currentIndex() == 1 else "click"
        result = {"mode": mode}
        if mode == "hold":
            result["hold_duration"] = round(self.hold_spin.value(), 3)
        else:
            result["delay_after"] = round(self.delay_spin.value(), 3)

        if idx == 0:
            result["type"] = "mouse"
            result["button"] = self.mouse_btn_combo.currentText()
        elif idx == 1:
            key = self.key_edit.text().strip()
            if not key:
                QMessageBox.warning(self, "提示", "请设置按键")
                return
            result["type"] = "keyboard"
            result["button"] = key
        elif idx == 2:
            keys = []
            for i in range(self.combo_list.count()):
                keys.append(self.combo_list.item(i).text())
            if not keys:
                QMessageBox.warning(self, "提示", "请至少添加一个按键到组合键")
                return
            result["type"] = "combo"
            result["keys"] = keys

        self._result = result
        self.accept()

    def get_result(self):
        return self._result
