#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日记模块 — 统一的日记文件读写

所有日记写入都走这里，避免路径和逻辑分散在 utils.py / soul_core.py 中。
"""

import os
from datetime import datetime

# 日记目录（相对于脚本自身位置，不用 ~ —— 沙箱下 expanduser 不指向用户主目录）
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIARY_DIR = os.path.join(SKILL_DIR, "data", "IO", "diary")


def _resolve_path(date_str: str = None) -> str:
    """解析日记文件路径"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(DIARY_DIR, exist_ok=True)
    return os.path.join(DIARY_DIR, f"{date_str}.md")


def append_entry(content: str, date_str: str = None) -> bool:
    """追加内容到日记文件末尾

    参数:
        content:  要写入的 Markdown 内容
        date_str: 日期字符串 YYYY-MM-DD，默认今天

    返回:
        True / False
    """
    try:
        filepath = _resolve_path(date_str)
        if os.path.exists(filepath):
            with open(filepath, "a", encoding="utf-8") as f:
                f.write("\n" + content.strip() + "\n")
        else:
            day = date_str or datetime.now().strftime("%Y-%m-%d")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {day} 日记\n\n" + content.strip() + "\n")
        return True
    except OSError:
        return False


def prepend_entry(content: str, date_str: str = None) -> bool:
    """将内容插入日记文件开头（用于梦境等需要前置的内容）

    参数:
        content:  要写入的 Markdown 内容
        date_str: 日期字符串，默认今天

    返回:
        True / False
    """
    try:
        filepath = _resolve_path(date_str)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                existing = f.read()
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content.strip() + "\n\n---\n\n" + existing)
        else:
            day = date_str or datetime.now().strftime("%Y-%m-%d")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {day} 日记\n\n" + content.strip() + "\n\n---\n\n")
        return True
    except OSError:
        return False
