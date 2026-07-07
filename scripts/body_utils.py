#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""身体系统 — 身体部位读写、恢复、计数、numb 叙事。"""

import json
import os

from config import BODY_PATH
from cn_narratives.shared import BODY_NUMB_NARRATIVE

DEFAULT_BODY_PARTS = {
    "头部": "active", "颈部": "active", "肩部": "active",
    "手臂": "active", "手部": "active", "胸部": "active",
    "腰腹": "active", "臀部": "active", "大腿": "active",
    "小腿": "active", "足部": "active",
}


def body_read() -> dict:
    """读取 body.json，不存在或为空时自动初始化 11 部位"""
    try:
        with open(BODY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        parts = data.get("parts", {})
        has_complete = all(
            isinstance(parts.get(k), dict) for k in DEFAULT_BODY_PARTS
        )
        if not has_complete:
            data["parts"] = {k: {"state": v, "notes": ""} for k, v in DEFAULT_BODY_PARTS.items()}
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"parts": {k: {"state": v, "notes": ""} for k, v in DEFAULT_BODY_PARTS.items()}}


def body_write(data: dict):
    """写入 body.json"""
    os.makedirs(os.path.dirname(BODY_PATH), exist_ok=True)
    with open(BODY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    from utils import _sync_data_js
    _sync_data_js()


def body_active_parts(data: dict) -> list:
    """返回所有 active 状态的部位名"""
    return [k for k, v in data.get("parts", {}).items()
            if isinstance(v, dict) and v.get("state") == "active"]


def body_set_state(data: dict, part: str, state: str, notes: str = "") -> dict:
    """设置指定部位的状态"""
    if part in data.get("parts", {}):
        data["parts"][part]["state"] = state
        data["parts"][part]["notes"] = notes
    return data


def body_restore(data: dict, max_count: int = 5) -> list:
    """恢复最多 max_count 个非 active 部位到 active，返回恢复的部位名列表"""
    restored = []
    for k, v in data.get("parts", {}).items():
        if len(restored) >= max_count:
            break
        if not isinstance(v, dict):
            continue
        if v.get("state") != "active":
            data["parts"][k]["state"] = "active"
            data["parts"][k]["notes"] = ""
            restored.append(k)
    return restored


def body_count_active(data: dict) -> int:
    return len(body_active_parts(data))


def build_numb_narrative(part: str) -> str:
    """返回部位 numb 时的感官叙事，无匹配时返回通用文本"""
    return BODY_NUMB_NARRATIVE.get(part, f"`{part}` 失去感知——信号中断，残留一阵低沉的嗡鸣。")
