# HeartChat — AI 桌宠项目建造文档

> 本文档记录项目的架构决策、实现进度和代码约定。每次续写项目前先阅读此文件。

---

## 项目概览

一个运行在 Windows 桌面的 AI 桌宠程序，以立绘形式展示角色「朱比华」。支持文字聊天（Phase 1）、语音回复（Phase 2）、RAG 专属问答（Phase 3）、语音输入（Phase 4）。

---

## 技术栈

| 模块 | 选型 | 备注 |
|------|------|------|
| GUI | PySide6 (Qt6) | 透明无边框窗口、信号机制 |
| LLM | DeepSeek API / 千问 Qwen（阿里云百炼） | OpenAI SDK 兼容，流式调用，设置可切换 |
| ASR（Phase 4） | 千问 Paraformer（阿里云百炼） | 录音 → 文字 |
| TTS（Phase 2） | 千问 CosyVoice v3.5 Flash（阿里云百炼） | 文字 → 语音，v3.5-flash，支持自定义端点 |
| Embedding（Phase 3） | 千问 text-embedding-v3（阿里云百炼） | 文本 → 向量 |
| RAG 向量库（Phase 3） | ChromaDB（本地） | 存 .xlsx 问答对 |
| RAG 数据源（Phase 3） | .xlsx 一问一答 | 问题/答案两列 |
| 配置 | .env + config/settings.py | python-dotenv 加载 |

> 全部 API 云端调用，无本地模型。

---

## 目录结构

```
/
├── CLAUDE.md                       # 本文件 — 项目建造文档
├── 架构方案_AI桌宠朱比华.md         # 完整架构方案
├── .env                            # API Key & 端点（手动创建）
├── requirements.txt                # Python 依赖
├── main.py                         # 应用入口
│
├── config/
│   ├── settings.py                 # 读取 .env，全局配置对象
│   └── characters.py               # (Phase 5) 角色档案定义（朱比华/夜乃樱）
│
├── core/
│   ├── ai_engine.py                # LLM 对话管理（DeepSeek / Qwen，模型预设可切换）
│   ├── rag_engine.py               # (Phase 3) ChromaDB + .xlsx
│   ├── tts_engine.py               # (Phase 2) CosyVoice API
│   └── audio_input.py              # (Phase 4) 录音 + ASR
│
├── ui/
│   ├── pet_window.py               # 透明桌面主窗口
│   ├── character_widget.py         # 立绘渲染
│   ├── chat_panel.py               # 聊天气泡窗
│   ├── drag_controller.py          # (Phase 1 内嵌在 pet_window)
│   └── audio_indicator.py          # (Phase 4 内联在 chat_panel)
│
├── data/
│   ├── vector_store/               # ChromaDB 持久化
│   ├── source/
│   │   ├── zhubihua/               # 朱比华知识库 xlsx
│   │   └── sakuya/              # 夜乃樱知识库 xlsx
│   └── chat_history/
│
├── assets/
│   ├── sprites/
│   │   ├── zhubihua/               # 朱比华丽绘
│   │   └── sakuya/              # 夜乃樱立绘
│   ├── audio/
│   │   ├── zhubihua/               # 朱比华 TTS 训练 wav
│   │   └── sakuya/              # 夜乃樱 TTS 训练 wav
│   └── styles/                     # QSS 样式表
│
└── utils/
    └── resource_helper.py          # 路径解析工具
```

---

## 开发阶段

### ✅ Phase 1 — MVP 核心对话（已完成）

**目标**：点击桌宠 → 打字 → DeepSeek 回复 → 看到文字

| 文件 | 状态 | 说明 |
|------|:----:|------|
| `CLAUDE.md` | ✅ 完成 | 本文件 |
| `架构方案_AI桌宠朱比华.md` | ✅ 完成 | 完整方案文档 |
| `.env` | ⏳ 需手动创建 | 复制 `.env.template` 并填入 Key |
| `requirements.txt` | ✅ 完成 | 核心依赖 |
| `.env.template` | ✅ 完成 | 环境变量模板 |
| `main.py` | ✅ 完成 | 应用入口，信号串联 |
| `config/settings.py` | ✅ 完成 | .env 加载+启动校验 |
| `ui/pet_window.py` | ✅ 完成 | 200×300 透明+置顶+可拖拽+托盘 |
| `ui/character_widget.py` | ✅ 完成 | 加载 `sipika.png` + QPainter 占位回退 + 状态指示器（idle/talking/listening） |
| `utils/resource_helper.py` | ✅ **新增** | 基于 `__file__` 的资产路径解析工具 |
| `ui/chat_panel.py` | ✅ 完成 | 失焦关闭+✕按钮+Enter发送+流式显示 |
| `core/ai_engine.py` | ✅ 完成 | LLM 流式对话+历史管理（DeepSeek / Qwen 可切换） |

### ✅ Phase 2 — 语音输出（已完成）

**目标**：AI 回复的同时，用千问 CosyVoice 播放语音。

