# -*- coding: utf-8 -*-
"""
核心点击引擎 - 使用 Windows SendInput API 实现系统级模拟输入
即使软件在后台也能模拟鼠标和键盘操作。
"""

import ctypes
import os
import sys
import time
import threading
import logging

from utils.logger import setup_logger, log_exception

logger = setup_logger("click_engine")

# ============================================================
# 平台判定
# ============================================================
# 本模块的输入模拟依赖 Windows 的 SendInput / PostMessage / EnumWindows。
# 在非 Windows 平台（Linux / macOS）上，模块依然要能正常导入，否则界面打不开，
# 所以这里退化成"空实现"：所有查询函数返回安全默认值，所有输入函数不做事并记日志。
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes.wintypes as wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    WINFUNCTYPE = ctypes.WINFUNCTYPE
else:
    # 非 Windows：用等价的 ctypes 基础类型凑出 wintypes 的最小实现，
    # 让下面的结构体定义在 Linux / macOS 上也能正常构建（仅用于声明，不会被真正调用）。
    import types as _types

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    wintypes = _types.SimpleNamespace(
        BOOL=ctypes.c_int,
        DWORD=ctypes.c_ulong,
        WORD=ctypes.c_ushort,
        HWND=ctypes.c_void_p,
        LONG=ctypes.c_long,
        LPARAM=ctypes.c_ssize_t,
        WPARAM=ctypes.c_size_t,
        UINT=ctypes.c_uint,
        ULONG=ctypes.c_ulong,
        POINT=_POINT,
        RECT=_RECT,
    )
    user32 = None
    kernel32 = None
    WINFUNCTYPE = ctypes.CFUNCTYPE

# 非 Windows 下提示只打一次，避免连点循环里刷屏
_platform_warned = False


def _warn_unsupported(action):
    """非 Windows 平台上的统一降级提示（只打一次）"""
    global _platform_warned
    if not _platform_warned:
        _platform_warned = True
        logger.error(
            f"当前平台 ({sys.platform}) 不支持输入模拟：{action} 等操作会被忽略。"
            " AutoClicker 的连点功能只能在 Windows 上使用。"
        )

# ============================================================
# Windows API 常量
# ============================================================
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001

