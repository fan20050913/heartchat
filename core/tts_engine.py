"""
TTS 语音合成引擎
使用阿里云百炼 dashscope SDK 调用 CosyVoice API。
"""

import sys
import re
import hashlib
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from config.settings import settings
from utils.resource_helper import asset_path


class TTSEngine(QObject):
    """语音合成引擎：文字 → CosyVoice SDK → 音频 → 播放。"""

    # 用于去除 emoji 的正则
    _EMOJI_PATTERN = re.compile(
        "[\U0001F600-\U0001F64F"      # 表情符号
        "\U0001F300-\U0001F5FF"        # 符号和象形文字
        "\U0001F680-\U0001F6FF"        # 交通和地图符号
        "\U0001F1E0-\U0001F1FF"        # 国旗
        "\U00002600-\U000027BF"        # 杂项符号
        "\U0000FE00-\U0000FE0F"        # 变体选择符
        "\U000020D0-\U000020FF"        # 组合用记号
        "]+"
    )

    play_started = Signal()
    play_finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)  # 确保音量最大
        self._player.mediaStatusChanged.connect(self._on_media_status)

        self._temp_dir = asset_path("assets", "audio")
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._current_file: Path | None = None
        self._enabled = bool(settings.ALIYUN_API_KEY)

        if not self._enabled:
            print("[TTS] ALIYUN_API_KEY 未设置，语音合成已禁用")

        self._cleanup_temp_files()

    def speak(self, text: str):
        if not self._enabled or not text:
            return
        text = self._clean_text(text)
        if not text:
            return
        self.stop()
        threading.Thread(target=self._request_tts, args=(text,), daemon=True).start()

    def speak_from_file(self, filepath: str):
        """直接播放本地音频文件（缓存复用用，不走 API）。"""
        if not self._enabled:
            return
        self.stop()
        self._play_on_main(filepath)

    def speak_cached(self, text: str, cache_dir: Path, label: str = ""):
        """语音合成 + 缓存复用。首次走 API 并缓存，之后直接本地播放。

        label: 可读文件名标识，如 "game_started_tsukiau"，不传则用 md5。
        """
        if not self._enabled or not text:
            return
        text = self._clean_text(text)
        if not text:
            return

        if label:
            safe = re.sub(r'[<>:"/\\|?*]', '_', label).strip('_')[:60]
            cache_file = cache_dir / f"{safe}.mp3"
        else:
            cache_key = hashlib.md5(text.encode("utf-8")).hexdigest()[:16]
            cache_file = cache_dir / f"{cache_key}.mp3"

        if cache_file.exists():
            print(f"[TTS] 缓存命中: {cache_file.name}")
            self.speak_from_file(str(cache_file))
            return

        # 缓存未命中 → 走 API，结果存到缓存目录
        self.stop()
        threading.Thread(
            target=self._request_tts, args=(text, cache_file), daemon=True
        ).start()

    def is_enabled(self) -> bool:
        """TTS 是否可用（已配置 API Key）。"""
        return self._enabled

    @staticmethod
    def _clean_text(text: str) -> str:
        """清除颜文字、emoji 等不适合语音合成的内容。"""
        # 去除 emoji
        text = TTSEngine._EMOJI_PATTERN.sub("", text)
        # 去除颜文字（括号包围且不含中文字符的表达式）
        text = re.sub(r'[\(（][^)）一-鿿]{1,30}[\)）]', "", text)
        # 去除装饰性波浪线和特殊符号
        text = re.sub(r'[〜~]+', "", text)
        # 合并多余空格
        text = re.sub(r'\s{2,}', " ", text)
        return text.strip()

    def stop(self):
        self._player.stop()
        self._remove_current_file()

    # ── TTS 请求（使用 dashscope SDK） ────────────────────

    def _request_tts(self, text: str, output_path: Path | None = None):
        try:
            try:
                print(f"[TTS] 开始合成: '{text[:30]}...' ({len(text)} 字)")
            except UnicodeEncodeError:
                print(f"[TTS] synthesizing {len(text)} chars")

            # 使用阿里云官方的 dashscope SDK
            import dashscope
            dashscope.api_key = settings.ALIYUN_API_KEY
            if settings.TTS_WS_URL:
                dashscope.base_websocket_api_url = settings.TTS_WS_URL
            if settings.TTS_HTTP_URL:
                dashscope.base_http_api_url = settings.TTS_HTTP_URL

            from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat

            synthesizer = SpeechSynthesizer(
                model=settings.TTS_MODEL,
                voice=settings.TTS_VOICE,
                format=AudioFormat.MP3_22050HZ_MONO_256KBPS,
            )

            audio_bytes = synthesizer.call(text)
            print(f"[TTS] SDK 返回: {len(audio_bytes)} bytes")

            if not audio_bytes or len(audio_bytes) < 200:
                print(f"[TTS] audio data too small", file=sys.stderr)
                self.error_occurred.emit("TTS 返回的音频数据为空")
                return

            # 保存到指定路径（缓存）或临时文件
            if output_path is None:
                ts = int(time.time() * 1000)
                output_path = self._temp_dir / f"tts_{ts}.mp3"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_bytes)
            print(f"[TTS] saved: {output_path}")

            self._play_on_main(str(output_path))

        except ImportError:
            print("[TTS] dashscope SDK not installed", file=sys.stderr)
            self.error_occurred.emit("TTS SDK 未安装，请执行 pip install dashscope")
        except Exception as e:
            import traceback
            err = f"{type(e).__name__}: {e}"
            tb = traceback.format_exc()
            # 写日志文件方便调试
            try:
                with open(asset_path("tts_error.log"), "w", encoding="utf-8") as f:
                    f.write(f"{err}\n{tb}")
            except Exception:
                pass
            print(f"[TTS] error: {err}", file=sys.stderr)
            print(tb, file=sys.stderr)
            self.error_occurred.emit(f"TTS 出错: {err}")

    # ── 播放 ──────────────────────────────────────────────

    def _play_on_main(self, filepath: str):
        self._current_file = Path(filepath)
        self._player.setSource(QUrl.fromLocalFile(filepath))
        self._player.play()
        self.play_started.emit()
        print(f"[TTS] 开始播放")

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            print("[TTS] 播放完成")
            self.play_finished.emit()
            self._remove_current_file()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            print("[TTS] invalid audio file", file=sys.stderr)
            self.error_occurred.emit("TTS 音频文件无效")
            self._remove_current_file()

    def _remove_current_file(self):
        if self._current_file and self._current_file.exists():
            # 只删临时合成文件（tts_*），不删缓存文件（game_voices）
            if self._current_file.name.startswith("tts_"):
                try:
                    self._current_file.unlink()
                except PermissionError:
                    pass
        self._current_file = None

    def _cleanup_temp_files(self):
        now = time.time()
        for f in self._temp_dir.glob("tts_*"):
            try:
                if now - f.stat().st_mtime > 3600:
                    f.unlink()
            except OSError:
                pass