**日语语音改造（2026-06）**：
- AI 回复文字：**中文**（显示在聊天区）
- TTS 语音输出：**日语**（听到的是日文语音）
- 流程（2026-06-07 合并优化）：LLM **一次流式输出双语** → 解析 `【显示】`/`【语音】` → 中文 typewriter 显示 + 日语直达 TTS
- 不再需要独立的翻译 LLM 调用（删除了 `translate_to_japanese()`）

| 文件 | 状态 | 说明 |
|------|:----:|------|
| `core/tts_engine.py` | ✅ **新建** | CosyVoice API + QMediaPlayer 播放 |
| `core/ai_engine.py` | ✅ **修改** | 新增 `tts_text_ready` 信号、`parse_bilingual()` 解析 |
| `ui/chat_panel.py` | ✅ 修改 | 添加 TTS 播放状态指示条；typewriter 伪流式显示 |
| `ui/pet_window.py` | ✅ 修改 | 聊天面板改为启动时创建（非懒加载） |
| `main.py` | ✅ 修改 | 串联 AI → 翻译 → TTS，文本等语音就绪后再显示 |
| `requirements.txt` | ✅ 修改 | 启用 dashscope SDK、requests 依赖 |

**同步机制（2026-06-07 合并改造后 — 信号驱动同步）**：
- LLM 流式输出双语文本（含 `【显示】`/`【语音】` 标签），引擎缓存不显示
- AI 回复完成后 → `parse_bilingual()` 解析出中文（显示用）和日语（TTS 用）
- **中文** → 缓存起来，等 `tts.play_started` 信号或 8s 超时 → typewriter 逐字显示（70ms/字）
- **日语** → 直接送 CosyVoice TTS（不需要翻译步骤）
- 文字和语音**同步出现**：`on_tts_ready` 同时触发文字显示 + 说话指示条
- 格式解析失败时降级：整段当中文显示，日语留空（TTS 静默跳过）
- TTS 出错时也强制显示文字，不卡住

**关键修复（2026-06-07）**：
- 历史存原始带标签文本，而非仅中文 → 修复第二轮起 TTS 不出声（模型看不到格式示例）
- `nonlocal _pending_display + _display_shown` 防重复显示
- typewriter 速度 70ms/字（约 14 字/秒）
- 加载动画从 `on_send` 持续到文字出现

**音色克隆**：
- 自定义音色 ID：`cosyvoice-v2-sibika-20bd078d46f545f98c35458cf8ec4d4b`
- 克隆方式：用户提供 38s WAV 音频 → base64 data URL 内联传入 `create_voice` API
- 踩坑：`create_voice` 的 `url` 参数不支持带 STS 签名的 OSS URL（403），改用 `data:audio/wav;base64,...` 绕过

**已知踩坑**：
- `dashscope` SDK 的 `SpeechSynthesizer` 要求 `format` 参数为 `AudioFormat` 枚举（如 `AudioFormat.MP3_22050HZ_MONO_256KBPS`），传字符串 `"mp3"` 会报 `AttributeError: 'str' object has no attribute 'sample_rate'`
- TTS 需要在 `.env` 配置 `ALIYUN_API_KEY`
- 无 Key 时 TTS 静默跳过，文字直接显示
- `VoiceEnrollmentService.create_voice()` 的 `url` 参数必须可公网访问，或直接用 `data:` URL 内联 base64

### ✅ Phase 3 — RAG 知识库（已完成）

**目标**：从 `.xlsx` 加载知识库，嵌入 ChromaDB，对话前检索相关知识注入 AI。

**已知踩坑**：
- ChromaDB `get_collection()` 在 collection 不存在时抛 `chromadb.errors.NotFoundError`，不是 `ValueError`
- dashscope `TextEmbedding.call()` 的 `response.output` 是 dict 类型，需用 `["embeddings"]` 而非 `.embeddings`
- Embedding 依赖（pandas, openpyxl）必须安装在项目 `.venv` 下，用 `uv pip install`
- 千问 text-embedding-v3 API 的 batch size 上限为 **10**，`BATCH_SIZE` 设为 20 会报 `InternalError.Algo.InvalidParameter`

| 文件 | 状态 | 说明 |
|------|:----:|------|
| `core/rag_engine.py` | ✅ **新建** | xlsx → Embedding(千问 text-embedding-v3) → ChromaDB → 检索 |
| `main.py` | ✅ 修改 | 启动时初始化 RAG，`on_send` 中检索并注入 context |
| `core/rag_engine.py` | ✅ 修改 | BATCH_SIZE 20→10（千问 text-embedding-v3 API 上限） |
| `data/source/zhubihua/朱比华知识库.xlsx` | ✅ 重建 | 23 条完整问答对（基于完整角色资料） |
| `data/source/sakuya/夜乃樱知识库.xlsx` | ✅ 新建 | 21 条完整问答对（基于完整角色资料） |

