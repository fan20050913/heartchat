# 📐 AI 桌宠「朱比华」— 最终架构方案

> 最后更新：2026-06-02

---

## 一、项目概述

一个运行在 Windows 桌面的 AI 桌宠程序，以立绘形式展示角色「朱比华」，支持文字/语音聊天、语音回复、基于 Q&A 知识库的专属问答。

**编程语言**：Python 3.10+

---

## 二、技术栈选型（全部 API 云端调用，无本地模型）

| 模块 | 选型 | 用途 |
|------|------|------|
| **GUI** | PySide6 (Qt6) | 透明无边框窗口、精灵动画、事件循环 |
| **LLM 对话** | DeepSeek API | 角色对话回复 |
| **ASR 语音输入** | 千问 Paraformer（阿里云百炼） | 录音 → 文字 |
| **TTS 语音输出** | 千问 CosyVoice（阿里云百炼） | 文字 → 朱比华声线语音播放 |
| **Text Embedding** | 千问 text-embedding-v3（阿里云百炼） | 用户提问 → 向量 |
| **RAG 向量库** | ChromaDB（**纯本地**） | 存储问答对向量，本地检索 |
| **RAG 数据源** | .xlsx 一问一答文件 | 朱比华的专属知识库 |
| **配置管理** | .env + config/settings.py | 统一管理 API Key 和端点 |

> 一个阿里云百炼账号搞定 ASR + TTS + Embedding 三个服务。

---

## 三、目录结构

```
ai-desktop-pet/
│
├── .env                          # API Key & 端点（不提交 git）
├── requirements.txt              # Python 依赖
├── main.py                       # 应用入口
│
├── config/
│   └── settings.py               # 读取 .env，全局配置对象
│
├── core/
│   ├── ai_engine.py              # DeepSeek API 对话管理
│   ├── rag_engine.py             # 导入 .xlsx + ChromaDB 检索
│   ├── tts_engine.py             # CosyVoice API 语音合成+播放
│   └── audio_input.py            # 麦克风录音+调用 ASR API
│
├── ui/
│   ├── pet_window.py             # 主窗口（透明、置顶、无边框）
│   ├── character_widget.py       # 立绘渲染+动画帧
│   ├── chat_panel.py             # 聊天气泡窗（输入+显示）
│   ├── drag_controller.py        # 鼠标拖拽逻辑
│   └── audio_indicator.py        # 录音状态动画指示器
│
├── data/
│   ├── vector_store/             # ChromaDB 持久化目录（自动生成）
│   ├── source/
│   │   └── 朱比华知识库.xlsx      # 一问一答格式
│   └── chat_history/             # 对话日志（可选）
│
├── assets/
│   ├── sprites/                  # 立绘 PNG / 序列帧
│   ├── audio/                    # TTS 播放缓存（运行时临时）
│   └── styles/                   # QSS 样式表
│
└── utils/
    └── resource_helper.py        # 路径解析工具
```

---

## 四、数据流（一次完整交互）

```
┌─ ① 用户看到朱比华在桌面浮动（待机动画） ──────────────────┐
│                                                           │
├─ ② 单击朱比华 → 弹出聊天气泡窗 chat_panel ───────────────│
│     窗口内：文本输入框 + 录音按钮 + 对话历史显示区           │
│                                                           │
├─ ③ 用户输入 ──────────────────────────────────────────────│
│    ├─ 打字 → 按 Enter → 直接拿到 text                      │
│    └─ 点击录音 → 说话 → 再点停止 → PCM 音频               │
│         → 千问 Paraformer ASR API → 文字                  │
│                                                           │
├─ ④ Core 处理 ────────────────────────────────────────────│
│    ├─ rag_engine：                                         │
│    │   用户文字 → Embedding API → 向量                     │
│    │   → ChromaDB search(Top-3) → 取出最相似 Q&A 对       │
│    │                                                       │
│    ├─ ai_engine：                                          │
│    │   system prompt = 角色人设 + RAG 检索到的问答对        │
│    │   + 对话历史                                          │
│    │   user message = 用户文字                              │
│    │   → DeepSeek API 流式 → 逐字显示在 chat_panel         │
│    │                                                       │
│    └─ tts_engine（与 LLM 流式同步进行）：                     │
│        DeepSeek 回复文字 → CosyVoice API → MP3            │
│        → QMediaPlayer 播放 → 播放完自动删除临时文件         │
│                                                           │
├─ ⑤ 用户看到文字 + 听到朱比华的声音 ───────────────────────│
│                                                           │
├─ ⑥ 点击气泡外区域 → 回收聊天窗，朱比华回到待机动画 ────────│
│                                                           │
└────────────────────────────────────────────────────────────
```

