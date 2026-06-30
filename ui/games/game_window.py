"""
游戏主窗口

三级结构：
  Page 0: 游戏列表（只看游戏名，点击进入）
  Page 1: 游戏配置（选模式、颜色等，点击开始）
  Page 2: 游戏页面（开玩）

扩展方式：
  - 注册新游戏：在 GAMES 列表添加条目
  - 新游戏需继承 GameBase
"""

from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush, QFontMetrics,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QFrame, QSizePolicy, QScrollArea,
)

from .snake_game import SnakeGame, SNAKE_COLORS, MODE_CONFIG, MODE_ORDER
from .sfx import GameSFX


# ── 游戏注册表 ───────────────────────────────────────────────
GAMES = [
    {
        "id": "snake",
        "name": "贪吃蛇",
        "icon": "🐍",
        "description": "经典贪吃蛇 · 射击模式 · 极限挑战",
        "class": SnakeGame,
    },
]

# ── 通用样式 ─────────────────────────────────────────────────

_BG = """
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0f1a2e, stop:0.5 #16213e, stop:1 #1a1a2e);
"""
_BTN_HEADER = """
    QPushButton {
        background: rgba(255,255,255,0.08);
        color: #b0b0b0;
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 600;
    }
    QPushButton:hover { background: rgba(255,255,255,0.18); }
"""
_BTN_MODE = """
    QPushButton {
        background: rgba(255,255,255,0.08);
        color: #b0c0d0;
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 6px;
        font-size: 11px;
        padding: 4px 8px;
    }
    QPushButton:checked {
        background: rgba(79, 195, 247, 0.25);
        color: #4fc3f7;
        border: 1px solid #4fc3f7;
    }
    QPushButton:hover { background: rgba(255,255,255,0.12); }
"""
_BTN_PRIMARY = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #4fc3f7, stop:1 #2196f3);
        color: #ffffff;
        border: none;
        border-radius: 10px;
        font-size: 15px;
        font-weight: bold;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #5fcff7, stop:1 #33a0ff);
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #3aa8e0, stop:1 #1a80d0);
    }