**检索机制**：
- 每次用户发送消息时，`rag.query(text)` 将问题转为向量
- ChromaDB 检索 top-3 最相关的问答对
- 结果格式化为 `Q: ...\nA: ...` 注入 AI 的 system prompt
- 无 xlsx 文件时 RAG 静默禁用，不影响聊天

**依赖**：`chromadb>=0.5` `pandas>=2.0` `openpyxl>=3.1`

### ✅ Phase 4 — 语音输入（已完成）

**目标**：点击录音按钮 → 说话 → 千问 Paraformer ASR 转写 → 文字填入输入框。

| 文件 | 状态 | 说明 |
|------|:----:|------|
| `core/audio_input.py` | ✅ **新建** | `AudioInputEngine(QObject)`: sounddevice 录音 + Paraformer ASR（dashscope） |
| `ui/chat_panel.py` | ✅ 修改 | 添加 🎤 录音按钮、脉冲动画、`mic_toggled` 信号、`set_transcribed_text()` |
| `main.py` | ✅ 修改 | 导入、实例化、串联 6 个信号（toggle/started/stopped/complete/error/cancel） |
| `ui/audio_indicator.py` | ⏭️ **内联** | 录音状态直接通过按钮变色 + 脉冲动画实现 |

**交互流程**：
- 点击 🎤 → 按钮变红脉冲 → 开始录音（sounddevice InputStream, 16kHz PCM）
- 点击 🔴 → 停止录音 → PCM 临时文件 → `Recognition.call()` → 转写结果填入输入框
- 错误时在聊天区显示红色提示

**已知踩坑**：
- `dashscope.audio.asr.Recognition.call()` 接收文件路径（`str`），不是裸字节，需先写临时 PCM 文件
- `Recognition.__init__` 强制要求 `callback` 参数，传 `RecognitionCallback` 子类，定义一个空实现的 `_NullCallback`
- PyAudio 在 Python 3.14 无预编译 wheel，改用 `sounddevice`（纯 C 扩展有 wheel）
- `result.get_sentence()` 返回 `list[dict]`，每个 dict 有 `"text"` 键
- 临时文件存 `tempfile.NamedTemporaryFile`，用完 `unlink(missing_ok=True)` 清理
- 录音超时 30 秒自动停止

### ✅ Phase 5 — 多角色切换（已完成）

**目标**：设置中可切换朱比华 ↔ 夜乃樱，角色独立立绘/人设/语音/知识库。

| 文件 | 状态 | 说明 |
|------|:----:|------|
| `config/characters.py` | ✅ **新建** | 角色档案注册表，含 system prompt / 立绘 / 语音 / RAG |

**角色人设完善（2026-06）**：
- 朱比华 system prompt → 从「可爱桌宠精灵」重写为风之一族末裔（外冷毒舌×百年漂泊×宿命牺牲）
- 夜乃樱 system prompt → 从「温柔优雅少女」重写为学园学生会长（冷峻会长×缺爱偏执×次元守护者）
- 两份 prompt 均基于完整角色资料重写，确保聊天体验符合真实人设
- RAG 知识库同步更新：朱比华 23 条（从旧 5 条测试数据重建）、夜乃樱 21 条（从空白新建）
| `config/settings.py` | ✅ 修改 | 加 CURRENT_CHARACTER 字段持久化到 .env |
| `core/ai_engine.py` | ✅ 修改 | system prompt 改为动态，加 set_character() 清历史 |
| `core/rag_engine.py` | ✅ 修改 | 加 switch_to_character() 切换 collection |
| `ui/character_widget.py` | ✅ 修改 | 支持 set_character() 动态切换立绘+名称 |
| `ui/chat_panel.py` | ✅ 修改 | 标题栏和发送者名动态化，加 set_character()/clear_all() |
| `ui/pet_window.py` | ✅ 修改 | 加 set_character() 动态更新窗口标题和托盘提示 |
| `main.py` | ✅ 修改 | _switch_character() 串联引擎+UI，设置对话框加角色下拉框 |

**资产目录结构变更**：
- `assets/sprites/sipika.png` → `assets/sprites/zhubihua/sipika.png`
- `assets/audio/sibika.wav` → `assets/audio/zhubihua/sibika.wav`
- `data/source/朱比华知识库.xlsx` → `data/source/zhubihua/朱比华知识库.xlsx`
- 新增 `assets/sprites/sakuya/`、`assets/audio/sakuya/`、`data/source/sakuya/`

**关键设计**：
- 角色 TTS 音色独立持久化：`TTS_VOICE` + `TTS_VOICE_{CHAR_ID}` 双存
- 切换时保存当前音色、恢复目标音色
- 新增角色只需在 `CHARACTERS` 字典添加一条记录
- 设置对话框角色下拉框 + 保存按钮触发切换

### ✅ Phase 6 — 文本模型切换（2026-06-04 完成）

**目标**：设置中可切换文本模型后端，支持 DeepSeek V4 Flash 与 Qwen 3.6 Plus。