---

## 五、模块详细设计

### 5.1 UI 层

#### pet_window.py
- `QWidget`，无边框 + 透明背景 + 置顶
- `FramelessWindowHint | WindowStaysOnTopHint | Tool`
- 子控件：`character_widget`（立绘）+ `chat_panel`（弹出式）
- sysTray 系统托盘（右键退出）

#### character_widget.py
- `QLabel` 或 QPainter 渲染 PNG 序列帧
- 状态机：`idle`（呼吸浮动）↔ `listening`（等待）↔ `speaking`（说话动画）

#### chat_panel.py
- `QFrame`，半透明圆角气泡
- 上部：对话历史显示（QTextBrowser / QListWidget）
- 下部：QTextEdit 输入框 + 录音按钮
- 按 Enter → emit signal，清空输入框
- 带关闭按钮（✕）

#### drag_controller.py
- `mousePressEvent` → 记录起始坐标
- `mouseMoveEvent` → `window.move()`
- `mouseReleaseEvent` → （可选边缘吸附）

#### audio_indicator.py
- 录音中显示声波动画条（QLabel 切换多帧）

---

### 5.2 Core 层

#### ai_engine.py
- 使用 OpenAI SDK（兼容 DeepSeek API）
- 流式调用 DeepSeek Chat
- 管理对话上下文历史
- Signal 发射逐字文本 / 完成信号 / 错误信号
- 后台线程运行，不阻塞 UI

#### rag_engine.py
**一次性导入流程：**
```python
df = pd.read_excel("朱比华知识库.xlsx")  # 两列: 问题/答案
for i, row in df.iterrows():
    vec = embedding_api.embed(row["问题"])
    collection.add(ids=[f"qa_{i}"], embeddings=[vec],
                   metadatas=[{"question": row["问题"], "answer": row["答案"]}])
```

**查询流程：**
```python
def retrieve(query: str, top_k: int = 3) -> list[dict]:
    q_vec = embedding_api.embed(query)
    results = collection.query(query_embeddings=[q_vec], n_results=top_k)
    return [{"question": r["question"], "answer": r["answer"]}
            for r in results["metadatas"][0]]
```

**阈值保护**：最高相似度 < 0.6 → 不注入 RAG，让 LLM 自由发挥

#### tts_engine.py
- 调用千问 CosyVoice API
- 音频流保存为临时 .mp3 → QMediaPlayer 播放
- 播放完自动清理临时文件
- 新回复打断旧播放

#### audio_input.py
- PyAudio 流式采集 16kHz 16bit mono PCM
- 录音结束 → 千问 Paraformer ASR API → 文字
- 发射完成信号

---

### 5.3 配置层

#### .env
```dotenv
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

ALIYUN_API_KEY=sk-xxx
ALIYUN_BASE_URL=https://dashscope.aliyuncs.com/api/v1

ASR_MODEL=paraformer-realtime-v2
TTS_MODEL=cosyvoice-v2
TTS_VOICE=longxiaochun
EMBEDDING_MODEL=text-embedding-v3

VECTOR_STORE_PATH=./data/vector_store
XLSX_PATH=./data/source/朱比华知识库.xlsx
```

#### config/settings.py
- `python-dotenv` 加载 .env
- `Settings` 类封装全部配置，初始化时校验必要 Key
- 全局单例 `settings = Settings()`

---

