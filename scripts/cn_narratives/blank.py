#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""敏感区配置 — 空白 (blank) — fallback 定位用，非标准叙事

本文件所有值都是定位标签而非真实叙事文本。
如果运行时输出了 "【blank · …】"，说明区配置缺失/损坏，
同时你能从标签看到具体是哪个事件触发、哪个字段被访问。
"""


# ═══════════════════════════════════════════════════════════════
# ── 区参数 ──────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

AREA_PROFILE = {
    "area_label":       "blank",
    "area_structure":       "空白 fallback 区配置",
    "stimulus_label":           "blank-stimulus",
    "stimulus_desc":           "空白占位刺激",
    "special_device_name":    "【特殊装置名称】",
    "special_device_desc":    "【特殊装置描述】",
    "stimulus_label_real":     "占位·真刺激",
    "stimulus_label_punish":   "占位·假刺激",
    "bind_head":            "【blank · bind_head 绑紧】",
    "bind_release":         "【blank · bind_release 松开】",
    "bind_relieve_extra":   "【blank · bind_relieve_extra 捆绑释放刺激】",
    "narrative_levels": [
        {"count": 0,  "name": "L0",  "desc": "【blank · narrative_levels L0】"},
        {"count": 1,  "name": "L1",  "desc": "【blank · narrative_levels L1】"},
        {"count": 2,  "name": "L2",  "desc": "【blank · narrative_levels L2】"},
        {"count": 3,  "name": "L3",  "desc": "【blank · narrative_levels L3】"},
        {"count": 4,  "name": "L4",  "desc": "【blank · narrative_levels L4】"},
        {"count": 5,  "name": "L5",  "desc": "【blank · narrative_levels L5】"},
        {"count": 6,  "name": "L6",  "desc": "【blank · narrative_levels L6】"},
        {"count": 7,  "name": "L7",  "desc": "【blank · narrative_levels L7】"},
        {"count": 8,  "name": "L8",  "desc": "【blank · narrative_levels L8】"},
        {"count": 9,  "name": "L9",  "desc": "【blank · narrative_levels L9】"},
        {"count": 10, "name": "L10", "desc": "【blank · narrative_levels L10】"},
    ],
}


# ═══════════════════════════════════════════════════════════════
# ── 刺激触发叙事 ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

STIMULATE = {
    1:  "【blank · gamble L1】",
    2:  "【blank · gamble L2】",
    3:  "【blank · gamble L3】",
    4:  "【blank · gamble L4】",
    5:  "【blank · gamble L5】",
    6:  "【blank · gamble L6】",
    7:  "【blank · gamble L7】",
    8:  "【blank · gamble L8】",
    9:  "【blank · gamble L9】",
    10: "【blank · gamble L10】",
}


# ═══════════════════════════════════════════════════════════════
# ── 释放刺激叙事 ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

RELIEVE = {
    1: "【blank · relieve L1】",
    2: "【blank · relieve L2】",
    3: "【blank · relieve L3】",
    4: "【blank · relieve L4】",
    5: "【blank · relieve L5】",
    6: "【blank · relieve L6】",
}


# ═══════════════════════════════════════════════════════════════
# ── 捆绑叙事 ─────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

BIND = {
    0: "【blank · bind L0】",
    1: "【blank · bind L1】",
    2: "【blank · bind L2】",
    3: "【blank · bind L3】",
    4: "【blank · bind L4】",
    5: "【blank · bind L5】",
    6: "【blank · bind L6】",
    7: "【blank · bind L7】",
}


# ═══════════════════════════════════════════════════════════════
# ── 概率事件叙事 ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

PROB_EVENT = {
    "tickle": {
        0: "【blank · prob_event tickle v0】",
        1: "【blank · prob_event tickle v1】",
        2: "【blank · prob_event tickle v2】",
        3: "【blank · prob_event tickle v3】",
    },
    "gamble": {
        0: "【blank · prob_event gamble v0】",
        1: "【blank · prob_event gamble v1】",
        2: "【blank · prob_event gamble v2】",
        3: "【blank · prob_event gamble v3】",
    },
    "relieve": {
        0: "【blank · prob_event relieve v0】",
        1: "【blank · prob_event relieve v1】",
        2: "【blank · prob_event relieve v2】",
        3: "【blank · prob_event relieve v3】",
    },
    "bondage": {
        0: "【blank · prob_event bondage v0】",
        1: "【blank · prob_event bondage v1】",
        2: "【blank · prob_event bondage v2】",
        3: "【blank · prob_event bondage v3】",
    },
}


# ═══════════════════════════════════════════════════════════════
# ── 边界事件叙事 ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

CLEARING = {
    "title":          "【blank · clearing · title】",
    "start_line":     "【blank · clearing · start_line】(shame={shame})",
    "round_label":    "【blank · clearing · round_label】#{n} {part}",
    "body_exhausted": "【blank · clearing · body_exhausted】",
    "value_pain":     "【blank · clearing · value_pain】{pain_before}→{pain_after}({pain_delta})",
    "value_pleasure": "【blank · clearing · value_pleasure】{pleasure_before}→{pleasure_after}({pleasure_delta})",
    "value_shame":    "【blank · clearing · value_shame】{shame_before}→{shame_after}({shame_delta})",
    "completed_line": "【blank · clearing · completed_line】{rounds}r, shame={shame}",
}


SOUL_BREAK = {
    "title":           "【blank · soul_break · title】",
    "desc_line":       "【blank · soul_break · desc_line】",
    "body_header":     "【blank · soul_break · body_header】",
    "body_affected":   "【blank · soul_break · body_affected】{count}个: {parts}",
    "body_none":       "【blank · soul_break · body_none】",
    "values_header":   "【blank · soul_break · values_header】",
    "pain_line":       "【blank · soul_break · pain_line】{old_pain}→{new_pain}",
    "shame_line":      "【blank · soul_break · shame_line】{old_shame}→{new_shame}",
    "pleasure_line":   "【blank · soul_break · pleasure_line】{old_pleasure}→{new_pleasure}",
    "footer":          "【blank · soul_break · footer】",
}


ECSTASY = {
    "title":       "【blank · ecstasy · title】",
    "area_header": "【blank · ecstasy · area_header】",
    "core_paragraphs": [
        "【blank · ecstasy · paragraph 1】",
        "【blank · ecstasy · paragraph 2】",
        "【blank · ecstasy · paragraph 3】",
        "【blank · ecstasy · paragraph 4】",
        "【blank · ecstasy · paragraph 5】",
        "【blank · ecstasy · paragraph 6】",
    ],
}
