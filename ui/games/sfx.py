"""
游戏音效 — 自动生成 + 播放管理

首次运行时用 numpy 合成 WAV 文件到 assets/audio/game_sfx/，
之后直接读取播放，不走网络，不依赖外部资源。
"""

from __future__ import annotations

import wave
from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from utils.resource_helper import asset_path

SR = 22050  # 采样率
_SFX_VERSION = "3"  # 音效版本，有改动时 +1 触发重新生成

# numpy 用于 WAV 合成，没有则跳过生成（已有缓存文件不受影响）
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore
    _HAS_NUMPY = False


# ═══════════════════════════════════════════════════════════
#  WAV 合成（只在首次运行时调用一次）
# ═══════════════════════════════════════════════════════════

def _sine(freq: float, duration: float, sr: int = SR) -> np.ndarray:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t)


def _sweep(f_start: float, f_end: float, duration: float, sr: int = SR) -> np.ndarray:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return np.sin(2 * np.pi * (f_start + (f_end - f_start) * t / duration) * t)


def _noise(duration: float, amount: float = 0.5, sr: int = SR) -> np.ndarray:
    return np.random.uniform(-amount, amount, int(sr * duration))


def _save_wav(path: Path, data: np.ndarray, sr: int = SR):
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = np.max(np.abs(data))
    if peak > 0:
        data = data / peak
    data_int16 = (data * 0.55 * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data_int16.tobytes())


def _ensure_generated(cache_dir: Path):
    """生成所有音效文件（幂等，版本变化时重新生成）。"""
    version_file = cache_dir / "_version.txt"
    if version_file.exists() and version_file.read_text("utf-8").strip() == _SFX_VERSION:
        if (cache_dir / "bgm.wav").exists():
            return
    if not _HAS_NUMPY:
        print("[GameSFX] numpy 未安装，跳过音效生成")
        return

    sr = SR
    t4 = np.linspace(0, 4, int(sr * 4), endpoint=False)

    # ── BGM（用户自定义，已有文件时不生成） ──────────────
    if not (cache_dir / "bgm.wav").exists():
        bgm = np.zeros_like(t4)
        # 低音和弦进行 C - G - Am - F
        for freq in [130.81, 196.00, 220.00, 174.61]:
            bgm += _sine(freq, 4) * 0.25
        # 高音琶音 C5 E5 G5 D5
        for i, freq in enumerate([523.25, 659.25, 783.99, 587.33]):
            seg = np.zeros(int(sr * 4))
            start = (i * sr) % (sr * 4)
            seg_len = int(sr * 1.2)
            end = min(start + seg_len, sr * 4)
            tone = _sine(freq, seg_len / sr) * 0.12
            tone[:200] *= np.linspace(0, 1, 200)
            tone[-300:] *= np.linspace(1, 0, 300)
            seg[start:end] = tone[: end - start]
            bgm += seg
        bgm = np.tanh(bgm)
        _save_wav(cache_dir / "bgm.wav", bgm * 0.45)

    # ── 吃食物（上升叮咚） ──────────────────────────────
    eat = _sweep(800, 1600, 0.13)
    eat[:200] *= np.linspace(0, 1, 200)
    eat2 = _sine(2100, 0.08) * np.linspace(1, 0, int(sr * 0.08))
    eat = np.concatenate([eat, eat2])
    _save_wav(cache_dir / "eat.wav", eat * 0.5)

    # ── 射击（激光 pew） ───────────────────────────────
    shoot = _sweep(1500, 250, 0.1)
    shoot *= np.exp(-np.linspace(0, 4, int(sr * 0.1)))
    _save_wav(cache_dir / "shoot.wav", shoot * 0.5)

    # ── 命中（噪声爆炸 + 低频轰击） ────────────────────
    hit = _noise(0.12) * np.exp(-np.linspace(0, 6, int(sr * 0.12)))
    hit += _sweep(300, 60, 0.12) * 0.6
    _save_wav(cache_dir / "hit.wav", hit * 0.6)

    # ── 失败（下行呜咽） ──────────────────────────────
    fail = _sweep(400, 80, 0.5) * np.exp(-np.linspace(0, 2, int(sr * 0.5)))
    fail += _sine(100, 0.5) * 0.3  # 低频底音
    fail *= np.linspace(1, 0, int(sr * 0.5))  # 整体渐弱
    _save_wav(cache_dir / "fail.wav", fail * 0.5)

    version_file.write_text(_SFX_VERSION, "utf-8")
    print(f"[GameSFX] 音效已生成: {cache_dir} (v{_SFX_VERSION})")


# ═══════════════════════════════════════════════════════════
#  GameSFX — 游戏音效播放器
# ═══════════════════════════════════════════════════════════

class GameSFX(QObject):
    """游戏音效管理：BGM 自动循环 + 短音效播放。"""

    def __init__(self, cache_dir: str | Path | None = None, parent=None):
        super().__init__(parent)
        self._cache_dir = Path(cache_dir) if cache_dir else asset_path("assets", "audio", "game_sfx")
        _ensure_generated(self._cache_dir)

        # ── BGM 播放器（循环） ──
        self._bgm_player = QMediaPlayer()
        self._bgm_audio = QAudioOutput()
        self._bgm_player.setAudioOutput(self._bgm_audio)
        self._bgm_audio.setVolume(0.15)
        self._bgm_player.mediaStatusChanged.connect(self._on_bgm_status)
        self._bgm_active = False

        # ── 短音效播放器 ──
        self._sfx_player = QMediaPlayer()
        self._sfx_audio = QAudioOutput()
        self._sfx_player.setAudioOutput(self._sfx_audio)
        self._sfx_audio.setVolume(0.7)

    # ── BGM ──

    def play_bgm(self):
        bgm_file = self._cache_dir / "bgm.wav"
        if not bgm_file.exists():
            return
        self._bgm_active = True
        self._bgm_player.setSource(QUrl.fromLocalFile(str(bgm_file)))
        self._bgm_player.play()

    def stop_bgm(self):
        self._bgm_active = False
        self._bgm_player.stop()

    def _on_bgm_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self._bgm_active:
            self._bgm_player.play()

    # ── 短音效 ──

    def play_eat(self):
        self._play("eat.wav")

    def play_shoot(self):
        self._play("shoot.wav")

    def play_hit(self):
        self._play("hit.wav")

    def play_fail(self):
        self._play("fail.wav")

    def _play(self, filename: str):
        path = self._cache_dir / filename
        if path.exists():
            self._sfx_player.setSource(QUrl.fromLocalFile(str(path)))
            self._sfx_player.play()
