"""
TTS 语音合成引擎
使用阿里云百炼 dashscope SDK 调用 CosyVoice API。
"""

import sys
import re
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

    def _request_tts(self, text: str):
        try:
            try:
                print(f"[TTS] 开始合成: '{text[:30]}...' ({len(text)} 字)")
            except UnicodeEncodeError:
                print(f"[TTS] synthesizing {len(text)} chars")

            # 使用阿里云官方的 dashscope SDK
            import dashscope
            dashscope.api_key = settings.ALIYUN_API_KEY

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

            # 保存临时文件
            ts = int(time.time() * 1000)
            temp_file = self._temp_dir / f"tts_{ts}.mp3"
            temp_file.write_bytes(audio_bytes)
            print(f"[TTS] saved: {temp_file}")

            self._play_on_main(str(temp_file))

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
