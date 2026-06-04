"""
角色立绘控件
加载并显示 assets/sprites/sipika.png 精灵图，无图时由 QPainter 绘制占位角色。
支持 idle / talking / listening 状态反馈。
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QBrush, QPen, QFont,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from utils.resource_helper import asset_path

W, H = 200, 300  # 控件固定尺寸


class CharacterWidget(QWidget):
    """固定 200×300 的角色立绘控件，显示 PNG 精灵图或 QPainter 占位。"""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(W, H)
        self.setCursor(Qt.PointingHandCursor)
        self.state = "idle"  # idle | talking | listening

        self._display_name = "朱比华"
        self._emoji = "✨"
        self._sprite_path: Path | None = None
        self._pixmap: QPixmap | None = None

    # ── 公开接口 ───────────────────────────────────────────

    def set_state(self, state: str):
        """更新角色状态：idle / talking / listening"""
        if state in ("idle", "talking", "listening"):
            self.state = state
            self.update()

    # ── 角色切换 ───────────────────────────────────────────

    def set_character(self, name: str, sprite_path: str | Path | None, emoji: str = "✨"):
        """切换角色立绘和显示名称。"""
        self._display_name = name
        self._emoji = emoji
        self._sprite_path = Path(sprite_path) if sprite_path else None
        self._load_image()
        self.update()

    # ── 图片加载 ───────────────────────────────────────────

    def _load_image(self):
        """加载精灵图，缩放到适配控件（保持比例）。"""
        if self._sprite_path and self._sprite_path.exists():
            pix = QPixmap(str(self._sprite_path))
            if not pix.isNull():
                self._pixmap = pix.scaled(
                    W, H, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                return
        self._pixmap = None
        print(f"[Character] 精灵图不存在或无效: {self._sprite_path}")

    # ── 鼠标事件 ──────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    # ── 绘图 ──────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._pixmap is not None:
            self._draw_sprite(painter)
        else:
            self._draw_placeholder(painter)

    def _draw_sprite(self, painter: QPainter):
        """绘制精灵图，居中显示（完整可见）。"""
        px = self._pixmap
        assert px is not None
        x = (W - px.width()) // 2
        y = (H - px.height()) // 2  # 垂直居中，头不会被裁
        painter.drawPixmap(x, y, px)

    def _draw_placeholder(self, painter: QPainter):
        """用 QPainter 绘制一个占位角色（无图片时回退）。"""
        # 圆形头像
        cx, cy, radius = W // 2, 80, 50
        gradient = QRadialGradient(cx, cy, radius, cx - 10, cy - 10)
        gradient.setColorAt(0, QColor("#FFE0BD"))
        gradient.setColorAt(1, QColor("#F5C6A0"))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPoint(cx, cy), radius, radius)

        # 眼睛
        eye_y = cy - 5
        painter.setBrush(QColor("#333333"))
        painter.drawEllipse(QPoint(cx - 15, eye_y), 5, 6)
        painter.drawEllipse(QPoint(cx + 15, eye_y), 5, 6)

        # 嘴巴（根据状态）
        painter.setPen(QPen(QColor("#CC6644"), 2))
        if self.state == "talking":
            painter.drawEllipse(QPoint(cx, eye_y + 25), 8, 6)
        elif self.state == "listening":
            painter.drawChord(QRect(cx - 10, eye_y + 18, 20, 14), 0, 180 * 16)
        else:
            painter.drawArc(QRect(cx - 10, eye_y + 18, 20, 14), 0, 180 * 16)

        # 身体（简易梯形）
        body_top = cy + radius + 5
        painter.setBrush(QColor("#F5C6A0"))
        painter.setPen(Qt.NoPen)
        body = QRect(W // 2 - 40, body_top, 80, H - body_top - 10)
        painter.drawRoundedRect(body, 10, 10)

        # 文字提示（动态角色名）
        painter.setPen(QColor("#999999"))
        font = QFont("Microsoft YaHei", 9)
        painter.setFont(font)
        painter.drawText(QRect(0, H - 30, W, 20), Qt.AlignCenter, f"{self._emoji} {self._display_name} {self._emoji}")