# 鼠标按键 -> 事件标志映射
MOUSE_FLAGS = {
    "left":   (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right":  (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
    "x1":     (MOUSEEVENTF_XDOWN, MOUSEEVENTF_XUP, 0x0001),
    "x2":     (MOUSEEVENTF_XDOWN, MOUSEEVENTF_XUP, 0x0002),
}

# PostMessage 窗口消息常量
WM_MOUSEFIRST = 0x0200
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102

MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002
MK_MBUTTON = 0x0010
MK_XBUTTON1 = 0x0020
MK_XBUTTON2 = 0x0040

# X 按钮在 wParam 高字里的标识
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002

# PostMessage 鼠标消息映射
# (DOWN 消息, UP 消息, MK_ 按下标志, wParam 高字里的 X 按钮标识)
POST_MOUSE_MSG = {
    "left":   (WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON, 0),
    "right":  (WM_RBUTTONDOWN, WM_RBUTTONUP, MK_RBUTTON, 0),
    "middle": (WM_MBUTTONDOWN, WM_MBUTTONUP, MK_MBUTTON, 0),
    "x1":     (WM_XBUTTONDOWN, WM_XBUTTONUP, MK_XBUTTON1, XBUTTON1),
    "x2":     (WM_XBUTTONDOWN, WM_XBUTTONUP, MK_XBUTTON2, XBUTTON2),
}

# ============================================================
# 虚拟键码映射表
# ============================================================
VK_MAP = {
    # 字母
    **{chr(c): c for c in range(ord('A'), ord('Z') + 1)},
    **{str(c): c for c in range(10)},
    # 功能键
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "F13": 0x7C, "F14": 0x7D, "F15": 0x7E, "F16": 0x7F,
    # 修饰键
    "Shift": 0x10, "Ctrl": 0x11, "Alt": 0x12, "Win": 0x5B,
    "shift": 0x10, "ctrl": 0x11, "alt": 0x12, "win": 0x5B,
    "LShift": 0xA0, "RShift": 0xA1, "LCtrl": 0xA2, "RCtrl": 0xA3,
    "LAlt": 0xA4, "RAlt": 0xA5, "LWin": 0x5B, "RWin": 0x5C,
    # 特殊键
    "Space": 0x20, "Enter": 0x0D, "Return": 0x0D, "Tab": 0x09,
    "Escape": 0x1B, "Esc": 0x1B, "Backspace": 0x08, "Back": 0x08,
    "Delete": 0x2E, "Del": 0x2E, "Insert": 0x2D, "Ins": 0x2D,
    "Home": 0x24, "End": 0x23, "PageUp": 0x21, "PageDown": 0x22,
    "PgUp": 0x21, "PgDn": 0x22,
    # 方向键
    "Up": 0x26, "Down": 0x28, "Left": 0x25, "Right": 0x27,
    # 数字小键盘
    "Num0": 0x60, "Num1": 0x61, "Num2": 0x62, "Num3": 0x63,
    "Num4": 0x64, "Num5": 0x65, "Num6": 0x66, "Num7": 0x67,
    "Num8": 0x68, "Num9": 0x69,
    "NumLock": 0x90, "ScrollLock": 0x91,
    # 符号键
    "Oem3": 0xC0,    # `~
    "OemMinus": 0xBD,  # -_
    "OemPlus": 0xBB,   # =+
    "Oem5": 0xDC,      # \|
    "Oem6": 0xDD,      # ]}
    "Oem4": 0xDB,      # [{
    "Oem1": 0xBA,      # ;:
    "Oem7": 0xDE,      # '"
    "OemComma": 0xBC,  # ,<
    "OemPeriod": 0xBE,  # .>
    "Oem2": 0xBF,      # /?
    "CapsLock": 0x14,
    "PrintScreen": 0x2C, "PrtSc": 0x2C,
    "Pause": 0x13,
}

# 反向映射：VK码 -> 名称（用于界面显示）
VK_REVERSE = {v: k for k, v in VK_MAP.items()}


def key_name_to_vk(name):
    """将按键名称转换为虚拟键码，找不到返回 None"""
    if name in VK_MAP:
        return VK_MAP[name]
    # 尝试大写
    name_cap = name.capitalize()
    if name_cap in VK_MAP:
        return VK_MAP[name_cap]
    name_upper = name.upper()
    if name_upper in VK_MAP:
        return VK_MAP[name_upper]
    return None


# ============================================================
# SendInput 结构体定义
# ============================================================
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    ]


def _send_mouse(button, down):
    """发送鼠标输入"""
    if not IS_WINDOWS:
        _warn_unsupported("鼠标 SendInput")
        return
    flags = MOUSE_FLAGS.get(button, MOUSE_FLAGS["left"])
    down_flag = flags[0]
    up_flag = flags[1]
    mouse_data = flags[2] if len(flags) > 2 else 0

    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.mi.dx = 0
    inp.mi.dy = 0
    inp.mi.mouseData = mouse_data
    inp.mi.dwFlags = down_flag if down else up_flag
    inp.mi.time = 0
    inp.mi.dwExtraInfo = ctypes.pointer(wintypes.ULONG(0))

    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def _send_keyboard(vk_code, down):
    """发送键盘输入"""
    if not IS_WINDOWS:
        _warn_unsupported("键盘 SendInput")
        return
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki.wVk = vk_code
    inp.ki.wScan = 0
    if down:
        inp.ki.dwFlags = 0
    else:
        inp.ki.dwFlags = KEYEVENTF_KEYUP
    inp.ki.time = 0
    inp.ki.dwExtraInfo = ctypes.pointer(wintypes.ULONG(0))

    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


# ============================================================
# 窗口操作辅助函数
# ============================================================
GA_ROOT = 2
SW_RESTORE = 9
SW_SHOWNOACTIVATE = 4
VK_LBUTTON = 0x01


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]


def is_minimized(hwnd):
    """检查窗口是否最小化"""
    if not IS_WINDOWS or not hwnd:
        return False
    return user32.IsIconic(hwnd) != 0


def is_window(hwnd):
    """检查句柄是否有效"""
    if not IS_WINDOWS or not hwnd:
        return False
    return user32.IsWindow(hwnd) != 0


def get_top_level_window(hwnd):
    """获取子窗口对应的顶层窗口句柄"""
    if not IS_WINDOWS or not hwnd:
        return hwnd
    root = user32.GetAncestor(hwnd, GA_ROOT)
    return root if root else hwnd


