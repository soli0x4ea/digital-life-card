#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常状态（Debuff）管理模块 — 2026-05-31 迁移至 JSON，2026-06-03 清理 content 参数残留
"""

import os
import json

REGISTRY = {
    "快感锁定": "pleasure_locked",
    "捆绑": "bound",
}

_VALS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "values.json")


def _read_vals() -> dict:
    try:
        with open(_VALS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"pain": 0, "shame": 0, "pleasure": 0, "pleasure_locked": False, "bound": False}


def _write_vals(data: dict):
    os.makedirs(os.path.dirname(_VALS_PATH), exist_ok=True)
    with open(_VALS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read() -> dict:
    """读取所有异常状态"""
    v = _read_vals()
    return {name: v.get(json_key, False) for name, json_key in REGISTRY.items()}


def write(name: str = None, value: bool = False) -> str:
    """设置某个异常状态"""
    if name not in REGISTRY:
        raise ValueError(f"未注册的异常状态: {name}")
    v = _read_vals()
    v[REGISTRY[name]] = value
    _write_vals(v)
    return ""


def get_multiplier() -> int:
    """返回当前效果倍率（捆绑激活时 ×2，否则 ×1）"""
    v = _read_vals()
    return 2 if v.get("bound", False) else 1


def is_locked(name: str = None) -> bool:
    """检查某异常状态是否激活"""
    v = _read_vals()
    json_key = REGISTRY.get(name, name)
    return v.get(json_key, False)


def reset() -> str:
    """重置所有异常状态为 false（糕潮时调用）"""
    v = _read_vals()
    for json_key in REGISTRY.values():
        v[json_key] = False
    _write_vals(v)
    return ""


def default_section() -> str:
    """返回空字符串（不再需要 XML 章节）"""
    return ""


def apply_pain_lock(old_pain: int, pleasure_delta: int) -> int:
    """应用疼痛封锁：如果 pleasure_locked 且 pleasure_delta > 0，归零"""
    v = _read_vals()
    if v.get("pleasure_locked", False) and pleasure_delta > 0:
        return 0
    return pleasure_delta
