"""
语音输入引擎
使用 sounddevice 录制麦克风音频，通过千问 Paraformer ASR 转写为文字。
"""

import sys
import time
import threading
import tempfile
from pathlib import Path

import numpy as np
import sounddevice as sd

from PySide6.QtCore import QObject, Signal

from config.settings import settings


class _NullCallback:
    """ASR 回调：仅用于满足 Recognition 构造函数的参数要求。"""
    def on_open(self):      pass
    def on_complete(self):  pass
    def on_error(self, r):  pass
    def on_close(self):     pass
    def on_event(self, r):  pass


class AudioInputEngine(QObject):
    """语音输入引擎：录音 → ASR 转写 → 文字。"""

    recording_started = Signal()
    recording_stopped = Signal()
    transcription_complete = Signal(str)
    transcription_error = Signal(str)

    SAMPLE_RATE = 16000
    CHANNELS = 1
    DTYPE = "int16"
    MAX_RECORD_SECONDS = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_recording = False
        self._audio_frames: list[bytes] = []
        self._available = self._check_mic()

    # ── 公开接口 ──────────────────────────────────────────

    def is_available(self) -> bool:
        return self._available

    def toggle_recording(self):
        """切换录音状态。"""
        if self._is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """开始录音。"""
        if self._is_recording or not self._available:
            return
        self._is_recording = True
        self._audio_frames = []
        self.recording_started.emit()
        threading.Thread(target=self._record_worker, daemon=True).start()

    def stop_recording(self):
        """停止录音，启动 ASR 转写。"""
        if not self._is_recording:
            return
        self._is_recording = False

    def cancel_recording(self):
        """紧急停止，丢弃录音数据（面板关闭时调用）。"""
        was_recording = self._is_recording
        self._is_recording = False
        if was_recording:
            self._audio_frames = []
            self.recording_stopped.emit()

    # ── 麦克风检测 ────────────────────────────────────────

    @staticmethod
    def _check_mic() -> bool:
        """检测是否有可用的麦克风设备。"""
        try:
            devices = sd.query_devices()
            return any(d["max_input_channels"] > 0 for d in devices)
        except Exception as e:
            print(f"[AudioInput] 麦克风检测失败: {e}", file=sys.stderr)
            return False

    # ── 录音线程 ──────────────────────────────────────────

    def _record_worker(self):
        """后台录音线程：循环读取音频数据直到停止。"""
        try:
            start_time = time.time()
            stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype=self.DTYPE,
            )
            stream.start()

            while self._is_recording:
                chunk, _ = stream.read(1024)
                self._audio_frames.append(chunk.tobytes())
                # 超时自动停止
                if time.time() - start_time > self.MAX_RECORD_SECONDS:
                    print("[AudioInput] 录音超时，自动停止")
                    self._is_recording = False
                    break

            stream.stop()
            stream.close()

        except Exception as e:
            print(f"[AudioInput] 录音异常: {e}", file=sys.stderr)
            self._is_recording = False
            self.transcription_error.emit(f"录音出错：{e}")
            self.recording_stopped.emit()
            return

        # 录音结束 → 启动 ASR
        self.recording_stopped.emit()
        if self._audio_frames:
            threading.Thread(target=self._run_asr, daemon=True).start()

    # ── ASR 转写 ──────────────────────────────────────────

    def _run_asr(self):
        """后台线程：PCM 字节 → 临时文件 → Paraformer ASR → 文字。"""
        if not self._audio_frames:
            self.transcription_error.emit("没有录制到音频")
            return

        try:
            # 拼接 PCM 数据
            pcm_data = b"".join(self._audio_frames)
            if len(pcm_data) < 1600:  # < 0.1 秒
                self.transcription_error.emit("录音太短，请再说一遍")
                return

            # 写入临时 PCM 文件
            tmp = tempfile.NamedTemporaryFile(suffix=".pcm", delete=False)
            tmp_path = tmp.name
            tmp.write(pcm_data)
            tmp.close()

            try:
                # 调用 Paraformer ASR
                import dashscope
                dashscope.api_key = settings.ALIYUN_API_KEY

                from dashscope.audio.asr import Recognition

                recognition = Recognition(
                    model=settings.ASR_MODEL,
                    callback=_NullCallback(),
                    format="pcm",
                    sample_rate=self.SAMPLE_RATE,
                )
                result = recognition.call(file=tmp_path)

                if result.status_code != 200:
                    msg = getattr(result, "message", "未知错误")
                    self.transcription_error.emit(f"语音识别失败：{msg}")
                    return

                sentences = result.get_sentence()
                text = self._parse_result(sentences)
                if text:
                    self.transcription_complete.emit(text)
                else:
                    self.transcription_error.emit("没有听清，请再说一遍")

            finally:
                # 清理临时文件
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    pass

        except ImportError:
            self.transcription_error.emit("语音识别 SDK 未安装")
        except Exception as e:
            print(f"[AudioInput] ASR 异常: {e}", file=sys.stderr)
            self.transcription_error.emit(f"语音识别出错：{e}")

    @staticmethod
    def _parse_result(sentences) -> str:
        """解析 ASR 返回的句子列表，提取文本。"""
        if not sentences:
            return ""
        if isinstance(sentences, dict):
            return sentences.get("text", "")
        if isinstance(sentences, list):
            return "".join(
                s.get("text", "") if isinstance(s, dict) else str(s)
                for s in sentences
            ).strip()
        return str(sentences).strip()
