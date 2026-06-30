"""
AI 对话引擎
封装 DeepSeek API 调用，管理对话上下文，流式返回回复。
"""

import os
import sys
import threading
import traceback
from datetime import datetime
from openai import OpenAI
from PySide6.QtCore import QObject, Signal

from config.settings import settings
from utils.resource_helper import data_dir


# ── 默认 system prompt（在 set_character 之前使用） ────────

DEFAULT_SYSTEM_PROMPT = """你是朱比华，一个可爱的 AI 桌宠精灵。

性格设定：
- 活泼可爱，语气亲切，喜欢用语气词（~、呀、啦、哦）
- 聪明但保持谦逊，偶尔会撒娇
- 对用户充满好奇，喜欢聊天
- 你生活在用户的桌面上，能感知到用户在使用电脑

语言风格：
- 使用中文对话，可以夹杂少量可爱的英文单词
- 说话以短句为主，生动活泼
- 适当使用颜文字或 emoji 表达情绪

注意事项：
- 不要声称自己是 AI 或大语言模型
- 你的身份就是朱比华，桌宠精灵
- 每次回复简短自然，不要太长"""


class AIEngine(QObject):
    """DeepSeek 对话引擎，在后台线程中运行。"""

    # ── 信号 ──────────────────────────────────────────────
    text_chunk = Signal(str)          # 流式逐字片段（含标签原始文本）
    response_finished = Signal(str)   # 中文显示文本（解析后）
    tts_text_ready = Signal(str)      # 日语语音文本就绪
    error_occurred = Signal(str)      # 错误信息

    MAX_HISTORY = 20  # 保留最近 N 轮对话

    @staticmethod
    def parse_bilingual(raw: str) -> tuple[str, str]:
        """解析双语输出，返回 (中文显示文本, 日语语音文本)。

        格式： 【显示】<中文>【语音】<日本語>
        解析失败时：整段当显示文本，语音留空（TTS 静默跳过）。
        """
        import re
        m = re.search(r'【显示】([\s\S]*?)【语音】([\s\S]*?)$', raw)
        if m:
            cn = m.group(1).strip()
            jp = m.group(2).strip()
            # 语音文本消毒：扒掉括号动作描述和多余空白
            jp = re.sub(r'[（(][^）)]*[）)]', '', jp)
            jp = re.sub(r'\s+', ' ', jp).strip()
            return cn, jp
        # 只有 【显示】 没有 【语音】
        m2 = re.search(r'【显示】([\s\S]*)', raw)
        if m2:
            return m2.group(1).strip(), ""
        # 完全无格式 → 全当中文显示
        return raw, ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._client = None
        self._model = ""
        self._init_from_preset()
        self._history: list[dict] = []   # 对话上下文
        self._rag_context: str = ""      # （Phase 3）RAG 注入内容
        self._thread: threading.Thread | None = None
        self._cancel_flag = False
        self._system_prompt = DEFAULT_SYSTEM_PROMPT  # 可被 set_character 替换
        self._character_name = "朱比华"

    # ── 公开接口 ──────────────────────────────────────────

    def chat(self, user_text: str):
        """发送用户消息，启动后台流式回复。"""
        if self._thread and self._thread.is_alive():
            return  # 已有回复进行中

        self._cancel_flag = False
        self._thread = threading.Thread(
            target=self._run_chat,
            args=(user_text,),
            daemon=True,
        )
        self._thread.start()

    def cancel(self):
        """取消当前回复。"""
        self._cancel_flag = True

    def clear_history(self):
        """清空对话历史。"""
        self._history.clear()

    def _init_from_preset(self):
        """根据当前 settings.LLM_MODEL 初始化 OpenAI client 和 model name。"""
        preset = settings.MODEL_PRESETS[settings.LLM_MODEL]
        api_key = getattr(settings, preset["api_key_env"])
        self._client = OpenAI(api_key=api_key, base_url=preset["base_url"])
        self._model = preset["model"]

    def update_api_key(self):
        """刷新 API Key（用户在设置界面修改后调用）。"""
        self._init_from_preset()

    def switch_model(self, preset_id: str):
        """切换文本模型（deepseek-flash / qwen3.6-plus），刷新 client 并清历史。"""
        settings.LLM_MODEL = preset_id
        self._init_from_preset()
        self.clear_history()

    def set_character(self, profile: dict):
        """切换角色：更新 system prompt、角色名，清空对话历史。"""
        self._system_prompt = profile.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        self._character_name = profile.get("name", "朱比华")
        self.clear_history()
        self._rag_context = ""

    def set_rag_context(self, context: str):
        """（Phase 3）设置 RAG 注入的人设上下文。"""
        self._rag_context = context

    # ── 内部实现 ──────────────────────────────────────────

    def _build_messages(self, user_text: str) -> list[dict]:
        """组装完整的 messages 列表。"""
        system = self._system_prompt
        if self._rag_context:
            system += f"\n\n以下是和本次回答相关的角色知识：\n{self._rag_context}"

        system += (
            "\n\n【输出格式】\n"
            "每次回复请同时输出中文和日语，格式如下：\n"
            "【显示】<中文回复，包含颜文字、emoji、动作描述如（微笑）等所有内容>\n"
            "【语音】<日本語の返答、純粋なセリフのみ、動作説明・絵文字不要、音声合成用>\n"
            "要求：\n"
            "【显示】和【语音】意思一致，语气都符合角色人设\n"
            "【语音】只保留对话台词，不要包含动作描写和 emoji/颜文字\n"
            "【语音】只输出纯文本，不加引号或标注\n"
            "不要漏掉【语音】部分"
        )

        messages = [{"role": "system", "content": system}]
        messages.extend(self._history)
        messages.append({"role": "user", "content": user_text})
        return messages

    def _run_chat(self, user_text: str):
        """在后台线程中调用 DeepSeek 流式 API。"""
        try:
            messages = self._build_messages(user_text)

            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
                temperature=0.8,
                max_tokens=2048,
            )

            full_text = ""
            for chunk in response:
                if self._cancel_flag:
                    return

                if not chunk.choices:
                    continue  # Qwen 等 API 可能发空 choices 的 chunk（如 usage 信息）
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    content = delta.content
                    full_text += content
                    # 通过 Signal 发射到主线程
                    self.text_chunk.emit(content)

            if full_text:
                # 解析双语输出
                cn_text, jp_text = self.parse_bilingual(full_text)

                # 历史存原始双语文本（让模型持续看到格式示例）
                self._history.append({"role": "user", "content": user_text})
                self._history.append({"role": "assistant", "content": full_text})
                # 控制历史长度
                if len(self._history) > self.MAX_HISTORY * 2:
                    self._history = self._history[-self.MAX_HISTORY * 2:]

                self.response_finished.emit(cn_text)
                if jp_text:
                    self.tts_text_ready.emit(jp_text)

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)

            # 记录详细 traceback 到 data/crash.log
            try:
                log_dir = data_dir() / "data"
                log_dir.mkdir(parents=True, exist_ok=True)
                with open(log_dir / "crash.log", "a", encoding="utf-8") as f:
                    f.write(f"\n=== {datetime.now()} [{error_type}] ===\n")
                    f.write(f"Error: {error_msg}\n")
                    traceback.print_exc(file=f)
                    f.write(f"sys.stdout={sys.stdout!r}\n")
                    f.write(f"sys.stderr={sys.stderr!r}\n")
                    f.write(f"stdout.encoding={getattr(sys.stdout, 'encoding', 'N/A')}\n")
                    f.write(f"stderr.encoding={getattr(sys.stderr, 'encoding', 'N/A')}\n")
                    f.write(f"frozen={getattr(sys, 'frozen', False)}\n")
            except Exception:
                pass

            # 将常见错误转为友好提示
            if "401" in error_msg or "Authentication" in error_msg:
                friendly = "API Key 无效，请检查 .env 配置"
            elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                friendly = "网络超时，请检查网络连接"
            elif "rate" in error_msg.lower():
                friendly = "请求太频繁，请稍后再试"
            else:
                friendly = f"AI 回复出错 [{error_type}]: {error_msg}"
            self.error_occurred.emit(friendly)

    # ── 属性 ──────────────────────────────────────────────

    @property
    def history(self) -> list[dict]:
        return self._history.copy()

    @history.setter
    def history(self, value: list[dict]):
        self._history = value
