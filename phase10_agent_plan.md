# Phase 10 — LangGraph Agent 系统设计

> 目标：为 HeartChat 桌宠引入 LangChain / LangGraph 驱动的 Agent 能力，从被动回复进化为主动陪伴的桌面共生体。
> 核心价值：练手 LangGraph 全套机制（StateGraph / ToolNode / Human-in-loop / Checkpointer / Subgraph）+ 打造别的产品做不到的桌宠体验。

---

## 架构总览

### 双事件循环模型

```
Qt 主线程 (UI)                     asyncio 线程 (Agent)
┌──────────────────────┐          ┌──────────────────────────────┐
│  PySide6 QApplication│          │  asyncio event loop          │
│                      │          │                              │
│  user_send ──Signal──┼─────────┼→ AgentBridge.invoke()        │
│                      │          │  ┌────────────────────────┐  │
│  on_agent_chunk  ←───┼─────────┼──│ LangGraph StateGraph    │  │
│  on_agent_done   ←───┼─────────┼──│  ├─ Supervisor Node     │  │
│  on_agent_error  ←───┼─────────┼──│  ├─ ToolNode            │  │
│                      │          │  ├─ Human-in-loop Node   │  │
│  tool_confirm ──Signal┼─────────┼──│  └─ Checkpointer/Saver │  │
│                      │          │  └────────────────────────┘  │
│  active_heartbeat ───QTimer─────│                              │
│  window_watcher ────QTimer─────│                              │
└──────────────────────┘          └──────────────────────────────┘
```

### 目录结构（新增）

```
core/
├── agent/                          # 新增 Agent 系统
│   ├── __init__.py
│   ├── bridge.py                   # asyncio ↔ Qt 桥接器 (AgentBridge)
│   ├── graph.py                    # StateGraph 定义
│   ├── state.py                    # Agent 状态 TypedDict
│   ├── supervisor.py               # Supervisor Node (LLM 决策)
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py             # @tool 装饰器注册
│   │   ├── web_search.py           # 网络搜索
│   │   ├── web_monitor.py          # 定时监控 (价格/页面变化)
│   │   ├── process.py              # 进程/系统信息
│   │   ├── screenshot.py           # 截屏分析
│   │   └── behavior.py             # 用户行为感知
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── checkpoint.py           # LangGraph Checkpointer
│   │   └── summary.py              # 对话摘要压缩
│   └── heartbeat.py                # 定时心跳 + 状态机
│
main.py                             # 新增 Agent 模式开关
```

---

## Phase 10 子阶段路线

### 10.1 — 基建：asyncio 桥 + 最简 StateGraph

**目标**：跑通 asyncio 线程 + Qt 信号桥，最简 StateGraph 直通回复。

| 文件 | 内容 |
|:----|:-----|
| `core/agent/bridge.py` | `AgentBridge(QObject)`: 启动 asyncio 线程、Qt Signal ↔ asyncio 互相调用 |
| `core/agent/state.py` | `AgentState(TypedDict)`: `messages`, `next` |
| `core/agent/graph.py` | 最简图: input → LLM → reply |

**练手点**：
- `asyncio.new_event_loop()` + `threading.Thread` 跑事件循环
- `asyncio.run_coroutine_threadsafe()` 从 Qt 线程提交任务
- `QObject.Signal` 从 asyncio 回调中 emit（`QMetaObject.invokeMethod`）
- LangGraph 最简 `StateGraph` + `add_node` + `add_edge`

**入口**：
```python
# main.py
agent_mode = settings.get("AGENT_ENABLED", False)
if agent_mode:
    bridge = AgentBridge()
    bridge.start()
    # user_send 改为走 bridge.send_message()
```

---

### 10.2 — 行为感知 + 情绪推断 Agent

**目标**：扩展已有 `window_watcher`，结合多源上下文做 LLM 推理。

**状态定义**：
```python
class AgentState(TypedDict):
    messages: Sequence[BaseMessage]
    next: str

    # 上下文 (由外部模块注入)
    frontend_window: str          # 当前前台窗口标题
    frontend_duration: int        # 停留秒数
    time_of_day: str              # 时间段
    active_hours: int             # 今天已用电脑时长
    idle_minutes: int             # 空闲分钟数
    switch_count: int             # 今天窗口切换次数

    # LLM 推理结果
    user_state: str               # 专注/烦躁/摸鱼/空闲/睡眠
    should_speak: bool            # 是否主动说话
    speak_reason: str             # 说话理由
    personality_hint: str         # 语气提示 (毒舌/温柔/沉默)
```

