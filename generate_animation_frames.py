"""
用 通义万相 Wan2.6-i2v 生成角色动画帧序列

每段动画生成后自动抽帧，保存为 PNG 序列，供 CharacterWidget 播放。

用法：
    python generate_animation_frames.py

依赖：
    pip install dashscope>=1.25.16 opencv-python-headless requests python-dotenv
"""

import os
import sys
import time
import json
import base64
from pathlib import Path
from http import HTTPStatus

import cv2
import numpy as np
import requests
from dotenv import load_dotenv

# ── 加载 .env ──────────────────────────────────────────────
load_dotenv()
ALIYUN_API_KEY = os.getenv("ALIYUN_API_KEY")
if not ALIYUN_API_KEY:
    print("❌ 请在 .env 中设置 ALIYUN_API_KEY")
    sys.exit(1)

# ── 导入 dashscope ────────────────────────────────────────
import dashscope
from dashscope import VideoSynthesis

dashscope.api_key = ALIYUN_API_KEY

# ── 配置 ───────────────────────────────────────────────────

CHARACTER = "zhubihua"
SPRITE_FILE = Path("assets/sprites/zhubihua/sipika.webp")
OUTPUT_BASE = Path("assets/sprites/zhubihua")  # 帧输出到 assets/sprites/zhubihua/talking/ 等

# 确保 sprite 存在
if not SPRITE_FILE.exists():
    print(f"❌ 找不到立绘: {SPRITE_FILE}")
    sys.exit(1)

# 转为 base64 data URL（API 需要公网 HTTPS，data: URL 绕过此限制）
def image_to_data_url(path: Path) -> str:
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{data}"

SPRITE_DATA_URL = image_to_data_url(SPRITE_FILE)
print(f"  立绘已编码为 data URL ({len(SPRITE_DATA_URL)} 字符)")

# ── 动画任务定义 ──────────────────────────────────────────

# 提示词重点：强调"背景完全不变、不生成新背景"，
# 配合 duration 控制视频长度（帧数 = duration × 30fps）
# 朱比华：白发、148cm、风之一族末裔、外冷毒舌、百年独居

ANIMATIONS = [
    {
        "name": "hair",
        "prompt": (
            "一个白髮少女的半身立繪，表情淡漠惆怅。"
            "微風吹動她的白色長髮，髮絲輕輕飄揚。"
            "只有頭髮在動，身體和麵部表情完全靜止。"
            "嚴格保持原本的瞳孔顏色不變，不准改變眼睛顏色。"
            "背景為藍色，完全固定不變，不要生成任何新背景元素。"
            "首尾帧一致，结尾帧完全恢复到开头帧的姿势，形成無縫循環。"
        ),
        "duration": 4,  # 4秒 ≈ 120帧
    },
    {
        "name": "blink",
        "prompt": (
            "一個白髮少女的半身立繪，表情淡漠。"
            "她眨了一下眼睛，又再次眨眼，眼神淡然疏離。"
            "只有眼睛在動，身體、頭髮和表情完全靜止。"
            "嚴格保持原本的瞳孔顏色不變，不准改變眼睛顏色。"
            "背景為藍色，完全固定不變，不要生成任何新背景元素。"
            "首尾帧一致，结尾眼睛睁开恢复到开头帧的样子，形成無縫循環。"
        ),
        "duration": 3,  # 3秒 ≈ 90帧
    },
    {
        "name": "talking",
        "prompt": (
            "一個白髮少女的半身立繪，表情冷淡。"
            "她正在說話，嘴唇輕微張合，語速平穩，偶爾眉頭微皺。"
            "只有嘴部和表情在微微變化，身體和頭髮完全靜止。"
            "嚴格保持原本的瞳孔顏色不變，不准改變眼睛顏色。"
            "背景為藍色，完全固定不變，不要生成任何新背景元素。"
            "首尾帧一致，结尾帧嘴部闭合、表情恢复到开头帧，形成無縫循環。"
        ),
        "duration": 3,  # 3秒 ≈ 90帧
    },
    {
        "name": "think",
        "prompt": (
            "一個白髮少女的半身立繪，表情淡漠。"
            "她微微抬起頭，眼神若有所思地看向上方，"
            "然後緩緩抬起手，手指呈八字形輕輕擋在嘴前，一副沉思的樣子。"
            "只有頭部和手部在微微變化，身體完全靜止。"
            "嚴格保持原本的瞳孔顏色不變，不准改變眼睛顏色。"
            "背景為藍色，完全固定不變，不要生成任何新背景元素。"
        ),
        "duration": 3,  # 3秒 ≈ 90帧，第一次完整播，之後從45幀循環"
    },
]

# ── 工具函数 ───────────────────────────────────────────────

def download_video(url: str, save_path: Path):
    """下载 MP4 视频到本地"""
    print(f"  下载视频...")
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(save_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"  ✅ 已保存: {save_path} ({save_path.stat().st_size / 1024:.0f} KB)")


