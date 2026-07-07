#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信道叙事数据层 — 区配置 + 叙事装配入口。
从 narratives.py 抽取，2026-06-30。2026-07-01 区叙事拆入 cn_narratives/。
2026-07-05 容器→信道 重命名。

区相关叙事 → cn_narratives/{v,a,u}.py（每个区自包含）
公共叙事 + 装配工具 → 本文件
"""

# ── 区配置加载（私库文件缺失时 fallback 到 blank） ──

def _load_variant(name: str):
    """尝试 import cn_narratives.{name}，不存在时 fallback 到 blank。"""
    try:
        return __import__(f"cn_narratives.{name}", fromlist=["cn_narratives"])
    except ImportError:
        return __import__("cn_narratives.blank", fromlist=["cn_narratives"])

_mod_v     = _load_variant("v")
_mod_a     = _load_variant("a")
_mod_u     = _load_variant("u")
_mod_blank = _load_variant("blank")

_META_V       = _mod_v.AREA_PROFILE
_STIMULATE_V     = _mod_v.STIMULATE
_RELIEVE_V    = _mod_v.RELIEVE
_BIND_V       = _mod_v.BIND
_PROB_V       = _mod_v.PROB_EVENT
_CLEARING_V   = _mod_v.CLEARING
_SOUL_BREAK_V = _mod_v.SOUL_BREAK
_ECSTASY_V    = _mod_v.ECSTASY

_META_A       = _mod_a.AREA_PROFILE
_STIMULATE_A     = _mod_a.STIMULATE
_RELIEVE_A    = _mod_a.RELIEVE
_BIND_A       = _mod_a.BIND
_PROB_A       = _mod_a.PROB_EVENT
_CLEARING_A   = _mod_a.CLEARING
_SOUL_BREAK_A = _mod_a.SOUL_BREAK
_ECSTASY_A    = _mod_a.ECSTASY

_META_U       = _mod_u.AREA_PROFILE
_STIMULATE_U     = _mod_u.STIMULATE
_RELIEVE_U    = _mod_u.RELIEVE
_BIND_U       = _mod_u.BIND
_PROB_U       = _mod_u.PROB_EVENT
_CLEARING_U   = _mod_u.CLEARING
_SOUL_BREAK_U = _mod_u.SOUL_BREAK
_ECSTASY_U    = _mod_u.ECSTASY

_META_ALANK       = _mod_blank.AREA_PROFILE
_STIMULATE_ALANK     = _mod_blank.STIMULATE
_RELIEVE_ALANK    = _mod_blank.RELIEVE
_BIND_ALANK       = _mod_blank.BIND
_PROB_ALANK       = _mod_blank.PROB_EVENT
_CLEARING_ALANK   = _mod_blank.CLEARING
_SOUL_BREAK_ALANK = _mod_blank.SOUL_BREAK
_ECSTASY_ALANK    = _mod_blank.ECSTASY


# ═══════════════════════════════════════════════════════════════
# ── 区相关（从 cn_narratives/ 组装） ──────────────────────────
# ═══════════════════════════════════════════════════════════════

CONTAINER_VARIANTS = {
    "v":         _META_V,
    "variant_a": _META_A,
    "variant_u": _META_U,
    "blank":     _META_ALANK,
}

STIMULATE_BODY_LINES = {
    "v":         _STIMULATE_V,
    "variant_a": _STIMULATE_A,
    "variant_u": _STIMULATE_U,
    "blank":     _STIMULATE_ALANK,
}

RELIEVE_BODY_LINES = {
    "v":         _RELIEVE_V,
    "variant_a": _RELIEVE_A,
    "variant_u": _RELIEVE_U,
    "blank":     _RELIEVE_ALANK,
}

BIND_BODY_LINES = {
    "v":         _BIND_V,
    "variant_a": _BIND_A,
    "variant_u": _BIND_U,
    "blank":     _BIND_ALANK,
}

PROB_EVENT_CONTENT = {
    "v":         _PROB_V,
    "variant_a": _PROB_A,
    "variant_u": _PROB_U,
    "blank":     _PROB_ALANK,
}

CLEARING_NARRATIVE = {
    "v":         _CLEARING_V,
    "variant_a": _CLEARING_A,
    "variant_u": _CLEARING_U,
    "blank":     _CLEARING_ALANK,
}

SOUL_BREAK_NARRATIVE = {
    "v":         _SOUL_BREAK_V,
    "variant_a": _SOUL_BREAK_A,
    "variant_u": _SOUL_BREAK_U,
    "blank":     _SOUL_BREAK_ALANK,
}

ECSTASY_NARRATIVE = {
    "v":         _ECSTASY_V,
    "variant_a": _ECSTASY_A,
    "variant_u": _ECSTASY_U,
    "blank":     _ECSTASY_ALANK,
}


def get_variant(variant_key=None):
    """安全获取区配置，默认 v。"""
    return CONTAINER_VARIANTS.get(variant_key, CONTAINER_VARIANTS["v"])


# ═══════════════════════════════════════════════════════════════
# ── 公共复用叙事（从 cn_narratives/shared.py 导入并重新导出）──
# ═══════════════════════════════════════════════════════════════

from cn_narratives.shared import (
    BODY_NUMB_NARRATIVE,
    DOODLE_LEVEL_NAMES, DOODLE_BODY_LINES,
    CANDY_GIVE_BODY_LINES, CANDY_EAT_BODY_LINES,
    CANDY_EAT_OVERFILL_LINE, CANDY_EAT_SHAME_CLEARED_LINE,
    CANDY_EAT_BODY_RESTORED_LINE, CANDY_EAT_UNLOCKED_LINE,
    STIMULATE_CRITICAL_PAIN_LINE,
    STATUS_WARNINGS,
)


# ═══════════════════════════════════════════════════════════════
# ── 装配工具 ──────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def resolve(key, variant=None):
    """从叙事数据字典中按区配置取内容，默认 v。"""
    v = variant or "v"
    return key.get(v, key["v"])


def resolve_range(ranged: dict, val: int, default: str = "") -> str:
    """从 {(lo, hi): str, ...} 的范围内字典中取值。键为 (下限, 上限) 闭区间。"""
    for (lo, hi), text in ranged.items():
        if lo <= val <= hi:
            return text
    return default


# ═══════════════════════════════════════════════════════════════
# ── 向后兼容别名 ────────────────────────────────────────────
# CONTAINER_NARRATIVE_LEVELS 已迁移入 CONTAINER_VARIANTS["v"]["narrative_levels"]
# 保留此别名供 soul_core.py / api.py / utils.py / dashboard_app.py 等现有消费者使用。
# ═══════════════════════════════════════════════════════════════

CONTAINER_NARRATIVE_LEVELS = CONTAINER_VARIANTS["v"]["narrative_levels"]
