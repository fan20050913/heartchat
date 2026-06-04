"""
聊天气泡窗
独立顶层窗口，半透明背景，显示对话历史+输入框+关闭按钮。
所有消息在左侧（聊天室风格），✕ 关闭。
"""

from PySide6.QtCore import Qt, Signal, QEvent, QRect, QTimer
from PySide6.QtGui import QFont, QColor, QTextCursor, QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QTextEdit, QPushButton, QFrame, QLabel, QSizePolicy,
)


class ChatPanel(QWidget):
    """聊天面板：独立窗口，显示对话+输入+关闭按钮。"""

    send_message = Signal(str)       # 用户发送文字
    panel_closed = Signal()          # 面板关闭
    mic_toggled = Signal()           # 用户点击录音按钮
    settings_requested = Signal()    # 用户点击设置按钮

    PANEL_WIDTH = 300
    PANEL_HEIGHT = 400

    def __init__(self, parent=None):
        super().__init__(parent)

        # 角色名（必须在 _init_ui 之前初始化）
        self._character_name = "朱比华"
        self._chat_title = "💬 与朱比华聊天"

        self._init_window()
        self._init_ui()

        # 记录 ai 回复是否正在流式输出
        self._streaming = False
        self._stream_buffer = ""
        self._messages: list[tuple[str, str, bool]] = []  # (sender, text, is_user)

        # 加载点动画（TTS 生成期间）
        self._loading_active = False
        self._loading_index = 0
        self._loading_dots = [".", "..", "...", "...."]
        self._loading_timer = QTimer(self)
        self._loading_timer.timeout.connect(self._on_loading_tick)

        # 录音状态
        self._is_recording = False
        self._recording_pulse = False
        self._recording_timer = QTimer(self)
        self._recording_timer.timeout.connect(self._on_recording_tick)

    # ── 窗口初始化 ────────────────────────────────────────

    def _init_window(self):
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.PANEL_WIDTH, self.PANEL_HEIGHT)

    # ── UI 构建 ───────────────────────────────────────────

    def _init_ui(self):
        # 最外层容器（浅蓝白调、圆角、半透明毛玻璃效果）
        container = QFrame(self)
        container.setObjectName("chatContainer")
        container.setStyleSheet("""
            #chatContainer {
                background: rgba(235, 245, 255, 242);
                border-radius: 14px;
                border: 1px solid rgba(180, 210, 240, 100);
            }
        """)
        container.setGeometry(0, 0, self.PANEL_WIDTH, self.PANEL_HEIGHT)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(6)

        self._build_title(layout)
        self._build_tts_indicator(layout)
        self._build_chat_area(layout)
        self._build_input_area(layout)

    def _build_title(self, parent_layout: QVBoxLayout):
        """标题栏：标题 + 关闭按钮。"""
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(6, 0, 0, 0)

        self._title_label = QLabel(self._chat_title)
        self._title_label.setStyleSheet("color: #3a5a7a; font-size: 13px; font-weight: bold;")
        title_bar.addWidget(self._title_label)

        title_bar.addStretch()

        # 设置按钮 ⚙️
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(24, 24)
        settings_btn.setStyleSheet("""
            QPushButton {
                background: rgba(180, 200, 220, 40);
                color: #7a9ab8;
                border: none;
                border-radius: 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(74, 144, 217, 100);
                color: white;
            }
        """)
        settings_btn.clicked.connect(self._on_settings)
        title_bar.addWidget(settings_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(180, 200, 220, 40);
                color: #8a9aa8;
                border: none;
                border-radius: 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #e74c3c;
                color: white;
            }
        """)
        close_btn.clicked.connect(self._on_close)
        title_bar.addWidget(close_btn)

        parent_layout.addLayout(title_bar)

    def _build_tts_indicator(self, parent_layout: QVBoxLayout):
        """TTS 播放状态指示条。"""
        self.tts_indicator = QLabel()
        self.tts_indicator.setVisible(False)
        self.tts_indicator.setFixedHeight(22)
        self.tts_indicator.setAlignment(Qt.AlignCenter)
        parent_layout.addWidget(self.tts_indicator)

    def _build_chat_area(self, parent_layout: QVBoxLayout):
        """聊天记录显示区。"""
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setStyleSheet("""
            QTextBrowser {
                background: transparent;
                border: none;
                color: #2c3e50;
                font-size: 13px;
            }
            QTextBrowser:focus { outline: none; }
        """)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        parent_layout.addWidget(self.browser, stretch=1)

    def _build_input_area(self, parent_layout: QVBoxLayout):
        """底部输入区域。"""
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 4, 0, 0)
        input_layout.setSpacing(6)

        self.input_edit = ChatInput()
        self.input_edit.setPlaceholderText("输入消息… (Enter 发送)")
        self.input_edit.setFixedHeight(44)
        self.input_edit.setStyleSheet("""
            QTextEdit {
                background: #ffffff;
                border: 1px solid #c0d8ef;
                border-radius: 10px;
                color: #2c3e50;
                font-size: 13px;
                padding: 6px 12px;
                selection-background-color: #b8d8ff;
            }
            QTextEdit:focus {
                border: 1px solid #4a90d9;
            }
        """)
        self.input_edit.send_requested.connect(self._on_send)
        input_layout.addWidget(self.input_edit, stretch=1)

        # 录音按钮
        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setFixedSize(44, 44)
        self.mic_btn.setToolTip("点击开始录音")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: #f0f4fa;
                border: 1px solid #c0d8ef;
                border-radius: 10px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: #e4ecf5;
                border: 1px solid #a8c8e8;
            }
        """)
        self.mic_btn.clicked.connect(self._on_mic_toggle)
        input_layout.addWidget(self.mic_btn)

        send_btn = QPushButton("发送")
        send_btn.setFixedSize(52, 44)
        send_btn.setStyleSheet("""
            QPushButton {
                background: #4a90d9;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #5fa3e8;
            }
            QPushButton:pressed {
                background: #3a7bc8;
            }
            QPushButton:disabled {
                background: #c0c8d0;
                color: #f0f0f0;
            }
        """)
        send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(send_btn)

        parent_layout.addLayout(input_layout)

    # ── 事件 ──────────────────────────────────────────────

    def event(self, event):
        """失焦时自动关闭（点击外面就关）。"""
        if event.type() == QEvent.WindowDeactivate:
            self._on_close()
        return super().event(event)

    def showEvent(self, event):
        """面板重新显示时重新渲染（后台可能已经跑完了）。"""
        super().showEvent(event)
        self._render_all()

    def _on_settings(self):
        """用户点击设置按钮。"""
        self.settings_requested.emit()

    def _on_close(self):
        """关闭面板：停加载动画，后台继续跑。"""
        self._stop_loading()
        self.hide()
        self.panel_closed.emit()

    def _on_send(self):
        if self._streaming:
            return  # 等待 AI 回复完才能发下一条

        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        self.input_edit.clear()

        # 显示用户消息
        self.append_message("你", text, is_user=True)

        # 发射信号交给 ai_engine
        self.send_message.emit(text)

    # ── 公开接口 ──────────────────────────────────────────

    def append_message(self, sender: str, text: str, is_user: bool = False):
        """在聊天区添加一条普通消息（非流式）。"""
        self._messages.append((sender, text, is_user))
        self._render_all()

    def start_streaming(self):
        """准备接收流式回复。"""
        self._stop_loading()
        self._streaming = True
        self._stream_buffer = ""
        self._messages.append((self._character_name, "", False))  # 占位

    def append_chunk(self, chunk: str):
        """追加流式片段，更新最后一条消息。"""
        self._stream_buffer += chunk
        if self._messages:
            self._messages[-1] = (self._character_name, self._stream_buffer, False)
        self._render_all()

    def finish_streaming(self, full_text: str):
        """流式完成，固定最后一条消息。"""
        self._stop_loading()
        self._streaming = False
        if self._messages:
            self._messages[-1] = (self._character_name, full_text, False)
        self._stream_buffer = ""
        self._render_all()

    # ── 录音按钮 ────────────────────────────────────────────

    def _on_mic_toggle(self):
        """用户点击录音按钮 → 交由 audio engine 处理。"""
        self.mic_toggled.emit()

    def set_recording_state(self, recording: bool):
        """根据录音状态更新按钮外观。"""
        self._is_recording = recording
        if recording:
            self._recording_pulse = False
            self._recording_timer.start(500)
            self.mic_btn.setText("🔴")
            self.mic_btn.setToolTip("点击停止录音")
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background: #cc0022;
                    border: 2px solid #ff4466;
                    border-radius: 10px;
                    font-size: 18px;
                }
            """)
        else:
            self._recording_timer.stop()
            self.mic_btn.setText("🎤")
            self.mic_btn.setToolTip("点击开始录音")
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background: #f0f4fa;
                    border: 1px solid #c0d8ef;
                    border-radius: 10px;
                    font-size: 18px;
                }
                QPushButton:hover {
                    background: #e4ecf5;
                    border: 1px solid #a8c8e8;
                }
            """)

    def _on_recording_tick(self):
        """脉冲动画：按钮在两个红色之间切换。"""
        self._recording_pulse = not self._recording_pulse
        bg = "#ff3344" if self._recording_pulse else "#bb0022"
        self.mic_btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: 2px solid #ff5577;
                border-radius: 10px;
                font-size: 18px;
            }}
        """)

    def set_transcribed_text(self, text: str):
        """ASR 转写结果填入输入框。"""
        self.input_edit.setPlainText(text)
        self.input_edit.setFocus()
        cursor = self.input_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.input_edit.setTextCursor(cursor)

    # ── TTS 等待加载动画 ──────────────────────────────────

    def start_loading_animation(self):
        """TTS 生成期间，循环显示 . → .. → ... → ...."""
        if self._loading_active:
            return
        self._loading_active = True
        self._loading_index = 0
        self._loading_timer.start(600)
        self._on_loading_tick()

    def _on_loading_tick(self):
        """定时器触发：更新最后一条消息为当前加载点。"""
        dots = self._loading_dots[self._loading_index % len(self._loading_dots)]
        self._loading_index += 1
        if self._messages:
            self._messages[-1] = (self._character_name, dots, False)
        self._render_all()

    def _stop_loading(self):
        """停止加载动画。"""
        self._loading_active = False
        self._loading_timer.stop()

    # ── 角色切换 ──────────────────────────────────────────

    def set_character(self, name: str, chat_title: str):
        """切换角色显示名和聊天框标题。"""
        self._character_name = name
        self._chat_title = chat_title
        if hasattr(self, "_title_label"):
            self._title_label.setText(chat_title)

    def clear_all(self):
        """清空所有消息（角色切换时用）。"""
        self._messages.clear()
        self._stream_buffer = ""
        self._streaming = False
        self.browser.clear()

    def _render_all(self):
        """重新渲染全部消息。"""
        html_parts = []
        for sender, text, is_user in self._messages:
            if is_user:
                label_color = "#4a90d9"
                bubble_bg = "#e8f2ff"
                bubble_border = "1px solid #d0e4f8"
            else:
                label_color = "#5b7ec2"
                bubble_bg = "#ffffff"
                bubble_border = "1px solid #e8ecf0"
            label = "你" if is_user else sender
            html_parts.append(f"""
            <div style="margin: 6px 0;">
                <div style="color: {label_color}; font-size: 12px; font-weight: bold; margin-bottom: 3px; padding-left: 2px;">
                    {label}
                </div>
                <div style="
                    background: {bubble_bg};
                    border: {bubble_border};
                    border-radius: 10px;
                    padding: 8px 12px;
                    color: #2d3436;
                    font-size: 13px;
                    line-height: 1.6;
                ">
                    {text}
                </div>
            </div>
            """)

        self.browser.setHtml("".join(html_parts))
        self.browser.moveCursor(QTextCursor.MoveOperation.End)
        self.browser.ensureCursorVisible()

    def show_tts_playing(self):
        """显示「正在说话」指示条。"""
        self.tts_indicator.setText(f"🔊 {self._character_name}正在说话...")
        self.tts_indicator.setStyleSheet("""
            color: #4a90d9; font-size: 11px; font-weight: bold;
            background: rgba(74, 144, 217, 20);
            border-radius: 6px; padding: 3px 8px;
        """)
        self.tts_indicator.show()

    def hide_tts_playing(self):
        """隐藏「正在说话」指示条。"""
        self.tts_indicator.hide()

    def show_error(self, message: str):
        """显示错误信息。"""
        html = f"""
        <div style="margin: 6px 0; text-align: center;">
            <div style="
                background: rgba(231, 76, 60, 30);
                border-radius: 8px;
                padding: 6px 12px;
                color: #c0392b;
                font-size: 12px;
                border: 1px solid rgba(231, 76, 60, 60);
            ">
                ⚠ {message}
            </div>
        </div>
        """
        self.browser.append(html)
        self.browser.moveCursor(QTextCursor.MoveOperation.End)
        self.browser.ensureCursorVisible()


class ChatInput(QTextEdit):
    """自定义输入框：Enter 发送，Shift+Enter 换行。"""

    send_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
            self.send_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)
