"""
Window Watcher — Windows 前台窗口检测

原理：Win32 API (ctypes) 获取前台窗口标题 + 进程名 + exe 路径，
无需安装额外依赖，无隐私负担（不截图、不录屏）。

QTimer 2s 轮询，缓存上次结果，变化才 emit signal。
"""

import ctypes
import ctypes.wintypes

from PySide6.QtCore import QObject, Signal, QTimer


class WindowWatcher(QObject):
    """Windows 前台窗口轮询器，变化时发射 window_changed 信号。"""

    window_changed = Signal(str, str, str, int)  # title, process_name, exe_path, pid

    # ── Win32 常量 ─────────────────────────────────────────────
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    def __init__(self, poll_interval: int = 2000, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._poll_interval = poll_interval
        self._last_key: tuple | None = None

        # 本程序自己的进程名（用于过滤掉自身窗口变化）
        self._self_exe: str = ""
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.wintypes.DWORD(260)
            kernel32 = ctypes.windll.kernel32
            if kernel32.QueryFullProcessImageNameW(
                kernel32.GetCurrentProcess(), 0, buf, ctypes.byref(size)
            ):
                self._self_exe = buf.value.lower()
        except Exception:
            pass

    # ── 生命周期 ───────────────────────────────────────────────

    def start(self):
        """开始轮询。"""
        self._timer.start(self._poll_interval)

    def stop(self):
        """停止轮询。"""
        self._timer.stop()

    def set_poll_interval(self, ms: int):
        """动态调整轮询间隔。"""
        self._poll_interval = ms
        if self._timer.isActive():
            self._timer.setInterval(ms)

    # ── 核心检测 ───────────────────────────────────────────────

    @staticmethod
    def get_foreground_window_info() -> tuple[str, str, str, int] | None:
        """获取当前前台窗口信息。

        Returns:
            (title, process_name, exe_path, pid) 或 None（获取失败时）
        """
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        # 窗口标题
        length = user32.GetWindowTextLengthW(hwnd) + 1
        title_buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, title_buf, length)
        title = title_buf.value or ""

        # 进程 PID
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pid_val = pid.value

        # 打开进程获取 exe 路径
        handle = kernel32.OpenProcess(
            WindowWatcher.PROCESS_QUERY_LIMITED_INFORMATION,
            False, pid,
        )
        if not handle:
            return (title, "", "", pid_val)

        try:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.wintypes.DWORD(260)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                exe_path = buf.value
                process_name = exe_path.rsplit("\\", 1)[-1] if "\\" in exe_path else exe_path
                return (title, process_name.lower(), exe_path, pid_val)
            return (title, "", "", pid_val)
        finally:
            kernel32.CloseHandle(handle)

    # ── 内部轮询 ───────────────────────────────────────────────

    def _is_self_window(self, exe_path: str) -> bool:
        """判断是否为桌宠自己的窗口（忽略，不触发变化）。"""
        if not exe_path or not self._self_exe:
            return False
        return exe_path.lower() == self._self_exe

    def _poll(self):
        """定时轮询：检测前台窗口变化并发射信号。"""
        try:
            info = self.get_foreground_window_info()
        except Exception:
            return  # 静默失败，下次轮询再试

        if info is None:
            return
        title, process, exe_path, pid = info

        # 跳过自己的窗口
        if self._is_self_window(exe_path):
            return

        key = (process, title)
        if key != self._last_key:
            self._last_key = key
            self.window_changed.emit(title, process, exe_path, pid)