def get_window_title(hwnd):
    """获取窗口标题"""
    if not IS_WINDOWS or not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def get_client_size(hwnd):
    """
    获取窗口客户区尺寸 (width, height)。
    对最小化窗口，使用 GetWindowPlacement 获取还原后的尺寸并估算客户区。
    """
    if not IS_WINDOWS or not hwnd:
        return (1, 1)
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w > 0 and h > 0:
        return (w, h)

    # 窗口可能最小化，尝试用 WindowPlacement 获取还原尺寸
    placement = WINDOWPLACEMENT()
    placement.length = ctypes.sizeof(WINDOWPLACEMENT)
    if user32.GetWindowPlacement(hwnd, ctypes.byref(placement)):
        nr = placement.rcNormalPosition
        # rcNormalPosition 包含非客户区（标题栏+边框），粗略减去
        w = max(1, (nr.right - nr.left) - 16)   # 左右边框 ~16px
        h = max(1, (nr.bottom - nr.top) - 46)   # 标题栏+边框 ~46px
        return (w, h)
    return (1, 1)


def restore_window(hwnd):
    """还原最小化的窗口（不激活）"""
    if not IS_WINDOWS or not hwnd:
        return
    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)


def get_window_under_cursor():
    """获取当前鼠标光标下的顶层窗口句柄和客户区坐标"""
    if not IS_WINDOWS:
        return 0, 0, 0
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    # WindowFromPoint 返回可能子窗口，需要找到顶层
    hwnd_raw = user32.WindowFromPoint(point)
    hwnd = get_top_level_window(hwnd_raw) if hwnd_raw else 0
    if hwnd:
        # 转换为客户区坐标
        client_pt = wintypes.POINT(point.x, point.y)
        user32.ScreenToClient(hwnd, ctypes.byref(client_pt))
        return hwnd, client_pt.x, client_pt.y
    return 0, 0, 0


def is_mouse_button_down():
    """检查鼠标左键是否当前按下"""
    if not IS_WINDOWS:
        return False
    return (user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000) != 0


# ============================================================
# PostMessage 后台输入函数
# ============================================================
def _make_lparam(x, y):
    """构造 lParam（低16位=x，高16位=y）"""
    return (y << 16) | (x & 0xFFFF)


def _post_mouse(hwnd, button, down, rel_x=0.5, rel_y=0.5, send_move=True):
    """
    通过 PostMessage 向后台窗口发送鼠标点击。
    rel_x, rel_y: 相对坐标 (0.0~1.0)，会根据窗口当前客户区尺寸换算为绝对像素坐标。
    窗口缩放时自动按比例重算。

    send_move: 点击前先补一条 WM_MOUSEMOVE。很多控件（网页、游戏 UI）靠
    WM_MOUSEMOVE 更新 hover / 命中状态，只发 DOWN/UP 会出现"点了但没反应"。
    对非 X 按钮，DOWN 时 wParam 的 X 标识位放在高字；
    UP 时该位必须为 0（Windows 的约定）。
    """
    if not IS_WINDOWS:
        _warn_unsupported("后台鼠标 PostMessage")
        return
    # 获取窗口当前客户区尺寸（支持最小化窗口的回退）
    w, h = get_client_size(hwnd)
    abs_x = int(rel_x * w)
    abs_y = int(rel_y * h)
    lparam = _make_lparam(abs_x, abs_y)

    msgs = POST_MOUSE_MSG.get(button, POST_MOUSE_MSG["left"])
    down_msg, up_msg, mk_flag, x_flag = msgs

    # 先把光标"移动"到目标点，控件才会有正确的命中与 hover 状态
    if send_move:
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam)

    if down:
        msg = down_msg
        wparam = mk_flag
    else:
        msg = up_msg
        wparam = 0

    # X 按钮的标识要放在 wParam 高字里，且只有 DOWN 消息需要
    if x_flag and down:
        wparam = (x_flag << 16) | wparam

    user32.PostMessageW(hwnd, msg, wparam, lparam)


def _post_keyboard(hwnd, vk_code, down):
    """通过 PostMessage 向后台窗口发送键盘输入"""
    if not IS_WINDOWS:
        _warn_unsupported("后台键盘 PostMessage")
        return
    if down:
        user32.PostMessageW(hwnd, WM_KEYDOWN, vk_code, 0)
    else:
        user32.PostMessageW(hwnd, WM_KEYUP, vk_code, 0)


