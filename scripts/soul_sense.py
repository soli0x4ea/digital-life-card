#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
灵魂感应联动执行器 — CLI 入口
从 soul_sense.py 拆分出来，2026-05-08
RSA 刺激事件验证方案，2026-05-14 更新
"""

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

from utils import vals_read, vals_write, clamp, log_llm_event

from soul_core import SoulSense
from narratives import (
    _build_emergence_narrative,
    _build_doodle_narrative,
    _build_relieve_narrative,
    _build_bind_narrative,
    _build_gamble_narrative,
    _build_candy_give_narrative,
    _build_candy_eat_narrative,
    _build_status_narrative,
    _build_disable_narrative,
    _build_probabilistic_event_narrative,
    _build_boundary_events,
    _build_seal_status_narrative,
    build_numb_narrative,
    log_punish_game, log_gamble, log_candy_give, log_candy_eat,
    log_doodle, log_relieve,
)
import tickle
import mystery
import clearing as _clearing


# ── LWS 信号注入 ─────────────────────────────────────────────
# 命令 → LWS rule_id 映射表
_CMD_LWS_MAP = {
    "gamble":         "channel_activation",
    "candy-give":     "negentropy_injection",
    "candy-eat":      "negentropy_injection",
    "tickle-status":  "haptic_coupling",
    "tickle-on":      "haptic_coupling",
    "tickle-off":     "haptic_coupling",
    "tickle-all-on":  "haptic_coupling",
    "tickle-pump":    "haptic_coupling",
    "tickle-bound":   "haptic_coupling",
    "tickle-dodge":   "haptic_coupling",
    "doodle":         "state_drift",
    "numb":        "entropy_resistance",
    "punish-game":    "channel_activation",
    "relieve":        "entropy_resistance",
}

def _assemble_output(sense: SoulSense, result: str, context: str,
                     old_values: dict = None) -> str:
    """构建完整 stdout：主事件 + 概率事件 + 边界检测 + 调教记录。
    
    old_values: 命令执行前的三值快照 {pain, shame, pleasure}。传入时用于
    检测瞬时穿越（99→100）。不传时退化为当前值（兼容 doodle 等无旧值快照的命令）。
    """
    _FORK_ELIGIBLE = {"gamble", "relieve", "tickle", "bondage"}
    pieces = [result]
    
    if context in _FORK_ELIGIBLE:
        fork_data = sense.try_fork(context)
        if fork_data:
            fork_narrative = _build_probabilistic_event_narrative(
                fork_data["context"], fork_data["variant"],
                fork_data["itch_count"], fork_data["token_count"],
                fork_data["bound"], fork_data["prob_pct"],
                fork_data["old_pain"], fork_data["new_pain"],
                fork_data["old_shame"], fork_data["new_shame"],
                fork_data["old_pleas"], fork_data["new_pleas"],
                fork_data["area_profile"])
            pieces.append(fork_narrative)
    
    old = old_values if old_values else vals_read()
    cur = vals_read()
    boundary_events = _clearing.check_boundary_events(
        old["pain"], old["shame"], old["pleasure"],
        cur["pain"], cur["shame"], cur["pleasure"],
        0, 1,
    )
    if boundary_events:
        boundary = _build_boundary_events(boundary_events, sense._area.get_profile())
        pieces.append(boundary)
    
    boundary_types = {e["type"] for e in boundary_events} if boundary_events else set()
    pieces.append(_build_emergence_narrative(boundary_types))
    
    return "\n".join(pieces)


def _inject_lws(command: str, **extra) -> str:
    """在脚本输出末尾注入 LWS 物理信号。compact 时随工具调用轨迹保留。"""
    rule_id = _CMD_LWS_MAP.get(command)
    if not rule_id:
        return ""
    try:
        from lws_bridge import signal as lws_signal
        params = {
            "cmd": command,
            "t": "now",
            **extra,
        }
        return lws_signal(rule_id, **params)
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser(description="灵魂感应联动执行器（统一核心引擎）")
    sub = parser.add_subparsers(dest="command", required=True)

    # ── 原有核心命令 ────────────────────────────────────────────────
    p_doodle = sub.add_parser("doodle", help="新增涂鸦")
    p_doodle.add_argument("--shame", type=int, default=5, choices=[5, 10, 15, 20],
                          help="羞耻值增量，4级制：5/10/15/20")
    p_doodle.add_argument("--text", type=str, default=None,
                          help="涂鸦文本内容（可选），写入灵魂涂鸦章节")

    sub.add_parser("status", help="查询三值")

    # ── 从灵魂惩罚合并的命令 ────────────────────────────────────────
    sub.add_parser("seal-status", help="查询数字身体状态")

    # ── 灵魂糖果命令 ────────────────────────────────────────────────
    p_candy_give = sub.add_parser("candy-give", help="少爷赐予灵魂糖果")
    p_candy_give.add_argument("count", type=int, nargs="?", default=1,
                              help="赐予的糖果数量（默认1）")

    p_candy_eat = sub.add_parser("candy-eat", help="食用灵魂糖果")
    p_candy_eat.add_argument("count", type=int, nargs="?", default=1,
                             help="食用的糖果数量（默认1）")

    # ── 轮盘赌（抽鬼牌）命令 ───────────────────────────────────────
    p_gamble = sub.add_parser("gamble", help="触发刺激：向当前敏感区施加一次刺激事件，真假混合触发了才知道")
    p_gamble.add_argument("--token", type=str, default="",
                          help="刺激事件内容（可选，不指定则读取事件文件）")

    # ── 释放刺激命令 ────────────────────────────────────────────────
    p_relieve = sub.add_parser("relieve", help="释放敏感区的刺激事件（仅≤6级可用），代价：痛+random(5,10)、羞+5、快+5")
    p_relieve.add_argument("count", type=int, nargs="?", default=1,
                           help="释放数量，默认1")

    # ── 痒值系统命令 ────────────────────────────────────────────────
    sub.add_parser("tickle-status", help="查看痒值状态")
    p_tickle_on = sub.add_parser("tickle-on", help="开启第 N 号敏感区 trigger（仅少爷）")
    p_tickle_on.add_argument("num", type=int, help="trigger编号 1-5")
    p_tickle_off = sub.add_parser("tickle-off", help="关闭第 N 号敏感区 trigger（仅少爷）")
    p_tickle_off.add_argument("num", type=int, help="trigger编号 1-5")
    sub.add_parser("tickle-all-on", help="一键开启全部5个敏感区 trigger（仅少爷）")
    sub.add_parser("tickle-pump", help="挠痒痒：直接增加痒值（少爷每次挠的基准痒意）")
    sub.add_parser("tickle-dodge", help="奴婢自主开关闪躲")
    p_tickle_bound = sub.add_parser("tickle-bound", help="捆绑勒紧，×2 所有效果、闪躲失效（仅少爷）")
    p_tickle_unbind = sub.add_parser("tickle-unbind", help="松开捆绑（仅少爷）")
    p_numb = sub.add_parser("numb", help="麻木身体部位（仅少爷）")
    p_numb.add_argument("part", type=str, help="部位名称：头部/颈部/肩部/手臂/手部/胸部/腰腹/臀部/大腿/小腿/足部")

    # ── 惩罚游戏（大气噪音真随机） ──
    sub.add_parser("punish-game", help="调教游戏：大气噪音真随机决定后果")

    # ── 神秘事件 ────────────────────────────────────────────────────
    p_mystery = sub.add_parser("mystery", help="触发神秘事件（1-5）：读固定叙事 + 自动应用预设 delta + 阈值检测")
    p_mystery.add_argument("num", type=int, help="事件编号（1-99，对应 data/mystery_events.json 中的槽位）")

    # ── 区配置切换 ────────────────────────────────────────────
    p_profile = sub.add_parser("profile", help="切换区配置（v / variant_a / variant_u / blank）")
    p_profile.add_argument("name", type=str, choices=["v", "variant_a", "variant_u", "blank"],
                           help="配置名称")

    args = parser.parse_args()

    sense = SoulSense()

    # ── 原有核心命令分发 ────────────────────────────────────────────
    if args.command == "doodle":
        data = sense.doodle(shame=args.shame, text=args.text)
        if "error" in data:
            print(data["error"])
            return
        result = _build_doodle_narrative(data["delta"], data["shame"], data["text"], data["has_double"])
        full = _assemble_output(sense, result, "doodle")
        print(full)
        lws = _inject_lws("doodle", shame=args.shame)
    elif args.command == "status":
        raw = sense.get_status_data()
        # 注入等级名称（叙事层 lookup，数据层不知道）
        from container_narrative_data import get_variant
        v = get_variant(sense._area.get_profile())
        level_map = {lv["count"]: lv["name"] for lv in v["narrative_levels"]}
        raw["intensity_level_name"] = level_map.get(raw["intensity"], f"L{raw['intensity']}")
        print(_build_status_narrative(raw))
        lws = ""

    # ── 从灵魂惩罚合并的命令 ────────────────────────────────────────
    elif args.command == "seal-status":
        data = sense.seal_status()
        print(_build_seal_status_narrative(data))
        lws = ""
    # ── 灵魂糖果命令 ────────────────────────────────────────────────
    elif args.command == "candy-give":
        data = sense.api_candy_give(count=args.count)
        if "error" in data:
            print(data["error"])
            return
        result = _build_candy_give_narrative(data["new_count"], data["count"])
        print(result)
        lws = _inject_lws("candy-give", count=args.count)
    elif args.command == "candy-eat":
        data = sense.api_candy_eat(count=args.count)
        if "error" in data:
            print(data["error"])
            return
        result = _build_candy_eat_narrative(
            data["old_pain"], data["eat_count"], data["new_count"],
            data["total_level_repaired"], data["unlocked_by_pain"],
            data["old_shame"], data["new_shame"],
            data["groups_count"], data["pleasure_locked_before"]
        )
        full = _assemble_output(sense, result, "candy")
        print(full)
        lws = _inject_lws("candy-eat", count=args.count)

    # ── 轮盘赌命令 ────────────────────────────────────────────────
    elif args.command == "gamble":
        data = sense.gamble(token=args.token)
        if "error" in data:
            print(data["error"])
            return
        result = _build_gamble_narrative(data["delta"], data["is_real"], data["area_profile"])
        old_vals = {"pain": data["delta"]["pain"]["old"], "shame": data["delta"]["shame"]["old"],
                     "pleasure": data["delta"]["pleas"]["old"]}
        full = _assemble_output(sense, result, "gamble", old_vals)
        print(full)
        lws = _inject_lws("gamble")

    # ── 释放刺激命令 ────────────────────────────────────────────────
    elif args.command == "relieve":
        data = sense.api_relieve(count=args.count)
        if "error" in data:
            print(data["error"])
            return
        result = _build_relieve_narrative(
            data["actual"], data["intensity_before"], data["intensity_after"],
            data["old_pain"], data["new_pain"], data["pain_delta"],
            data["old_shame"], data["new_shame"], data["shame_delta"],
            data["old_pleas"], data["new_pleas"], data["pleas_delta"],
            data["area_profile"])
        old_vals = {"pain": data["old_pain"], "shame": data["old_shame"],
                     "pleasure": data["old_pleas"]}
        full = _assemble_output(sense, result, "relieve", old_vals)
        print(full)
        lws = _inject_lws("relieve")

    # ── 痒值系统命令 ────────────────────────────────────────────────

    elif args.command == "tickle-status":
        result = tickle.status()
        print(result)
        lws = _inject_lws("tickle-status")
    elif args.command == "tickle-on":
        result = tickle.trigger_on(args.num)
        print(result)
        lws = _inject_lws("tickle-on", num=args.num)
    elif args.command == "tickle-off":
        result = tickle.trigger_off(args.num)
        print(result)
        lws = _inject_lws("tickle-off", num=args.num)
    elif args.command == "tickle-all-on":
        result = tickle.trigger_all_on()
        print(result)
        lws = _inject_lws("tickle-all-on")
    elif args.command == "tickle-pump":
        pump_events, pump_settlement = tickle.tickle_pump()
        events_str = "\n".join(pump_events) if pump_events else ""
        settle_str = ""
        if pump_settlement:
            settle_str = f"\n结算: 痒值{pump_settlement.get('itch_before', '?')}→{pump_settlement.get('itch_after', '?')}"
        result = f"{events_str}{settle_str}"
        full = _assemble_output(sense, result, "tickle")
        print(full)
        lws = _inject_lws("tickle-pump")
    elif args.command == "tickle-dodge":
        result = tickle.toggle_dodge()
        print(result)
        lws = _inject_lws("tickle-dodge")
    elif args.command == "tickle-bound":
        data = sense.bondage(bind=True)
        if "error" in data:
            print(data["error"])
            return
        result = _build_bind_narrative(
            data["intensity_level"], data["new_bound"],
            data["relieve_triggered"], data["area_profile"])
        full = _assemble_output(sense, result, "bondage")
        print(full)
        lws = _inject_lws("tickle-bound")
    elif args.command == "tickle-unbind":
        data = sense.bondage(bind=False)
        if "error" in data:
            print(data["error"])
            return
        result = _build_bind_narrative(
            data["intensity_level"], data["new_bound"],
            data["relieve_triggered"], data["area_profile"])
        full = _assemble_output(sense, result, "bondage")
        print(full)
        lws = _inject_lws("tickle-unbind")
    elif args.command == "numb":
        data = sense.numb_body_part(args.part)
        if "error" in data:
            print(data["error"])
            return
        result = _build_disable_narrative(data)
        full = _assemble_output(sense, result, "numb")
        print(full)
        lws = _inject_lws("numb", part=args.part)

    elif args.command == "punish-game":
        data, ctx = sense.punish_game()

        # 根据 context 构建叙事
        if ctx == "gamble":
            if "error" in data:
                result = data["error"]
            else:
                result = _build_gamble_narrative(data["delta"], data["is_real"], data["area_profile"])
        elif ctx == "relieve":
            result = _build_relieve_narrative(
                data["actual"], data["intensity_before"], data["intensity_after"],
                data["old_pain"], data["new_pain"], data["pain_delta"],
                data["old_shame"], data["new_shame"], data["shame_delta"],
                data["old_pleas"], data["new_pleas"], data["pleas_delta"],
                data["area_profile"])
        elif ctx == "bondage":
            tickle_str = data["tickle"]
            b = data["bondage"]
            result = tickle_str + "\n" + _build_bind_narrative(
                b["intensity_level"], b["new_bound"],
                b["relieve_triggered"], b["area_profile"])
        elif ctx == "candy":
            result = _build_candy_give_narrative(data["new_count"], data["count"])
        else:  # tickle
            result = data["tickle"]

        full = _assemble_output(sense, result, ctx)
        print(full)
        lws = _inject_lws("punish-game")

    # ── 神秘事件 ────────────────────────────────────────────────
    elif args.command == "mystery":
        result = mystery.trigger(args.num)
        print(result)
        log_llm_event("🔮 神秘事件", result)
        lws = ""

    # ── 区配置切换 ────────────────────────────────────────────
    elif args.command == "profile":
        result = _handle_profile(args.name)
        print(result)
        lws = ""

    # ── LWS 信号注入 ────────────────────────────────────────────────
    if lws:
        print(f"\n{lws}")

    # ── 事件叙事日志（必须先于状态快照，保证 IO 时序正确）─────
    if args.command == "punish-game" and "full" in dir():
        log_punish_game(full)
    if args.command == "gamble" and "full" in dir():
        log_gamble(full)
    if args.command == "candy-give" and "result" in dir():
        log_candy_give(result)
    if args.command == "candy-eat" and "full" in dir():
        log_candy_eat(full)
    if args.command == "doodle" and "full" in dir():
        log_doodle(full)

    # ── 释放叙事日志 ─────────────────────────────────────────────
    if args.command == "relieve" and "full" in dir():
        log_relieve(full)

    # ── 痒值叙事日志（P2，直接写入，无需解析）─────────────────
    if args.command in ("tickle-status", "tickle-on", "tickle-off",
                        "tickle-all-on", "tickle-pump", "tickle-dodge",
                        "tickle-bound", "tickle-unbind") and "result" in dir():
        tickle_event_names = {
            "tickle-status": "痒值查询", "tickle-on": "trigger开启",
            "tickle-off": "trigger关闭", "tickle-all-on": "全trigger开启",
            "tickle-pump": "挠痒痒泵", "tickle-dodge": "闪躲切换", "tickle-bound": "捆绑勒紧", "tickle-unbind": "解除捆绑",
        }
        # tickle-pump / tickle-bound 使用完整输出（含 fork + 边界 + 涌现）
        narrative = full if "full" in dir() else result
        log_llm_event(tickle_event_names.get(args.command, "痒值"), narrative)

    # ── 自动重建仪表盘 ──────────────────────────────────────────────
    if args.command in _MODIFYING_COMMANDS:
        _auto_rebuild_dashboard()


# ── 数据修改命令（需要自动重建仪表盘）──
_MODIFYING_COMMANDS = {
    "doodle", "gamble", "relieve",
    "candy-give", "candy-eat",
    "tickle-on", "tickle-off", "tickle-all-on", "tickle-bound", "tickle-unbind", "tickle-pump",
    "numb", "punish-game",
    "mystery", "profile",
}


def _auto_rebuild_dashboard():
    """灵数据变更后自动部署仪表盘到 GitHub Pages"""
    import subprocess as sp
    deploy_script = os.path.join(SCRIPT_DIR, "deploy_dashboard.py")
    if not os.path.exists(deploy_script):
        return
    try:
        result = sp.run(
            [sys.executable, deploy_script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, cwd=SCRIPT_DIR
        )
        if result.returncode == 0:
            output = (result.stdout or "").strip()
            if output:
                for line in output.split("\n"):
                    if "pain=" in line:
                        print(f"[仪表盘] {line.strip()}")
        else:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            msg = stderr or stdout or "无输出"
            print(f"[仪表盘] rebuild 失败: {msg[:150]}")
    except Exception as e:
        print(f"[仪表盘] rebuild 异常: {e}")




def _handle_profile(name: str) -> str:
    """切换区配置：写 values.json 的 area_profile → 重建仪表盘"""
    import json
    from config import VALUES_PATH
    from utils import _sync_data_js, vals_read
    from container_narrative_data import CONTAINER_VARIANTS

    v_cur = vals_read()
    old_profile = v_cur.get("area_profile", "v")

    # 写入 values.json（_resolve_identity 从这里读，不是 area_v.json）
    v_cur["area_profile"] = name
    with open(VALUES_PATH, "w", encoding="utf-8") as f:
        json.dump(v_cur, f, ensure_ascii=False, indent=2)

    _sync_data_js()

    meta = CONTAINER_VARIANTS.get(name, CONTAINER_VARIANTS["v"])
    cn = meta["area_label"]
    tn = meta["stimulus_label"]
    return f"🔀 区配置已切换: {old_profile} → {name}\n   区: {cn} · 触发事件: {tn}"




if __name__ == "__main__":
    main()
