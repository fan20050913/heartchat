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
| TTS（Phase 2） | 千问 CosyVoice（阿里云百炼） | 文字 → 语音，先用默认音色 longxiaochun |
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
- 流程：AI 回复中文 → **DeepSeek 翻译为动漫日语** → 自定义克隆音色合成日语语音
- TTS 生成期间聊天区显示加载动画 。→ 。。→ 。。。→ 。。。。循环

| 文件 | 状态 | 说明 |
|------|:----:|------|
| `core/tts_engine.py` | ✅ **新建** | CosyVoice API + QMediaPlayer 播放 |
| `core/ai_engine.py` | ✅ **修改** | 新增 `translate_to_japanese()` 方法 |
| `ui/chat_panel.py` | ✅ 修改 | 添加 TTS 播放状态指示条 |
| `ui/pet_window.py` | ✅ 修改 | 聊天面板改为启动时创建（非懒加载） |
| `main.py` | ✅ 修改 | 串联 AI → 翻译 → TTS，文本等语音就绪后再显示 |
| `requirements.txt` | ✅ 修改 | 启用 dashscope SDK、requests 依赖 |

**同步机制**：
- AI 流式输出时只缓存不显示（`_pending_reply` 列表）
- AI 回复完成后 → DeepSeek 翻译为日语（后台线程）
- 翻译完成后 → 调用 CosyVoice TTS 合成日语语音
- TTS 开始播放时（`play_started` 信号）同时显示完整**中文**文字
- TTS 出错时也立即显示文字，不卡住

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
| `deepseek-flash` | DeepSeek V4 Flash + CosyVoice V2 | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` | `deepseek-v4-flash` |
| `qwen3.5-flash` | Qwen 3.5 Flash + CosyVoice V2 | `ALIYUN_API_KEY` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.5-flash` |

**关键设计**：
- 模型预设定义在 `settings.MODEL_PRESETS`，新增模型只需加一条记录
- `ai_engine.py` 通过 `_init_from_preset()` 统一初始化，不硬编码任何模型
- 设置对话框下拉框即时切换（不等保存），切换自动清对话历史
- Qwen 模型复用 `ALIYUN_API_KEY`（Dashscope OpenAI 兼容端点），无需额外配置

**已知踩坑**：
- DeepSeek 旧模型名 `deepseek-chat` / `deepseek-reasoner` 将于 2026-07-24 停用，`deepseek-flash` 预设直接使用新名 `deepseek-v4-flash`
- Qwen 的 OpenAI 兼容端点是 `dashscope.aliyuncs.com/compatible-mode/v1`，不是 `/api/v1`
- 切换模型时 `ai.switch_model()` 自动调用 `clear_history()`，避免跨模型上下文混用

**目标**：修复文字依赖 TTS 信号导致文字卡死、加载动画无限循环的问题。

| 文件 | 状态 | 说明 |
|------|:----:|------|
| `main.py` | ✅ 修改 | `on_finished()` 改为动态延时 + `QTimer` 显示文字，独立于 TTS `play_started` 信号 |
| `main.py` | ✅ 修改 | 新增 `_calc_tts_delay()` 按文本长度估算 TTS 耗时 |
| `main.py` | ✅ 修改 | 移除 `isVisible()` 守卫，关面板后后台继续跑 |
| `ui/chat_panel.py` | ✅ 修改 | `_on_close()` 停加载动画；新增 `showEvent()` 重新渲染 |

**文字显示逻辑**：
```
AI完成 → 按文本长度算延时 → QTimer → 显示文字（独立于 TTS）
       → 后台翻译 → TTS → 播放语音（文字已出，语音随缘）
```

**延时公式**：`delay = min(10000, max(3500, int(3000 + text_len * 70)))`（单位 ms）
- 短文本（10字）~3.7s，长文本（100字）~10s 封顶
- 系数可根据实际 TTS 语速调整

**安全特性**：
- 文字不再等 TTS 信号，不会因 TTS 卡死而无法显示
- 关面板时只停动画，后台翻译/TTS 继续运行
- 再开面板时 `showEvent` 触发重新渲染

**待优化**：TTS 语音有时只念开头（可能 CosyVoice 长度限制或翻译截断），当前未修

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
| 立绘渲染 | QPainter 直接绘制 | Phase 1 不依赖外部图片文件 |
| 聊天框 | 独立顶层窗口 | 避免父窗口裁剪，便于定位管理 |

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
TTS_MODEL=cosyvoice-v2
TTS_VOICE=longxiaochun_v2
EMBEDDING_MODEL=text-embedding-v3

VECTOR_STORE_PATH=./data/vector_store
XLSX_PATH=./data/source/zhubihua/朱比华知识库.xlsx

# 角色专属 TTS 音色（由切换逻辑自动管理）
# TTS_VOICE_ZHUBIHUA=cosyvoice-v2-xxx
# TTS_VOICE_SAKUYA=cosyvoice-v2-xxx
CURRENT_CHARACTER=sakuya

# 文本模型选择（deepseek-flash / qwen3.6-plus）
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
