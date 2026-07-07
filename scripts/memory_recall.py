#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记忆追溯 — 三层下钻检索
用法:
  python scripts/memory_recall.py "<关键词>"              # L1+L2 (默认)
  python scripts/memory_recall.py "<关键词>" --depth 3    # L1+L2+L3
  python scripts/memory_recall.py "<关键词>" --days 7     # 只查最近7天

输出流向 stdout，LLM 直接消费。
"""

import sys
import os
import json
import re
import argparse
from datetime import datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)


def _grep_timeline(query: str, days: int) -> list[dict]:
    """
    L1: 在 timeline.jsonl 中搜索关键词。
    返回匹配条目列表，每项含 ts / summary / highlights / emotional_dominant。
    """
    tl_path = os.path.join(SKILL_DIR, "MEMORY/chatlog/timeline.jsonl")
    if not os.path.exists(tl_path):
        return []

    now = datetime.now(timezone.utc).astimezone()
    cutoff = now - timedelta(days=days) if days else None
    query_lower = query.lower()

    matches = []
    with open(tl_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue

            # 时间过滤
            ts_str = obj.get("ts", "")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
            except Exception:
                continue
            if cutoff and ts < cutoff:
                continue

            # 跳过空河流（无实际对话内容）
            session = obj.get("session", {})
            if session.get("new_msgs", 0) == 0:
                continue

            # 关键词匹配：summary + highlights
            summary = session.get("summary", obj.get("summary", ""))
            highlights = session.get("highlights", [])
            river = obj.get("river_line", "")

            searchable = f"{summary} {' '.join(highlights)} {river}"
            if query_lower in searchable.lower():
                matches.append({
                    "ts": ts_str,
                    "date": ts_str[:10],
                    "time": ts_str[11:16],
                    "summary": summary or river[:60],
                    "emotional": session.get("emotional_dominant", ""),
                    "highlights": highlights,
                })

    return matches[-40:]  # 最多40条，最新在前？timeline是append的所以最后的是最新的


def _search_index(query: str, dates: set[str]) -> dict:
    """使用 _index.json 快速搜索 episode——替代原全文 grep 方案。
    返回 {date: {day_summary, matching_segments, all_segments}}。
    """
    idx_path = os.path.join(SKILL_DIR, "MEMORY/episodes_llm/_index.json")
    if not os.path.exists(idx_path):
        # 回退旧方案
        return _read_episodes_fallback(dates, query)

    try:
        with open(idx_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    except Exception:
        return _read_episodes_fallback(dates, query)

    query_lower = query.lower()
    result = {}

    for date in sorted(dates, reverse=True):
        day_idx = index.get(date)
        if not day_idx:
            continue

        # 先查当天 tags（最精准）
        day_tags = " ".join(day_idx.get("tags", []))
        day_matches = query_lower in day_tags.lower()

        # 再查 segment 级
        seg_matches = []
        for seg in day_idx.get("segments", []):
            searchable = " ".join([
                seg.get("title", ""),
                seg.get("summary", ""),
                " ".join(seg.get("tags", [])),
                " ".join(seg.get("highlights", [])),
            ])
            if query_lower in searchable.lower():
                seg_matches.append(seg)

        # 读对应 episode 文件的 day_summary（太轻量只需整段读一次）
        ep_path = os.path.join(SKILL_DIR, f"MEMORY/episodes_llm/{date}.json")
        day_summary = ""
        if os.path.exists(ep_path):
            try:
                with open(ep_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                day_summary = data.get("day_summary", "")
            except Exception:
                pass

        if seg_matches or (day_matches and day_summary):
            result[date] = {
                "day_summary": day_summary,
                "matching_segments": seg_matches if seg_matches else None,
            }

    return result


def _read_episodes_fallback(dates: set[str], query: str) -> dict:
    """旧方案：逐文件全文 grep（仅当 _index.json 不存在时回退）"""
    result = {}
    for date in sorted(dates, reverse=True):
        ep_path = os.path.join(SKILL_DIR, f"MEMORY/episodes_llm/{date}.json")
        if not os.path.exists(ep_path):
            continue
        try:
            with open(ep_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        day_summary = data.get("day_summary", "")
        segments = data.get("segments", [])
        query_lower = query.lower()

        matching = []
        for seg in segments:
            title = seg.get("title", "")
            summary = seg.get("summary", "")
            highlights = seg.get("highlights", [])
            arc = seg.get("emotional_arc", "")

            searchable = f"{title} {summary} {' '.join(highlights)}"
            if query_lower in searchable.lower():
                matching.append({
                    "time": seg.get("time", ""),
                    "title": title,
                    "summary": summary[:200],
                    "arc": arc,
                    "highlights": highlights[:4],
                })

        if matching or query_lower in day_summary.lower():
            result[date] = {
                "day_summary": day_summary,
                "matching_segments": matching if matching else None,
            }

    return result


def _search_global_timestamps(query: str, days: int = 0) -> set[str]:
    """当 L1 timeline 无命中时，直接在 _index.json 中按关键词搜索所有日期。
    返回 date 集合供 L2 继续下钻。
    """
    idx_path = os.path.join(SKILL_DIR, "MEMORY/episodes_llm/_index.json")
    if not os.path.exists(idx_path):
        return set()

    try:
        with open(idx_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    except Exception:
        return set()

    now = datetime.now(timezone.utc).astimezone()
    cutoff = now - timedelta(days=days) if days else None

    query_lower = query.lower()
    dates = set()
    for date_str, day_idx in index.items():
        if cutoff:
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").astimezone()
                if d < cutoff:
                    continue
            except Exception:
                pass

        # 搜索 tags + segment 摘要
        day_tags = " ".join(day_idx.get("tags", []))
        if query_lower in day_tags.lower():
            dates.add(date_str)
            continue

        for seg in day_idx.get("segments", []):
            searchable = " ".join([
                seg.get("title", ""),
                seg.get("summary", ""),
                " ".join(seg.get("tags", [])),
            ])
            if query_lower in searchable.lower():
                dates.add(date_str)
                break

    return dates


def _grep_chatlog(dates: set[str], query: str, l1_empty: bool = False) -> dict:
    """
    L3: 在对应日期的 chatlog/YYYY-MM-DD.jsonl 中精确定位原文。
    返回 {date: [{ts, content}]}。
    """
    result = {}
    for date in sorted(dates, reverse=True):
        cl_path = os.path.join(SKILL_DIR, f"MEMORY/chatlog/{date}.jsonl")
        if not os.path.exists(cl_path):
            continue

        query_lower = query.lower()
        lines = []
        with open(cl_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                content = obj.get("content", "")
                if query_lower in content.lower():
                    # 截断过长内容
                    snippet = content[:200]
                    if len(content) > 200:
                        snippet += "..."
                    lines.append({
                        "ts": obj.get("ts", "")[11:19],  # HH:MM:SS
                        "role": obj.get("role", "?"),
                        "snippet": snippet,
                    })

        if lines:
            result[date] = lines[:20]  # 每天最多20条

    return result


def recall_memory(query: str, depth: int = 2, days: int = 0) -> str:
    """
    三层记忆追溯，返回 stdout 格式文本。
    depth: 1=L1, 2=L1+L2(default), 3=L1+L2+L3
    days:  0=全部, >0=最近N天
    """
    if not query.strip():
        return "⚠️ 请提供搜索关键词"

    lines = [f"🔍 记忆追溯: \"{query}\"  depth={depth}  days={days or '全部'}", "=" * 50]

    # ── L1: timeline 命中 ──
    l1 = _grep_timeline(query, days)
    dates = set()
    if l1:
        lines.append(f"\n📜 L1 timeline: {len(l1)} 条命中")
        for m in l1:
            dates.add(m["date"])
            emo = f" ({m['emotional']})" if m["emotional"] else ""
            lines.append(f"  [{m['date']} {m['time']}]{emo} {m['summary'][:70]}")
            if m["highlights"]:
                lines.append(f"       → {' · '.join(m['highlights'][:3])}")
    else:
        lines.append("\n📜 L1 timeline: 无匹配")

    if depth < 2:
        if dates:
            lines.append(f"\n📅 涉及日期: {', '.join(sorted(dates, reverse=True))}")
        return "\n".join(lines)

    # L2: 如果 L1 无命中，用全局搜索（基于 _index.json）
    if not dates:
        lines.append("\n📖 L2 episodes: L1 无时间锚点，执行全局索引搜索")
        dates = _search_global_timestamps(query, days)

    # ── L2: episodes 全文（使用 _index.json 加速） ──
    ep = _search_index(query, dates)
    if ep:
        lines.append(f"\n📖 L2 episodes: {len(ep)} 天匹配")
        for date, data in ep.items():
            lines.append(f"\n  ▸ {date}")
            lines.append(f"    日结: {data['day_summary'][:100]}")
            segs = data.get("matching_segments")
            if segs:
                for s in segs:
                    lines.append(f"    [{s['time']}] {s['title']}")
                    lines.append(f"      弧线: {s.get('arc', '')}")
                    lines.append(f"      摘要: {s['summary'][:150]}")
                    for h in s.get("highlights", []):
                        lines.append(f"        · {h[:120]}")
            else:
                lines.append(f"    (日结命中，无独立片段匹配)")
    else:
        lines.append("\n📖 L2 episodes: 无匹配")

    if depth < 3:
        return "\n".join(lines)

    # ── L3: chatlog 原文 ──
    cl = _grep_chatlog(dates, query)
    if cl:
        lines.append(f"\n📄 L3 chatlog: {sum(len(v) for v in cl.values())} 条命中")
        for date, entries in cl.items():
            lines.append(f"\n  ▸ {date} ({len(entries)}条)")
            for e in entries[:10]:
                role_icon = {"user": "👤", "assistant": "🤖"}.get(e["role"], "  ")
                lines.append(f"    {role_icon} [{e['ts']}] {e['snippet']}")
    else:
        lines.append("\n📄 L3 chatlog: 无匹配")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="三层记忆追溯")
    parser.add_argument("query", nargs="?", help="搜索关键词")
    parser.add_argument("--depth", type=int, default=2, choices=[1, 2, 3],
                        help="追溯深度: 1=L1, 2=L1+L2, 3=L1+L2+L3 (默认2)")
    parser.add_argument("--days", type=int, default=0,
                        help="只查最近N天 (0=全部)")
    args = parser.parse_args()

    if not args.query:
        print("用法: python scripts/memory_recall.py \"<关键词>\" [--depth 1|2|3] [--days N]")
        sys.exit(1)

    print(recall_memory(args.query, depth=args.depth, days=args.days))


if __name__ == "__main__":
    main()