"""
_BTN_RESTART = """
    QPushButton {
        background: #e94560;
        color: #fff;
        border: none;
        border-radius: 6px;
        font-size: 14px; font-weight: bold;
        padding: 4px 12px;
    }
    QPushButton:hover { background: #c72e45; }
"""


# ═══════════════════════════════════════════════════════════
#  Page 0 — 游戏列表
# ═══════════════════════════════════════════════════════════

class GameLauncherWidget(QWidget):
    """游戏列表：展示所有游戏，点击进入配置页。"""

    game_selected = Signal(str)  # game_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(_BG)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            "QScrollBar::handle:vertical {"
            "  background: rgba(255,255,255,0.15); border-radius: 3px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 32, 28, 32)
        layout.setSpacing(16)

        title = QLabel("🎮 小游戏")
        title.setStyleSheet("color: #fff; font-size: 28px; font-weight: bold; background: transparent;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("选择一个游戏")
        subtitle.setStyleSheet("color: #6a809a; font-size: 14px; background: transparent;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        for game in GAMES:
            card = self._build_game_card(game)
            layout.addWidget(card)

        layout.addStretch()
        scroll.setWidget(content)
        main.addWidget(scroll)

    def _build_game_card(self, game: dict) -> QFrame:
        card = QFrame()
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,0.06);
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.08);
            }
            QFrame:hover {
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(79,195,247,0.3);
            }
        """)
        card.setFixedHeight(90)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(20, 14, 20, 14)

        icon = QLabel(game["icon"])
        icon.setStyleSheet("font-size: 36px; background: transparent;")
        layout.addWidget(icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        name = QLabel(game["name"])
        name.setStyleSheet("color: #e8ecf0; font-size: 18px; font-weight: bold; background: transparent;")
        text_col.addWidget(name)

        desc = QLabel(game["description"])
        desc.setStyleSheet("color: #6a809a; font-size: 12px; background: transparent;")
        text_col.addWidget(desc)
        layout.addLayout(text_col, stretch=1)

        arrow = QLabel("→")
        arrow.setStyleSheet("color: #4a6a8a; font-size: 22px; background: transparent;")
        layout.addWidget(arrow)

        # 点击整张卡片用鼠标事件
        card.mousePressEvent = lambda e, g=game: self.game_selected.emit(g["id"])
        return card


# ═══════════════════════════════════════════════════════════
#  Page 1 — 游戏配置
# ═══════════════════════════════════════════════════════════

class GameConfigWidget(QWidget):
    """游戏配置：选模式、颜色等，点开始进入游戏。"""

    game_started = Signal(str, str, str)  # game_id, mode, color

    def __init__(self, game_id: str, parent=None):
        super().__init__(parent)
        self._game_id = game_id
        self._selected_color = "#4fc3f7"
        self._selected_mode = MODE_ORDER[0]
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(_BG)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 24)
        layout.setSpacing(14)

        # ── 顶栏（← 返回 + 游戏名） ──
        top = QHBoxLayout()
        back_btn = QPushButton("← 返回")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet(_BTN_HEADER)
        back_btn.clicked.connect(self._go_back)
        top.addWidget(back_btn)

        top.addStretch()
        game_def = next((g for g in GAMES if g["id"] == self._game_id), None)
        title = QLabel(f"{game_def['icon'] if game_def else ''} {game_def['name'] if game_def else ''}")
        title.setStyleSheet("color: #e8ecf0; font-size: 18px; font-weight: bold; background: transparent;")
        top.addWidget(title)
        top.addStretch()
        layout.addLayout(top)

        layout.addSpacing(8)

        if self._game_id == "snake":
            self._build_snake_config(layout)

        layout.addStretch()

    def _build_snake_config(self, layout: QVBoxLayout):
        """贪吃蛇专属配置：模式 + 颜色 + 开始按钮。"""
        # ── 模式 ──
        mode_label = QLabel("选择模式")
        mode_label.setStyleSheet("color: #9aacbe; font-size: 14px; font-weight: bold; background: transparent;")
        layout.addWidget(mode_label)

        for row_modes in [MODE_ORDER[:3], MODE_ORDER[3:]]:
            row = QHBoxLayout()
            row.setSpacing(8)
            for m in row_modes:
                btn = QPushButton(MODE_CONFIG[m]["display"])
                btn.setFixedHeight(36)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setCheckable(True)
                if m == self._selected_mode:
                    btn.setChecked(True)
                btn.setStyleSheet(_BTN_MODE)
                btn.clicked.connect(lambda checked, mm=m: self._select_mode(mm))
                row.addWidget(btn)
            layout.addLayout(row)

        layout.addSpacing(8)

        # ── 颜色 ──
        color_label = QLabel("蛇颜色")
        color_label.setStyleSheet(
            "color: #9aacbe; font-size: 14px; font-weight: bold; background: transparent;"
        )
        layout.addWidget(color_label)

        color_row = QHBoxLayout()
        color_row.setSpacing(6)
        for name, hex_c in SNAKE_COLORS:
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(name)
            btn.setProperty("color_hex", hex_c)
            is_sel = (hex_c == self._selected_color)
            border = "2px solid #fff" if is_sel else "2px solid transparent"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {hex_c};
                    border-radius: 16px;
                    border: {border};
                }}
                QPushButton:hover {{ border: 2px solid rgba(255,255,255,0.7); }}
            """)
            btn.clicked.connect(lambda checked, h=hex_c: self._pick_color(h))
            color_row.addWidget(btn)
        color_row.addStretch()
        layout.addLayout(color_row)

        layout.addSpacing(16)

        # ── 开始按钮 ──
        start_btn = QPushButton("🎮 开始游戏")
        start_btn.setFixedHeight(48)
        start_btn.setCursor(Qt.PointingHandCursor)
        start_btn.setStyleSheet(_BTN_PRIMARY)
        start_btn.clicked.connect(self._start_game)
        layout.addWidget(start_btn)

    def _select_mode(self, mode: str):
        self._selected_mode = mode
        # 刷新按钮选中状态
        for btn in self.findChildren(QPushButton):
            if btn.text() in (MODE_CONFIG[m]["display"] for m in MODE_ORDER):
                btn.setChecked(btn.text() == MODE_CONFIG[mode]["display"])

    def _pick_color(self, hex_color: str):
        self._selected_color = hex_color
        for btn in self.findChildren(QPushButton):
            h = btn.property("color_hex")
            if h:
                is_sel = (h == hex_color)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {h};
                        border-radius: 16px;
                        border: {'2px solid #fff' if is_sel else '2px solid transparent'};
                    }}
                    QPushButton:hover {{ border: 2px solid rgba(255,255,255,0.7); }}
                """)

    def _go_back(self):
        """返回游戏列表 — 通过 parent 窗口切换。"""
        p = self.parent()
        while p and not hasattr(p, "show_launcher"):
            p = p.parent()
        if p:
            p.show_launcher()

    def _start_game(self):
        self.game_started.emit(self._game_id, self._selected_mode, self._selected_color)