| 文件 | 状态 | 说明 |
|------|:----:|------|
| `config/settings.py` | ✅ 修改 | 新增 `LLM_MODEL` 字段 + `MODEL_PRESETS` 模型预设注册表 |
| `core/ai_engine.py` | ✅ 修改 | 初始化/API刷新改为从预设读取；新增 `switch_model()` / `_init_from_preset()` |
| `main.py` | ✅ 修改 | 设置对话框加模型下拉框（即时切换）；`_save_keys` 联动刷新 |
| `.env.template` | ✅ 修改 | 新增 `LLM_MODEL=deepseek-flash` |
| `.env` | ✅ 修改 | 新增 `LLM_MODEL=deepseek-flash` |

**模型预设**：

| Preset ID | 显示名 | API Key | Base URL | 模型名 |
|-----------|--------|---------|----------|--------|
| `deepseek-flash` | DeepSeek V4 Flash + CosyVoice V3.5 Flash | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` | `deepseek-v4-flash` |
| `qwen3.5-flash` | Qwen 3.5 Flash + CosyVoice V3.5 Flash | `ALIYUN_API_KEY` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.5-flash` |

**关键设计**：
- 模型预设定义在 `settings.MODEL_PRESETS`，新增模型只需加一条记录
- `ai_engine.py` 通过 `_init_from_preset()` 统一初始化，不硬编码任何模型
- 设置对话框下拉框即时切换（不等保存），切换自动清对话历史
- Qwen 模型复用 `ALIYUN_API_KEY`（Dashscope OpenAI 兼容端点），无需额外配置

**已知踩坑**：
- DeepSeek 旧模型名 `deepseek-chat` / `deepseek-reasoner` 将于 2026-07-24 停用，`deepseek-flash` 预设直接使用新名 `deepseek-v4-flash`
- Qwen 的 OpenAI 兼容端点是 `dashscope.aliyuncs.com/compatible-mode/v1`，不是 `/api/v1`
- 切换模型时 `ai.switch_model()` 自动调用 `clear_history()`，避免跨模型上下文混用

### ✅ Phase 7 — 合并回答+翻译 + 动画行为优化（2026-06-07）

**目标**：LLM 一次输出双语，删除独立翻译步骤；优化立绘动画循环行为。

| 文件 | 状态 | 说明 |
|:----:|:----:|:------|
| `core/ai_engine.py` | ✅ 修改 | 新增 `tts_text_ready` 信号 + `parse_bilingual()`；删除 `translate_to_japanese()`；历史存原始标签文本 |
| `ui/chat_panel.py` | ✅ 修改 | typewriter 伪流式（70ms/字）；`_on_close`/`clear_all` 停 typewriter 定时器 |
| `ui/character_widget.py` | ✅ 修改 | `think` 动画第一次播完 0→89 帧，之后从 45 帧循环（跳过抬手动作） |
| `main.py` | ✅ 修改 | 删除 `on_chunk`/`_pending_reply`/`_translate_and_speak()`/`_calc_tts_delay()`；新增 `on_tts_text()`/`_show_display_text()` 信号驱动同步 |

**管道变化**：
```
改前：LLM 生成中文 → translate_to_japanese() → TTS
                                         ↑ 第二次 API 调用
改后：LLM 一次流式双语 → parse_bilingual() → TTS（日语）
                                          → typewriter 显示（中文，等 TTS play_started 或 8s 超时）
```

**思考动画行为**：
- `think` 动画共 90 帧，第一次完整播放抬手→托腮
- 播完后从第 45 帧循环（仅托腮阶段，不再重复抬手动作）
- `hair`/`talking`/`blink` 正常 0→全帧无限循环

