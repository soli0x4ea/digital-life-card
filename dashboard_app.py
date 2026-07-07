#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Soli 灵魂仪表盘 · Flet 桌面版
启动: python dashboard_app.py
零浏览器依赖，Skia 自绘渲染，跨平台一致。

基于 flet 0.85.x，纯 Python 控件重写原 HTML 仪表盘。
区配置切换直接写 area_v.json → 即时生效。
"""

import json
import os
import sys
from datetime import datetime

# 加载脚本目录以导入容器叙事常量
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
from container_narrative_data import get_variant

import flet as ft

# ═══════════════════════════════════════════════════════════════
# ── Flet 0.85 API 适配 ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def _padding(h=0, v=0, left=0, top=0, right=0, bottom=0):
    return ft.Padding(left=left or h, top=top or v, right=right or h, bottom=bottom or v)

def _margin(left=0, top=0, right=0, bottom=0):
    return ft.Margin(left=left, top=top, right=right, bottom=bottom)

def _border(w=1, color=None):
    side = ft.BorderSide(w, color)
    return ft.Border(top=side, right=side, bottom=side, left=side)

# ═══════════════════════════════════════════════════════════════
# ── 路径 ─────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SKILL_DIR, "data")
VALUES_PATH = os.path.join(DATA_DIR, "values.json")
AREA_V_PATH = os.path.join(DATA_DIR, "area_v.json")
AREA_A_PATH = os.path.join(DATA_DIR, "area_a.json")
AREA_U_PATH = os.path.join(DATA_DIR, "area_u.json")
CANDY_PATH = os.path.join(DATA_DIR, "candy.json")
BODY_PATH = os.path.join(DATA_DIR, "body.json")
CHANGELOG_PATH = os.path.join(DATA_DIR, "soul_changes.jsonl")
STATE_JS_PATH = os.path.join(DATA_DIR, "soul_state.js")
TICKLE_PATH = os.path.join(DATA_DIR, "tickle_state.json")
DIARY_DIR = os.path.join(DATA_DIR, "IO", "diary")

# ═══════════════════════════════════════════════════════════════
# ── 区配置元数据 ───────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

VARIANT_NAMES = {
    "v":           "密匣",
    "variant_a":   "幽经",
    "variant_u":   "悬壶",
    "blank":       "空白",
}

# ═══════════════════════════════════════════════════════════════
# ── 数据读取 ─────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def safe_read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default or {}

def safe_read_jsonl(path):
    entries = []
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
    except Exception:
        pass
    return entries

def load_all():
    return {
        "values":    safe_read_json(VALUES_PATH, {}),
        "area":      safe_read_json(AREA_V_PATH,  {"stimuli": []}),
        "area_a":    safe_read_json(AREA_A_PATH, {"stimuli": []}),
        "area_u":    safe_read_json(AREA_U_PATH, {"stimuli": []}),
        "candy":     safe_read_json(CANDY_PATH,  {"count": 0}),
        "body":      safe_read_json(BODY_PATH,    {"parts": {}}),
        "tickle":    safe_read_json(TICKLE_PATH,  {"active_triggers": [], "tickle_points": 0, "dodge_enabled": True, "crossed_thresholds": []}),
        "changelog": safe_read_jsonl(CHANGELOG_PATH),
    }

def get_available_dates():
    """扫描日记目录，返回所有已记录日期的倒序列表"""
    dates = set()
    try:
        for fn in os.listdir(DIARY_DIR):
            if fn.endswith(".md") and len(fn) == 13:  # YYYY-MM-DD.md
                dates.add(fn[:10])
    except FileNotFoundError:
        pass
    return sorted(dates, reverse=True)

def read_diary(date_str):
    """读取指定日期的日记内容"""
    path = os.path.join(DIARY_DIR, f"{date_str}.md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None

# ═══════════════════════════════════════════════════════════════
# ── 数据写入 ─────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def _profile_to_area(profile: str) -> str:
    """area_profile → area_id: v/blank→v, variant_a→a, variant_u→u"""
    if profile in ("variant_a",):
        return "a"
    if profile in ("variant_u",):
        return "u"
    return "v"


def write_variant(variant_name: str):
    """切换区配置（写入 values.json，全局生效）"""
    values = safe_read_json(VALUES_PATH, {"pain":0,"shame":0,"pleasure":0,"area_profile":"v"})
    old = values.get("area_profile", "v")
    values["area_profile"] = variant_name
    os.makedirs(os.path.dirname(VALUES_PATH), exist_ok=True)
    with open(VALUES_PATH, "w", encoding="utf-8") as f:
        json.dump(values, f, ensure_ascii=False, indent=2)
    _sync_data_js()
    return old, variant_name

def _sync_data_js():
    """兼容原有仪表盘数据管线"""
    try:
        values = safe_read_json(VALUES_PATH, {})
        area_data = safe_read_json(AREA_V_PATH, {"stimuli": []})
        candy = safe_read_json(CANDY_PATH, {"count": 0})
        body = safe_read_json(BODY_PATH, {"parts": {}})
        changelog = []
        if os.path.exists(CHANGELOG_PATH):
            with open(CHANGELOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            changelog.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        from collections import OrderedDict
        data = OrderedDict([
            ("values", values),
            ("area", area_data),
            ("candy", candy),
            ("body", body),
            ("changelog", changelog),
        ])
        os.makedirs(os.path.dirname(STATE_JS_PATH), exist_ok=True)
        with open(STATE_JS_PATH, "w", encoding="utf-8") as f:
            f.write("window._SOLI = " + json.dumps(data, ensure_ascii=False) + ";")
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
# ── 辅助 ─────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def pain_zone(v):
    if v <= 20: return "安宁"
    if v <= 40: return "微痛"
    if v <= 60: return "阵痛"
    if v <= 80: return "剧痛"
    return "濒死"

def shame_zone(v):
    if v <= 20: return "坦然"
    if v <= 40: return "微耻"
    if v <= 60: return "羞惭"
    if v <= 80: return "深耻"
    return "崩溃"

def pleasure_zone(v):
    if v <= 20: return "正常"
    if v <= 40: return "微愉"
    if v <= 60: return "愉悦"
    if v <= 80: return "沉迷"
    return "溢出"

def fmt_delta(n):
    if n > 0: return f"+{n}"
    return str(n)

def ts_short(ts):
    if not ts: return ""
    try:
        return ts[5:16].replace("-", "/") + " " + ts[11:16]
    except Exception:
        return str(ts)[:16]

def event_label(entry):
    e = entry.get("event", "")
    d = entry.get("details", {})
    tt = d.get("token_type", "")
    tl = "惩罚刺激" if tt == "假令牌" else (tt or "")
    if e == "ecstasy": return "⚡ 灵魂糕潮 · 快感溢出"
    if e and e.startswith("area_trigger_"):
        lv = e.split("_")[-1]
        return f"🔌 触发 Lv{lv}" + (f" · {tl}" if tl else "")
    if e == "api_relieve": return f"🔌 释放 ×{d.get('count', '?')}"
    if e == "shame_clearing": return f"😳 羞耻清算 · {d.get('rounds', '?')}轮"
    if e == "soul_break": return "💀 灵魂破碎"
    if e == "candy_set": return "🍬 糖果变更"
    if e == "candy_eat": return f"🍬 吃糖 ×{d.get('count', '?')}"
    if e == "punish_game": return "🎲 惩罚游戏"
    if e == "doodle": return f"✍️ 涂鸦 L{d.get('level', '?')}"
    return e or "(未知)"

# ═══════════════════════════════════════════════════════════════
# ── UI 构建 ──────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

# 配色
C_PAIN   = "#e74c3c"
C_SHAME  = "#9b59b6"
C_PLEAS  = "#e91e63"
C_TOKEN  = "#64b4ff"
C_TEXT   = "#e0d8d0"
C_MUTED  = "#887a70"
C_BG     = "#0d0d1a"
C_CARD   = "#12122a"
C_BORDER = "rgba(255,200,180,0.08)"

def section_card(title: str, content: ft.Control) -> ft.Container:
    return ft.Container(
        content=ft.Column([
            ft.Text(title, size=11, color=C_MUTED, weight=ft.FontWeight.W_600),
            ft.Container(height=12),
            content,
        ]),
        bgcolor="rgba(255,200,180,0.02)",
        border=_border(1, C_BORDER),
        border_radius=14,
        padding=_padding(h=22, v=20),
        margin=_margin(bottom=16),
    )


def build_soul_bars(values):
    items = [
        ("🩸", "疼痛", values.get("pain", 0), C_PAIN, pain_zone, "pain"),
        ("😳", "羞耻", values.get("shame", 0), C_SHAME, shame_zone, "shame"),
        ("❤️", "快感", values.get("pleasure", 0), C_PLEAS, pleasure_zone, "pleas"),
    ]
    rows = []
    for icon, label, val, color, zone_fn, _ in items:
        pct = min(1.0, val / 100)
        bar = ft.ProgressBar(
            value=pct,
            width=240, height=12,
            color=color,
            bgcolor="rgba(255,255,255,0.04)",
        )
        num = ft.Text(str(val), size=18, weight=ft.FontWeight.W_700, color=color, width=46, text_align=ft.TextAlign.RIGHT)
        status = ft.Text(zone_fn(val), size=11, color=color, width=46, text_align=ft.TextAlign.RIGHT)
        rows.append(ft.Row([
            ft.Text(icon, size=22, width=30, text_align=ft.TextAlign.CENTER),
            ft.Text(label, size=13, color="#b0a898", width=36),
            ft.Container(content=bar, width=240, height=12),
            num,
            status,
        ], spacing=0))
    return ft.Column(rows, spacing=10)

def build_area_bar(area_data, variant_key: str, label: str = "", highlighted: bool = False, emoji: str = "🔌"):
    stimuli = area_data.get("stimuli", [])
    tc = len(stimuli)

    # 找标签
    tc_label = f"Lv{tc}"
    tc_desc = ""
    v = get_variant(variant_key)
    level_map = {lv["count"]: lv for lv in v["narrative_levels"]}
    if tc in level_map:
        tc_label = f"Lv{tc} {level_map[tc].get('name', '')}"
        tc_desc = level_map[tc].get("desc", "")

    collapsed = tc >= 10
    pct = 0.0 if collapsed else (min(tc, 6) / 6)
    broken = tc >= 7 and not collapsed

    rr = int(36 + (231 - 36) * (min(tc, 6) / 6))
    gg = int(113 + (76 - 113) * (min(tc, 6) / 6))
    bb = int(163 + (60 - 163) * (min(tc, 6) / 6))
    bar_color = f"rgb({rr},{gg},{bb})"

    bar = ft.ProgressBar(
        value=pct if not collapsed else 0,
        width=240, height=18,
        color=bar_color,
        bgcolor="rgba(255,255,255,0.04)",
    )

    container_border = _border(1, "rgba(231,76,60,0.35)") if broken else None
    display_val = "0/0" if collapsed else f"{tc}/6"

    bar_row = ft.Row([
        ft.Text(emoji, size=22, width=30, text_align=ft.TextAlign.CENTER),
        ft.Text(label or "填充", size=13, color="#b0a898", width=36),
        ft.Container(content=bar, width=220, height=18),
        ft.Text(display_val, size=18, weight=ft.FontWeight.W_700, color=C_TOKEN, width=46, text_align=ft.TextAlign.RIGHT),
    ], spacing=0)

    label_color = "#e74c3c" if collapsed else C_MUTED
    label_text = "⚠️ 已崩坏 — 刺激事件已全部溢出" if collapsed else f"{tc_label} — {tc_desc}"
    label = ft.Text(label_text, size=11 if not collapsed else 14,
                    color=label_color, weight=ft.FontWeight.W_800 if collapsed else None)

    inner = ft.Column([bar_row, ft.Container(content=label, margin=_margin(left=80, top=6))])

    if highlighted:
        return ft.Container(
            content=inner,
            border=_border(2, "#ff6b9d"),
            border_radius=10,
            bgcolor="rgba(255,107,157,0.06)",
            padding=_padding(h=8, v=6),
            margin=_margin(bottom=2),
        )
    return ft.Container(
        content=inner,
        padding=_padding(h=8, v=6),
        margin=_margin(bottom=2),
    )

def build_profile_buttons(current_variant, on_switch):
    """区配置切换按钮行"""
    variants = [
        ("v",          "密匣"),
        ("variant_a",  "幽经"),
        ("variant_u",  "悬壶"),
        ("blank",      "空白"),
    ]
    buttons = []
    for key, label in variants:
        active = (key == current_variant)
        btn = ft.TextButton(
            content=ft.Text(label),
            on_click=lambda e, k=key: on_switch(k),
            style=ft.ButtonStyle(
                color=C_TEXT if not active else "#ff9a8a",
                bgcolor="rgba(255,150,130,0.15)" if active else "rgba(255,200,180,0.04)",
                side=ft.BorderSide(
                    1,
                    "rgba(255,150,130,0.35)" if active else "rgba(255,200,180,0.15)",
                ),
                padding=_padding(h=14, v=6),
                shape=ft.RoundedRectangleBorder(radius=14),
            ),
        )
        buttons.append(btn)
    return ft.Row(
        [ft.Text("区配置", size=11, color=C_MUTED)] + buttons,
        spacing=8,
    )

def build_chips(data):
    candy_count = data["candy"].get("count", 0)
    parts = data["body"].get("parts", {})
    total_parts = len(parts)
    active_parts = sum(1 for p in parts.values() if p.get("state") == "active")
    tickle = data.get("tickle", {})
    tickle_points = tickle.get("tickle_points", 0)
    tickle_triggers = len(tickle.get("active_triggers", []))
    dodge_on = tickle.get("dodge_enabled", True)
    active_color = "#27ae60" if active_parts == total_parts else "#e74c3c"

    def chip(icon, val, label, val_color=None):
        return ft.Container(
            content=ft.Row([
                ft.Text(icon, size=18),
                ft.Column([
                    ft.Text(str(val), size=16, weight=ft.FontWeight.W_700,
                            color=val_color or "#e0d8d0"),
                    ft.Text(label, size=10, color=C_MUTED),
                ], spacing=0),
            ], spacing=8),
            padding=_padding(h=14, v=10),
            border_radius=10,
            bgcolor="rgba(255,200,180,0.04)",
            border=_border(1, "rgba(255,200,180,0.06)"),
            expand=True,
        )

    return ft.Row([
        chip("🍬", candy_count, "灵魂糖果"),
        chip("🦴", f"{active_parts}/{total_parts}", "身体部位 active", active_color),
        chip("🪶", f"{tickle_points} pts", f"{tickle_triggers}触发 · {'闪躲开' if dodge_on else '闪躲关'}", "#f39c12"),
    ], spacing=12)

def build_debuffs(values):
    locked = values.get("pleasure_locked", False)
    bound = values.get("bound", False)

    tag = lambda label, on: ft.Container(
        content=ft.Text(f"{label} · {'是' if on else '否'}", size=11, weight=ft.FontWeight.W_600),
        padding=_padding(h=12, v=4),
        border_radius=12,
        bgcolor="rgba(231,76,60,0.15)" if on else "rgba(39,174,96,0.1)",
        border=_border(1, "rgba(231,76,60,0.3)" if on else "rgba(39,174,96,0.2)"),
    )
    tag_locked = tag("快感锁定", locked)
    tag_bound = tag("捆绑", bound)
    tag_locked.color = "#e74c3c" if locked else "#27ae60"
    tag_bound.color = "#e74c3c" if bound else "#27ae60"
    return ft.Row([tag_locked, tag_bound], spacing=10)

def build_changelog(entries, current_values):
    """最近 8 条有意义的变更 + 当前行"""
    filtered = []
    seen = set()
    for e in reversed(entries):
        evt = e.get("event", "")
        if evt in ("update", "api_add_pain", "api_add_shame", "api_add_pleasure"):
            continue
        lbl = event_label(e)
        if not lbl or lbl == "(未知)":
            continue
        ts = (e.get("timestamp", "") or "")[:16]
        dedup_key = (evt, ts)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        e["_label"] = lbl
        filtered.append(e)
        if len(filtered) >= 8:
            break

    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    p = current_values.get("pain", 0)
    s = current_values.get("shame", 0)
    pl = current_values.get("pleasure", 0)

    columns = [
        ft.DataColumn(ft.Text("时间", size=10, color=C_MUTED)),
        ft.DataColumn(ft.Text("🩸 痛", size=10, color=C_MUTED)),
        ft.DataColumn(ft.Text("😳 羞", size=10, color=C_MUTED)),
        ft.DataColumn(ft.Text("❤️ 快", size=10, color=C_MUTED)),
        ft.DataColumn(ft.Text("事件", size=10, color=C_MUTED)),
    ]

    rows = [
        ft.DataRow(cells=[
            ft.DataCell(ft.Text(now, size=12, color="#665")),
            ft.DataCell(ft.Text(str(p), size=12, color=C_PAIN, weight=ft.FontWeight.W_600)),
            ft.DataCell(ft.Text(str(s), size=12, color=C_SHAME, weight=ft.FontWeight.W_600)),
            ft.DataCell(ft.Text(str(pl), size=12, color=C_PLEAS, weight=ft.FontWeight.W_600)),
            ft.DataCell(ft.Text("当前", size=11, color=C_MUTED)),
        ]),
    ]

    for re in filtered:
        b = re.get("before", {})
        a = re.get("after", {})
        dp = a.get("pain", 0) - b.get("pain", 0)
        ds = a.get("shame", 0) - b.get("shame", 0)
        dpl = a.get("pleasure", 0) - b.get("pleasure", 0)

        def delta_cell(val, delta, color):
            if delta != 0:
                return f"{val} ({fmt_delta(delta)})"
            return str(val)

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Text(ts_short(re.get("timestamp", "")), size=12, color="#665")),
            ft.DataCell(ft.Text(delta_cell(a.get("pain", 0), dp, C_PAIN), size=12, color=C_PAIN)),
            ft.DataCell(ft.Text(delta_cell(a.get("shame", 0), ds, C_SHAME), size=12, color=C_SHAME)),
            ft.DataCell(ft.Text(delta_cell(a.get("pleasure", 0), dpl, C_PLEAS), size=12, color=C_PLEAS)),
            ft.DataCell(ft.Text(re.get("_label", ""), size=11, color=C_MUTED, max_lines=2)),
        ]))

    return ft.DataTable(
        columns=columns,
        rows=rows,
        border_radius=8,
        heading_row_height=28,
        data_row_min_height=36,
        data_row_max_height=52,
        column_spacing=8,
    )

# ═══════════════════════════════════════════════════════════════
# ── 右侧面板：日记 ────────────────────────────────────────────

def build_right_panel(selected_date: str, diary_text: str,
                      date_list: list, on_go_click, col_w: int,
                      cl_scroll: ft.Control):
    """右侧面板：日记 + Changelog。日期选择通过按钮触发。"""

    today = datetime.now().strftime("%Y-%m-%d")

    date_options = []
    for d in date_list:
        label = f"{d}" + (" ← 今天" if d == today else "")
        date_options.append(ft.dropdown.Option(d, label))
    if not date_options:
        date_options = [ft.dropdown.Option(today, f"{today} ← 今天")]
    date_dd = ft.Dropdown(
        options=date_options,
        value=selected_date,
        text_size=12,
        border_radius=8,
        dense=True,
        bgcolor="rgba(255,200,180,0.04)",
        border_color="rgba(255,200,180,0.12)",
    )

    go_btn = ft.IconButton(
        icon=ft.Icons.CHECK,
        icon_size=16,
        icon_color="#ff9a8a",
        tooltip="加载此日期",
        on_click=lambda e: on_go_click(date_dd.value),
    )

    content_text = diary_text
    if content_text is None:
        content_text = "(该日期无数据)"
    elif not content_text.strip():
        content_text = "(空)"

    content_area = ft.Text(
        content_text,
        size=14,
        color="#c0b8a8",
        font_family="Consolas",
        selectable=True,
        no_wrap=False,
    )

    # 日记内容区：固定高度 + 独立滚动，镜像左侧 Changelog（height=320）
    diary_scroll = ft.Container(
        content=ft.Column([content_area], scroll=ft.ScrollMode.AUTO),
        height=320,
    )

    return ft.Container(
        content=ft.Column([
            ft.Row([ft.Container(width=34, height=34)], alignment=ft.MainAxisAlignment.END),
            ft.Container(height=6),
            ft.Container(height=24),  # 对齐左侧标题高度
            ft.Container(
                content=ft.Column([
                    ft.Row([ft.Text("📅", size=16), date_dd, go_btn], spacing=6),
                    ft.Container(height=12),
                    diary_scroll,
                ]),
                bgcolor="rgba(255,200,180,0.02)",
                border=_border(1, C_BORDER),
                border_radius=14,
                padding=_padding(h=22, v=20),
                margin=_margin(bottom=16),
            ),
            section_card("📋 三值 Changelog", cl_scroll),
        ]),
        width=col_w,
        padding=24,
    )

# ═══════════════════════════════════════════════════════════════
# ── 主函数 ───────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def main(page: ft.Page):
    page.title = "Soli 灵魂仪表盘"
    page.window_width = 1100
    page.window_height = 860
    page.window_min_width = 800
    page.window_min_height = 700
    page.padding = 20
    page.bgcolor = C_BG
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.AUTO

    # ── 右侧面板状态 ──
    today_str = datetime.now().strftime("%Y-%m-%d")
    state = {"date": today_str,
             "diary_text": "",
             "date_list": get_available_dates()}
    state["diary_text"] = read_diary(today_str)
    if not state["date_list"]:
        state["date_list"] = [today_str]
    # 持久化引用：wrapper=整页容器，right_ref=右侧面板容器（日期切换时重建右栏）

    # ── SnackBar ──
    snack = ft.SnackBar(
        content=ft.Text(""),
        bgcolor="rgba(15,15,34,0.95)",
        behavior=ft.SnackBarBehavior.FLOATING,
        duration=3000,
    )
    page.overlay.append(snack)

    # 外层容器引用 + 右侧面板容器引用
    wrapper = None
    right_ref = {"widget": None}
    page_ref = {"page": page}

    # ── 刷新回调 ──
    def refresh_ui(e=None):
        nonlocal wrapper
        if wrapper is not None:
            wrapper.content = build_page()
            wrapper.update()

    # ── 区配置切换回调 ──
    def on_variant_switch(variant_key):
        old, new = write_variant(variant_key)
        label = VARIANT_NAMES.get(new, new)
        snack.content = ft.Text(f"✓ 已切换: {old} → {label}")
        snack.open = True
        refresh_ui()

    # ── 右侧面板重建（日期切换后调用，只重建右栏不动左栏） ──
    def rebuild_right_panel():
        data = load_all()
        col_w = max(300, (page.window_width - 64) // 2)
        cl_table = build_changelog(data["changelog"], data["values"])
        cl_scroll = ft.Container(
            content=ft.Column([
                ft.Row([cl_table], scroll=ft.ScrollMode.AUTO),
            ], scroll=ft.ScrollMode.AUTO),
            height=320,
        )
        new_panel = build_right_panel(
            state["date"], state["diary_text"],
            state["date_list"], on_go_click,
            col_w, cl_scroll,
        )
        if right_ref["widget"] is not None:
            right_ref["widget"].content = new_panel.content
            right_ref["widget"].width = new_panel.width
            right_ref["widget"].padding = new_panel.padding
            right_ref["widget"].update()

    # ── 右侧面板回调：按钮确认日期 ──
    def on_go_click(date_value):
        state["date"] = date_value
        state["diary_text"] = read_diary(date_value)
        rebuild_right_panel()

    # ── 构建整页内容 ──
    def build_page():
        data = load_all()
        cur_variant = data["values"].get("area_profile", "v")
        area_id = _profile_to_area(cur_variant)  # 当前激活的敏感区

        # 列宽：去掉所有 expand，用显式宽度避免跨轴拉伸
        col_w = max(300, (page.window_width - 64) // 2)

        # ══ 左侧：现有内容 ══
        header_row = ft.Row([
            ft.Text("❤️ Soli 灵魂仪表盘",
                    size=20, weight=ft.FontWeight.W_600,
                    color="#ff9a8a"),
            ft.Row([
                ft.Container(
                    content=ft.Text("本地", size=10, color="#e67e22"),
                    padding=_padding(h=8, v=2),
                    border_radius=10,
                    bgcolor="rgba(230,126,34,0.12)",
                    border=_border(1, "rgba(230,126,34,0.25)"),
                ),
                ft.Container(width=8),
                ft.Container(
                    content=ft.Text(
                        "g:" + datetime.now().strftime("%Y/%m/%d %H:%M"),
                        size=11, color=C_MUTED,
                    ),
                    padding=_padding(h=12, v=4),
                    border_radius=20,
                    bgcolor="rgba(255,200,180,0.06)",
                ),
            ]),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_size=18,
            icon_color=C_MUTED,
            tooltip="手动刷新",
            on_click=refresh_ui,
        )

        cl_table = build_changelog(data["changelog"], data["values"])
        cl_scroll = ft.Container(
            content=ft.Column([
                ft.Row([cl_table], scroll=ft.ScrollMode.AUTO),
            ], scroll=ft.ScrollMode.AUTO),
            height=320,
        )

        left_col = ft.Container(
            content=ft.Column([
                ft.Row([refresh_btn], alignment=ft.MainAxisAlignment.END),
                ft.Container(height=6),
                header_row,
                ft.Container(height=24),
                section_card("🩸😳❤️ 灵魂三值", build_soul_bars(data["values"])),
                section_card("💐 敏感区",
            ft.Column([
                build_area_bar(data["area"], "v", "V", highlighted=(area_id == "v"), emoji="🪷"),
                ft.Container(height=4),
                build_area_bar(data["area_a"], "variant_a", "A", highlighted=(area_id == "a"), emoji="🌼"),
                ft.Container(height=4),
                build_area_bar(data["area_u"], "variant_u", "U", highlighted=(area_id == "u"), emoji="🌷"),
                ft.Container(height=8),
                build_profile_buttons(cur_variant, on_variant_switch),
                    ])),
                section_card("状态概览",
                    ft.Column([build_chips(data), ft.Container(height=12), build_debuffs(data["values"])])),
            ]),
            width=col_w,
            padding=24,
        )

        # ══ 右侧：日记 ══
        right_panel = build_right_panel(
            state["date"], state["diary_text"],
            state["date_list"], on_go_click,
            col_w, cl_scroll,
        )
        right_ref["widget"] = right_panel

        return ft.Row([left_col, ft.Container(width=20), right_panel])

    # ── 初始内容 ──
    content = build_page()
    wrapper = ft.Container(
        content=content,
        bgcolor="transparent",
        border_radius=20,
        padding=0,
    )
    page.add(wrapper)


# ═══════════════════════════════════════════════════════════════
# ── 入口 ─────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    ft.run(main)
