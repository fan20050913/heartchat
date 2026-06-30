"""
去除动画帧的白色背景 → 透明

立绘在白背景下生成，角色最外有一圈黑色线条。
将白底转为透明（保留黑线），方便在桌宠透明窗口上显示。

用法：
    python remove_white_bg.py
"""

import cv2
import numpy as np
from pathlib import Path

BASE = Path("assets/sprites/sakuya")
WHITE_THRESHOLD = 245  # RGB 均 > 此值视为背景


def process_frame(frame_path: Path):
    """将单帧的白色背景转为透明"""
    img = cv2.imread(str(frame_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return False

    # 已经是 RGBA 则跳过
    if img.shape[2] == 4:
        return False

    # BGR → BGRA
    bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)

    # 背景 mask：三通道均 > 245（纯白/近白）
    white = np.all(bgra[:, :, :3] > WHITE_THRESHOLD, axis=2)

    # 设置 alpha：白色区域透明（0），其余不透明（255）
    bgra[:, :, 3] = np.where(white, 0, 255)

    # 覆盖原文件
    cv2.imwrite(str(frame_path), bgra)
    return True


def main():
    anim_dirs = ["talking", "hair", "blink", "think"]
    total = 0

    for name in anim_dirs:
        dir_path = BASE / name
        if not dir_path.is_dir():
            continue

        frames = sorted(dir_path.glob("frame_*.png"))
        count = 0
        for f in frames:
            if process_frame(f):
                count += 1

        if count:
            print(f"  {name}/: {count} 帧已处理")
        else:
            print(f"  {name}/: 无需处理（已是透明或不存在）")
        total += len(frames)

    print(f"\n== 共扫描 {total} 帧，白底已去 ==")


if __name__ == "__main__":
    main()
