"""
桌面主窗口
透明无边框、置顶、可拖拽，包含角色立绘控件和聊天气泡窗。
"""

import json
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QMouseEvent, QIcon
from PySide6.QtWidgets import (
    QWidget, QApplication, QSystemTrayIcon, QMenu, QStyle,
)

from config import settings
from config.characters import CHARACTERS, get_default_character
from ui.character_widget import CharacterWidget
from ui.chat_panel import ChatPanel
from utils.resource_helper import asset_path

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

        # ── 吸附隐藏 ──────────────────────────────────────
        self._docked: bool = False
        self._docked_edge: str = ""       # left / right / top / bottom
        self._normal_pos: QPoint | None = None  # 吸附前的位置（恢复用）
        self._anim: QPropertyAnimation | None = None
        self._EAR_SIZE = 50  # 露在外面的耳朵宽度/高度

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
        # 用当前角色立绘做图标
        cid = getattr(settings, "CURRENT_CHARACTER", None) or get_default_character()
        profile = CHARACTERS.get(cid)
        icon_path = str(asset_path(profile["sprite_path"])) if profile else ""
        icon = QIcon(icon_path) if icon_path and Path(icon_path).exists() else self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray.setIcon(icon)
        self.tray.setToolTip("夜乃樱 - AI 桌宠")

        menu = QMenu()
        menu.addAction("显示/隐藏", self._toggle_show)
        menu.addSeparator()
        menu.addAction("退出", QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

    # ── 窗口位置记忆 ───────────────────────────────────────

    def _save_position(self):
        """将窗口位置写入 JSON 文件（吸附状态存正常位置）。"""
        try:
            if self._docked and self._normal_pos:
                pos = self._normal_pos
            else:
                pos = self.pos()
            data = {"x": pos.x(), "y": pos.y()}
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
            if self._docked:
                self._undock()
                # 取消吸附后也记录拖拽起点，允许同一次点击继续拖
                self._drag_pos = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                event.accept()
                return
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
        if not self._docked:
            self._save_position()  # 正常位置才存
            self._check_edge_dock()

    # ── 吸附隐藏 ──────────────────────────────────────────

    DOCK_THRESHOLD = 15  # 拖到离边缘多近触发吸附

    def _check_edge_dock(self):
        """检测窗口是否靠近屏幕边缘，是则吸附隐藏。"""
        screen = QApplication.primaryScreen().availableGeometry()
        x, y = self.x(), self.y()
        w, h = self.width(), self.height()
        t = self.DOCK_THRESHOLD

        if x <= screen.x() + t:
            self._dock_to_edge("left", screen)
        elif x + w >= screen.right() - t:
            self._dock_to_edge("right", screen)
        elif y <= screen.y() + t:
            self._dock_to_edge("top", screen)
        elif y + h >= screen.bottom() - t:
            self._dock_to_edge("bottom", screen)

    def _dock_to_edge(self, edge: str, screen):
        """吸附到指定边缘，留 20px 耳朵可见。"""
        if self._docked:
            return
        self._docked = True
        self._docked_edge = edge
        self._normal_pos = (
            self._normal_pos or self.pos()
        )  # 存吸附前位置

        # 聊天面板跟着一起藏
        if self.chat_panel.isVisible():
            self.chat_panel.hide()

        ear = self._EAR_SIZE
        if edge == "left":
            target = QPoint(screen.x() - self.width() + ear, self.y())
        elif edge == "right":
            target = QPoint(screen.right() - ear, self.y())
        elif edge == "top":
            target = QPoint(self.x(), screen.y() - self.height() + ear)
        else:  # bottom
            target = QPoint(self.x(), screen.bottom() - ear)

        self._animate_to(target)
        print(f"[窗口] 吸附到 {edge}")

    def _undock(self):
        """点击耳朵弹出窗口。"""
        if not self._docked:
            return
        target = self._normal_pos or self.pos()
        self._docked = False
        self._docked_edge = ""
        self._normal_pos = None
        self._animate_to(target)
        self.activateWindow()
        print("[窗口] 取消吸附")

    def _animate_to(self, target: QPoint):
        """QPropertyAnimation 平滑移动到目标位置。"""
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setEndValue(target)
        self._anim.start()

    def _toggle_show(self):
        """托盘菜单：显示/隐藏主窗口。"""
        if self._docked:
            self._undock()
            self.show()
            self.activateWindow()
        elif self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()

    def moveEvent(self, event):
        """主窗口移动时记录正常位置，聊天面板跟随。"""
        super().moveEvent(event)
        is_animating = self._anim is not None and self._anim.state() == QPropertyAnimation.Running
        if not self._docked and not is_animating:
            self._normal_pos = self.pos()
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

    # ── 角色切换 ──────────────────────────────────────────

    def set_character(self, window_title: str, tray_tooltip: str, sprite_path: str = None):
        """切换窗口标题、托盘提示和托盘图标。"""
        self.setWindowTitle(window_title)
        if hasattr(self, "tray"):
            self.tray.setToolTip(tray_tooltip)
            if sprite_path and Path(sprite_path).exists():
                self.tray.setIcon(QIcon(sprite_path))

    # ── 公开接口 ──────────────────────────────────────────

    def get_chat_panel(self):
        """返回聊天面板实例（始终有效）。"""
        return self.chat_panel