**状态流**：
```
发送 → thinking（抬手托腮动画）
  ↓
AI 完成 → 保持 thinking（不提前 idle）
  ↓
TTS 开始 → talking（说话口型）
  ↓
TTS 结束 → idle（头发飘动循环）
  │
  ├─ TTS 不可用/无日语 → idle（文字显示时）
  └─ 出错 → idle

---

## 立绘动态化方案（gaijin.md 合并）

**场景约束**：每个角色一张 PNG 立绘，控件 200×300，PySide6 QPainter 渲染。

### 四种方案横评

| 方案 | 互动性 | 画质/自然度 | 素材成本 | 开发量 | 运行时 |
|:----:|:------:|:-----------:|:--------:|:-----:|:------:|
| **A 全图微变换** | ⭐ | ⭐⭐ | 0 | 几小时 | 极低 |
| B 分层动画 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 高（切图） | 低~中 | 低 |
| **C 预渲染帧** | ⭐⭐ | ⭐⭐⭐⭐⭐ | 高（AI 生成） | 低 | 极低 |
| D AI 实时 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 0 | 极高 | 极高 |

**实际选用**：**方案 C**（预渲染帧序列）—— AI 离线生成动画帧，QTimer 30fps 播放。

### ✅ 方案 C — 夜乃樱动画（已完成）

| 动画 | 帧数 | 时长 | 说明 |
|:----:|:----:|:----:|:------|
| `talking/` | 90 | 3s | 说话口型循环 |
| `hair/` | 120 | 4s | 头发飘动空闲循环 |
| `blink/` | 90 | 3s | 眨眼序列循环 |
| `think/` | 90 | 3s | 抬手托腮，第一次完整播，之后 45~89 循环 |

### ✅ 方案 C — 朱比华动画（2026-06-28 生成）

| 动画 | 帧数 | 时长 | 说明 |
|:----:|:----:|:----:|:------|
| `talking/` | 90 | 3s | 说话口型 |
| `hair/` | 120 | 4s | 白发飘动空闲循环 |
| `blink/` | 90 | 3s | 眨眼序列 |
| `think/` | 90 | 3s | 偏头发呆，第一次完整播，之后 45~89 循环 |

**踩坑**：
- think 初次提示词含「輕輕嘆氣」触发内容审核（GreenNet），改为「靜靜發呆」后通过
- 生成脚本 `generate_animation_frames.py` 改 `CHARACTER="zhubihua"` 后直接跑通，无需改代码

### 小游戏集成

小游戏（贪吃蛇等）建议**直接 PySide6 重写集成到桌宠进程**，通信零成本、零依赖。仅在 3D 大作时走独立进程 + IPC。

**关键结论**：问题是「游戏是桌宠的一部分还是桌宠旁边的独立伙伴」——集成到桌宠体验一体，独立进程技术栈自由但通信是持续维护负担。

---

### ✅ Phase 8 — 小游戏系统（2026-06-16 完成）

**目标**：贪吃蛇移植到 PySide6 QPainter，集成到桌宠进程，预留角色语音联动接口。

**三级结构**：
```
🎮 按钮（聊天面板 ✕ 下方）
  └→ Page 0: GameLauncher（游戏列表，目前仅贪吃蛇）
       └→ Page 1: GameConfig（模式/颜色配置）
            └→ Page 2: GamePlay（开玩 + 顶部信息栏）
```

| 文件 | 状态 | 说明 |
|:----:|:----:|:------|
| `ui/games/__init__.py` | ✅ **新建** | 导出 GameBase + GameWindow |
| `ui/games/game_base.py` | ✅ **新建** | GameBase 基类：start/stop/pause 生命周期 + `game_event` 信号 |
| `ui/games/game_window.py` | ✅ **新建** | GameWindow（resizable + maximize）：列表页 → 配置页 → 游戏页 |
| `ui/games/snake_game.py` | ✅ **新建** | 贪吃蛇完整移植：5 种模式、射击机制、8 色选择、最高分持久化 |
| `ui/chat_panel.py` | ✅ **修改** | 新增 `game_requested` 信号 + ✕ 下方 🎮 按钮 |
| `main.py` | ✅ **修改** | 创建 GameWindow，连接游戏按钮，预留 `game_event` 连线位 |

**游戏注册表**（`game_window.py` 的 `GAMES` 列表）：
```python
GAMES = [
    {
        "id": "snake",
        "name": "贪吃蛇",
        "icon": "🐍",
        "description": "经典贪吃蛇 · 射击模式 · 极限挑战",
        "class": SnakeGame,
    },
    # 新游戏在此加一条记录
]
```

**语音联动接口**（已预留，角色 TTS 后续接入）：
- `GameBase.game_event` 信号，事件类型：`game_over` / `food_eaten` / `enemy_killed`
- `main.py` 中有 `# game_window.game_event.connect(...)` 注释位

**修复踩坑**：
- 方法名 `_game_over` 与属性 `self._game_over` 重名 → 方法改名 `_handle_game_over`
- 窗口固定大小 → 改为 `resize(540, 640)` + `setMinimumSize(440, 520)`，支持缩放最大化

### ✅ Phase 8.1 — 游戏语音联动 + 音效系统（2026-06-26）

**目标**：游戏事件触发角色语音（带缓存复用），贪吃蛇带背景音乐和音效。

**游戏语音**（缓存复用）：
| 机制 | 说明 |
|:----|:------|
| 首次触发 | TTS API 合成 → 存 `assets/audio/game_voices/{label}.mp3` |
| 后续触发 | 直接本地播放，零延迟，不依赖网络 |
| 缓存文件名 | 可读命名如 `game_opened_tsukiau.mp3`、`game_over_shikatanai.mp3` |

**游戏音效**（`ui/games/sfx.py` — `GameSFX` 类）：
- 首次运行 numpy 自动合成 WAV，缓存到 `assets/audio/game_sfx/`
- BGM（4s 循环）/ 吃食物 / 射击 / 命中 / 失败 五种音效
- BGM 由用户自定义文件，代码不覆盖
- 版本号控制（`_SFX_VERSION` + `_version.txt`），修改后自动重新生成

**角色话术联动**：
- 夜乃樱风格话术：简洁冷淡、不撒娇、自然日语
- 概率控制：game_opened/started/over 100%，food_eaten 12%，enemy_killed 25%

