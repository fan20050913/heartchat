"""
小游戏系统

架构设计：
  GameBase          — 所有游戏的基类，定义 start/stop/pause 生命周期
  game_event 信号   — 供 main.py 串联角色语音联动（暂未接入，已预留接口）

扩展方式：
  1. 新建一个类继承 GameBase
  2. 实现 start() / stop() / paintEvent() / 游戏逻辑
  3. 在 game_event 信号中触发关键事件
  4. 在 GameWindow 中注册新游戏

计划中的语音联动事件（暂未实现）：
  "game_over"        — 游戏失败 → 角色嘲讽/安慰
  "score_milestone"  — 达到里程碑分数 → 角色鼓励
  "food_eaten"       — 吃到食物 → 角色随机反应
  "enemy_killed"     — 击杀敌人（射击模式）→ 角色称赞
"""

from .game_base import GameBase
from .game_window import GameWindow

__all__ = ["GameBase", "GameWindow"]
