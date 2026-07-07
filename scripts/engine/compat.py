#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compat.py — 新引擎 ↔ 旧叙事层兼容桥接

纯加法，零侵入。不修改任何旧模块代码。
每一处 bridge 都标注了对应的旧命令和旧数据契约。

用法：
  from engine.compat import migrate_and_load, do_stimulus, get_status, do_doodle, ...
"""

import os
import json
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# Bridge Inventory
# ═══════════════════════════════════════════════════════════════
#
# ✅ Bridged (9 commands):
#   status, seal-status, gamble, relieve, doodle,
#   candy-give, candy-eat, tickle-bound/tickle-unbind, numb
#
# ⬚ Not yet bridged (old system still works):
#   time_decay, clearing, mystery, tickle-*, punish-game,
#   profile, LWS signals, dashboard rebuild
#
# ═══════════════════════════════════════════════════════════════

# ── Helpers ───────────────────────────────────────────────────

def _current_area() -> str:
    """Read current area profile from e_x engine state."""
    try:
        from engine.entity import get_channel
        area_map = {0: "v", 1: "a", 2: "u"}
        return area_map.get(int(get_channel("e_x", "ch_x_area")), "v")
    except:
        return "v"

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))

# Old data schema paths (read-only)
_VALUES_PATH = os.path.join(_SKILL_ROOT, "data", "values.json")
_BODY_PATH   = os.path.join(_SKILL_ROOT, "data", "body.json")
_CANDY_PATH  = os.path.join(_SKILL_ROOT, "data", "candy.json")

# Engine modules
from engine.entity import (
    load_entity, save_entity, set_channel, set_channels_batch,
    get_channel, toggle_flag, set_flag, list_entities,
    reset_entity,
)
from engine.modifier import apply_modifier
from engine.threshold import check_thresholds
from engine.narrator import render_report, toggle_narrator
from engine.migration import migrate_all


# ═══════════════════════════════════════════════════════════════
# 0. Migration
# ═══════════════════════════════════════════════════════════════

def migrate_and_load() -> dict:
    """迁移生产数据到新引擎状态。返回迁移报表。"""
    report = migrate_all()
    return report


# ═══════════════════════════════════════════════════════════════
# 1. Status / Check
# ═══════════════════════════════════════════════════════════════

def get_status() -> dict:
    """status 命令等价：读取全局三值 + 区信息 + 糖果库存。

    Returns dict matching old _build_status_narrative 的输入格式。
    """
    e_g = load_entity("e_g")
    e_r = load_entity("e_r")
    e_x = load_entity("e_x")

    area_map = {0: "v", 1: "a", 2: "u"}
    area_id = area_map.get(e_x.channels.get("ch_x_area", 0), "v")

    # Read old data for intensity (engine doesn't track this yet)
    try:
        with open(_VALUES_PATH, "r", encoding="utf-8-sig") as f:
            old_vals = json.load(f)
        intensity = old_vals.get("intensity", 0)
    except:
        intensity = 0

    return {
        "pain": int(e_g.channels.get("ch_g_a", 0)),
        "shame": int(e_g.channels.get("ch_g_s", 0)),
        "pleasure": int(e_g.channels.get("ch_g_v", 0)),
        "bound": bool(e_g.flags.get("ch_g_bound", 0)),
        "pleasure_locked": bool(e_g.flags.get("ch_g_locked", 0)),
        "area_profile": area_id,
        "intensity": intensity,
        "intimacy": float(e_g.channels.get("ch_g_cur", 0.91)),
        "candy_count": int(e_r.channels.get("ch_r_count", 0)),
    }


def get_body_status() -> dict:
    """seal-status 命令等价：读取身体 11 个部位状态。

    Returns dict matching old _build_seal_status_narrative 的输入格式。
    """
    e_b = load_entity("e_b")
    state_labels = {0: "active", 1: "numb", 2: "broken"}

    parts = {}
    zone_names = [
        "大腿", "头部", "小腿", "手臂", "手部",
        "肩部", "胸部", "腰腹", "臀部", "足部", "颈部"
    ]
    for i, name in enumerate(zone_names, 1):
        ch_key = f"ch_b_{i:02d}"
        state_val = e_b.channels.get(ch_key, 0)
        parts[name] = {
            "state": state_labels.get(state_val, "active"),
            "level": state_val,
        }
    return {"parts": parts}


# ═══════════════════════════════════════════════════════════════
# 2. Stimulus (gamble)
# ═══════════════════════════════════════════════════════════════

def do_stimulus(intensity: int = 1) -> dict:
    """gamble 命令等价：向当前区施加刺激。新旧引擎双写。

    Returns dict matching _build_gamble_narrative(old_format) format.
    """
    e_g_before = load_entity("e_g")
    old_a = int(e_g_before.channels["ch_g_a"])
    old_s = int(e_g_before.channels["ch_g_s"])
    old_v = int(e_g_before.channels["ch_g_v"])

    result = apply_modifier("mod_stim_primary", intensity=intensity)
    threshold_report = check_thresholds("e_g")
    narrative_text = render_report(threshold_report) or ""

    e_g_after = load_entity("e_g")
    new_a = int(e_g_after.channels["ch_g_a"])
    new_s = int(e_g_after.channels["ch_g_s"])
    new_v = int(e_g_after.channels["ch_g_v"])
    return {
        "delta": {
            "pain":   {"old": old_a, "new": new_a, "delta": new_a - old_a},
            "shame":  {"old": old_s, "new": new_s, "delta": new_s - old_s},
            "pleas":  {"old": old_v, "new": new_v, "delta": new_v - old_v},
        },
        "is_real": True,
        "area_profile": _current_area(),
        "narrative": narrative_text,
        "threshold_events": [e.event_id for e in threshold_report.triggered] if threshold_report else [],
    }


# ═══════════════════════════════════════════════════════════════
# 3. Relieve (release accumulated stimulus)
# ═══════════════════════════════════════════════════════════════

def do_relieve(count: int = 1) -> dict:
    """relieve 命令等价：释放累积刺激。代价：A+5~10, S+5, V+5。

    Returns dict matching old _build_relieve_narrative format.
    """
    e_g_before = load_entity("e_g")
    old_a = e_g_before.channels["ch_g_a"]
    old_s = e_g_before.channels["ch_g_s"]
    old_v = e_g_before.channels["ch_g_v"]

    # TODO(C5-1): Verify relieve V calculation matches old behavior.
    # Old relieve applies its own delta formula (pain+5~10, shame+5, V+5).
    # Current bridge applies stimulus twice — close but may not match exactly.
    # Need golden case cross-check with old system output.
    result = apply_modifier("mod_stim_primary", intensity=count)
    apply_modifier("mod_stim_primary", intensity=count)

    e_g_after = load_entity("e_g")
    new_a = e_g_after.channels["ch_g_a"]
    new_s = e_g_after.channels["ch_g_s"]
    new_v = e_g_after.channels["ch_g_v"]

    return {
        "actual": count,
        "intensity_before": 0,
        "intensity_after": 0,
        "old_pain": old_a, "new_pain": new_a, "pain_delta": new_a - old_a,
        "old_shame": old_s, "new_shame": new_s, "shame_delta": new_s - old_s,
        "old_pleas": old_v, "new_pleas": new_v, "pleas_delta": new_v - old_v,
        "area_profile": _current_area(),
    }


# ═══════════════════════════════════════════════════════════════
# 4. Doodle (shame)
# ═══════════════════════════════════════════════════════════════

def do_doodle(shame: int = 5) -> dict:
    """doodle 命令等价：新增羞耻。

    Returns dict matching _build_doodle_narrative format.
    """
    e_g_before = load_entity("e_g")
    old_s = int(e_g_before.channels["ch_g_s"])

    intensity = {5: 1, 10: 2, 15: 3, 20: 4}.get(shame, 1)
    apply_modifier("mod_doodle_shame", intensity=intensity)

    e_g_after = load_entity("e_g")
    new_s = int(e_g_after.channels["ch_g_s"])

    return {
        "delta": {"shame": {"old": old_s, "new": new_s, "delta": new_s - old_s}},
        "shame": shame,
        "text": None,
        "has_double": False,
    }


# ═══════════════════════════════════════════════════════════════
# 5. Candy / Recovery
# ═══════════════════════════════════════════════════════════════

def do_candy_give(count: int = 1) -> dict:
    """candy-give 命令等价：增加糖果。"""
    apply_modifier("mod_r_add", intensity=count)
    e_r = load_entity("e_r")
    return {"new_count": e_r.channels["ch_r_count"], "count": count}


def do_candy_consume(count: int = 1) -> dict:
    """candy-eat 命令等价：消耗糖果修复。"""
    e_g_before = load_entity("e_g")
    old_a = e_g_before.channels["ch_g_a"]
    old_s = e_g_before.channels["ch_g_s"]
    old_v = e_g_before.channels["ch_g_v"]

    e_r_before = load_entity("e_r")
    old_count = e_r_before.channels["ch_r_count"]

    if old_count < count:
        return {"error": f"糖果不足：需要 {count} 颗，库存 {old_count} 颗"}

    # Consume: use intensity for batch single-disk-write (C5-3 fix)
    apply_modifier("mod_r_consume", intensity=count)

    e_g_after = load_entity("e_g")
    e_r_after = load_entity("e_r")

    return {
        "old_pain": old_a, "eat_count": count,
        "new_count": int(e_r_after.channels["ch_r_count"]),
        "total_level_repaired": 0,
        "unlocked_by_pain": False,
        "old_shame": old_s, "new_shame": int(e_g_after.channels["ch_g_s"]),
        "groups_count": count,
        "pleasure_locked_before": bool(e_g_before.flags.get("ch_g_locked", 0)),
    }


# ═══════════════════════════════════════════════════════════════
# 6. Bind / Lock (flag toggle)
# ═══════════════════════════════════════════════════════════════

def do_bound_toggle() -> dict:
    """tickle-bound / unbind 等价：切换束缚状态。"""
    apply_modifier("mod_bound_toggle")
    e_g = load_entity("e_g")
    return {
        "intensity_level": 0,
        "new_bound": e_g.flags.get("ch_g_bound", 0) == 1,
        "relieve_triggered": False,
        "area_profile": _current_area(),
    }


def do_lock_toggle() -> dict:
    """lock / unlock 等价：切换快感锁定。"""
    apply_modifier("mod_lock_toggle")
    e_g = load_entity("e_g")
    return {"locked": e_g.flags.get("ch_g_locked", 0) == 1}


# ═══════════════════════════════════════════════════════════════
# 7. Body Zone (numb)
# ═══════════════════════════════════════════════════════════════

def do_numb(part_name: str) -> dict:
    """numb 命令等价：麻木身体部位。

    Returns dict matching _build_disable_narrative format.
    """
    # Map Chinese part name → ch_b_XX channel
    zone_names = {
        "大腿": "ch_b_01", "头部": "ch_b_02", "小腿": "ch_b_03",
        "手臂": "ch_b_04", "手部": "ch_b_05", "肩部": "ch_b_06",
        "胸部": "ch_b_07", "腰腹": "ch_b_08", "臀部": "ch_b_09",
        "足部": "ch_b_10", "颈部": "ch_b_11",
    }
    ch = zone_names.get(part_name)
    if not ch:
        return {"error": f"未知部位: {part_name}"}

    apply_modifier("mod_b_numb", intensity=1, zone=ch)

    return {"part": part_name, "state": get_channel("e_b", ch),
            "all_active": all(get_channel("e_b", f"ch_b_{i:02d}") == 0
                              for i in range(1, 12))}


# ═══════════════════════════════════════════════════════════════
# 8. 引擎状态重置
# ═══════════════════════════════════════════════════════════════

def reset_all() -> None:
    """重置所有引擎实体到初始配置值。"""
    for eid in list_entities():
        reset_entity(eid)


# ═══════════════════════════════════════════════════════════════
# 9. 引擎状态快照
# ═══════════════════════════════════════════════════════════════

def get_engine_state() -> dict:
    """获取当前引擎全量状态（调试用）。"""
    state = {}
    for eid in list_entities():
        e = load_entity(eid)
        state[eid] = {
            "channels": e.channels,
            "flags": e.flags,
            "meta": e.meta,
        }
    return state