| 文件 | 状态 | 说明 |
|:----:|:----:|:------|
| `core/tts_engine.py` | ✅ 修改 | 新增 `speak_cached()` / `speak_from_file()`；`_request_tts()` 加 `output_path` 参数 |
| `main.py` | ✅ 修改 | 连接 `game_window.game_event` 到语音联动；话术表带 label + prob |
| `ui/games/sfx.py` | ✅ **新建** | GameSFX 音效播放器 + numpy WAV 合成 |
| `ui/games/snake_game.py` | ✅ 修改 | 集成 SFX 触发点（BGM、eat、shoot、hit、fail） |
| `ui/games/game_window.py` | ✅ 修改 | 创建 GameSFX 传给 SnakeGame |

**已知踩坑**：
- `_remove_current_file()` 原版无差别删文件 → 改为只删 `tts_*` 临时文件，不删缓存
- numpy WAV 合成需 `from __future__ import annotations` 防止无 numpy 时类型标注崩溃
- 游戏短音效 QMediaPlayer 必须在主线程操作（QTimer 回调天然在主线程）

---

### ✅ Phase 8.2 — 游戏角色语音分角色（2026-06-28 完成）

**目标**：游戏语音话术和缓存按角色分立，切换角色时自动跟随。

| 文件 | 状态 | 说明 |
|:----:|:----:|:------|
| `config/characters.py` | ✅ 修改 | 每个角色新增 `game_phrases` 字段（夜乃樱/朱比华各一套） |
| `main.py` | ✅ 修改 | 移除硬编码 `_GAME_PHRASES`，改为从角色档案动态读取 |

**缓存目录结构**：
```
assets/audio/game_voices/
├── sakuya/       # 夜乃樱—冷峻学生会长风
│   ├── game_opened_nani.mp3
│   ├── game_started_tekagen.mp3
│   └── ...
├── zhubihua/      # 朱比华—毒舌百年独居风
│   ├── game_opened_hima.mp3
│   └── ...
```

**角色话术风格对比**：

| 事件 | 夜乃樱 | 朱比华 |
|:----:|--------|--------|
| game_opened | 「…何をする？」 | 「…何だよ、暇なのか？」 |
| game_started | 「手加減はしないぞ」「…始めるか」 | 「…付き合ってやるから感謝しろよ」「泣くなよ」 |
| game_over | 「…ちっ、仕方ない、もう一回だ」「次は勝つ」 | 「…ちっ、もう一勝負だ」「…次こそ本気出す」 |
| food_eaten | 「…まあ、その調子だ」「…悪くない」 | 「…ふん、まあまあだな」「…へえ」 |
| enemy_killed | 「狙いは正確だな」「…なかなかやる」 | 「…そこだ」「…なかなかやるじゃん」 |

**关键设计**：
- `_switch_character()` 中同步更新 `_current_game_phrases` 和 `_current_game_voice_cache`
- 缓存目录自动创建 `game_voices/{character_id}/`
- 话术表可设 `prob`（触发概率），`game_opened/started/over` 100%，`food_eaten` 12%，`enemy_killed` 25%
- 新角色只需在 `characters.py` 加 `game_phrases` 即可

---

### Phase 9 — TTS 模型升级 + 声音克隆管理（2026-06-26，进行中）

**目标**：从 CosyVoice v2 升级到 v3.5-flash，完善声音克隆管理 UI。

| 文件 | 状态 | 说明 |
|:----:|:----:|:------|
| `config/settings.py` | ✅ 修改 | 默认模型 `cosyvoice-v2` → `cosyvoice-v3.5-flash`；新增 `TTS_WS_URL`/`TTS_HTTP_URL` 自定义端点 |
| `core/tts_engine.py` | ✅ 修改 | 合成前设置 dashscope 自定义端点（如有配置）；dashscope SDK 版本兼容 |
| `main.py` | ✅ 修改 | 声音克隆 `target_model` 改为动态读取 `settings.TTS_MODEL`；创建后轮询状态（`query_voice`，最多 30 次 10s 间隔）；检测音色优先选 model 版本一致的；多个音色弹出选择框供手动选取；新增删除音色功能 |
| `.env.template` | ✅ 修改 | 更新默认 TTS_MODEL，加端点注释 |
| `.env` | ✅ 修改 | TTS_MODEL、TTS_VOICE、角色专属 voice ID 同步更新 |

**声音克隆选择框**：
- `_VoiceTaskSignals` 新增 `show_picker` 信号（`Signal(list)`），后台线程查完列表后通过信号发回主线程
- `_show_voice_picker()` 主线程处理：1 个自动切 / 多个弹框选 / 选中可删除
- 删除调用 `VoiceEnrollmentService.delete_voice()`，确认后才执行，列表实时刷新

**已知踩坑**：
- `cosyvoice-v3.5`（无后缀）不是有效模型名，DashScope WebSocket 直接断连
- v2 克隆的音色不兼容 v3.5-flash/plus，需要重新创建
- 旧版 voice ID 存于角色专属 key（`TTS_VOICE_SAKUYA`/`TTS_VOICE_ZHUBIHUA`），切换角色时自动恢复