# ============================================================
# 窗口枚举
# ============================================================
# 回调函数类型（Windows 用 WINFUNCTYPE，非 Windows 退化为 CFUNCTYPE）
WNDENUMPROC = WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def enum_windows_detail():
    """
    枚举所有有标题的顶层窗口（包括最小化的窗口），
    返回 [(hwnd, title, process_name), ...]
    process_name 为窗口所属进程的可执行文件名（如 chrome.exe），获取失败则为空字符串。
    """
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    results = []

    if not IS_WINDOWS:
        return results

    def _get_process_name(hwnd):
        """通过窗口句柄获取对应进程的可执行文件名"""
        try:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == 0:
                return ""
            handle = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if not handle:
                return ""
            try:
                buf = ctypes.create_unicode_buffer(260)
                size = wintypes.DWORD(260)
                if kernel32.QueryFullProcessImageNameW(
                        handle, 0, buf, ctypes.byref(size)):
                    return os.path.basename(buf.value)
                return ""
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return ""

    def _callback(hwnd, lparam):
        if not user32.IsWindow(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if title.strip():
            proc_name = _get_process_name(hwnd)
            results.append((hwnd, title, proc_name))
        return True

    proc = WNDENUMPROC(_callback)
    user32.EnumWindows(proc, 0)
    return results


def enum_windows():
    """
    枚举所有有标题的顶层窗口（包括最小化的窗口），返回 [(hwnd, title), ...]
    """
    return [(hwnd, title) for hwnd, title, _ in enum_windows_detail()]


# ============================================================
# 进程枚举
# ============================================================

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = -1


class _PROCESSENTRY32W(ctypes.Structure):
    """PROCESSENTRY32W 结构体（用于进程快照遍历）"""
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def enum_processes():
    """
    枚举系统中所有运行中的进程，返回 [(pid, process_name), ...]。
    使用 CreateToolhelp32Snapshot + Process32First/Next。
    非 Windows 平台没有 Toolhelp，直接返回空列表。
    """
    results = []
    if not IS_WINDOWS:
        return results
    snapshot = kernel32.CreateToolhelp32Snapshot(
        TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        logger.warning("CreateToolhelp32Snapshot 失败")
        return results

    entry = _PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)

    try:
        if kernel32.Process32FirstW(
                snapshot, ctypes.byref(entry)):
            while True:
                results.append((entry.th32ProcessID, entry.szExeFile))
                if not kernel32.Process32NextW(
                        snapshot, ctypes.byref(entry)):
                    break
    except Exception as e:
        log_exception(logger, e, "枚举进程失败")
    finally:
        kernel32.CloseHandle(snapshot)

    return results


def get_process_window_list():
    """
    枚举所有进程，并关联其窗口信息。
    返回 [(pid, process_name, [(hwnd, window_title), ...]), ...]
    有窗口的进程排在前面，无窗口的进程排在后面。

    同一个 .exe 可能启动多个进程（Chrome / Edge / VS Code 都是这样），
    每个进程有自己的窗口。所以按 (pid, name) 去重，而不是按 name：
    否则同名进程只会留下第一个 PID 的窗口，其余窗口在进程选择框里全部消失，
    用户就选不到自己真正想点的那个窗口。
    """
    # 先拿到每个窗口的 (hwnd, title, pid, proc_name)
    entries = []
    for hwnd, title, proc_name in enum_windows_detail():
        pid = 0
        if IS_WINDOWS:
            buf = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(buf))
            pid = buf.value
        entries.append((pid, proc_name, hwnd, title))

    # 按 (pid, name) 分组，同一个进程的多个窗口并到一起
    grouped = {}
    order = []
    for pid, name, hwnd, title in entries:
        key = (pid, name)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append((hwnd, title))

    # 把 enum_processes() 里没有窗口的进程也补进来，保持"进程全表"的语义。
    # 无窗口的进程对"选择目标窗口"毫无用处，所以这部分仍按进程名去重，
    # 只留第一个 PID —— 否则 Chrome 这类应用会凭空多出几十条噪音行。
    known = set(grouped.keys())
    seen_nameless = set()
    for pid, name in enum_processes():
        key = (pid, name)
        if key in known:
            continue
        if name in seen_nameless:
            continue
        seen_nameless.add(name)
        known.add(key)
        grouped[key] = []
        order.append(key)

    result = [(pid, name, grouped[(pid, name)]) for pid, name in order]

    # 有窗口的排前面；同组内按 "进程名 + 最小 pid" 稳定排序
    result.sort(key=lambda x: (len(x[2]) == 0, x[1].lower(), x[0]))
    return result