### 5.4 线程模型

```
主线程: QApplication 事件循环（UI 绘制、用户交互）
  ├── Worker 线程 1: LLM 网络请求（threading.Thread + Signal）
  ├── Worker 线程 2: TTS 网络请求 + 播放（QThread + Signal）
  ├── Worker 线程 3: RAG 检索（QThread, 极快可忽略）
  └── Worker 线程 4: 音频采集（PyAudio 独立线程）
```

所有网络请求均放在工作线程，主线程只负责 UI 更新。

---

## 六、实现优先级（分阶段交付）

### Phase 1 — MVP 核心对话（目标：能打字聊天）

| 文件 | 内容 |
|------|------|
| `main.py` | 启动 QApplication，加载 pet_window |
| `pet_window.py` | 透明桌面窗口，可拖动 |
| `character_widget.py` | QPainter 绘制占位立绘 |
| `chat_panel.py` | 弹出聊天框，Enter 发送，✕ 关闭 |
| `ai_engine.py` | 接 DeepSeek API，流式回复 |
| `.env` + `config/settings.py` | 配置管理 |

**Phase 1 跑通后**：点击桌宠 → 打字 → DeepSeek 回复 → 看到文字

### Phase 2 — 语音输出

| 文件 | 内容 |
|------|------|
| `tts_engine.py` | CosyVoice API + 播放 |

### Phase 3 — RAG 知识库

| 文件 | 内容 |
|------|------|
| `rag_engine.py` | ChromaDB 导入 .xlsx + 检索 |
| 修改 `ai_engine.py` | 注入 RAG 上下文到 system prompt |

### Phase 4 — 语音输入

| 文件 | 内容 |
|------|------|
| `audio_input.py` | 录音 + ASR API |
| 修改 `chat_panel.py` | 加录音按钮 + 状态指示 |

---

## 七、关键边界情况处理

| 场景 | 处理方式 |
|------|---------|
| 网络断开 | chat_panel 显示「网络连接失败」，不崩溃，重试恢复 |
| API Key 无效 | 启动时 settings.validate() 报错，不给空跑机会 |
| DeepSeek 流式中断 | 已收到的文字先显示，提示「回复被中断」 |
| TTS 播放中又来新回复 | 停止当前播放，直接播最新的 |
| ASR 识别为空 | 不发送空消息，提示「没有听清，请再说一遍」 |
| RAG 检索引擎抛异常 | 降级为纯 LLM 回复（不注入 RAG），不阻塞对话 |
| 录音无权限 | 提示用户检查麦克风权限，仍可用打字输入 |
| .xlsx 文件不存在 | 启动时检查，缺文件则跳过 RAG 初始化（log 警告） |
| .xlsx 为纯空文件 | 跳过 RAG，纯 LLM |
| .xlsx 格式不对（无问题/列） | 报错信息提示格式要求 |

---

## 八、依赖清单（requirements.txt）

```
PySide6>=6.6
openai>=1.0              # DeepSeek API（兼容 OpenAI SDK）
python-dotenv>=1.0       # 读取 .env
chromadb>=0.5            # 本地向量库
pandas>=2.0              # 读取 .xlsx
openpyxl>=3.1            # xlsx 引擎
requests>=2.31           # TTS/ASR HTTP 调用
pyaudio>=0.2.14          # 麦克风采集
soundfile>=0.12          # 音频格式处理
numpy>=1.24              # 音频数据处理
```

---

## 九、已确认的需求（2026-06-02）

| # | 问题 | 结论 |
|:-:|------|------|
| 1 | 默认音色 | **先用阿里云自带 `longxiaochun` 跑通，后续提供朱比华原声再克隆** |
| 2 | 立绘素材 | **先用占位图开发，后续替换** |
| 3 | 窗口尺寸 | **200×300** |
| 4 | 聊天框风格 | **全部消息在左侧（聊天室风格）** |
| 5 | 对话框关闭 | **加 ✕ 关闭按钮** |
| 6 | 动画帧 | **Phase 1 先静态图，后续再加动画** |
