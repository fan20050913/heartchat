"""
路径解析工具
提供基于项目根目录（开发模式）或 exe 所在目录（PyInstaller 打包后）的路径解析。
"""

import sys
from pathlib import Path


def base_dir() -> Path:
    """返回打包资源根目录。

    - 打包后（PyInstaller --onedir）：返回 _internal/ 目录（sys._MEIPASS）
    - 开发模式：返回项目根目录（本文件所在目录的上一级）
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """返回用户数据目录（可读写，持久化用）。

    - 打包后：exe 所在目录（与 _internal/ 同级）
    - 开发模式：项目根目录
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def asset_path(*parts: str) -> Path:
    """拼接基础目录下的资产路径。

    Usage:
        asset_path("assets", "sprites", "sipika.webp")
        # => /exe/dir/assets/sprites/sipika.webp
    """
    return base_dir().joinpath(*parts)