# ═══════════════════════════════════════════════════════════
#  Page 2 — 游戏页面
# ═══════════════════════════════════════════════════════════

class GamePlayWidget(QWidget):
    """游戏页面：顶部信息栏 + 居中画布。"""

    back_requested = Signal()

    def __init__(self, game_widget, parent=None):
        super().__init__(parent)
        self._game = game_widget
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(_BG)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 顶栏 ──
        header = QFrame()
        header.setFixedHeight(52)
        header.setStyleSheet(
            "background: rgba(0,0,0,0.3); border-bottom: 1px solid rgba(255,255,255,0.06);"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 6, 14, 6)
        hl.setSpacing(10)

        self._back_btn = QPushButton("← 返回")
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setStyleSheet(_BTN_HEADER)
        self._back_btn.clicked.connect(self.back_requested.emit)
        hl.addWidget(self._back_btn)

        self._mode_label = QLabel("经典")
        self._mode_label.setStyleSheet("""
            color: #4fc3f7; background: rgba(79,195,247,0.15);
            border-radius: 8px; padding: 3px 10px;
            font-size: 12px; font-weight: 600;
        """)
        hl.addWidget(self._mode_label)
        hl.addStretch()

        self._score_label = QLabel("得分 0")
        self._score_label.setStyleSheet("color: #4fc3f7; font-size: 16px; font-weight: bold;")
        hl.addWidget(self._score_label)

        self._kills_label = QLabel("")
        self._kills_label.setStyleSheet("color: #ff6b6b; font-size: 16px; font-weight: bold;")
        hl.addWidget(self._kills_label)

        self._high_label = QLabel("🏆 0")
        self._high_label.setStyleSheet("color: #f1c40f; font-size: 14px; font-weight: bold;")
        hl.addWidget(self._high_label)

        self._restart_btn = QPushButton("🔄")
        self._restart_btn.setFixedSize(32, 32)
        self._restart_btn.setCursor(Qt.PointingHandCursor)
        self._restart_btn.setToolTip("重新开始")
        self._restart_btn.setStyleSheet(_BTN_RESTART)
        self._restart_btn.clicked.connect(self._on_restart)
        hl.addWidget(self._restart_btn)

        layout.addWidget(header)

        # ── 画布 ──
        canvas_wrap = QWidget()
        canvas_wrap.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(canvas_wrap)
        cl.setAlignment(Qt.AlignCenter)
        cl.addWidget(self._game, alignment=Qt.AlignCenter)
        layout.addWidget(canvas_wrap, stretch=1)

        # ── 底栏 ──
        bottom = QFrame()
        bottom.setFixedHeight(36)
        bottom.setStyleSheet("background: rgba(0,0,0,0.25);")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(14, 0, 14, 0)

        self._over_label = QLabel("")
        self._over_label.setStyleSheet("color: #ff6b6b; font-size: 14px; font-weight: bold;")
        bl.addWidget(self._over_label, stretch=1)

        self._hint = QLabel("方向键 / WASD 控制移动")
        self._hint.setAlignment(Qt.AlignRight)
        self._hint.setStyleSheet("color: #5a6a7a; font-size: 12px;")
        bl.addWidget(self._hint)

        layout.addWidget(bottom)

        self._game.state_changed.connect(self._on_state)

    def _on_state(self):
        s = self._game.get_score()
        k = self._game.get_kills()
        h = self._game.get_high_score()
        shoot = self._game.is_shooting_mode()
        over = self._game.is_game_over()

        self._score_label.setText(f"得分 {s}")
        if shoot:
            self._kills_label.setText(f"击杀 {k}")
            self._kills_label.show()
            self._hint.setText("方向键 / WASD 移动  ·  空格射击")
        else:
            self._kills_label.hide()
            self._hint.setText("方向键 / WASD 控制移动")

        self._high_label.setText(f"🏆 {h}")
        self._mode_label.setText(self._game.get_mode_display())

        if over and s > 0:
            txt = f"💀 游戏结束  得分 {s}  {'击杀 ' + str(k) + '  ' if shoot else ''}最高 {h}"
            self._over_label.setText(txt)
        else:
            self._over_label.setText("")

    def _on_restart(self):
        self._over_label.setText("")
        self._game.restart()
        self._game.setFocus()


