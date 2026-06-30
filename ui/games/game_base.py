"""
小游戏基类

所有小游戏继承此基类，确保统一的游戏生命周期和事件接口。
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


class GameBase(QWidget):
    """游戏基类，提供统一的 start/stop/pause 接口和事件信号。

    子类需要实现的接口：
    - start() — 开始/重新开始游戏
    - stop()  — 停止游戏
    - paintEvent() — 渲染画面

    语音联动（未来接入 — 接口已预留）：
    game_event 信号携带 (event_type, data) 供 main.py 连接。
    """

    # ── 游戏事件信号（供角色语音联动） ─────────────────────
    # event_type: str — "game_over" | "score_milestone" | "combo" | "food_eaten" | "enemy_killed"
    # data: dict — 事件相关数据（分数、击杀数、模式等）
    game_event = Signal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._paused = False

    # ── 生命周期 ───────────────────────────────────────────

    def start(self):
        """开始或重新开始游戏。"""
        self._running = True
        self._paused = False

    def stop(self):
        """停止游戏（关闭窗口时调用）。"""
        self._running = False
        self._paused = False

    def pause(self):
        """暂停游戏（可选实现）。"""
        self._paused = True

    def resume(self):
        """恢复游戏（可选实现）。"""
        self._paused = False

    # ── 状态查询 ──────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ── 子类可覆盖的辅助方法 ──────────────────────────────

    def emit_event(self, event_type: str, **data):
        """发射游戏事件（供子类调用，未来用于语音联动）。"""
        self.game_event.emit(event_type, data)
