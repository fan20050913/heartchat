"""
AI 桌宠「朱比华」— 应用入口

Phase 2 功能：Phase 1 + AI 回复语音播放（千问 CosyVoice TTS）
"""

import os
import sys

# ⚠ 注意：所有第三方库（openai/httpx/PySide6/dashscope/chromadb）都在
#    main() 内部延迟导入，确保先重定向 sys.stdout/stderr 到 devnull。
#    防止这些库在 import 时捕获 stderr 引用导致 UnicodeEncodeError。


def main():
    # ── 编码修复：PyInstaller -w 模式无控制台，所有 print 重定向到 devnull ──
    if getattr(sys, "frozen", False):
        devnull = open(os.devnull, "w", encoding="utf-8")
        sys.stdout = devnull
        sys.stderr = devnull
        # 同时抑制 httpx/openai/dashscope/chromadb 的日志输出
        import logging
        for lib in ("httpx", "httpcore", "openai", "dashscope",
                     "urllib3", "chromadb", "chromadb.telemetry"):
            logging.getLogger(lib).addHandler(logging.NullHandler())

        # ── 修复 httpx header 编码问题 ─────────────────────
        # httpx 默认用 ASCII 编码 HTTP header value，打包后 openai SDK
        # 传了含中文的 header 值导致 UnicodeEncodeError。
        # 打补丁：ASCII 失败时自动退回 UTF-8。
        import httpx._models
        _orig_normalize = httpx._models._normalize_header_value
        def _safe_normalize(value, encoding=None):
            if isinstance(value, str):
                try:
                    return value.encode("ascii")
                except UnicodeEncodeError:
                    return value.encode("utf-8")
            return _orig_normalize(value, encoding)
        httpx._models._normalize_header_value = _safe_normalize

    # ════════════════════════════════════════════════════════
    #   以下 import 都在 sys.stdout/stderr 重定向之后进行
    # ════════════════════════════════════════════════════════
    import threading
    import base64
    import wave
    from pathlib import Path

    import requests
    import numpy as np

    from PySide6.QtCore import QObject, Signal, QTimer
    from PySide6.QtWidgets import (
        QApplication, QMessageBox, QDialog, QVBoxLayout,
        QHBoxLayout, QLineEdit, QLabel, QPushButton, QFrame,
        QComboBox, QScrollArea, QWidget,
    )

    from config.settings import settings
    from config.characters import get_character, get_character_list
    from utils.resource_helper import asset_path
    from ui.pet_window import PetWindow
    from core.ai_engine import AIEngine
    from core.tts_engine import TTSEngine
    from core.rag_engine import RAGEngine
    from core.audio_input import AudioInputEngine

    # ── 校验配置 ─────────────────────────────────────────
    try:
        settings.validate()
    except ValueError as e:
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "配置错误", str(e))
        sys.exit(1)

    # ── 创建应用 ─────────────────────────────────────────
    app = QApplication(sys.argv)
    app.setApplicationName("HeartChat - AI 桌宠")
    app.setQuitOnLastWindowClosed(False)

    # ── 创建窗口 ─────────────────────────────────────────
    pet = PetWindow()
    pet.show()

    # ── 聊天面板（已预先创建） ────────────────────────────
    panel = pet.get_chat_panel()

    # ── AI 引擎 ──────────────────────────────────────────
    ai = AIEngine()

    # ── TTS 引擎 ─────────────────────────────────────────
    tts = TTSEngine()

    # ── RAG 知识库引擎 ────────────────────────────────────
    rag = RAGEngine()

    # ── 语音输入引擎 (Phase 4) ────────────────────────────
    audio = AudioInputEngine()
    if not audio.is_available():
        print("[AudioInput] 未检测到麦克风，语音输入已禁用")

    # ── 角色系统 ─────────────────────────────────────────

    def _save_current_tts_voice():
        """保存当前 TTS_VOICE 到角色专属 env key。"""
        cid = settings.CURRENT_CHARACTER
        if not cid:
            return
        from dotenv import set_key, find_dotenv
        env_key = f"TTS_VOICE_{cid.upper()}"
        set_key(find_dotenv(), env_key, settings.TTS_VOICE)

    def _restore_character_tts_voice(character_id: str):
        """从角色专属 env key 恢复 TTS_VOICE，无则用角色默认。"""
        env_key = f"TTS_VOICE_{character_id.upper()}"
        saved = os.getenv(env_key)
        if saved:
            settings.TTS_VOICE = saved
        else:
            profile = get_character(character_id)
            if profile:
                settings.TTS_VOICE = profile.get("tts_voice", "longxiaochun_v2")

    def _switch_character(character_id: str):
        """完整角色切换：持久化 → 引擎 → UI。"""
        profile = get_character(character_id)
        if not profile:
            print(f"[角色] 未知角色: {character_id}")
            return

        # 1. 保存当前角色 TTS 音色
        _save_current_tts_voice()

        # 2. 持久化角色选择
        settings.CURRENT_CHARACTER = character_id
        from dotenv import set_key, find_dotenv
        set_key(find_dotenv(), "CURRENT_CHARACTER", character_id)

        # 3. 恢复目标角色 TTS 音色
        _restore_character_tts_voice(character_id)

        # 4. 更新 AI 引擎（换 system prompt + 清历史）
        ai.set_character(profile)

        # 5. 更新 RAG 知识库（asset_path 解析相对路径，兼容打包）
        xlsx_path = str(asset_path(profile["rag_xlsx"]))
        rag.switch_to_character(character_id, xlsx_path)

        # 6. 更新立绘
        sprite_path = asset_path(profile["sprite_path"])
        pet.character.set_character(profile["name"], sprite_path, profile.get("emoji", "✨"))

        # 7. 更新聊天面板
        panel.set_character(profile["sender_name"], profile["chat_title"])

        # 8. 更新主窗口
        pet.set_character(profile["window_title"], profile["tray_tooltip"])

        # 9. 清空聊天显示
        panel.clear_all()

        print(f"[角色] 已切换到: {profile['name']}")

    # ── 初始化当前角色 ────────────────────────────────────
    _switch_character(settings.CURRENT_CHARACTER)

    # ── 信号串联 ─────────────────────────────────────────

    def on_send(text: str):
        """用户发送消息 → RAG 检索 → 启动 AI 回复。"""
        panel.start_streaming()
        context = rag.query(text)
        if context:
            print(f"[RAG] 注入上下文: {len(context)} 字")
        ai.set_rag_context(context)
        ai.chat(text)

    # 用于缓存 AI 回复，等待 TTS 就绪后一同显示
    _pending_reply: list[str] = []

    def on_chunk(chunk: str):
        """流式输出片段 → 暂不显示，缓存起来等 TTS 就绪。"""
        _pending_reply.append(chunk)

    def _calc_tts_delay(text_len: int) -> int:
        """根据文本长度估算 TTS 生成耗时。"""
        return min(10000, max(3500, int(3500 + text_len * 75)))

    def on_finished(full_text: str):
        """AI 回复完成 → 延时显示文字 + 后台 TTS。"""
        full_reply = "".join(_pending_reply)
        _pending_reply.clear()
        delay = _calc_tts_delay(len(full_reply))
        print(f"[main] on_finished, delay={delay}ms, reply_len={len(full_reply)}")

        # 后台 TTS（不影响文字显示）
        if tts.is_enabled():
            threading.Thread(
                target=_translate_and_speak,
                args=(full_text,),
                daemon=True,
            ).start()

        # 延时后显示文字
        panel.start_loading_animation()
        QTimer.singleShot(delay, lambda: (
            print(f"[main] 定时器触发, 显示 {len(full_reply)} 字"),
            panel.finish_streaming(full_reply)
        ))

    def _strip_action_descriptions(text: str) -> str:
        """去掉括号内的动作/场景描述，只保留对话台词。"""
        import re
        # 去掉 （...） 和 （...） 与前后文字的间隔，避免留空括号痕迹
        result = re.sub(r'[（(][^）)]*[）)]', '', text)
        # 去掉因此产生的多余空白和标点重复
        result = re.sub(r'\s+', ' ', result).strip()
        return result

    def _translate_and_speak(chinese_text: str):
        """翻译中文为动漫日语 → 调用 TTS 合成。"""
        try:
            # 先扒掉括号动作描述，只翻译台词
            dialog_only = _strip_action_descriptions(chinese_text)
            japanese_text = ai.translate_to_japanese(dialog_only)
            tts.speak(japanese_text)
        except Exception as e:
            import traceback
            try:
                from utils.resource_helper import data_dir
                log_dir = data_dir() / "data"
                log_dir.mkdir(parents=True, exist_ok=True)
                with open(log_dir / "crash.log", "a", encoding="utf-8") as f:
                    f.write(f"\n=== translate_and_speak error at {__import__('datetime').datetime.now()} ===\n")
                    traceback.print_exc(file=f)
            except Exception:
                pass
            # 出错时依然显示文字（面板可能已关闭，但 finish_streaming 渲染不受影响）
            if _pending_reply:
                panel.finish_streaming("".join(_pending_reply))
            _pending_reply.clear()

    def on_tts_ready():
        """TTS 开始播放 → 停动画 + 显示说话指示条（文字已由定时器负责）。"""
        panel._stop_loading()
        panel.show_tts_playing()

    def on_tts_disabled(full_text: str):
        """TTS 不可用时，AI 回复完成后直接显示文字。"""
        panel.finish_streaming(full_text)
        _pending_reply.clear()

    def on_error(error_msg: str):
        """AI 出错 → 显示错误。"""
        panel.finish_streaming("")
        panel.show_error(error_msg)

    # ── 角色状态联动 ─────────────────────────────────────

    def _set_character_state(state: str):
        """更新角色立绘状态。"""
        pet.character.set_state(state)

    # ── 信号连接 ─────────────────────────────────────────

    # 聊天 → AI
    panel.send_message.connect(on_send)

    # AI → 聊天界面 + 角色状态
    ai.text_chunk.connect(on_chunk)
    ai.response_finished.connect(on_finished)
    ai.error_occurred.connect(on_error)

    # 开始对话 → talking
    panel.send_message.connect(lambda _: _set_character_state("talking"))
    # AI 完成或出错 → idle
    ai.response_finished.connect(lambda _: _set_character_state("idle"))
    ai.error_occurred.connect(lambda _: _set_character_state("idle"))

    # TTS → 聊天界面 + 角色状态
    tts.play_started.connect(on_tts_ready)
    tts.play_started.connect(lambda: _set_character_state("talking"))
    tts.play_finished.connect(panel.hide_tts_playing)
    tts.play_finished.connect(lambda: _set_character_state("idle"))
    tts.error_occurred.connect(lambda msg: (
        panel.show_error(msg),
        panel._stop_loading(),
        _set_character_state("idle"),
    ))

    # ── API Key 配置 + 声音克隆对话框 ─────────────────────

    class _VoiceTaskSignals(QObject):
        """后台线程 → UI 线程的信号桥接。"""
        status = Signal(str)
        voice_found = Signal(str)   # voice_id → 更新当前音色标签
        error = Signal(str)
        done = Signal()

    def _set_tts_voice(voice_id: str):
        """更新运行时和 .env 的 TTS_VOICE（同时存角色专属 key）。"""
        from dotenv import set_key, find_dotenv
        settings.TTS_VOICE = voice_id
        env_path = find_dotenv()
        set_key(env_path, "TTS_VOICE", voice_id)
        # 也存到角色专属 key，切换角色时恢复
        cid = settings.CURRENT_CHARACTER
        if cid:
            set_key(env_path, f"TTS_VOICE_{cid.upper()}", voice_id)

    def _show_settings():
        """弹出设置对话框（API Key + 声音克隆）。"""
        dialog = QDialog(pet)
        dialog.setWindowTitle("设置")
        dialog.setFixedSize(440, 520)
        dialog.setStyleSheet("""
            QDialog { background: #f0f6ff; border-radius: 12px; }
            QLabel { color: #3a5a7a; font-size: 13px; font-weight: bold; }
            QLabel#statusLabel { font-weight: normal; font-size: 12px; color: #5a7a9a; }
            QLineEdit {
                background: #ffffff;
                border: 1px solid #c0d8ef;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                color: #2c3e50;
            }
            QLineEdit:focus { border: 1px solid #4a90d9; }
            QPushButton { border-radius: 8px; padding: 8px 16px; font-size: 12px; font-weight: bold; }
            QFrame#voiceGroup {
                background: rgba(255,255,255,180);
                border: 1px solid #d0e4f8;
                border-radius: 10px;
                padding: 10px;
            }
            QScrollArea { background: transparent; border: none; }
        """)

        # ── 可滚动内容区 ────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 18, 20, 0)
        content_layout.setSpacing(12)

        # ── API Key 区域 ────────────────────────────────────
        content_layout.addWidget(QLabel("DeepSeek API Key"))
        deepseek_input = QLineEdit()
        deepseek_input.setPlaceholderText("sk-...")
        deepseek_input.setText(settings.DEEPSEEK_API_KEY)
        deepseek_input.setEchoMode(QLineEdit.EchoMode.Password)
        content_layout.addWidget(deepseek_input)

        content_layout.addWidget(QLabel("阿里云百炼 API Key"))
        aliyun_input = QLineEdit()
        aliyun_input.setPlaceholderText("sk-...")
        aliyun_input.setText(settings.ALIYUN_API_KEY)
        aliyun_input.setEchoMode(QLineEdit.EchoMode.Password)
        content_layout.addWidget(aliyun_input)

        # ── 角色选择 ────────────────────────────────────────
        content_layout.addWidget(QLabel("当前角色"))
        char_selector = QComboBox()
        # 先阻塞信号避免初始设 index 触发切换
        char_selector.blockSignals(True)
        char_selector.addItems(
            f"{name} ({cid})" for cid, name in get_character_list()
        )
        # 选中当前角色
        current_idx = 0
        for i, (cid, _) in enumerate(get_character_list()):
            if cid == settings.CURRENT_CHARACTER:
                current_idx = i
                break
        char_selector.setCurrentIndex(current_idx)
        char_selector.blockSignals(False)
        char_selector.setStyleSheet("""
            QComboBox {
                background: #ffffff;
                border: 1px solid #c0d8ef;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                color: #2c3e50;
            }
        """)
        content_layout.addWidget(char_selector)

        # ── 文本模型选择 ────────────────────────────────────
        content_layout.addWidget(QLabel("文本模型"))
        model_selector = QComboBox()
        model_keys = list(settings.MODEL_PRESETS.keys())
        model_selector.addItems([
            settings.MODEL_PRESETS[k]["display"] for k in model_keys
        ])
        model_selector.setCurrentIndex(model_keys.index(settings.LLM_MODEL))
        model_selector.setStyleSheet(char_selector.styleSheet())
        content_layout.addWidget(model_selector)

        # 切换提示
        model_hint = QLabel("⚠ 切换模型将清空当前对话历史")
        model_hint.setObjectName("statusLabel")
        model_hint.setStyleSheet("font-weight: normal; font-size: 11px; color: #8a9aaa;")
        content_layout.addWidget(model_hint)

        def _on_model_selected(idx: int):
            preset_id = model_keys[idx]
            if preset_id == settings.LLM_MODEL:
                return
            ai.switch_model(preset_id)
            from dotenv import set_key, find_dotenv
            set_key(find_dotenv(), "LLM_MODEL", preset_id)

        model_selector.currentIndexChanged.connect(_on_model_selected)

        # ── 当前音色 + 状态标签（先创建，供下方信号连接使用） ──
        current_label = QLabel("当前音色: 默认")
        current_label.setObjectName("statusLabel")
        status_label = QLabel("就绪 ✓")
        status_label.setObjectName("statusLabel")

        # ── 创建信号桥接 ────────────────────────────────
        voice_sig = _VoiceTaskSignals()
        voice_sig.status.connect(status_label.setText)
        voice_sig.voice_found.connect(lambda vid: current_label.setText(f"当前音色: {vid}"))
        voice_sig.error.connect(lambda msg: status_label.setText(f"❌ {msg}"))

        # ── 下拉框实时切换角色 + 自动检测音色 ──────────────
        def _on_character_selected(idx: int):
            char_list = get_character_list()
            if idx < 0 or idx >= len(char_list):
                return
            cid = char_list[idx][0]
            if cid == settings.CURRENT_CHARACTER:
                return
            # 立即切换角色引擎 + UI
            _switch_character(cid)
            # 后台自动检测云端音色
            threading.Thread(
                target=_do_check_voice, args=(voice_sig,), daemon=True
            ).start()

        char_selector.currentIndexChanged.connect(_on_character_selected)

        # ── 声音克隆区域 ────────────────────────────────────
        voice_group = QFrame()
        voice_group.setObjectName("voiceGroup")
        voice_layout = QVBoxLayout(voice_group)
        voice_layout.setContentsMargins(10, 10, 10, 10)
        voice_layout.setSpacing(8)

        voice_layout.addWidget(QLabel("🔊 声音克隆"))
        voice_layout.addWidget(current_label)
        voice_layout.addWidget(status_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        # ── 检测已有音色 ─────────────────────────────────

        def _do_check_voice(sig: _VoiceTaskSignals):
            """后台线程：查询音色列表，匹配当前角色的自定义音色。"""
            import dashscope
            from dashscope.audio.tts_v2 import VoiceEnrollmentService

            char_id = settings.CURRENT_CHARACTER
            sig.status.emit("⏳ 查询中...")
            dashscope.api_key = settings.ALIYUN_API_KEY
            try:
                service = VoiceEnrollmentService()
                voices = service.list_voices(page_index=0, page_size=50)
                # 同时搜角色 ID 和旧前缀 sibika（兼容之前克隆的）
                search_terms = [char_id]
                if char_id == "zhubihua":
                    search_terms.append("sibika")
                custom = [v for v in voices if any(
                    t in v.get("voice_id", "").lower() for t in search_terms
                )]
                if custom:
                    vid = custom[0]["voice_id"]
                    sig.voice_found.emit(vid)
                    sig.status.emit("✅ 找到自定义音色")
                    _set_tts_voice(vid)
                    print(f"[声音克隆] {char_id} 已切换到: {vid}")
                else:
                    sig.status.emit("❌ 未找到自定义音色，点「创建」按钮新建")
            except Exception as e:
                import traceback
                traceback.print_exc()
                sig.error.emit(f"查询失败: {e}")
            finally:
                sig.done.emit()

        check_btn = QPushButton("🔍 检测已有音色")
        check_btn.setStyleSheet("background:#e4ecf5; color:#3a5a7a; border:1px solid #c0d8ef;")
        check_btn.clicked.connect(lambda: threading.Thread(
            target=_do_check_voice, args=(voice_sig,), daemon=True
        ).start())
        btn_row.addWidget(check_btn)

        # ── 从当前角色的 wav 创建音色 ─────────────────────

        def _get_current_wav_path():
            """返回当前角色对应的 TTS 训练音频路径。"""
            profile = get_character(settings.CURRENT_CHARACTER)
            if profile:
                wav_rel = profile.get("audio_wav", "")
                if wav_rel:
                    return asset_path(wav_rel)
            return asset_path("assets", "audio", "zhubihua", "sibika.wav")

        def _do_create_voice(sig: _VoiceTaskSignals):
            """后台线程：从当前角色的 wav 创建自定义音色。"""
            import dashscope
            from dashscope.audio.tts_v2 import VoiceEnrollmentService
            from dashscope.audio.asr import Recognition

            class _NullCallback:
                def on_open(self): pass
                def on_complete(self): pass
                def on_error(self, r): pass
                def on_close(self): pass
                def on_event(self, r): pass

            wav_path = _get_current_wav_path()
            if not wav_path.exists():
                sig.error.emit(f"未找到训练音频: {wav_path}")
                return

            sig.status.emit("⏳ 处理音频中...")

            try:
                # 转 16kHz 单声道
                import wave, numpy as np
                with wave.open(str(wav_path), "rb") as w:
                    frames = w.readframes(w.getnframes())
                    sr = w.getframerate()
                    nch = w.getnchannels()
                    sw = w.getsampwidth()
                data = np.frombuffer(frames, dtype=np.int16)
                if nch > 1:
                    data = data.reshape(-1, nch).mean(axis=1).astype(np.int16)
                if sr == 48000:
                    data = data[::3]
                    sr = 16000
                # 写临时文件
                mono_path = wav_path.parent / "sibika_mono.wav"
                with wave.open(str(mono_path), "wb") as w:
                    w.setnchannels(1); w.setsampwidth(sw); w.setframerate(sr)
                    w.writeframes(data.tobytes())

                sig.status.emit("⏳ 转写音频内容...")
                dashscope.api_key = settings.ALIYUN_API_KEY
                recognition = Recognition(
                    model=settings.ASR_MODEL, callback=_NullCallback(),
                    format="wav", sample_rate=sr,
                )
                result = recognition.call(file=str(mono_path))
                preview_text = ""
                if result.status_code == 200:
                    sentences = result.get_sentence()
                    preview_text = "".join(
                        s.get("text", "") if isinstance(s, dict) else str(s)
                        for s in (sentences or [])
                    )

                sig.status.emit("⏳ 上传并克隆音色（约30秒）...")
                audio_b64 = base64.b64encode(mono_path.read_bytes()).decode("ascii")
                resp = requests.post(
                    "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization",
                    headers={
                        "Authorization": f"Bearer {settings.ALIYUN_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "voice-enrollment",
                        "input": {
                            "action": "create_voice",
                            "target_model": "cosyvoice-v2",
                            "prefix": settings.CURRENT_CHARACTER,
                            "url": f"data:audio/wav;base64,{audio_b64}",
                            "language_hints": ["ja"],
                            "max_prompt_audio_length": 30.0,
                            **({"preview_text": preview_text} if preview_text else {}),
                        },
                    },
                    timeout=120,
                )
                if resp.status_code != 200:
                    raise RuntimeError(resp.json().get("message", resp.text))

                voice_id = resp.json()["output"]["voice_id"]
                _set_tts_voice(voice_id)
                sig.voice_found.emit(voice_id)
                sig.status.emit("✅ 创建成功！")
                print(f"[声音克隆] 创建成功: {voice_id}")

                # 清理临时文件
                mono_path.unlink(missing_ok=True)
                # 启用 TTS
                if not tts.is_enabled():
                    tts._enabled = True

            except Exception as e:
                import traceback
                traceback.print_exc()
                sig.error.emit(f"创建失败: {e}")

        create_btn = QPushButton("✨ 从训练音频创建")
        create_btn.setStyleSheet("background:#4a90d9; color:white; border:none;")
        create_btn.clicked.connect(lambda: threading.Thread(
            target=_do_create_voice, args=(voice_sig,), daemon=True
        ).start())
        btn_row.addWidget(create_btn)

        voice_layout.addLayout(btn_row)

        content_layout.addWidget(voice_group)
        content_layout.addStretch()

        # ── 滚动区 + 底部按钮 ─────────────────────────────
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(20, 8, 20, 18)
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton { background: #e8ecf0; color: #5a6a7a; border: none; }
            QPushButton:hover { background: #d0d8e0; }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton { background: #4a90d9; color: white; border: none; }
            QPushButton:hover { background: #5fa3e8; }
        """)
        save_btn.clicked.connect(lambda: _save_keys(
            dialog, deepseek_input.text().strip(), aliyun_input.text().strip(),
            char_selector,
        ))
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def _save_keys(dialog: QDialog, deepseek_key: str, aliyun_key: str,
                    char_selector: QComboBox):
        """保存 API Key + 角色选择到 .env，更新运行时配置。"""
        if not deepseek_key and not aliyun_key:
            QMessageBox.warning(dialog, "提示", "至少需要填写一个 API Key")
            return

        from dotenv import set_key
        # 打包后 .env 在 exe 同级，开发模式用 find_dotenv 自动查找
        if getattr(sys, "frozen", False):
            env_path = str(Path(sys.executable).parent / ".env")
        else:
            from dotenv import find_dotenv
            env_path = find_dotenv()

        changed = False
        if deepseek_key and deepseek_key != settings.DEEPSEEK_API_KEY:
            set_key(env_path, "DEEPSEEK_API_KEY", deepseek_key)
            settings.DEEPSEEK_API_KEY = deepseek_key
            # 当前模型用 DeepSeek Key 时才刷新 AI 引擎
            if settings.MODEL_PRESETS[settings.LLM_MODEL]["api_key_env"] == "DEEPSEEK_API_KEY":
                ai.update_api_key()
            changed = True

        if aliyun_key and aliyun_key != settings.ALIYUN_API_KEY:
            set_key(env_path, "ALIYUN_API_KEY", aliyun_key)
            settings.ALIYUN_API_KEY = aliyun_key
            # TTS/ASR/RAG 每次调用都重新读取 settings，无需额外刷新
            # 但 TTS 初始化时缓存了 enabled 状态，需同步
            if tts._enabled != bool(aliyun_key):
                if hasattr(tts, '_enabled'):
                    tts._enabled = bool(aliyun_key)
            # 当前模型用 Aliyun Key 时刷新 AI 引擎（Qwen 模式）
            if settings.MODEL_PRESETS[settings.LLM_MODEL]["api_key_env"] == "ALIYUN_API_KEY":
                ai.update_api_key()
            changed = True

        if changed:
            QMessageBox.information(dialog, "完成", "API Key 已保存到 .env 文件并立即生效")
        else:
            QMessageBox.information(dialog, "提示", "Key 无变化")

        dialog.accept()

    # 设置按钮 → 配置对话框
    panel.settings_requested.connect(_show_settings)

    # ── 音频输入信号串联 (Phase 4) ─────────────────────────

    # 录音按钮 → 引擎
    panel.mic_toggled.connect(audio.toggle_recording)

    # 录音状态 → 更新按钮外观 + 角色状态
    audio.recording_started.connect(panel.set_recording_state)
    audio.recording_started.connect(lambda: _set_character_state("listening"))
    audio.recording_stopped.connect(panel.set_recording_state)
    audio.recording_stopped.connect(lambda: _set_character_state("idle"))

    # 转写结果 → 填入输入框
    audio.transcription_complete.connect(panel.set_transcribed_text)

    # ASR 错误 → 聊天区显示
    audio.transcription_error.connect(panel.show_error)

    # 关闭面板时取消录音
    panel.panel_closed.connect(audio.cancel_recording)

    # ── 运行 ─────────────────────────────────────────────
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
