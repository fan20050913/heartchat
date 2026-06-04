"""
桌面主窗口
透明无边框、置顶、可拖拽，包含角色立绘控件和聊天气泡窗。
"""

import json
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QWidget, QApplication, QSystemTrayIcon, QMenu, QStyle,
)

from ui.character_widget import CharacterWidget
from ui.chat_panel import ChatPanel

_WINDOW_STATE = Path("data/window_state.json")


class PetWindow(QWidget):
    """桌面精灵主窗口：200×300，透明，置顶，可拖动。"""

    def __init__(self):
        super().__init__()
        self._init_window()
        self._load_position()
        self._init_chat_panel()
        self._init_character()
        self._init_tray()

        self._drag_pos = None

        # 退出时保存窗口位置
        QApplication.instance().aboutToQuit.connect(self._save_position)

    # ── 初始化 ────────────────────────────────────────────

    def _init_window(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(200, 300)

    def _init_chat_panel(self):
        """预先创建聊天面板（隐藏），方便外部连接信号。"""
        self.chat_panel = ChatPanel()
        self.chat_panel.panel_closed.connect(self._on_chat_closed)

    def _init_character(self):
        self.character = CharacterWidget(self)
        self.character.clicked.connect(self._toggle_chat)

    def _init_tray(self):
        """系统托盘（右键退出）。"""
        self.tray = QSystemTrayIcon(self)
        # 使用内置图标（无外部依赖）
        icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray.setIcon(icon)
        self.tray.setToolTip("朱比华 - AI 桌宠")

        menu = QMenu()
        menu.addAction("显示/隐藏", self._toggle_show)
        menu.addSeparator()
        menu.addAction("退出", QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

    # ── 窗口位置记忆 ───────────────────────────────────────

    def _save_position(self):
        """将当前窗口位置写入 JSON 文件。"""
        try:
            data = {"x": self.x(), "y": self.y()}
            _WINDOW_STATE.parent.mkdir(parents=True, exist_ok=True)
            _WINDOW_STATE.write_text(json.dumps(data), encoding="utf-8")
        except OSError as e:
            print(f"[窗口] 保存位置失败: {e}")

    def _load_position(self):
        """从 JSON 文件恢复窗口位置。"""
        try:
            if _WINDOW_STATE.exists():
                data = json.loads(_WINDOW_STATE.read_text(encoding="utf-8"))
                self.move(data["x"], data["y"])
                print(f"[窗口] 恢复位置: ({data['x']}, {data['y']})")
        except (OSError, json.JSONDecodeError, KeyError) as e:
            print(f"[窗口] 读取位置失败（使用默认）: {e}")

    # ── 拖拽 ──────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        self._save_position()  # 拖拽完就保存位置

    def moveEvent(self, event):
        """主窗口移动时，聊天面板跟随。"""
        super().moveEvent(event)
        if self.chat_panel.isVisible():
            self._position_chat_panel()

    # ── 聊天面板管理 ──────────────────────────────────────

    def _toggle_chat(self):
        if self.chat_panel.isVisible():
            self.chat_panel.hide()
        else:
            self._position_chat_panel()
            self.chat_panel.show()
            self.chat_panel.activateWindow()
            self.chat_panel.input_edit.setFocus()

    def _position_chat_panel(self):
        """将聊天面板放在主窗口左侧。"""
        x = self.x() - self.chat_panel.width() - 5
        y = self.y() - 30
        self.chat_panel.move(x, y)

    def _on_chat_closed(self):
        """聊天面板关闭后的清理。"""
        pass

    def _toggle_show(self):
        """托盘菜单：显示/隐藏主窗口。"""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()

    # ── 角色切换 ──────────────────────────────────────────

    def set_character(self, window_title: str, tray_tooltip: str):
        """切换窗口标题和托盘提示。"""
        self.setWindowTitle(window_title)
        if hasattr(self, "tray"):
            self.tray.setToolTip(tray_tooltip)

    # ── 公开接口 ──────────────────────────────────────────

    def get_chat_panel(self):
        """返回聊天面板实例（始终有效）。"""
        return self.chat_panel
