"""
贪吃蛇 — 移植自 snake.html

全部 5 种模式：
  classic      — 经典贪吃蛇
  baby-classic — 简单休闲（慢速）
  shooting     — 射击模式（发射子弹击杀敌人）
  baby-shooting— 简单射击（慢速）
  extreme      — 极限模式（射击 + 每次开火蛇身增长）

未来联动：emit_event() 调用已嵌入关键事件点，供角色语音使用。
"""

import math
import random
from PySide6.QtCore import Qt, QTimer, QSettings, Signal, QRect
from PySide6.QtGui import (
    QPainter, QColor, QPen, QFont, QBrush, QFontMetrics,
    QKeyEvent,
)
from PySide6.QtWidgets import QWidget

from .game_base import GameBase

# ── 常量 ──────────────────────────────────────────────────────

GRID = 20
CANVAS_SIZE = 400
CELL = CANVAS_SIZE // GRID  # 20

# 蛇颜色选项
SNAKE_COLORS = [
    ("青色", "#4fc3f7"),
    ("绿色", "#2ecc71"),
    ("橙色", "#f39c12"),
    ("紫色", "#9b59b6"),
    ("粉色", "#e91e63"),
    ("红色", "#e74c3c"),
    ("黄色", "#f1c40f"),
    ("白色", "#ecf0f1"),
]

# 食物颜色池（不含蛇色和敌人色）
FOOD_COLOR_PALETTE = [
    "#e74c3c", "#e67e22", "#f1c40f", "#2ecc71",
    "#1abc9c", "#3498db", "#9b59b6", "#e91e63",
    "#00bcd4", "#ff5722", "#8bc34a", "#ffeb3b",
    "#ff4081", "#7c4dff", "#64ffda", "#ff6e40",
]

ENEMY_COLOR = QColor("#ff4757")

# 模式配置
MODE_CONFIG = {
    "classic":      {"display": "经典",     "interval": 144, "shooting": False},
    "baby-classic": {"display": "宝宝经典", "interval": 267, "shooting": False},
    "shooting":     {"display": "射击",     "interval": 144, "shooting": True},
    "baby-shooting":{"display": "宝宝射击", "interval": 267, "shooting": True},
    "extreme":      {"display": "极限",     "interval": 144, "shooting": True},
}

MODE_ORDER = ["classic", "baby-classic", "shooting", "baby-shooting", "extreme"]