**待定 — TTS 流式播放**（2026-06-26 讨论，❌ 已砍掉）：
- 目标：边合成边播，不等整段语音完成
- 方案 D（推荐）：streaming callback 分块写临时文件，QMediaPlayer 分块链式播放
- 方案 C：QAudioOutput + PCM 直喂，延迟最低但编码大
- 阻塞点：分块文件衔接咔哒声 / Windows 文件锁，不解决，功能砍掉

---

### ✅ Phase 9.1 — 前台窗口检测（Window Watcher）（2026-06-29）

**目标**：检测用户切换的前台窗口，角色用日语吐槽 + 中文气泡。

| 文件 | 状态 | 说明 |
|:----:|:----:|:------|
| `core/window_watcher.py` | ✅ **新建** | Win32 API 轮询前台窗口（ctypes），QTimer 2s 间隔，`window_changed` 信号 |
| `config/characters.py` | ✅ **修改** | 两个角色各一套窗口话术表（浏览器/IDE/终端/媒体/学习/游戏/兜底），`(ja, zh, label, prob)` 格式 |
| `main.py` | ✅ **修改** | 集成 watcher → 匹配规则 → 日语 TTS 缓存播放 + 中文气泡显示 |

**缓存目录**（首次 TTS API 合成后本地复用）：
```
assets/audio/window_voices/
├── sakuya/       # 夜乃樱话术缓存
└── zhubihua/     # 朱比华话术缓存
```

**关键设计**：
- 去重键 `(process_name, pid)` — 同一浏览器实例无论切标签不重复播，关了重开才再次触发
- 分类规则 prob=1.0，匹配必触发；兜底低概率不吵
- 角色切换时话术和缓存目录自动跟随

### ✅ Phase 9.2 — 屏幕边缘吸附隐藏（2026-06-29）

**目标**：拖拽桌宠到屏幕边缘吸附隐藏，留 50px 耳朵，点击弹出。

| 文件 | 状态 | 说明 |
|:----:|:----:|:------|
| `ui/pet_window.py` | ✅ **修改** | 新增 `_check_edge_dock()`/`_dock_to_edge()`/`_undock()`/`_animate_to()` |

**关键设计**：
- 边缘检测阈值 15px，拖到屏幕边缘触发
- QPropertyAnimation 200ms OutCubic 滑出/滑入
- 吸附时聊天面板自动隐藏
- 点击耳朵取消吸附，同一次点击可继续拖拽
- `_normal_pos` 记录吸附前位置，`_save_position()` 吸附时存正常位置
- 托盘菜单「显示/隐藏」也触发取消吸附

### ✅ Phase 9.3 — 动画循环优化 + 游戏 BGM/气泡（2026-06-29）

**目标**：动画帧首尾一致解决瞬移，BGM 提前到选模式时播放，游戏事件加中文气泡。

| 文件 | 状态 | 说明 |
|:----:|:----:|:------|
| `generate_animation_frames.py` | ✅ **修改** | hair/blink/talking/think 全部加「首尾帧一致，形成無縫循環」；think 改為抬頭+八字擋嘴；API 參數 `media`→`img_url`（適配新 SDK） |
| `ui/character_widget.py` | ✅ **修改** | 新增 crossfade 过渡（切换动画时 133ms 淡入淡出消除瞬移） |
| `ui/games/game_window.py` | ✅ **修改** | BGM 从 SnakeGame.start() 提前到 `_on_game_selected()`（配置页即播放）；返回列表时 stop_bgm |
| `config/characters.py` | ✅ **修改** | 游戏话术每条加 `zh` 字段（中文气泡）；media 规则加 `kugou/qqmusic/cloudmusic` 匹配国内音乐软件；新增音乐专用话术 |
| `main.py` | ✅ **修改** | `_get_game_phrase` 返回 3 值（含 `zh`）；`_on_game_event` 调 `show_bubble()` |

**关键设计**：
- 游戏事件触发时：日语 TTS + 中文气泡同步（复用 `show_bubble` 窗口吐槽机制）
- BGM 流程：选游戏 → 配置页即播 BGM → 开始游戏继续 → 返回列表停止
- 窗口检测新增国内音乐软件支持，话术区隔视频/音乐

---

## 已确认的需求

| # | 问题 | 结论 |
|:-:|------|------|
| 1 | 默认音色 | 先用 `longxiaochun` 跑通，后续提供原声再克隆 |
| 2 | 立绘素材 | 先用 QPainter 绘制占位图，后续替换 PNG |
| 3 | 窗口尺寸 | 200×300 |
| 4 | 聊天框样式 | 全部消息在左侧（聊天室风格） |
| 5 | 关闭方式 | 加 ✕ 关闭按钮 |
| 6 | 动画帧 | Phase 1 纯静态，后续再加 |

---

## 代码约定

