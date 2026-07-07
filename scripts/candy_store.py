#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
糖果库存共享模块 — 迁移至 JSON (2026-05-31)
格式：soul_state.json 中的 candy 字段
旧版 XML 解析保留为备用，由 soul_core 内部调用
"""

import json
import os
import re

from config import CANDY_PATH, SOUL_PATH


def parse_candy_count() -> int:
    """从 candy.json 读取糖果库存数量"""
    try:
        with open(CANDY_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
        return state.get("count", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        return _parse_candy_count_xml()


def update_candy_inventory(count: int = 0) -> int:
    """更新 candy.json 中的糖果库存数量，返回新值"""
    try:
        with open(CANDY_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    
    state["count"] = count
    
    os.makedirs(os.path.dirname(CANDY_PATH), exist_ok=True)
    with open(CANDY_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    from utils import _sync_data_js
    _sync_data_js()
    return count


def _parse_candy_count_xml() -> int:
    """备用：从 SOUL.md 解析 XML 格式糖果库存"""
    try:
        with open(SOUL_PATH, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return 0

    tag_start = content.find("<库存状态>")
    if tag_start == -1:
        return 0

    tag_end = content.find("</库存状态>", tag_start)
    if tag_end == -1:
        section = content[tag_start:]
    else:
        section = content[tag_start:tag_end]

    m = re.search(r"<糖果数>(\d+)</糖果数>", section)
    if m:
        return int(m.group(1))
    return 0