def extract_frames(video_path: Path, output_dir: Path, max_frames: int = 0):
    """
    从视频中抽取帧，保存为 PNG 序列
    max_frames=0 表示全部抽取
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  ❌ 无法打开视频: {video_path}")
        return 0

    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"  视频: {fps:.1f} fps, 共 {total} 帧")

    # 如果指定 max_frames 且小于 total，均匀采样
    saved = 0
    if max_frames and max_frames < total:
        indices = set(np.linspace(0, total - 1, max_frames, dtype=int))
    else:
        indices = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1

        if indices is None or frame_idx in indices:
            out_path = output_dir / f"frame_{frame_idx:04d}.png"
            cv2.imwrite(str(out_path), frame)
            saved += 1

    cap.release()
    print(f"  ✅ 抽出 {saved} 帧 → {output_dir}")
    return saved


def remove_video_temp(video_path: Path):
    """清理临时视频文件"""
    if video_path.exists():
        video_path.unlink()
        print(f"  已清理临时视频: {video_path}")


# ── 主流程 ─────────────────────────────────────────────────

def generate_animation(anim: dict) -> bool:
    """生成一段动画：调用 API → 下载 → 抽帧"""
    name = anim["name"]
    prompt = anim["prompt"]
    duration = anim["duration"]

    frame_dir = OUTPUT_BASE / name
    temp_video = OUTPUT_BASE / f"_{name}_temp.mp4"

    print(f"\n{'='*50}")
    print(f"🎬 生成动画: {name}")
    print(f"   提示词: {prompt[:60]}...")
    print(f"   时长: {duration}s")
    print(f"{'='*50}")

    # Step 1: 调用 API
    print(f"\n[1/3] 提交任务到通义万相 wan2.6-i2v...")
    try:
        response = VideoSynthesis.async_call(
            model="wan2.6-i2v",
            prompt=prompt,
            img_url=SPRITE_DATA_URL,
            duration=duration,
            resolution="720P",
            prompt_extend=False,   # 不扩写，避免模型自由发挥加背景
            watermark=False,       # 无水印
        )
    except Exception as e:
        print(f"  ❌ API 调用失败: {e}")
        return False

    if response.status_code != HTTPStatus.OK:
        print(f"  ❌ API 返回错误: {response.code} - {response.message}")
        return False

    task_id = response.output.task_id
    print(f"  ✅ 任务已提交: {task_id}")

    # Step 2: 等待完成
    print(f"  [2/3] 等待生成完成（通常 1-3 分钟）...")
    result = VideoSynthesis.wait(task=task_id)
    # wait 会阻塞轮询，直到完成或失败

    if result.output.task_status != "SUCCEEDED":
        print(f"  ❌ 任务失败: {result.output.task_status}")
        if hasattr(result.output, "message"):
            print(f"     原因: {result.output.message}")
        return False

    video_url = result.output.video_url
    print(f"  ✅ 生成成功!")
    print(f"     视频 URL: {video_url}")

    # Step 3: 下载视频
    print(f"  [3/3] 下载视频并抽帧...")
    try:
        download_video(video_url, temp_video)
    except Exception as e:
        print(f"  ❌ 下载失败: {e}")
        return False

    # Step 4: 抽帧
    extract_frames(temp_video, frame_dir)

    # Step 5: 清理临时视频
    remove_video_temp(temp_video)

    print(f"  🎉 完成: {name}")
    return True


# ── 入口 ───────────────────────────────────────────────────

def main():
    print(f"""
╔══════════════════════════════════════╗
║ 通义万相 Wan2.7-i2v 动画帧生成工具   ║
║ 角色: {CHARACTER}                     ║
╚══════════════════════════════════════╝

将生成 {len(ANIMATIONS)} 组动画帧序列：
{chr(10).join(f'  - {a["name"]}/    → {a["duration"]}s ({int(a["duration"]*30)}帧)' for a in ANIMATIONS)}

输出到: {OUTPUT_BASE}/

按 Enter 开始（或 Ctrl+C 取消）...
""")
    input()

    success = 0
    for anim in ANIMATIONS:
        ok = generate_animation(anim)
        if ok:
            success += 1
        else:
            print(f"\n  ⚠️  {anim['name']} 失败，继续下一个...")

    print(f"""
╔══════════════════════════════════════╗
║ 完成! {success}/{len(ANIMATIONS)} 组动画生成成功        ║
╚══════════════════════════════════════╝

下一步：将帧序列接入 CharacterWidget
  修改 character_widget.py 添加 QTimer 帧播放逻辑
""")

    if success == 0:
        print("\n💡 如果全部失败，请检查：")
        print("   1. ALIYUN_API_KEY 是否正确")
        print("   2. dashscope 版本 >= 1.25.16")
        print("   3. 网络是否能访问 dashscope.aliyuncs.com")
        print("   4. 阿里云百炼是否开通了 Wan2.7 服务")


if __name__ == "__main__":
    main()