### 命名规范
- 文件名：`snake_case.py`
- 类名：`PascalCase`
- 函数/方法：`snake_case`
- 常量：`UPPER_SNAKE_CASE`

### PySide6 约定
- UI 组件用 Qt 内置信号/槽机制
- 跨线程通信统一用 `Signal`（`pyqtSignal`）
- 耗时操作（网络请求）放在 `threading.Thread` 后台线程，通过 Signal 回传结果
- 不使用 `QThread` 子类化，而是用 `QObject` worker + `QThread` 或 `threading.Thread`

### 信号命名
- `{subject}_{action}`：`text_chunk`, `response_finished`, `error_occurred`

### 错误处理
- 网络异常 → emit `error` 信号 → UI 显示友好提示
- API Key 缺失 → 启动时 `settings.validate()` 直接报错
- 任何模块不应阻塞主线程 UI

### 数据流模式
```
用户输入 → [UI 层 emit signal] → [Core 层后台处理] → [Core 层 emit signal] → [UI 层更新]
```

---

## 关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| LLM | DeepSeek（默认）/ Qwen 可切换 | DeepSeek 价格低角色扮演强，Qwen 阿里云免费额度可用，设置可随时切换 |
| 语音输入路径 | ASR → 文字 → LLM | DeepSeek 不支持音频多模态，必须走 ASR |
| TTS | 千问 CosyVoice | 中文效果好，支持声音克隆，与阿里云其他服务统一 |
| RAG 向量库 | ChromaDB（本地） | 轻量、纯 Python、无需额外服务 |
| 嵌入模型 | 千问 text-embedding-v3（API） | 只用 API，不本地部署 |
| 配置 | .env + settings.py | 统一管理密钥，不硬编码，不提交 |
| 立绘渲染 | 帧序列动画（QTimer 30fps） | 方案 C 预渲染帧，效果最自然且运行时开销极低 |
| 动画方案 | 方案 C（预渲染帧序列） | AI 离线生成，QTimer 定时换帧；think 动画 45 帧循环 |
| 聊天框 | 独立顶层窗口 | 避免父窗口裁剪，便于定位管理 |
| 小游戏集成 | PySide6 重写（同一进程） | 通信零成本、零额外依赖；仅在 3D 大作走 IPC |

---

## 运行方式

```bash
# 1. 安装依赖（使用 uv）
uv sync

# 2. 创建 .env 文件（从下方模板复制）
#    填入你的 API Key

# 3. 启动
python main.py
```

### 打包（PyInstaller）

```bash
# 安装 PyInstaller
uv pip install pyinstaller

# 打包 + 自动复制 readme
pyinstaller --onedir --windowed --name "HeartChat" ^
  --add-data "assets;assets" ^
  --add-data "data/source;data/source" ^
  --add-data ".env.template;." ^
  --distpath "D:\demoexe" ^
  main.py && ^
copy readme.txt D:\demoexe\HeartChat\
```

打包后结构：
```
D:\demoexe\HeartChat/
├── HeartChat.exe
├── readme.txt       ← 使用说明
├── .env             ← 用户在此创建/编辑
│
└── _internal/
    ├── ...
    └── .env.template   ← 首次运行自动生成 .env
```

### .env 模板

```dotenv
DEEPSEEK_API_KEY=sk-你的key
DEEPSEEK_BASE_URL=https://api.deepseek.com

ALIYUN_API_KEY=sk-你的阿里云百炼key
ALIYUN_BASE_URL=https://dashscope.aliyuncs.com/api/v1

ASR_MODEL=paraformer-realtime-v2
TTS_MODEL=cosyvoice-v3.5-flash
TTS_VOICE=longxiaochun_v2

# CosyVoice 自定义端点（专属实例，留空用默认）
# TTS_WS_URL=wss://xxx.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference
# TTS_HTTP_URL=https://xxx.cn-beijing.maas.aliyuncs.com/api/v1

EMBEDDING_MODEL=text-embedding-v3

VECTOR_STORE_PATH=./data/vector_store
XLSX_PATH=./data/source/zhubihua/朱比华知识库.xlsx

# 角色专属 TTS 音色（由切换逻辑自动管理）
# TTS_VOICE_ZHUBIHUA=cosyvoice-v3.5-flash-xxx
# TTS_VOICE_SAKUYA=cosyvoice-v3.5-flash-xxx
CURRENT_CHARACTER=sakuya

# 文本模型选择（deepseek-flash / qwen3.5-flash）
LLM_MODEL=deepseek-flash
```

---

## 依赖清单

```
PySide6>=6.6
openai>=1.0
python-dotenv>=1.0
dashscope>=1.20          # Phase 2 — CosyVoice TTS
chromadb>=0.5            # Phase 3
pandas>=2.0              # Phase 3
openpyxl>=3.1            # Phase 3
requests>=2.31           # Phase 2+
sounddevice>=0.5         # Phase 4（替代 pyaudio，Python 3.14 无 pyaudio wheel）
numpy>=1.24              # Phase 4
```