**图结构**：
```
                    ┌──────────────────┐
                    │  collect_context │  ← 注入 window/timer/psutil
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │  infer_state     │  ← LLM 推理用户状态
                    └────────┬─────────┘
                             │
                    ┌────────┴─────────┐
                    │ should_speak?    │  ← 条件路由
                    └────────┬─────────┘
                     yes     │  no
                     ┌───────┴───────┐
                     ▼               ▼
              ┌────────────┐   ┌──────────┐
              │ generate   │   │  silent  │  ← 什么都不做
              │ response   │   └──────────┘
              └──────┬─────┘
                     ▼
              ┌────────────┐
              │  TTS+气泡  │
              └────────────┘
```

**练手点**：
- 条件路由 `add_conditional_edges`
- 多源状态注入
- LLM 结构化输出（指定输出 schema）

**场景示例**：
```
[23:47, 前台: WebStorm, 已连续编码 3h]
  → Node 1: collect_context
  → Node 2: infer_state → "用户超时工作, 疲惫"
  → Node 3: generate → "主人, 该睡了" (冷峻会长语气)
  → TTS + 气泡
```

---

### 10.3 — 自适应陪伴 + ToolNode

**目标**：加入工具调用能力，桌宠能真正「做事情」而不是只说话。

**工具清单**：

| 工具 | 实现 | 是否需要确认 |
|:----|:-----|:-----------:|
| `web_search` | DuckDuckGo / SearXNG API | ❌ |
| `webpage_snapshot` | 截图当前页面 → LLM 分析 | ✅ 隐私 |
| `system_status` | `psutil`: CPU/内存/磁盘/网络 | ❌ |
| `app_launch` | `subprocess.Popen` 启动应用 | ✅ |
| `set_timer` | QTimer 定时提醒 | ❌ |
| `clipboard_read` | 读取剪贴板内容 | ✅ |

**图结构**（复用 10.2 + ToolNode）：
```
collect_context → infer_state → should_speak?
  │ yes                              │ no
  └──→ supervisor ──→ ToolNode ←───┘ silent
         │  │              │
         │  └── tool_done ─┘
         │         │
         └──→ generate_reply → TTS+气泡
```

**练手点**：
- `@tool` 装饰器 + 参数 schema
- `ToolNode` 集成
- Human-in-loop: `interrupt()` 等待用户确认
- 工具结果注入 LLM 上下文

---

### 10.4 — 信息猎犬（定时网络 Agent）

**目标**：按定时计划执行网络信息检索 + 摘要播报。

**多节点流水线**（LangGraph 的强项）：

```
[定时触发] (每 30min, 上班前)
    ↓
Node 1: fetch_sources
  ├─ HackerNews API → top stories
  ├─ GitHub Trending → repos
  └─ (可选) RSS/API 其他源
    ↓
Node 2: llm_filter
  ├─ 去重
  ├─ 判断重要性 (1-10分)
  └─ 保留 3-5 条重点
    ↓
Node 3: llm_summarize
  ├─ 每条 1-2 句中文摘要
  └─ 判断是否值得 TTS 播报
    ↓
Node 4: route
  ├─ 有重要消息? → deliver
  └─ 没有? → silent
    ↓
Node 5: deliver
  ├─ 日语 TTS: 「主人、今日の注目ニュース…」
  └─ 中文气泡: 详细内容
```

**练手点**：
- 多节点依赖链（每个节点输出是下一个的输入）
- 结构化输出 schema（重要性评分、分类）
- 定时触发（与 Qt QTimer 配合）
- Subgraph 设计（每个源可独立成子图）

---

### 10.5 — RPG 日常系统（Checkpointer 持久化）

**目标**：桌宠拥有 `mood/energy/relationship` 属性，跨会话持久化。

**状态扩展**：
```python
class AgentState(TypedDict):
    messages: Sequence[BaseMessage]
    next: str
    context: dict    # 窗口/时间/行为上下文

    # RPG 属性（checkpoint 持久化）
    mood: str                    # 高兴/happy / 普通/normal / 烦躁/irritated / 困/tired
    energy: int                  # 0-100, 随时间恢复, 活动消耗
    relationship: int            # 亲密度 0-100, 互动增/冷落减
    last_active: str             # ISO datetime, 用于计算离线时长
    daily_count: int             # 今天互动次数
    daily_goal: str | None       # 今天想做的事
```

**行为规则**（LangGraph 条件路由）：

