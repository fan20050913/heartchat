# 动画帧优化方案

> 现状：每个角色 4 套动画（talking/hair/blink/think），每套 45-120 帧 PNG，文件多体积大。

---

## 方案对比

| 方案 | 文件数减少 | 体积减少 | 代码改动 | 复杂度 |
|:----:|:---------:|:--------:|:--------:|:------:|
| **降帧率** | — | ~44% (帧数) | 改帧率常数 | ⭐ |
| **PNG→WebP** | — | ~70-80% | 3 行（改后缀） | ⭐ |
| **精灵图 Sprite Sheet** | 840→8 | +~20-30% | 中等（切帧逻辑） | ⭐⭐ |
| **WebM 视频序列** | 840→8 | ~95% | 大（视频解码） | ⭐⭐⭐⭐ |

---

## 方案详情

### 1️⃣ 降帧率（不花钱的优化）

| 动画 | 当前 | 建议 | 帧节省 |
|:----|:----:|:----:|:------:|
| `hair`（头发飘动） | 30fps 120帧/4s | **15fps 60帧/4s** | -50% |
| `blink`（眨眼） | 30fps 90帧/3s | **15fps 45帧/3s** | -50% |
| `talking`（说话口型） | 30fps 90帧/3s | **20fps 60帧/3s** | -33% |
| `think`（发呆） | 30fps 90帧/3s | **15fps 45帧/3s** | -50% |

- 效果：帧数减少约 **44%**，降低显存占用
- 代价：需要重新 AI 生成帧序列，或抽帧后改 `FPS`/`total_frames` 常数
- 视觉：头发飘动/眨眼这类慢速运动，15fps 看不出差别

### 2️⃣ PNG → WebP（立即见效）

```bash
# 批量转换
ffmpeg -i frame_%02d.png -lossless 1 output.webp
```

- `QPixmap.load()` 原生支持 `.webp`，**加载代码几乎不用改**
- 无损模式下体积减至 PNG 的 20-30%
- 有损模式下（`-lossless 0 -q 80`）可再减一半，立绘差异几乎看不出

### 3️⃣ 精灵图 Sprite Sheet（推荐）

将所有帧合并为一张大图，运行时按坐标切帧：

```
talking.webp (单文件, 90帧合并)
┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
│ f0 │ f1 │ f2 │ f3 │ f4 │ f5 │ f6 │ f7 │ f8 │ f9 │
├────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
│ f10│ f11│ ...│    │    │    │    │    │    │    │
└────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘
```

```python
# character_widget.py 改动示意
class SpriteSheetAnimation:
    def __init__(self, sheet, cols, total_frames, frame_size):
        self.sheet = QPixmap(sheet)
        self.cols = cols
        self.frame_size = frame_size

    def get_frame(self, index):
        col = index % self.cols
        row = index // self.cols
        return self.sheet.copy(
            col * self.frame_size.width(),
            row * self.frame_size.height(),
            self.frame_size.width(),
            self.frame_size.height()
        )
```

**优点**：
- 文件数：840 个文件 → **8 个文件**（2 角色 × 4 动画）
- 体积再减 20-30%（消除 PNG 头开销 + 文件系统簇浪费）
- 加载一次缓存整图，比逐个文件 IO 更快

**代价**：
- 修改 `character_widget.py` 的帧加载逻辑
- `QPixmap.copy()` 每次取帧有轻微开销（可预缓存为列表消除）

### 4️⃣ WebM 视频序列（极致压缩）

每段动画编码为 VP9 + Alpha 通道的 WebM：

```bash
ffmpeg -framerate 30 -i frame_%02d.png \
  -c:v libvpx-vp9 -pix_fmt yuva420p -lossless 0 -crf 30 \
  talking.webm
```

**路线 A — QMediaPlayer 直接播放**：
- 最简单，代码量最少
- 但精确跳帧困难，不适合循环动画的帧精确控制

**路线 B — 解码为帧列表缓存**（推荐）：
```
启动 → 读取 8 个 WebM → 解码为 QPixmap[]
→ QTimer 播放时从内存取帧 → 零磁盘 IO
```

- 内存换磁盘 IO，运行时更流畅
- 代价：启动时解码耗时、依赖 `PyAV` 或 `ffmpeg-python`

---

## 推荐路线

```
Phase A（马上做，零代码改）
└─ PNG → WebP（无损，批量转换命令）
   └─ 体积 -70~80%，加载代码不改

Phase B（想做就做，中等改造成本）
└─ 精灵图 Sprite Sheet
   └─ 840 文件 → 8 文件，再减 20%，加载更快

Phase C（极致优化，暂时不急）
└─ 降帧率 + WebM 视频序列
   └─ 需要重新生成帧序列 + 大改代码
```

**推荐组合**：**Phase A + Phase B** —— 一步到位降到 8 个 WebP 文件，体积 -90%。

---

## 目前资产统计

| 角色 | talking | hair | blink | think | 合计 |
|:----:|:-------:|:----:|:-----:|:-----:|:----:|
| 夜乃樱 | 90帧 | 120帧 | 90帧 | 90帧 | 390帧 |
| 朱比华 | 90帧 | 120帧 | 90帧 | 90帧 | 390帧 |
| **总计** | | | | | **780帧 × PNG** |

优化目标：780 帧 PNG（大量文件 ~50MB）→ **8 个 WebP 精灵图（~3-5MB -90%）**