def find_window_by_title(title):
    """
    根据窗口标题查找 HWND（精确匹配）。
    如果找不到精确匹配，尝试包含匹配。
    """
    windows = enum_windows()
    for hwnd, t in windows:
        if t == title:
            return hwnd
    for hwnd, t in windows:
        if title in t:
            return hwnd
    return 0


class ClickEngine:
    """
    点击引擎 - 在独立线程中执行点击/按键序列
    支持单次点击、连点、长按、组合键宏
    支持前台(SendInput)和后台(PostMessage)两种模式
    """

    def __init__(self):
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._action_callback = None
        self._target_hwnd = 0       # 后台模式目标窗口句柄
        self._target_mode = "foreground"  # "foreground" 或 "background"
        self._click_x = 0.5         # 后台点击 X 比例 (0.0~1.0)
        self._click_y = 0.5         # 后台点击 Y 比例 (0.0~1.0)
        self._held_keys = []        # hold=0 时保持按下的键/按钮列表

    @property
    def is_running(self):
        return self._running

    def set_action_callback(self, callback):
        """设置动作回调，callback(index) 在每个动作执行前调用"""
        self._action_callback = callback

    def start(self, profile):
        """开始执行连点"""
        if not IS_WINDOWS:
            logger.error(
                f"当前平台 ({sys.platform}) 不支持输入模拟，无法开始连点。"
                " 连点功能依赖 Windows 的 SendInput / PostMessage，只能在 Windows 上使用。"
            )
            return False
        with self._lock:
            if self._running:
                return False
            self._running = True

        # 确定目标模式和窗口
        self._target_mode = profile.get("target_mode", "foreground")
        target_title = profile.get("target_title", "")
        self._click_x = profile.get("click_x", 0.5)
        self._click_y = profile.get("click_y", 0.5)
        if self._target_mode == "background":
            # 优先使用传入的 HWND（运行时从下拉框获取），无效则用标题查找
            self._target_hwnd = profile.get("target_hwnd", 0)
            if not self._target_hwnd or not is_window(self._target_hwnd):
                self._target_hwnd = find_window_by_title(target_title) if target_title else 0
            if not self._target_hwnd:
                logger.warning(f"未找到目标窗口: {target_title}，回退到前台模式")
                self._target_mode = "foreground"
            elif is_minimized(self._target_hwnd):
                logger.info(f"目标窗口已最小化，尝试还原 (HWND={self._target_hwnd})")
                restore_window(self._target_hwnd)
                time.sleep(0.2)
        else:
            self._target_hwnd = 0
            self._target_mode = "foreground"

        logger.info(f"引擎启动 | 模式={self._target_mode} | 动作数={len(profile.get('actions', []))} | "
                     f"间隔={profile.get('interval', 1)}ms | 重复={'无限' if profile.get('repeat', 0)==0 else profile.get('repeat', 0)}")
        self._thread = threading.Thread(target=self._run_loop, args=(profile,), daemon=True)
        self._thread.start()
        return True

    def stop(self):
        """停止连点"""
        with self._lock:
            self._running = False
        logger.info("引擎停止")

    def _run_loop(self, profile):
        """主循环：反复执行动作序列"""
        actions = profile.get("actions", [])
        interval_ms = profile.get("interval", 1)
        repeat = profile.get("repeat", 0)  # 0 = 无限
        loop_delay_ms = profile.get("loop_delay", 0)

        interval = interval_ms / 1000.0 if interval_ms > 0 else 0
        loop_delay = loop_delay_ms / 1000.0

        self._held_keys = []
        held_indices = set()  # hold=0 已按下的动作索引，后续循环跳过

        count = 0
        while True:
            with self._lock:
                if not self._running:
                    break

            for i, action in enumerate(actions):
                with self._lock:
                    if not self._running:
                        break

                # 跳过已经 hold=0 按下的动作（一直按，不重复发送）
                if i in held_indices:
                    continue

                # 通知回调
                if self._action_callback:
                    try:
                        self._action_callback(i)
                    except Exception:
                        pass

                is_held = self._execute_action(action)
                if is_held:
                    held_indices.add(i)

                delay = action.get("delay_after", 0)
                if delay > 0:
                    self._precise_sleep(delay)

            count += 1
            if repeat > 0 and count >= repeat:
                break

            # 如果所有动作都已 hold=0，sleep 避免忙等待
            if len(held_indices) >= len(actions):
                self._precise_sleep(0.05)
                continue

            # 循环间延迟
            if loop_delay > 0:
                self._precise_sleep(loop_delay)
            elif interval > 0:
                self._precise_sleep(interval)

        with self._lock:
            self._running = False

        # 清理：松开所有 hold=0 保持按下的键/按钮
        self._release_held_keys()

        # 通知回调结束
        if self._action_callback:
            try:
                self._action_callback(-1)
            except Exception as e:
                log_exception(logger, e, "动作回调结束通知失败")

    def _execute_action(self, action):
        """执行单个动作（自动选择前台/后台模式）

        Returns:
            True 表示该动作为 hold=0（一直按），调用方应跳过后续重复执行
        """
        try:
            action_type = action.get("type", "mouse")
            mode = action.get("mode", "click")

            if action_type == "mouse":
                button = action.get("button", "left")
                if mode == "hold":
                    hold = action.get("hold_duration", 0.05)
                    self._do_mouse(button, True)
                    if hold <= 0:
                        # 一直按：记录但不松开
                        self._held_keys.append(("mouse", button))
                        return True
                    self._precise_sleep(hold)
                    self._do_mouse(button, False)
                else:
                    self._do_mouse(button, True)
                    self._do_mouse(button, False)

            elif action_type == "keyboard":
                key_name = action.get("button", "")
                vk = key_name_to_vk(key_name)
                if vk is None:
                    return False
                if mode == "hold":
                    hold = action.get("hold_duration", 0.05)
                    self._do_keyboard(vk, True)
                    if hold <= 0:
                        self._held_keys.append(("keyboard", vk))
                        return True
                    self._precise_sleep(hold)
                    self._do_keyboard(vk, False)
                else:
                    self._do_keyboard(vk, True)
                    self._do_keyboard(vk, False)

            elif action_type == "combo":
                keys = action.get("keys", [])
                vk_list = []
                for key_name in keys:
                    vk = key_name_to_vk(key_name)
                    if vk is not None:
                        vk_list.append(vk)
                        self._do_keyboard(vk, True)
                        self._precise_sleep(0.001)

                if mode == "hold":
                    hold = action.get("hold_duration", 0.05)
                    if hold <= 0:
                        # 一直按：记录所有键但不松开
                        for vk in vk_list:
                            self._held_keys.append(("keyboard", vk))
                        return True
                    self._precise_sleep(hold)
                else:
                    self._precise_sleep(0.01)

                for vk in reversed(vk_list):
                    self._do_keyboard(vk, False)
                    self._precise_sleep(0.001)

        except Exception as e:
            log_exception(logger, e, f"执行动作失败: type={action.get('type')}, button={action.get('button', '')}")

        return False

    def _release_held_keys(self):
        """松开所有因 hold=0 而保持按下的键/按钮"""
        for key_type, key in self._held_keys:
            try:
                if key_type == "mouse":
                    self._do_mouse(key, False)
                elif key_type == "keyboard":
                    self._do_keyboard(key, False)
            except Exception as e:
                log_exception(logger, e, f"释放保持按键失败: {key_type}={key}")
        self._held_keys.clear()

    def _do_mouse(self, button, down):
        """发送鼠标输入（前台用 SendInput，后台用 PostMessage 固定坐标）"""
        if self._target_mode == "background" and self._target_hwnd:
            _post_mouse(self._target_hwnd, button, down, self._click_x, self._click_y)
        else:
            _send_mouse(button, down)

    def _do_keyboard(self, vk_code, down):
        """发送键盘输入（前台用 SendInput，后台用 PostMessage）"""
        if self._target_mode == "background" and self._target_hwnd:
            _post_keyboard(self._target_hwnd, vk_code, down)
        else:
            _send_keyboard(vk_code, down)

    def _precise_sleep(self, seconds):
        """高精度睡眠：短间隔使用忙等待，长间隔使用 time.sleep"""
        if seconds <= 0:
            return
        if seconds < 0.003:
            # 忙等待，精度最高但占CPU
            end = time.perf_counter() + seconds
            while time.perf_counter() < end:
                pass
        else:
            end = time.perf_counter() + seconds
            while time.perf_counter() < end:
                remaining = end - time.perf_counter()
                if remaining > 0.002:
                    time.sleep(remaining * 0.5)
                # 最后2ms忙等