```
relationship < 20: 冷淡模式, 少主动
relationship 20-60: 普通模式, 正常互动
relationship > 60: 亲近模式, 主动增多, 解锁特殊台词
relationship > 80: 特殊互动, 专属称呼

energy 每隔 30min 回 5
互动消耗 energy 3-10
mood 受 relationship + 互动频率 + 时段影响
```

**练手点**：
- `MemorySaver` / `SqliteSaver` 持久化
- `Checkpointer` 断点恢复
- 状态跨 session 保持
- 条件路由复杂策略

---

### 10.6 — MCP 升级（可选）

**目标**：将 `@tool` 替换为 MCP Client 协议，学习 Anthropic MCP 标准。

**变化**：
```
改前: tool = @tool 装饰器 → ToolNode 直接调用
改后: tool = MCP Client → MCP Server (stdio/HTTP)
```

| 优势 | 代价 |
|:----|:-----|
| 工具标准化、跨 LLM 复用 | 多一层抽象 |
| 可接入社区 MCP Server | MCP SDK 学习成本 |
| 工具热插拔 | 进程通信额外复杂度 |

**建议时机**：等 10.1-10.5 跑熟之后作为架构升级，不要一上来就引入。

---

## 角色 Agent 行为风格

每种行为在最终输出时要经过角色 personality 过滤：

| 场景 | 夜乃樱（冷峻会长） | 朱比华（毒舌漂泊） |
|:----|:---------|:----------|
| 超时工作 | 「…休め。効率が落ちてる」 | 「…まだやってんの？バカじゃないの」 |
| 摸鱼被抓 | 「…仕事は終わったのか？」 | 「…さぼってる場合？」 |
| 深夜催睡 | 「…もう遅い。寝ろ」 | 「…明日死にたいの？」 |
| 主动关心 | 「…今日は早めに終われそうか」 | 「…まあ、死なない程度に頑張れよ」 |
| 信息播报 | 「…これを見ておけ、重要だ」 | 「…ちょっと面白いのあったぞ」 |

每条由 LLM 实时生成 + 角色 system prompt 约束，不是固定话术。

---

## 和现有代码的关系

### 无需修改的模块
- `core/ai_engine.py` — 作为普通对话模式保留
- `core/tts_engine.py` — TTS 播放接口不变
- `core/rag_engine.py` — RAG 检索复用
- `ui/` 全部 — UI 层只加信号连接

### 新增的文件
全部在 `core/agent/` 下，不侵入现有代码。

### 修改的文件（main.py）

```python
# 设置对话框增加：
# - Agent 模式开关（普通对话 / Agent 模式）
# - Agent 行为配置（主动程度/允许工具/信息源）
# - 重启后生效（切换时清 Agent 状态）

# 信号连接新增：
if settings.AGENT_ENABLED:
    chat_panel.send_signal.connect(bridge.send_message)
    bridge.chunk_received.connect(on_agent_chunk)
    bridge.tool_called.connect(on_tool_call)
    bridge.response_done.connect(on_agent_reply)
    window_watcher.window_changed.connect(bridge.on_window_change)
```

---

## 依赖清单（新增）

```
langchain>=0.3             # 基础链
langchain-community>=0.3   # 社区工具集
langgraph>=0.2             # 图状态机
langchain-core>=0.3        # 核心抽象

# 工具用到的
duckduckgo-search>=7.0     # web_search (无需 API Key)
psutil>=6.0                # 系统监控
Pillow>=10.0               # 截图
pyautogui>=0.9             # (可选) 鼠标键盘模拟

# 持久化 (可选)
langgraph-checkpoint-sqlite>=2.0
```

vs LangChain 全家桶（200+ 子包），我们只挑需要的装，尽量精简。

---

## 推荐优先级

```
Priority 1 [10.1 + 10.2] — 基建 + 行为感知 Agent
  展示: 桌宠开始「看懂你在干什么」并主动反应
  练手: asyncio 桥、StateGraph、条件路由、结构化输出

Priority 2 [10.3] — ToolNode + Human-in-loop
  展示: 桌宠能执行动作、用户可确认/拒绝
  练手: ToolNode、interrupt、权限控制

Priority 3 [10.4] — 信息猎犬
  展示: 定时播报新闻/更新
  练手: 多节点流水线、定时触发

Priority 4 [10.5] — RPG 系统 + Checkpointer
  展示: 有「感情」的桌宠
  练手: 持久化、跨 session 状态、复杂条件路由

Priority 5 [10.6] — MCP 升级
  展示: 架构升级、标准化工具接口
  练手: MCP 协议、Client/Server 通信
```

---

> 本文档对应的记忆：完成 10.1 + 10.2 基础架子后更新进度。
