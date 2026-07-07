#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
episode 搜索索引构建器 — 方案 A+B
1. 扫描 MEMORY/episodes_llm/YYYY-MM-DD.json，从段标题/高亮中提取 tags
2. 生成 _index.json（轻量可搜索索引）
3. 若读入的 episode 没有 tags 字段，自动补写（未来 LLM 生成时可自带 tags）

用法：
  python scripts/build_search_index.py              # 扫描并重建索引
  python scripts/build_search_index.py --inject     # 同时将 tags 写回 episode 文件
"""

import json
import os
import re
import argparse
from pathlib import Path
from collections import OrderedDict

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
EPISODES_DIR = SKILL_DIR / "MEMORY" / "episodes_llm"
INDEX_FILE = EPISODES_DIR / "_index.json"

# ── 常用停用词（过滤噪音） ──
STOP_WORDS = {
    "一个", "这个", "那个", "什么", "怎么", "如何", "可以", "没有",
    "不是", "就是", "但是", "而且", "因为", "所以", "如果", "虽然",
    "以及", "其中", "之后", "之前", "关于", "对于", "通过", "进行",
    "以及", "还是", "只是", "不过", "然后", "接着", "同时", "已经",
    "还有", "所有", "这些", "那些", "他们", "自己", "每个", "整个",
    "了", "的", "和", "在", "是", "有", "就", "也", "都", "不", "把",
    "被", "让", "给", "跟", "对", "从", "到", "用", "以", "与",
    "the", "a", "an", "this", "that", "it", "is", "are", "was", "were",
    "to", "of", "in", "for", "on", "with", "as", "at", "by",
}


def _extract_title_tags(title: str) -> list[str]:
    """从 segment 标题提取有意义的关键词标签"""
    tags = set()

    # 去掉 # 前缀和 emoji
    clean = re.sub(r'^#\s*', '', title)
    clean = re.sub(r'[\U0001F300-\U0001FAFF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF'
                   r'\U0001F1E0-\U0001F1FF\u2600-\u27BF\uFE00-\uFE0F]', '', clean)
    clean = clean.strip()

    # 用：或 : 分割，取后面部分作为精炼标签
    parts = re.split(r'[：:]', clean)
    for part in parts:
        # 去掉装饰性前缀
        part = re.sub(r'^[「『【（\[\(]\s*', '', part)
        part = re.sub(r'[」』】）\]\)]\s*$', '', part)
        part = part.strip()
        if len(part) < 2 or len(part) > 20:
            continue
        if part.lower() in STOP_WORDS:
            continue
        tags.add(part)

    return sorted(tags)


def _extract_highlight_tags(highlights: list[str]) -> list[str]:
    """从 highlights 提取核心名词标签"""
    tags = set()
    for h in highlights:
        # 去掉 emoji 前缀
        clean = re.sub(r'^[\U0001F300-\U0001FAFF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF'
                       r'\U0001F1E0-\U0001F1FF\u2600-\u27BF\uFE00-\uFE0F\U0001F3E0-\U0001F3FF]+\s*', '', h)

        # 提取引号内关键词
        quoted = re.findall(r'[「」""]([^「」""]{2,15})[「」""]', clean)
        for q in quoted:
            if q.lower() not in STOP_WORDS:
                tags.add(q)

        # 提取 "xxx" 前后常见架构词
        for kw in ["重构", "修复", "迁移", "新增", "删除", "拆分", "合并",
                    "重构。", "升级", "改造", "采纳", "废弃", "引入",
                    "方案", "架构", "引擎", "管线", "闭环", "检测",
                    "叙事", "命令", "输出", "系统", "容器", "令牌",
                    "糖果", "涂鸦", "调教", "惩罚", "清算", "破碎",
                    "糕潮", "梦境", "反思", "自动化", "记忆",
                    "三层分离", "全量覆盖", "merge"]:
            if kw in clean:
                tags.add(kw)

    return sorted(tags)


def _extract_episode_tags(episode: dict) -> list[str]:
    """对一个 episode 文件提取 tags"""
    tags = set()
    segments = episode.get("segments", [])
    for seg in segments:
        title_tags = _extract_title_tags(seg.get("title", ""))
        highlight_tags = _extract_highlight_tags(seg.get("highlights", []))
        tags.update(title_tags)
        tags.update(highlight_tags)
    return sorted(tags)


def build_index(inject: bool = False) -> dict:
    """扫描所有 episode JSON 文件，构建 _index.json"""
    if not EPISODES_DIR.exists():
        print(f"[index] episodes_llm 目录不存在: {EPISODES_DIR}")
        return {}

    json_files = sorted(
        [f for f in EPISODES_DIR.iterdir() if f.suffix == ".json" and f.stem != "_index"],
        reverse=True
    )
    print(f"[index] 扫描到 {len(json_files)} 个 episode 文件")

    index = OrderedDict()
    for fpath in json_files:
        date_str = fpath.stem
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                episode = json.load(f)
        except Exception as e:
            print(f"  ⚠ {date_str}: 读取失败 ({e})")
            continue

        # 提取 tags
        existing_tags = episode.get("tags", [])
        if existing_tags:
            tags = existing_tags
        else:
            tags = _extract_episode_tags(episode)
            # 注入 tags 到 episode 文件
            if inject:
                episode["tags"] = tags
                try:
                    with open(fpath, "w", encoding="utf-8") as f:
                        json.dump(episode, f, ensure_ascii=False, indent=2)
                    print(f"  ✏ {date_str}: 注入 tags -> {tags}")
                except Exception as e:
                    print(f"  ⚠ {date_str}: 写入失败 ({e})")

        # 构建 segment 级索引
        seg_index = []
        segments = episode.get("segments", [])
        for seg in segments:
            seg_title = seg.get("title", "")
            seg_highlights = seg.get("highlights", [])
            seg_summary = seg.get("summary", "")[:200]

            # 该 segment 独有的 tags
            seg_tags = set()
            title_tags = _extract_title_tags(seg_title)
            hl_tags = _extract_highlight_tags(seg_highlights)
            seg_tags.update(title_tags)
            seg_tags.update(hl_tags)

            seg_index.append({
                "time": seg.get("time", ""),
                "title": re.sub(r'^#\s*', '', seg_title),
                "tags": sorted(seg_tags),
                "summary": seg_summary,
                "arc": seg.get("emotional_arc", "")[:120],
                "highlights": seg_highlights[:4],
            })

        index[date_str] = {
            "tags": tags,
            "segments": seg_index,
        }

    # 写入 _index.json
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"[index] ✓ _index.json 已生成 ({len(index)} 天, {INDEX_FILE})")
    
    # 输出 tag 云
    all_tags = set()
    for v in index.values():
        all_tags.update(v["tags"])
    print(f"[index]   覆盖标签 {len(all_tags)} 个: {', '.join(sorted(all_tags)[:30])}...")

    return index


def main():
    parser = argparse.ArgumentParser(description="episode 搜索索引构建器")
    parser.add_argument("--inject", action="store_true",
                        help="同时将自动提取的 tags 写回 episode 文件")
    args = parser.parse_args()

    build_index(inject=args.inject)


if __name__ == "__main__":
    main()
