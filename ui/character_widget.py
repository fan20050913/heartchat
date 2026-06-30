"""
角色立绘控件
加载并显示 assets/sprites/{name}.webp 精灵图，无图时由 QPainter 绘制占位角色。
支持 idle / talking / listening 状态反馈。
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QRect, QPoint, QTimer
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QBrush, QPen, QFont,
    QRadialGradient, QFontMetrics, QPainterPath,
)
from PySide6.QtWidgets import QWidget
from PySide6.QtWidgets import QWidget

from utils.resource_helper import asset_path

W, H = 200, 300  # 控件固定尺寸
FPS = 30
FRAME_MS = 1000 // FPS  # ~33ms


class CharacterWidget(QWidget):
    """固定 200×300 的角色立绘控件，支持帧序列动画 + 静态 PNG 回退。"""

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

        # ── 帧动画支持 ────────────────────────────────────
        self._animations: dict[str, list[QPixmap]] = {}  # anim_name -> frames
        self._current_anim = "hair"                       # 当前播放的动画组
        self._frame_idx = 0
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._next_frame)

        # ── 过渡动画（cross-fade 消除动作瞬移） ─────────
        self._crossfade = False       # 是否在过渡中
        self._crossfade_old_pix: QPixmap | None = None  # 旧动画当前帧快照
        self._crossfade_steps = 4     # 4帧 ≈ 133ms 过渡
        self._crossfade_step = 0

        # ── 气泡 ─────────────────────────────────────────
        self._bubble_text: str = ""
        self._bubble_visible: bool = False
        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self.hide_bubble)

    # ── 公开接口 ───────────────────────────────────────────

    def set_state(self, state: str):
        """更新角色状态：idle / talking / listening / thinking"""
        if state not in ("idle", "talking", "listening", "thinking"):
            return
        self.state = state
        # 状态 → 动画组映射
        anim_map = {"idle": "hair", "talking": "talking", "listening": "hair", "thinking": "think"}
        new_anim = anim_map.get(state, "hair")
        if new_anim in self._animations and new_anim != self._current_anim:
            # 快照当前帧，开始 crossfade
            frames = self._animations.get(self._current_anim)
            if frames:
                self._crossfade_old_pix = frames[self._frame_idx % len(frames)]
            else:
                self._crossfade_old_pix = None
            self._current_anim = new_anim
            self._frame_idx = 0
            self._crossfade = True
            self._crossfade_step = 0
        elif new_anim in self._animations:
            self._current_anim = new_anim
            self._frame_idx = 0
        self.update()

    # ── 角色切换 ───────────────────────────────────────────

    def set_character(self, name: str, sprite_path: str | Path | None, emoji: str = "✨"):
        """切换角色立绘、动画帧序列和显示名称。"""
        self._display_name = name
        self._emoji = emoji
        self._sprite_path = Path(sprite_path) if sprite_path else None
        self._load_image()
        self._load_animations()
        self.set_state("idle")
        self._start_animation()
        self.update()

    # ── 气泡 ──────────────────────────────────────────────

    def show_bubble(self, text: str, duration_ms: int = 5000):
        """在立绘上方显示中文气泡，停留后自动消失。"""
        if not text:
            return
        self._bubble_text = text
        self._bubble_visible = True
        self._bubble_timer.start(duration_ms)
        self.update()

    def hide_bubble(self):
        """隐藏气泡。"""
        self._bubble_visible = False
        self._bubble_text = ""
        self._bubble_timer.stop()
        self.update()

    # ── 图片加载 ───────────────────────────────────────────

    def _load_image(self):
        """加载静态精灵图（作为帧序列不存在的回退）。"""
        if self._sprite_path and self._sprite_path.exists():
            pix = QPixmap(str(self._sprite_path))
            if not pix.isNull():
                self._pixmap = pix.scaled(
                    W, H, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                return
        self._pixmap = None
        print(f"[Character] 精灵图不存在或无效: {self._sprite_path}")

    # ── 帧序列加载 ────────────────────────────────────────

    def _load_animations(self):
        """从精灵图同目录加载 {talking,hair,blink}/ 帧序列。"""
        self._animations.clear()
        self._current_anim = "hair"
        self._frame_idx = 0
        self._anim_timer.stop()

        if not self._sprite_path or not self._sprite_path.exists():
            return

        base_dir = self._sprite_path.parent
        for anim_name in ("talking", "hair", "blink", "think"):
            frame_dir = base_dir / anim_name
            if not frame_dir.is_dir():
                continue
            # 按 frame_0000.webp, frame_0001.webp, ... 顺序排序（支持 .png 回退）
            frame_files = sorted(frame_dir.glob("frame_*.webp")) or sorted(frame_dir.glob("frame_*.png"))
            if not frame_files:
                continue
            pixmaps = []
            for f in frame_files:
                pix = QPixmap(str(f))
                if not pix.isNull():
                    scaled = pix.scaled(
                        W, H, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    pixmaps.append(scaled)
            if pixmaps:
                self._animations[anim_name] = pixmaps
                print(f"[Character] 加载 {anim_name}: {len(pixmaps)} 帧")

    def _start_animation(self):
        """有帧序列时启动动画计时器。"""
        if self._animations:
            self._anim_timer.start(FRAME_MS)

    def _next_frame(self):
        """QTimer 回调：前进一帧。think 第一次完整播完，之后从中间帧循环。"""
        # 过渡计数推进
        if self._crossfade:
            self._crossfade_step += 1
            if self._crossfade_step >= self._crossfade_steps:
                self._crossfade = False
                self._crossfade_old_pix = None

        frames = self._animations.get(self._current_anim)
        if not frames:
            return
        if self._current_anim == "think":
            total = len(frames)
            if self._frame_idx < total - 1:
                self._frame_idx += 1
            else:
                # 播完一遍后从中间帧循环（跳过抬手/偏头起始动作）
                self._frame_idx = min(total // 2, total - 1)
        else:
            self._frame_idx = (self._frame_idx + 1) % len(frames)
        self.update()

    # ── 鼠标事件 ──────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    # ── 绘图 ──────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 优先显示动画帧
        frames = self._animations.get(self._current_anim)
        if frames:
            self._draw_frame(painter, frames[self._frame_idx])
        elif self._pixmap is not None:
            self._draw_sprite(painter)
        else:
            self._draw_placeholder(painter)

        # 气泡（画在最上层）
        if self._bubble_visible and self._bubble_text:
            self._draw_bubble(painter)

    def _draw_bubble(self, painter: QPainter):
        """在立绘顶部绘制中文气泡。"""
        text = self._bubble_text
        if not text:
            return

        font = QFont("Microsoft YaHei", 11)
        painter.setFont(font)
        fm = QFontMetrics(font)

        # 气泡最大宽度 = 控件宽 - 16px 边距
        max_bubble_w = self.width() - 16
        bubble_w = max_bubble_w

        # 用 QFontMetrics 精确计算 word wrap 后的高度
        text_rect = fm.boundingRect(
            QRect(0, 0, bubble_w - 16, 0),
            Qt.AlignCenter | Qt.TextWordWrap, text,
        )
        bubble_h = text_rect.height() + 20

        # 位置：顶部居中
        bx = (self.width() - bubble_w) // 2
        by = 4

        # 圆角背景
        path = QPainterPath()
        path.addRoundedRect(bx, by, bubble_w, bubble_h, 8, 8)
        painter.setPen(QPen(QColor(180, 190, 200), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
        painter.drawPath(path)

        # 文字居中 + 自动换行
        text_rect = QRect(bx + 8, by + 6, bubble_w - 16, bubble_h - 12)
        painter.setPen(QColor(44, 62, 80))
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, text)

    def _draw_frame(self, painter: QPainter, pixmap: QPixmap):
        """居中绘制一帧动画，支持 crossfade 过渡。"""
        if self._crossfade and self._crossfade_old_pix is not None:
            # 旧帧逐渐淡出，新帧逐渐淡入
            progress = self._crossfade_step / self._crossfade_steps  # 0→1
            # 绘制旧帧（透明度递减）
            painter.setOpacity(1.0 - progress)
            xo = (W - self._crossfade_old_pix.width()) // 2
            yo = (H - self._crossfade_old_pix.height()) // 2
            painter.drawPixmap(xo, yo, self._crossfade_old_pix)
            # 绘制新帧（透明度递增）
            painter.setOpacity(progress)
            xn = (W - pixmap.width()) // 2
            yn = (H - pixmap.height()) // 2
            painter.drawPixmap(xn, yn, pixmap)
            painter.setOpacity(1.0)
        else:
            x = (W - pixmap.width()) // 2
            y = (H - pixmap.height()) // 2
            painter.drawPixmap(x, y, pixmap)

    def _draw_sprite(self, painter: QPainter):
        """绘制静态精灵图（回退）。"""
        px = self._pixmap
        assert px is not None
        x = (W - px.width()) // 2
        y = (H - px.height()) // 2
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