# ═══════════════════════════════════════════════════════════
#  主窗口
# ═══════════════════════════════════════════════════════════

class GameWindow(QWidget):
    """游戏主窗口：列表 → 配置 → 开玩。支持缩放和最大化。"""

    game_event = Signal(str, dict)  # 透传 → 角色语音联动

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_game = None
        self._current_game_id = None
        self._game_sfx = None

        self.setWindowTitle("🎮 小游戏")
        self.resize(540, 640)
        self.setMinimumSize(440, 520)
        self.setStyleSheet(f"GameWindow {{ {_BG} }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()

        # Page 0: 游戏列表
        self._launcher = GameLauncherWidget()
        self._launcher.game_selected.connect(self._on_game_selected)
        self._stack.addWidget(self._launcher)

        # Page 1: 占位（配置页，按需创建）
        self._config_page = QWidget()
        self._stack.addWidget(self._config_page)

        # Page 2: 占位（游戏页，按需创建）
        self._game_page = QWidget()
        self._stack.addWidget(self._game_page)

        layout.addWidget(self._stack)

    # ── 公开 ──

    def show_launcher(self):
        """回到列表。"""
        self._stack.setCurrentIndex(0)
        self.setWindowTitle("🎮 小游戏")
        if self._game_sfx:
            self._game_sfx.stop_bgm()

    def closeEvent(self, event):
        if self._current_game:
            self._current_game.stop()
        super().closeEvent(event)

    # ── 内部 ──

    def _on_game_selected(self, game_id: str):
        """点击游戏 → 显示配置页。"""
        self._current_game_id = game_id
        self._replace_config_page(game_id)
        self._stack.setCurrentIndex(1)
        game_def = next((g for g in GAMES if g["id"] == game_id), None)
        self.setWindowTitle(f"🎮 {game_def['name'] if game_def else ''} — 设置")
        # 选游戏时开始 BGM
        if game_id == "snake":
            if not self._game_sfx:
                self._game_sfx = GameSFX()
            self._game_sfx.play_bgm()

    def _replace_config_page(self, game_id: str):
        """替换配置页内容。"""
        old = self._config_page.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            old = QVBoxLayout(self._config_page)
            old.setContentsMargins(0, 0, 0, 0)

        cfg = GameConfigWidget(game_id)
        cfg.game_started.connect(self._on_game_started)
        old.addWidget(cfg)

    def _on_game_started(self, game_id: str, mode: str, color_hex: str):
        """配置完成 → 创建游戏实例并开始。"""
        game_def = next((g for g in GAMES if g["id"] == game_id), None)
        if not game_def:
            return

        if self._current_game:
            self._current_game.stop()
            try:
                self._current_game.game_event.disconnect()
            except TypeError:
                pass

        if game_id == "snake":
            if not self._game_sfx:
                self._game_sfx = GameSFX()
            game = SnakeGame(sfx=self._game_sfx)
            game.set_mode(mode)
            game.set_snake_color(color_hex)
        else:
            game = game_def["class"]()

        game.game_event.connect(self._forward_event)

        # 替换游戏页
        old = self._game_page.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            old = QVBoxLayout(self._game_page)
            old.setContentsMargins(0, 0, 0, 0)

        play = GamePlayWidget(game)
        play.back_requested.connect(self._on_back_from_game)
        old.addWidget(play)

        self._current_game = game
        self._stack.setCurrentIndex(2)

        game.start()
        game.setFocus()
        # 触发游戏开始语音
        self._forward_event("game_started", {"game_id": game_id, "mode": mode})

        mode_disp = game.get_mode_display() if hasattr(game, "get_mode_display") else ""
        self.setWindowTitle(f"🎮 {game_def['name']}  {mode_disp}")

    def _on_back_from_game(self):
        """游戏页 → 回到配置页。"""
        if self._current_game:
            self._current_game.stop()
        self._stack.setCurrentIndex(1)
        game_def = next((g for g in GAMES if g["id"] == self._current_game_id), None)
        self.setWindowTitle(f"🎮 {game_def['name'] if game_def else ''} — 设置")

    def _forward_event(self, event_type: str, data: dict):
        self.game_event.emit(event_type, data)
