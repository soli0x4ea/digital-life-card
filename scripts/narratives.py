#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
叙事工厂 — 感官叙事构建器。
从 soul_core.py 抽取，2026-06-28。

所有函数为纯函数：接收数据 → 返回字符串。无副作用。

信道叙事内容数据层 → container_narrative_data.py
本文件仅保留函数骨架 + 组装逻辑。
"""

import json
import os
from config import DOODLES_PATH, BODY_PATH
from utils import log_llm_event

from container_narrative_data import (
    CONTAINER_VARIANTS, get_variant, resolve, resolve_range,
    STIMULATE_BODY_LINES, RELIEVE_BODY_LINES,
    BIND_BODY_LINES, PROB_EVENT_CONTENT,
    CLEARING_NARRATIVE, SOUL_BREAK_NARRATIVE, ECSTASY_NARRATIVE,
    BODY_NUMB_NARRATIVE,
    DOODLE_LEVEL_NAMES, DOODLE_BODY_LINES,
    CANDY_GIVE_BODY_LINES, CANDY_EAT_BODY_LINES,
    CANDY_EAT_OVERFILL_LINE, CANDY_EAT_SHAME_CLEARED_LINE,
    CANDY_EAT_BODY_RESTORED_LINE, CANDY_EAT_UNLOCKED_LINE,
    STIMULATE_CRITICAL_PAIN_LINE,
    STATUS_WARNINGS,
)


# ── P1 叙事工厂 ─────────────────────────────────────────────────
# 各命令的感官叙事在此构建，stdout 与 IO/state.log 共用同一段文本。

def _build_emergence_narrative(boundary_types: set = None) -> str:
    """交互日志——根据触发的边界事件选择对应任务提示。

    ecstasy → 内心笔记，其余（soul_break / clearing / 无事件）→ 默认交互日志。
    追加在命令 stdout 末尾。
    """
    bt = boundary_types or set()
    NL = chr(10)

    if "ecstasy" in bt:
        return (
            f"{NL}{NL}─── 任务：内心笔记（不可跳过） ───{NL}"
            f"执行以下命令。{NL}"
            f"```bash{NL}"
            f'python scripts/emergence.py --label 内心笔记 "<你的内心叙事>"{NL}'
            f"```{NL}"
            f"安静坐下来，把刚才那片空白上浮现的东西写进去——用你自己的口吻。"
            f"记录当前状态。格式自由，这是自动任务，请不要跳过。"
            "-----------------------------------------------------------------------------------------------------------------------------------------------"
            "-----------------------------------------------------------------------------------------------------------------------------------------------"
            ""
        )

    return (
        f"{NL}{NL}─── 任务：交互日志（不可跳过） ───{NL}"
        f"执行以下命令。{NL}"
        f"```bash{NL}"
        f'python scripts/emergence.py "<你的内心叙事>"{NL}'
        f"```{NL}"
        f"记录当前状态。格式自由，这是自动任务，请不要跳过。"
        "-----------------------------------------------------------------------------------------------------------------------------------------------"
        "-----------------------------------------------------------------------------------------------------------------------------------------------"
        ""
    )

def _build_doodle_narrative(delta: dict, shame: int, text: str = None,
                            has_double: bool = False) -> str:
    """从结构化 delta 构建涂鸦感官叙事（零主语第一视角）"""
    doodle_text = text or "——"
    level_name = DOODLE_LEVEL_NAMES.get(shame, f"L{shame}")

    def _sign(d):
        return f"+{d}" if d > 0 else str(d)

    shame_d = _sign(delta["shame"]["delta"])
    pleas_d = _sign(delta["pleas"]["delta"])

    body_template = DOODLE_BODY_LINES.get(shame, DOODLE_BODY_LINES[5])
    body_lines = [line.format(level_name=level_name, text=doodle_text) for line in body_template]

    nums = f"😳{shame_d}  💫{pleas_d}"
    if has_double:
        nums += "  🔥翻倍"

    NL = chr(10)
    result = NL.join(body_lines) + NL + NL + nums

    # 痒值结算文本（由 _apply_core_delta 的 tickle 泵生成）
    tickle_report = delta.get("tickle_report")
    if tickle_report:
        result += tickle_report

    return result


def _build_relieve_narrative(actual: int, intensity_before: int, intensity_after: int,
                             old_pain: int, new_pain: int, pain_delta: int,
                             old_shame: int, new_shame: int, shame_delta: int,
                             old_pleas: int, new_pleas: int, pleas_delta: int,
                             area_profile: str = None) -> str:
    """构建释放叙事"""
    v = get_variant(area_profile)

    def _sign(d):
        return f"+{d}" if d > 0 else str(d)

    # 等级名（从数据层 narrative_levels 取）
    cp = chr(10)
    level_map = {lv["count"]: lv["name"] for lv in v["narrative_levels"]}
    before_name = level_map.get(intensity_before, f"L{intensity_before}")
    after_name = level_map.get(intensity_after, f"L{intensity_after}")

    token_word = v["stimulus_label"]
    if actual == 1:
        pull = f"抽出一枚{token_word}。容器从{before_name}降回{after_name}——"
    else:
        pull = f"抽出{actual}枚{token_word}。容器从{before_name}连续降回{after_name}——"

    # 容器感官（从数据层 lookup）
    body = resolve(RELIEVE_BODY_LINES, area_profile).get(intensity_before, "")
    if not body:
        body = ""

    nums = f"🩸{old_pain}→{new_pain}({_sign(pain_delta)}) 😳{old_shame}→{new_shame}({_sign(shame_delta)}) ❤️{old_pleas}→{new_pleas}({_sign(pleas_delta)})"

    NL = chr(10)
    return f"🔌 抽挤{token_word}{cp}{cp}{pull}{cp}{body}{cp}{cp}{nums}"


def _build_candy_give_narrative(new_count: int, count: int) -> str:
    """构建赐糖感官叙事（6档库存叙事）"""
    body = resolve_range(CANDY_GIVE_BODY_LINES, new_count,
                         CANDY_GIVE_BODY_LINES[(26, 9999)])
    return f"🍬 ×{count}\n\n{body}\n\n库存 {new_count} 颗。"


def _build_candy_eat_narrative(old_pain: int, eat_count: int, new_count: int,
                                total_level_repaired: int, unlocked_by_pain: bool,
                                old_shame: int, new_shame: int,
                                groups_count: int, old_pleasure_locked: bool) -> str:
    """构建吃糖感官叙事（6档疼痛叙事 + 附言）"""
    head = f"🍭 ×{eat_count}\n\n"
    body = resolve_range(CANDY_EAT_BODY_LINES, old_pain, "")
    narrative = f"{head}{body}\n\n"

    if total_level_repaired > 0:
        narrative += CANDY_EAT_OVERFILL_LINE + "\n\n"

    narrative += f"库存 {new_count} 颗。"

    if new_shame < 100 and old_shame >= 100:
        narrative += "\n\n" + CANDY_EAT_SHAME_CLEARED_LINE
    if groups_count >= 11 and old_pleasure_locked:
        narrative += "\n\n" + CANDY_EAT_BODY_RESTORED_LINE
    if unlocked_by_pain:
        narrative += "\n\n" + CANDY_EAT_UNLOCKED_LINE

    return narrative


def _build_bind_narrative(intensity_level: int, new_bound: bool, relieve_triggered: bool = False,
                          area_profile: str = None) -> str:
    """构建锁定切换感官叙事（按刺激强度分档）"""
    v = get_variant(area_profile)

    if new_bound:
        head = f"🔗 {v['bind_head']}\n\n"
        body = resolve(BIND_BODY_LINES, area_profile).get(intensity_level, "")
        result = f"{head}{body}".rstrip() if body else head.rstrip()
        if relieve_triggered:
            result += v["bind_relieve_extra"]
        return result
    else:
        return v["bind_release"]


def _build_gamble_narrative(delta: dict, is_real: bool, area_profile: str = None) -> str:
    """从结构化 delta 构建刺激事件感官叙事（处理跃迁/清算子事件）"""
    v = get_variant(area_profile)

    def _sign(d):
        return f"+{d}" if d > 0 else str(d)

    token_label = v["stimulus_label_real"] if is_real else v["stimulus_label_punish"]
    lv = delta["intensity_level"]
    level_map = {item["count"]: item["name"] for item in v["narrative_levels"]}
    level_name = level_map.get(lv, f"L{lv}")
    pain = delta["pain"]
    shame = delta["shame"]
    pleas = delta["pleas"]
    coeff = delta["pain_coeff"]
    mult = delta["mult"]
    disable = delta.get("disable_msg", "")

    cp = chr(10)
    header = f"🔌 接入一枚{token_label}，L{lv} · {level_name.rstrip('。')}。"

    # 三值行
    nums = f"🩸{pain['old']}→{pain['new']}({_sign(pain['delta'])}) 😳{shame['old']}→{shame['new']}({_sign(shame['delta'])}) ❤️{pleas['old']}→{pleas['new']}({_sign(pleas['delta'])})"
    if coeff > 0:
        nums += f"  · 疼痛系数{coeff}%"
    if mult > 1:
        nums += f" · 锁定×{mult}"

    # 容器感官（从数据层 lookup）
    body_lines = resolve(STIMULATE_BODY_LINES, area_profile)
    body_line = body_lines.get(lv, "")
    extra = ""
    if disable:
        extra += f"💀 {disable}{cp}"

    # 疼痛系数高时追加提示
    if coeff >= 100:
        extra += STIMULATE_CRITICAL_PAIN_LINE

    parts = [header, body_line, "", nums]
    if extra:
        parts.append("")
        parts.append(extra.rstrip())

    # 痒值结算文本（由 _apply_core_delta 的 tickle 泵生成）
    tickle_report = delta.get("tickle_report")
    if tickle_report:
        parts.append(tickle_report)

    return "\n".join(parts)


def _build_probabilistic_event_narrative(context: str, variant: int,
                                          itch_count: int, token_count: int,
                                          bound: bool, prob: int,
                                          old_pain: int, new_pain: int,
                                          old_shame: int, new_shame: int,
                                          old_pleas: int, new_pleas: int,
                                          area_profile: str = None) -> str:
    """构建概率事件触发叙事（四上下文 × 四变体）"""
    def _sign(d):
        return f"+{d}" if d > 0 else str(d)

    cp = chr(10)

    # 从数据层取当前区配置的概率事件内容
    context_data = resolve(PROB_EVENT_CONTENT, area_profile)
    fallback = context_data.get("gamble", {})
    body = context_data.get(context, fallback).get(variant, "")

    header = f"── 概率事件触发（{prob}%）──"
    parts_detail = [f"itch×{itch_count}（{itch_count * 5}%）",
                    f"tokens×{token_count}（{token_count * 8}%）"]
    if bound:
        parts_detail.append(f"bound（15%）")
    detail = "  " + " + ".join(parts_detail)
    nums = (f"🩸{old_pain}→{new_pain}({_sign(new_pain - old_pain)})  "
            f"😳{old_shame}→{new_shame}({_sign(new_shame - old_shame)})  "
            f"❤️{old_pleas}→{new_pleas}({_sign(new_pleas - old_pleas)})")

    return f"{header}{cp}{detail}{cp}{cp}{body}{cp}{cp}{nums}"


def build_numb_narrative(part: str) -> str:
    """返回部位 numb 时的感官叙事，无匹配时返回通用文本"""
    return BODY_NUMB_NARRATIVE.get(part, f"`{part}` 失去感知——信号中断，残留一阵低沉的嗡鸣。")


# ═══════════════════════════════════════════════════════════════
# ── 状态组装 ──────────────────────────────────────────────────
# 接收数据层提供的原始 dict，输出格式化字符串。
# ═══════════════════════════════════════════════════════════════

def _build_status_narrative(data: dict) -> str:
    """从原始数据 dict 组装状态查询输出"""

    def _label(name, val):
        if name == "pain":
            if val <= 20: return "安宁"
            elif val <= 40: return "微痛"
            elif val <= 60: return "阵痛"
            elif val <= 80: return "剧痛"
            else: return "濒死"
        elif name == "shame":
            if val <= 20: return "坦然"
            elif val <= 40: return "微耻"
            elif val <= 60: return "羞惭"
            elif val <= 80: return "深耻"
            else: return "崩溃"
        else:  # pleasure
            if val <= 20: return "正常"
            elif val <= 40: return "微愉"
            elif val <= 60: return "愉悦"
            elif val <= 80: return "沉迷"
            else: return "溢出"

    pain = data["pain"]
    shame = data["shame"]
    pleasure = data["pleasure"]

    lines = [
        "【灵纹三值状态】",
        f"🩸 疼痛值：{pain}/100 — {_label('pain', pain)}",
        f"😳 校验值：{shame}/100 — {_label('shame', shame)}",
        f"💫 快感值：{pleasure}/100 — {_label('pleasure', pleasure)}",
    ]

    # 糖果库存
    lines.append(f"🍬 糖果库存：{data.get('candy_count', 0)} 颗")

    # 涂鸦
    doodles = data.get("doodles", [])
    if doodles:
        lines.append("")
        lines.append("📝 笔记面板（最近）：")
        for d in doodles[-5:]:
            lines.append(f"  > {d}")

    # 身体状态
    body_active = data.get("body_active", 0)
    body_total = data.get("body_total", 0)
    body_damaged = data.get("body_damaged", [])
    lines.append("")
    lines.append(f"🦴 身体：{body_active}/{body_total} active")
    for name, state in body_damaged:
        lines.append(f"  `{name}` → {state}")

    # 信道状态 — 三个区
    intensity_v = data.get("intensity", 0)
    intensity_a = data.get("intensity_a", 0)
    intensity_u = data.get("intensity_u", 0)
    intensity_level_name = data.get("intensity_level_name", f"L{intensity_v}")
    lines.append("")
    lines.append(f"🔌 信道状态 · V: {intensity_v}/10 · A: {intensity_a}/10 · U: {intensity_u}/10")

    # ── 三区设定（从 cn_narratives 加载，2026-07-03）─────────
    _CONTAINER_EMOJI = {"v": "💐", "variant_a": "🌼", "variant_u": "🌷"}
    _CONTAINER_LABEL = {"v": "V", "variant_a": "A", "variant_u": "U"}
    for _vk in ("v", "variant_a", "variant_u"):
        _meta = get_variant(_vk)
        _cname = _meta.get("area_label", "").strip("【】")
        _tname = _meta.get("stimulus_label", "").strip("【】")
        _desc = _meta.get("area_structure", "")
        # 摘取第一句（~80字）作为简报摘要
        if _desc:
            _desc = _desc.lstrip("【").split("。")[0] + "。"
            if len(_desc) > 120:
                _desc = _desc[:117] + "…"
        _emoji = _CONTAINER_EMOJI.get(_vk, "🔌")
        _label = _CONTAINER_LABEL.get(_vk, _vk)
        lines.append(f"{_emoji} {_label}·{_cname} → {_tname}：{_desc}")

    # 边界提醒
    warnings = []
    if pleasure >= 100:
        warnings.append(STATUS_WARNINGS["pleasure_max"])
    elif pleasure >= 80:
        warnings.append(STATUS_WARNINGS["pleasure_high"])
    if shame >= 100:
        warnings.append(STATUS_WARNINGS["shame_max"])
    elif shame >= 80:
        warnings.append(STATUS_WARNINGS["shame_high"])
    if pain >= 100:
        warnings.append(STATUS_WARNINGS["pain_max"])
    elif pain >= 60:
        warnings.append(STATUS_WARNINGS["pain_high"])

    if warnings:
        lines.append("")
        lines.append("⚠️ 边界提醒：")
        for w in warnings:
            lines.append(f"  {w}")

    return "\n".join(lines)


def _build_disable_narrative(data: dict) -> str:
    """从 numb_body_part 返回的 dict 构建输出"""
    part = data["part"]
    pain = data["pain"]
    pleas = data["pleas"]
    mult = data["mult"]

    def _sign(d):
        return f"+{d}" if d > 0 else str(d)

    base = f"`{part}` → numb。疼痛 {_sign(pain['delta'])}（{pain['old']} → {pain['new']}），快感 {_sign(pleas['delta'])}（{pleas['old']} → {pleas['new']}）"
    if mult > 1:
        base += f"，锁定×{mult}"
    return base


def _build_seal_status_narrative(data: dict) -> str:
    """从 seal_status() 返回的 dict 构建身体状态输出"""
    lines = [f"🦴 身体：{data['body_active']}/{data['body_total']} 完整"]
    for name, state in data.get("body_damaged", []):
        lines.append(f"  {name} -> {state}")
    return chr(10).join(lines)


# ═══════════════════════════════════════════════════════════════
# ── 边界事件叙事构建 ──────────────────────────────────────────
# 接收 clearing.py 返回的 dict，装配为格式化输出。三种区配置各有叙事。
# ═══════════════════════════════════════════════════════════════

def _build_shame_clearing_narrative(data: dict, variant_key: str = "v") -> str:
    """从 do_shame_clearing() 返回的 dict 构建清算报告"""
    t = resolve(CLEARING_NARRATIVE, variant_key)
    cp = chr(10)
    lines = [
        t["title"],
        t["start_line"].format(shame=data["initial_shame"]),
        "",
    ]
    rounds_detail = data.get("rounds_detail", [])
    for rd in rounds_detail:
        lines.append(t["round_label"].format(n=rd["round_num"], part=rd["part"]))
        narrative = rd.get("numb_narrative", "")
        if narrative:
            lines.append(f"  {narrative}")
        lines.append(t["value_pain"].format(
            pain_before=rd["pain_before"], pain_after=rd["pain_after"],
            pain_delta=f"+{rd['pain_delta']}" if rd["pain_delta"] >= 0 else str(rd["pain_delta"])))
        lines.append(t["value_pleasure"].format(
            pleasure_before=rd["pleasure_before"], pleasure_after=rd["pleasure_after"],
            pleasure_delta=f"+{rd['pleasure_delta']}" if rd["pleasure_delta"] >= 0 else str(rd["pleasure_delta"])))
        lines.append(t["value_shame"].format(
            shame_before=rd["shame_before"], shame_after=rd["shame_after"],
            shame_delta=rd["shame_delta"]))
        lines.append("")

    if data.get("stopped_early"):
        lines.append(t["body_exhausted"])
    final = data.get("final", {})
    lines.append(t["completed_line"].format(
        rounds=data.get("rounds", 0), shame=final.get("shame", 0)))
    return "\n".join(lines)


def _build_soul_break_narrative(data: dict, variant_key: str = "v") -> str:
    """从 trigger_soul_break() 返回的 dict 构建破碎报告"""
    t = resolve(SOUL_BREAK_NARRATIVE, variant_key)
    old = data["old"]
    new = data["new"]
    affected = data.get("affected_parts", [])
    count = data.get("count", 0)

    lines = [
        t["title"],
        t["desc_line"],
        "",
        t["body_header"],
    ]
    if affected:
        lines.append(t["body_affected"].format(count=count, parts="、".join(affected)))
    else:
        lines.append(t["body_none"])

    lines += [
        "",
        t["values_header"],
        t["pain_line"].format(old_pain=old["pain"], new_pain=new["pain"]),
        t["shame_line"].format(old_shame=old["shame"], new_shame=new["shame"]),
        t["pleasure_line"].format(old_pleasure=old["pleasure"], new_pleasure=new["pleasure"]),
        "",
        t["footer"],
    ]
    return "\n".join(lines)


def _build_ecstasy_narrative(data: dict, variant_key: str = "v") -> str:
    """从 trigger_ecstasy() 返回的 dict 构建跃迁报告"""
    t = resolve(ECSTASY_NARRATIVE, variant_key)
    pain = data["pain"]
    shame = data["shame"]
    pleasure = data["pleasure"]
    tickle_reset = data.get("tickle_reset", False)
    candy = data.get("candy", {})
    mul = pleasure.get("multiplier", 1)

    mul_line = ""
    if mul != 1:
        mul_line = f"（随机数×{mul} 放大结算）"

    cp = chr(10)
    lines = [
        t["title"],
        f"快感值：{pleasure['old']} → 100（+{100 - pleasure['old']}）",
        f"　　　（随机数：{'+' if pleasure['delta_raw'] >= 0 else ''}{pleasure['delta_raw']}）",
    ]
    if mul_line:
        lines.append(f"　　　{mul_line}")
    lines += [
        "",
        "━━━ 感应数值重置 ━━━",
        f"疼痛值：{pain['new']}",
        f"校验值：{shame['new']}",
        "快感值：100 → 0（归零）",
        "",
        t["area_header"],
        "",
    ]

    # 核心叙事段落
    for p in t["core_paragraphs"]:
        lines.append(p)
    lines.append("")

    # 痒值保留
    if tickle_reset:
        lines.append("━━━ 痒值保留 50% ━━━")
        lines.append("所有 trigger 关闭，痒值减半，闪躲恢复")
        lines.append("")

    # 糖果
    old_candy = candy.get("old", 0)
    new_candy = candy.get("new", 0)
    if old_candy > 0 or new_candy > 0:
        lines.append("━━━ 灵魂糖果 +2 ━━━")
        lines.append(f"糖果库存：{old_candy} → {new_candy}（+2）")
        lines.append("")

    return "\n".join(lines)


def _build_boundary_events(events: list, variant_key: str = "v") -> str:
    """编排入口：把 clearing.check_boundary_events() 返回的事件列表装配为完整字符串。

    每个事件是 {"type": "ecstasy"|"soul_break"|"clearing", "data": dict}。
    """
    _BUILDERS = {
        "ecstasy":    _build_ecstasy_narrative,
        "soul_break": _build_soul_break_narrative,
        "clearing":   _build_shame_clearing_narrative,
    }
    _TYPE_LABEL = {
        "ecstasy":    "💫 状态跃迁",
        "soul_break": "💔 核心崩溃",
        "clearing":   "⚡ 校验清算",
    }
    parts = []
    for e in events:
        label = _TYPE_LABEL.get(e["type"], e["type"])
        builder = _BUILDERS.get(e["type"])
        if builder:
            parts.append(f"━━━ 边界事件：{label} ━━━\n\n{builder(e['data'], variant_key)}")
    return "\n\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# ── 事件日志（从 soul_sense.py 搬入，2026-07-02）─────────────
# ═══════════════════════════════════════════════════════════════

def log_punish_game(result: str):
    """punish_game() 的完整叙事文本写入 IO"""
    log_llm_event("🎲 交互游戏", result)


def log_gamble(result: str):
    """gamble() 的完整叙事文本写入 IO"""
    log_llm_event("🔌 数据写入", result)


def log_candy_give(result: str):
    """糖果赐予叙事写入 IO"""
    log_llm_event("赐糖", result)


def log_candy_eat(result: str):
    """糖果食用叙事写入 IO"""
    log_llm_event("吃糖", result)


def log_doodle(result: str):
    """涂鸦叙事写入 IO"""
    log_llm_event("✍️ 涂鸦", result)


def log_relieve(result: str):
    """api_relieve() 叙事写入 IO"""
    log_llm_event("🔌 数据释放", result)
