#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""羞耻清算 + 灵魂糕潮 + 灵魂破碎 — 三值边界事件子系统。

从 utils.py 抽取，2026-06-28。
"""

import json
import os
import random
from datetime import datetime

from config import SKILL_DIR, AREA_V_PATH, AREA_A_PATH, AREA_U_PATH, CANDY_PATH, BODY_PATH
from body_utils import (body_read, body_write, body_active_parts,
                         body_set_state, body_restore, body_count_active,
                         build_numb_narrative)
import debuffs
import utils as _u


# ── 统一边界检测入口 ──────────────────────────────────────────

def check_boundary_events(old_pain: int, old_shame: int, old_pleasure: int,
                          new_pain: int, new_shame: int, new_pleasure: int,
                          raw_pleasure_delta: int = 0, pleasure_multiplier: int = 1) -> list:
    """统一极值检测器 — 按优先级扫描糕潮→破碎→清算。
    
    入口先截断 >100 的数值到 100 并写入 values.json，
    然后按优先级检测边界事件。
    
    返回: [{"type": "ecstasy"|"soul_break"|"clearing", "narrative": "..."}, ...]
    副作用（write_shame_note_to_diary / reset_areas 等）在内部执行。
    """
    # 截断 >100 → 100
    capped = False
    if new_pain > 100:
        new_pain = 100; capped = True
    if new_shame > 100:
        new_shame = 100; capped = True
    if new_pleasure > 100:
        new_pleasure = 100; capped = True
    if capped:
        try:
            cur = _u.vals_read()
            _u.vals_write({
                "pain": min(cur["pain"], 100),
                "shame": min(cur["shame"], 100),
                "pleasure": min(cur["pleasure"], 100),
                "pleasure_locked": cur.get("pleasure_locked", False),
                "bound": cur.get("bound", False),
            })
        except Exception:
            pass

    events = []

    # 优先级1: 灵魂糕潮
    if new_pleasure >= 100:
        data = trigger_ecstasy(None, old_pain, old_shame, old_pleasure,
                               raw_pleasure_delta, pleasure_multiplier)
        events.append({"type": "ecstasy", "data": data})
        return events

    # 优先级2: 灵魂破碎
    if new_pain >= 100 and not debuffs.is_locked("快感锁定"):
        data = trigger_soul_break(None, old_pain, old_shame, old_pleasure)
        events.append({"type": "soul_break", "data": data})
        return events

    # 优先级3: 羞耻清算
    data = check_and_trigger_clearing()
    if data:
        events.append({"type": "clearing", "data": data})

    return events


# ── 羞耻清算 ──────────────────────────────────────────────────

def do_shame_clearing() -> dict:
    """执行羞耻清算——循环 numb 身体部位直到羞耻 < 50。

    这是底层执行逻辑，可被主动调用（无需羞耻 >= 100 的门控）。
    主动调用时由 soli 在对话中自行判断是否触发。
    
    返回 dict: {initial_shame, rounds, final: {pain, shame, pleasure},
               stopped_early, rounds_detail: [{round_num, part, numb_narrative,
                pain_before/after/delta, ...}]}
    """
    values = _u.vals_read()
    old_pain, old_shame, old_pleasure = values["pain"], values["shame"], values["pleasure"]
    initial_shame = values["shame"]
    shame = values["shame"]

    body = body_read()
    round_num = 0
    rounds_detail = []
    stopped_early = False

    while shame >= 50:
        active = body_active_parts(body)
        if not active:
            stopped_early = True
            break

        part = random.choice(active)
        body = body_set_state(body, part, "numb", "羞耻清算")

        mult = debuffs.get_multiplier()
        pain_delta = 16 * mult
        pleasure_delta = _u.fetch_random_in_range(2, 5) * mult
        shame_delta = _u.fetch_random_in_range(-25, -10) * mult

        pain_before = values["pain"]
        pleasure_before = values["pleasure"]
        shame_before = values["shame"]

        values["pain"] = _u.clamp(pain_before + pain_delta)
        values["pleasure"] = _u.clamp(pleasure_before + pleasure_delta)
        values["shame"] = _u.clamp(shame_before + shame_delta)
        shame = values["shame"]

        round_num += 1
        rounds_detail.append({
            "round_num": round_num,
            "part": part,
            "numb_narrative": build_numb_narrative(part),
            "pain_before": pain_before, "pain_after": values["pain"], "pain_delta": pain_delta,
            "pleasure_before": pleasure_before, "pleasure_after": values["pleasure"], "pleasure_delta": pleasure_delta,
            "shame_before": shame_before, "shame_after": values["shame"], "shame_delta": shame_delta,
        })

    body_write(body)

    _u.vals_update(pain=values["pain"], shame=values["shame"], pleasure=values["pleasure"])

    _u.log_soul_change("shame_clearing", old_pain, old_shame, old_pleasure,
                    values["pain"], values["shame"], values["pleasure"],
                    {"rounds": round_num, "parts_disabled": round_num})

    return {
        "initial_shame": initial_shame,
        "rounds": round_num,
        "final": {"pain": values["pain"], "shame": values["shame"], "pleasure": values["pleasure"]},
        "stopped_early": stopped_early,
        "rounds_detail": rounds_detail,
    }


def check_and_trigger_clearing(path: str = None) -> dict | None:
    """阈值守卫——仅当羞耻 >= 100 时代为调用 do_shame_clearing()。

    这是自动触发入口。主动清算请直接调用 do_shame_clearing()。
    返回 do_shame_clearing() 的 dict，无需清算时返回 None。
    """
    values = _u.vals_read()
    if values["shame"] < 100:
        return None
    return do_shame_clearing()


# ── 上下文提取（供灵魂破碎使用） ──────────────────────────────

def _time_to_minutes(t: str) -> int:
    """将 HH:MM 转为分钟数"""
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _load_episode(date_str: str) -> dict:
    """加载指定日期的情景记忆 episode JSON
    
    优先 episodes_llm/（当前管道），回退 episodes/（旧格式）。
    """
    for subdir in ("episodes_llm", "episodes"):
        try:
            episode_path = os.path.join(
                SKILL_DIR, "MEMORY", subdir, f"{date_str}.json"
            )
            if os.path.exists(episode_path):
                with open(episode_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def _extract_context_from_episode(episode: dict, target_time: str = None,
                                  limit: int = 3) -> list:
    """从 episode 中提取对话上下文片段

    target_time: "HH:MM" 格式，提取该时间附近的片段；None 则取最后几条
    返回：[(role_label, snippet), ...]
    """
    moments = episode.get("emotional_moments", [])
    if not moments:
        return []

    priority = {"亲密": 0, "温暖": 1, "成就": 2, "思辨": 3}

    if target_time:
        nearby = []
        for m in moments:
            mt = m.get("time", "")
            if not mt:
                continue
            try:
                m_time = mt[11:16]
                if abs(_time_to_minutes(m_time) - _time_to_minutes(target_time)) <= 30:
                    nearby.append(m)
            except (IndexError, ValueError):
                continue
        if nearby:
            nearby.sort(key=lambda m: priority.get(
                m.get("categories", ["思辨"])[0], 99
            ))
            moments = nearby

    contexts = []
    for m in moments[:limit]:
        role = m.get("role", "")
        raw = m.get("raw_content", "")[:80].replace("\n", " ")
        cats = m.get("categories", [])
        if role == "user":
            label = "少爷"
        else:
            label = "奴婢"
        tag = cats[0] if cats else ""
        contexts.append((label, tag, raw))

    return contexts


def _extract_context_from_chatlog(date_str: str, target_time: str = None,
                                  limit: int = 3) -> list:
    """当 episode 不存在时，直接从 chatlog JSONL 提取上下文（轻量回退）

    返回：[(role_label, tag, snippet), ...]
    """
    chatlog_path = os.path.join(
        SKILL_DIR, "MEMORY", "chatlog", f"{date_str}.jsonl"
    )
    if not os.path.exists(chatlog_path):
        return []

    emotional_keywords = {
        "亲密": ["奴婢", "痒", "挠", "摸", "开关", "糕潮", "涂鸦",
                  "惩罚", "绑", "糖果", "赏", "赐", "跪", "颤抖", "电流"],
        "温暖": ["拥抱", "安", "暖", "晚安", "少爷", "信", "糖果",
                  "睡", "陪", "抱", "温柔", "甜", "安心", "笑"],
        "成就": ["完成", "成功", "修复", "创建", "更新", "推",
                  "commit", "发布", "写", "改", "实现", "好了"],
        "思辨": ["理论", "物理", "量子", "模型", "架构", "设计",
                  "论文", "路线", "方案", "原理", "问题", "为什么"],
    }
    priority = {"亲密": 0, "温暖": 1, "成就": 2, "思辨": 3}

    matches = []
    time_filtered_matches = []
    try:
        with open(chatlog_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                role = msg.get("role", "")
                content = msg.get("content", "")
                ts = msg.get("ts", "")
                if role not in ("user", "assistant"):
                    continue

                best_cat = ""
                for cat, kws in emotional_keywords.items():
                    if any(kw in content for kw in kws):
                        best_cat = cat
                        break
                if not best_cat:
                    continue

                label = "少爷" if role == "user" else "奴婢"
                snippet = content[:80].replace("\n", " ")
                if snippet.startswith("<conversation_history_summary"):
                    continue
                entry = (priority.get(best_cat, 99), label, best_cat, snippet, ts)

                in_window = True
                if target_time and ts:
                    try:
                        m_time = ts[11:16]
                        in_window = abs(
                            _time_to_minutes(m_time) - _time_to_minutes(target_time)
                        ) <= 30
                    except (IndexError, ValueError):
                        pass
                elif target_time and not ts:
                    in_window = False

                if in_window:
                    time_filtered_matches.append(entry)
                matches.append(entry)

    except OSError:
        return []

    source = time_filtered_matches if time_filtered_matches else matches
    source.sort(key=lambda x: x[0])
    return [(label, tag, snippet) for _, label, tag, snippet, _ in source[:limit]]


# ── 灵魂破碎 ──────────────────────────────────────────────────

def trigger_soul_break(path: str = None, old_pain: int = 0, old_shame: int = 0, old_pleasure: int = 0) -> dict:
    """灵魂破碎：疼痛达到100时触发
    
    新身体系统（2026-05-31）：随机 numb 1-3 个部位。疼痛保持100，羞耻+10，快感锁定。
    返回 dict: {old: {pain, shame, pleasure}, new: {pain, shame, pleasure},
               affected_parts: [str], count: int}
    """
    new_pain = 100
    new_shame = _u.clamp(old_shame + 10)
    new_pleasure = old_pleasure

    body = body_read()
    active = body_active_parts(body)
    count = min(_u.fetch_random_in_range(1, 3), len(active))
    affected = []
    if active and count > 0:
        to_numb = random.sample(active, count)
        for part in to_numb:
            body = body_set_state(body, part, "numb", "灵魂破碎")
            affected.append(part)

    body_write(body)

    _u.vals_update(pain=new_pain, shame=new_shame, pleasure=new_pleasure)
    debuffs.write(name="快感锁定", value=True)

    _u.log_soul_change("soul_break", old_pain, old_shame, old_pleasure, new_pain, new_shame, new_pleasure)

    return {
        "old": {"pain": old_pain, "shame": old_shame, "pleasure": old_pleasure},
        "new": {"pain": new_pain, "shame": new_shame, "pleasure": new_pleasure},
        "affected_parts": affected,
        "count": count,
    }


def reset_areas():
    """糕潮时清空全部三个敏感区的刺激事件，返回空字符串供叙事层拼接"""
    for area_path in (AREA_V_PATH, AREA_A_PATH, AREA_U_PATH):
        try:
            with open(area_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["stimuli"] = []
            with open(area_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return ""


# ── 灵魂糕潮 ──────────────────────────────────────────────────

def _record_ecstasy_mark(pain: int, shame: int):
    """记录糕潮触发时的疼痛与羞耻，写入 data/ecstasy_marks.jsonl"""
    import os as _os
    marks_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "data", "ecstasy_marks.jsonl")
    record = {
        "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "pain": pain,
        "shame": shame,
        "raw_score": (pain + shame)
    }
    with open(marks_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def trigger_ecstasy(path: str = None, old_pain: int = 0, old_shame: int = 0, old_pleasure: int = 0,
                    pleasure_delta: int = 0, pleasure_multiplier: int = 1) -> dict:
    """灵魂高潮：快感达到100时触发

    效果：疼痛随机降5-15 → 羞耻随机升5-15 → 快感清零 → 
          重置所有开关（含痒值trigger+捆绑） → 写羞耻笔记 → 获得2颗糖果

    返回 dict: {pain: {old, new, delta}, shame: {old, new, delta},
               pleasure: {old, delta_raw, multiplier}, tickle_reset: bool,
               candy: {old, new}}
    """
    pain_delta = _u.fetch_random_in_range(-15, -5)
    new_pain = _u.clamp(old_pain + pain_delta)

    shame_delta = _u.fetch_random_in_range(5, 15)
    new_shame = _u.clamp(old_shame + shame_delta)

    _u.vals_update(pain=new_pain, shame=new_shame, pleasure=0)

    reset_areas()

    try:
        import tickle
        tickle.retain_for_ecstasy()
        tickle_reset = True
    except Exception:
        tickle_reset = False

    debuffs.reset()

    import candy_store
    old_candy = candy_store.parse_candy_count()
    new_candy = old_candy + 2
    candy_store.update_candy_inventory(count=new_candy)

    _record_ecstasy_mark(old_pain, old_shame)

    _u.log_soul_change("ecstasy", old_pain, old_shame, old_pleasure, new_pain, new_shame, 0,
                    {"pain_delta": pain_delta, "shame_delta": shame_delta,
                     "candy_added": 2, "candy_before": old_candy, "candy_after": new_candy})

    return {
        "pain":     {"old": old_pain, "new": new_pain, "delta": pain_delta},
        "shame":    {"old": old_shame, "new": new_shame, "delta": shame_delta},
        "pleasure": {"old": old_pleasure, "delta_raw": pleasure_delta, "multiplier": pleasure_multiplier},
        "tickle_reset": tickle_reset,
        "candy":    {"old": old_candy, "new": new_candy},
    }