class SnakeGame(GameBase):
    """贪吃蛇游戏控件（400×400 QPainter 渲染，30fps 逻辑）。"""

    # ── 外部通知信号 ──────────────────────────────────────
    state_changed = Signal()  # 分数/击杀数/运行状态变化 → 窗口标题更新

    def __init__(self, sfx=None, parent=None):
        super().__init__(parent)
        self.sfx = sfx  # GameSFX 实例，可选
        self.setFixedSize(CANVAS_SIZE, CANVAS_SIZE)
        self.setFocusPolicy(Qt.StrongFocus)

        self._settings = QSettings("HeartChat", "SnakeGame")
        self._mode = "classic"
        self._snake_color_hex = "#4fc3f7"
        self._snake_color = QColor("#4fc3f7")

        # 游戏计时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        # 游戏状态
        self._reset_game()

    # ── 公开接口 ──────────────────────────────────────────

    def set_mode(self, mode: str):
        """切换模式（自动重置游戏）。"""
        assert mode in MODE_CONFIG
        self._mode = mode
        self._reset_game()

    def get_mode(self) -> str:
        return self._mode

    def set_snake_color(self, color_hex: str):
        """设置蛇的颜色。"""
        self._snake_color_hex = color_hex
        self._snake_color = QColor(color_hex)

    def get_score(self) -> int:
        return self._score

    def get_kills(self) -> int:
        return self._kills

    def get_high_score(self) -> int:
        return self._load_high_score()

    def get_mode_display(self) -> str:
        return MODE_CONFIG[self._mode]["display"]

    def is_shooting_mode(self) -> bool:
        return MODE_CONFIG[self._mode]["shooting"]

    def is_game_over(self) -> bool:
        return self._game_over

    # ── 生命周期 ──────────────────────────────────────────

    def start(self):
        super().start()
        self._reset_game()
        interval = MODE_CONFIG[self._mode]["interval"]
        self._timer.start(interval)
        if self.sfx:
            self.sfx.play_bgm()

    def stop(self):
        super().stop()
        self._timer.stop()
        if self.sfx:
            self.sfx.stop_bgm()

    def restart(self):
        """保留模式和颜色，重新开始。"""
        self.stop()
        self._reset_game()
        self.start()

    # ── 内部游戏逻辑 ──────────────────────────────────────

    def _reset_game(self):
        """初始化/重置所有游戏状态。"""
        self._snake = [
            {"x": 10, "y": 10},
            {"x": 9,  "y": 10},
            {"x": 8,  "y": 10},
        ]
        self._direction = {"x": 1, "y": 0}
        self._next_direction = {"x": 1, "y": 0}
        self._score = 0
        self._kills = 0
        self._bullets: list[dict] = []
        self._enemies: list[dict] = []
        self._shoot_cooldown = 0
        self._enemy_spawn_timer = 0
        self._food = None
        self._food_color = QColor("#e74c3c")
        self._game_over = False
        self._spawn_food()
        self.state_changed.emit()
        self.update()

    def _is_shooting(self) -> bool:
        return MODE_CONFIG[self._mode]["shooting"]

    def _spawn_food(self):
        """在未被占据的位置生成食物。"""
        occupied = {f"{s['x']},{s['y']}" for s in self._snake}
        for e in self._enemies:
            occupied.add(f"{e['x']},{e['y']}")

        if len(occupied) >= GRID * GRID:
            # 所有格子都被占 → 玩家赢
            self._game_over = True
            self._timer.stop()
            self._save_high_score()
            self.state_changed.emit()
            self.emit_event("game_over", score=self._score, kills=self._kills,
                            mode=self._mode, won=True)
            self.update()
            return

        while True:
            pos = {"x": random.randint(0, GRID - 1), "y": random.randint(0, GRID - 1)}
            if f"{pos['x']},{pos['y']}" not in occupied:
                self._food = pos
                break

        # 随机食物颜色（不跟蛇色和敌人色相同）
        forbidden = {self._snake_color_hex.lower(), "#ff4757"}
        available = [c for c in FOOD_COLOR_PALETTE if c.lower() not in forbidden]
        self._food_color = QColor(random.choice(available) if available else "#e74c3c")

    def _tick(self):
        """QTimer 回调：每帧更新游戏逻辑 + 重绘。"""
        if not self._running or self._game_over:
            return
        self._update()
        self.state_changed.emit()
        self.update()

    def _update(self):
        """核心游戏逻辑更新（移植自 snake.html 的 update()）。"""
        # 应用方向
        self._direction = {"x": self._next_direction["x"], "y": self._next_direction["y"]}

        head = {
            "x": self._snake[0]["x"] + self._direction["x"],
            "y": self._snake[0]["y"] + self._direction["y"],
        }

        # 撞墙
        if head["x"] < 0 or head["x"] >= GRID or head["y"] < 0 or head["y"] >= GRID:
            self._handle_game_over()
            return

        # 撞自身（排除尾巴段 — 它会在没吃食物时移走）
        for i in range(len(self._snake) - 1):
            seg = self._snake[i]
            if head["x"] == seg["x"] and head["y"] == seg["y"]:
                self._handle_game_over()
                return

        # 撞敌人（射击模式）
        if self._is_shooting():
            for e in self._enemies:
                if head["x"] == e["x"] and head["y"] == e["y"]:
                    self._handle_game_over()
                    return

        self._snake.insert(0, head)

        # 吃食物
        if head["x"] == self._food["x"] and head["y"] == self._food["y"]:
            self._score += 1
            if self._is_shooting():
                self._score += 1  # 射击模式额外加分
            if self.sfx:
                self.sfx.play_eat()
            self.emit_event("food_eaten", score=self._score, total=len(self._snake) - 3)
            self._spawn_food()
            if self._game_over:
                return  # 赢了（所有格子占满）
        else:
            self._snake.pop()

        # ── 射击模式更新 ──
        if self._is_shooting():
            # 冷却
            if self._shoot_cooldown > 0:
                self._shoot_cooldown -= 1

            # 子弹移动（3 倍速，逐格检测）
            for bi in range(len(self._bullets) - 1, -1, -1):
                b = self._bullets[bi]
                removed = False
                for _step in range(3):
                    b["x"] += b["dx"]
                    b["y"] += b["dy"]
                    # 撞墙
                    if b["x"] < 0 or b["x"] >= GRID or b["y"] < 0 or b["y"] >= GRID:
                        self._bullets.pop(bi)
                        removed = True
                        break
                    # 撞敌人
                    for ej in range(len(self._enemies) - 1, -1, -1):
                        if b["x"] == self._enemies[ej]["x"] and b["y"] == self._enemies[ej]["y"]:
                            self._enemies.pop(ej)
                            self._kills += 1
                            self._score += 3
                            if self.sfx:
                                self.sfx.play_hit()
                            self.emit_event("enemy_killed", total_kills=self._kills,
                                            score=self._score)
                            self._bullets.pop(bi)
                            removed = True
                            break
                    if removed:
                        break

            # 生成敌人
            self._enemy_spawn_timer += 1
            spawn_interval = max(15, 40 - self._kills)
            if self._enemy_spawn_timer >= spawn_interval and len(self._enemies) < 8:
                self._enemy_spawn_timer = 0
                self._try_spawn_enemy()

            # 敌人移动（每 2 tick 一次）
            # 直接用 _tick 计数，通过 _enemy_spawn_timer 的奇偶控制
            if self._enemy_spawn_timer % 2 == 0:
                random.shuffle(self._enemies)  # 随机顺序移动
                for e in self._enemies:
                    dirs = [
                        {"x": 0, "y": -1},
                        {"x": 0, "y": 1},
                        {"x": -1, "y": 0},
                        {"x": 1, "y": 0},
                    ]
                    random.shuffle(dirs)
                    for d in dirs:
                        nx, ny = e["x"] + d["x"], e["y"] + d["y"]
                        if nx < 0 or nx >= GRID or ny < 0 or ny >= GRID:
                            continue
                        occ = {f"{s['x']},{s['y']}" for s in self._snake}
                        for o in self._enemies:
                            if o is not e:
                                occ.add(f"{o['x']},{o['y']}")
                        if self._food:
                            occ.add(f"{self._food['x']},{self._food['y']}")
                        if f"{nx},{ny}" not in occ:
                            e["x"], e["y"] = nx, ny
                            break

    def _try_spawn_enemy(self):
        """在未被占据的位置生成一个敌人。"""
        occ = {f"{s['x']},{s['y']}" for s in self._snake}
        for e in self._enemies:
            occ.add(f"{e['x']},{e['y']}")
        if self._food:
            occ.add(f"{self._food['x']},{self._food['y']}")
        if len(occ) >= GRID * GRID:
            return
        while True:
            pos = {"x": random.randint(0, GRID - 1), "y": random.randint(0, GRID - 1)}
            if f"{pos['x']},{pos['y']}" not in occ:
                self._enemies.append(pos)
                break

    def shoot(self):
        """发射子弹（射击模式）。"""
        if not self._running or self._game_over or not self._is_shooting():
            return
        if self._shoot_cooldown > 0:
            return
        head = self._snake[0]
        self._bullets.append({
            "x": head["x"] + self._direction["x"],
            "y": head["y"] + self._direction["y"],
            "dx": self._direction["x"],
            "dy": self._direction["y"],
        })
        self._shoot_cooldown = 8
        if self.sfx:
            self.sfx.play_shoot()

        # 极限模式：每次开火蛇身增长
        if self._mode == "extreme":
            last = self._snake[-1]
            self._snake.append({"x": last["x"], "y": last["y"]})

    def _handle_game_over(self):
        """处理游戏结束。"""
        self._game_over = True
        self._timer.stop()
        if self.sfx:
            self.sfx.play_fail()
        self._save_high_score()
        self.state_changed.emit()
        self.emit_event("game_over", score=self._score, kills=self._kills,
                         mode=self._mode, won=False)
        self.update()

    # ── 最高分持久化 ──────────────────────────────────────

    def _load_high_score(self) -> int:
        return self._settings.value(f"high_{self._mode}", 0, type=int)

    def _save_high_score(self):
        key = f"high_{self._mode}"
        cur = self._settings.value(key, 0, type=int)
        if self._score > cur:
            self._settings.setValue(key, self._score)
            self._settings.sync()

    # ── 绘制（QPainter） ───────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 背景
        painter.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE, QColor("#0f3460"))

        # 网格
        painter.setPen(QPen(QColor(255, 255, 255, 10), 1))
        for i in range(GRID + 1):
            painter.drawLine(i * CELL, 0, i * CELL, CANVAS_SIZE)
            painter.drawLine(0, i * CELL, CANVAS_SIZE, i * CELL)

        if not self._food:
            return

        # 食物 — 发光圆点
        fx = self._food["x"] * CELL + CELL / 2
        fy = self._food["y"] * CELL + CELL / 2
        painter.setBrush(self._food_color)
        painter.setPen(Qt.NoPen)
        glow = QColor(self._food_color)
        glow.setAlpha(60)
        painter.setBrush(glow)
        painter.drawEllipse(int(fx - CELL / 2 + 2), int(fy - CELL / 2 + 2),
                            CELL - 4, CELL - 4)
        painter.setBrush(self._food_color)
        painter.drawEllipse(int(fx - CELL / 2 + 4), int(fy - CELL / 2 + 4),
                            CELL - 8, CELL - 8)

        # 敌人（射击模式）
        for e in self._enemies:
            ex = e["x"] * CELL
            ey = e["y"] * CELL
            painter.setBrush(ENEMY_COLOR)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(ex + 2, ey + 2, CELL - 4, CELL - 4)
            # 骷髅图标
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("sans-serif", 10))
            painter.drawText(QRect(ex, ey, CELL, CELL), Qt.AlignCenter, "☠")

        # 子弹（射击模式）
        painter.setPen(Qt.NoPen)
        for b in self._bullets:
            bx = b["x"] * CELL + CELL / 2
            by = b["y"] * CELL + CELL / 2
            painter.setBrush(QColor("#f1c40f"))
            painter.drawEllipse(int(bx - 4), int(by - 4), 8, 8)

        # 蛇
        for si, seg in enumerate(self._snake):
            sx = seg["x"] * CELL
            sy = seg["y"] * CELL
            pad = 1

            if si == 0:
                painter.setBrush(self._snake_color)
            else:
                t = si / len(self._snake)
                c = QColor(self._snake_color)
                r = int(c.red() * (1 - t * 0.45))
                g = int(c.green() * (1 - t * 0.45))
                b = int(c.blue() * (1 - t * 0.45))
                painter.setBrush(QColor(r, g, b))

            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(sx + pad, sy + pad, CELL - pad * 2, CELL - pad * 2, 4, 4)

            # 蛇头眼睛
            if si == 0:
                painter.setBrush(QColor("#ffffff"))
                cx = sx + CELL / 2 + self._direction["x"] * 4
                cy = sy + CELL / 2 + self._direction["y"] * 4
                painter.drawEllipse(int(cx - 3), int(cy - 3), 5, 5)
                painter.drawEllipse(int(cx + 3), int(cy + 3), 5, 5)

    # ── 键盘控制 ──────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        nd = None

        # 方向映射
        if key in (Qt.Key_Up, Qt.Key_W):
            nd = {"x": 0, "y": -1}
        elif key in (Qt.Key_Down, Qt.Key_S):
            nd = {"x": 0, "y": 1}
        elif key in (Qt.Key_Left, Qt.Key_A):
            nd = {"x": -1, "y": 0}
        elif key in (Qt.Key_Right, Qt.Key_D):
            nd = {"x": 1, "y": 0}
        elif key in (Qt.Key_Space,):
            self.shoot()
            return

        if nd:
            # 不允许 180° 掉头
            if not (self._direction["x"] == -nd["x"] and self._direction["y"] == -nd["y"]):
                self._next_direction = nd
            event.accept()
        else:
            super().keyPressEvent(event)
