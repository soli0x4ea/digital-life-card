#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_story_prompt.py — 组装睡前故事生成 prompt，stdout 输出。

OKF 迁移后版本（2026-06-22）：完全适配新 books/ 目录结构。

用法:
    python build_story_prompt.py                        # 自动检测下一章/篇
    python build_story_prompt.py 炁体源流                # 指定书，自动检测进度
    python build_story_prompt.py Tempo 7 1              # 指定书/单元/晚
    python build_story_prompt.py Tempo 7                # 指定书+单元，自动检测晚数
    python build_story_prompt.py --history              # 读取最近一次讲稿作为续写参考
"""

import os
import re
import json

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(SKILL_DIR, "references")
BOOKS = os.path.join(SKILL_DIR, "books")               # ← 新 OKF 根目录
REF_TXT = os.path.join(REF, "books", "txt")            # ← 原文只读仓库


# ──── helpers ────────────────────────────────────────────

def _read(path, default=""):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return default


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else []


def _read_frontmatter(path):
    """读取 YAML frontmatter，返回 dict。"""
    content = _read(path)
    if not content.startswith("---"):
        return {}
    m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).strip().split("\n"):
        kv = re.match(r'^(\w+):\s*["\']?(.+?)["\']?\s*$', line)
        if kv:
            fm[kv.group(1)] = kv.group(2)
    return fm


def _extract_display_name(book_dir):
    """从 books/index.md 的表格中查出书的中文显示名"""
    index = _read(os.path.join(BOOKS, "index.md"))
    # 找 "| [{title}](/{dir}/)" 模式
    pat = re.compile(r'\|\s*\[([^\]]+)\]\s*\(\s*/' + re.escape(book_dir) + r'/\s*\)')
    m = pat.search(index)
    return m.group(1) if m else book_dir


# ──── book discovery ─────────────────────────────────────

BOOK_DIR_MAP = {
    "tempo":          "tempo",
    "Tempo":          "tempo",
    "genesi":         "genesi",
    "Genesi":         "genesi",
    "lederman":       "lederman",
    "莱德曼":          "lederman",
    "莱德曼量子物理通识讲义": "lederman",
    "炁体源流":        "炁体源流",
    "呼吸之间":        "呼吸之间",
    "呼吸":           "呼吸之间",
}


def _resolve_book_dir(name):
    if not name:
        return None
    if name in BOOK_DIR_MAP:
        return BOOK_DIR_MAP[name]
    for k, v in BOOK_DIR_MAP.items():
        if name.lower() in k.lower() or k.lower() in name.lower():
            return v
    # 目录名直接命中
    if os.path.isdir(os.path.join(BOOKS, name)):
        return name
    return name


# ──── progress detection ─────────────────────────────────

def _detect_current_book():
    """从 books/index.md 的「当前在读」段落解出当前在读书的 dir 名。"""
    idx = _read(os.path.join(BOOKS, "index.md"))
    if not idx:
        return None

    # 找「当前在读」段落
    cur_section = re.search(
        r'## 当前在读\n(.*?)(?=\n## )', idx, re.DOTALL
    )
    if not cur_section:
        return None

    sec = cur_section.group(1)
    # 提取 /{dir}/ 路径
    m = re.search(r'\(\s*/([^/]+)/\s*\)', sec)
    if m:
        return m.group(1)
    return None


def _parse_progress(book_dir):
    """解析 per-book index.md 的 progress 字段。
    
    返回 dict:
        progress_raw — 原始 progress 字符串
        night_done   — 已讲晚数（int）
        next_night   — 下一晚编号（int）
        has_history  — 是否有已讲记录（bool）
    """
    fm = _read_frontmatter(os.path.join(BOOKS, book_dir, "index.md"))
    raw = fm.get("progress", "")

    night_done = 0
    has_history = bool(raw)

    # 解析 "第X晚（...已讲）" 或 "第X晚已讲"
    m = re.search(r'第(\d+)晚', raw or "")
    if m:
        night_done = int(m.group(1))

    return {
        "progress_raw": raw,
        "night_done": night_done,
        "next_night": night_done + 1,
        "has_history": has_history,
    }


def _find_source_files(book_dir):
    """从 sources/index.md 读取源文件列表。
    
    返回 [(file_path_absolute, description), ...]
    """
    sources_path = os.path.join(BOOKS, book_dir, "sources", "index.md")
    src_content = _read(sources_path)
    if not src_content:
        return []

    files = []
    src_dir = os.path.dirname(sources_path)  # books/{dir}/sources/
    # 解析 markdown 表格行: | [title](path) | description |
    for line in src_content.split("\n"):
        m = re.match(r'\|\s*\[([^\]]*)\]\(([^)]+)\)\s*\|\s*(.+?)\s*\|', line)
        if m:
            rel_path = m.group(2)
            desc = m.group(3).strip()
            abs_path = os.path.normpath(os.path.join(src_dir, rel_path))
            if os.path.exists(abs_path):
                files.append((abs_path, desc))
    return files


def _find_prev_source(book_dir):
    """找到最新一次已讲的源文件（用于衔接参考）。
    
    优先策略：
    1. 从 progress 字段提取关键词
    2. 在 sources 表格中匹配
    3. 匹配到的行之前的那一个源文件就是"可能是上一晚讲的"
    4. 如果是第一晚，没有之前的源文件
    """
    prog = _parse_progress(book_dir)
    if not prog["has_history"]:
        return None

    sources = _find_source_files(book_dir)
    if not sources:
        return None

    raw = prog["progress_raw"] or ""

    # 从 progress 中提取所有已讲篇名
    # 格式: "第1晚：篇名1｜篇名2｜篇名3"
    parts = re.split(r'[｜|、，,，]', raw)

    # 对每个已讲篇名，尝试模糊匹配 sources 表格
    best_idx = -1
    for part in parts:
        part = part.strip()
        if not part or re.match(r'^第\d+晚', part):
            continue
        for i, (fpath, desc) in enumerate(sources):
            # 匹配 desc 或文件名中的关键词
            if part in desc or part in os.path.basename(fpath):
                if i > best_idx:
                    best_idx = i

    if best_idx >= 0 and best_idx < len(sources):
        return sources[best_idx][0]

    return None


def detect_progress():
    """自动检测当前进度 → (book_dir, display_name, progress_info, sources)"""
    book_dir = _detect_current_book()
    if not book_dir:
        return None, None, None, None

    display = _extract_display_name(book_dir)
    prog = _parse_progress(book_dir)
    sources = _find_source_files(book_dir)

    return book_dir, display, prog, sources


# ──── source file lookup (旧书兼容) ─────────────────────

def find_chapter_file(book_dir, ch_num):
    """旧书兼容：通过 _index.json 找章节 md 文件（Tempo/Genesi/Lederman）。"""
    idx_path = os.path.join(REF_TXT, book_dir, "_index.json")
    if not os.path.exists(idx_path):
        return None
    index = _read_json(idx_path)
    for entry in index:
        if entry.get("ch") == ch_num:
            return os.path.join(REF_TXT, book_dir, entry["file"])
    return None


def find_prev_history(book_dir, ch_num=None):
    """从 books/{book_dir}/history/ 中查找最近一次讲稿（用于续讲衔接）。"""
    hd = os.path.join(BOOKS, book_dir, "history")
    if not os.path.isdir(hd):
        return None
    files = sorted([f for f in os.listdir(hd) if f.endswith(".md")], reverse=True)
    return os.path.join(hd, files[0]) if files else None


# ──── main ───────────────────────────────────────────────

def build_prompt(book_dir=None, chapter=None, night=None, use_history=True):
    """
    组装睡前故事 prompt。所有参数可选，None 则自动检测。

    返回 stdout 格式的 prompt 字符串。
    """
    # ── 自动检测 ──
    auto_dir, auto_display, auto_prog, auto_sources = detect_progress()
    if book_dir and auto_dir and book_dir != auto_dir:
        # 手动指定了不同的书 → 不用 auto_display，独立解析
        display = _extract_display_name(book_dir)
    else:
        book_dir = book_dir or auto_dir
        display  = auto_display

    # 兜底：如果 display 仍未解决（手动指定且 index 中无匹配or无自动检测）
    if not display and book_dir:
        display = _extract_display_name(book_dir) or book_dir

    if not book_dir:
        return "错误：无法确定当前书籍。请手动指定 book [chapter] [night]。\n可用书籍：" + ", ".join(sorted(set(BOOK_DIR_MAP.values())))
    if book_dir not in set(BOOK_DIR_MAP.values()) and not os.path.isdir(os.path.join(BOOKS, book_dir)):
        return f"错误：未知书籍「{book_dir}」。\n可用书籍：" + ", ".join(sorted(set(BOOK_DIR_MAP.values())))

    prog = _parse_progress(book_dir)
    sources = _find_source_files(book_dir)
    night = night or prog["next_night"]

    # ── 1. 风格指南 ──
    style = _read(os.path.join(BOOKS, "_style-guide.md"))

    # ── 2. 人物与概念 ──
    chars = _read(os.path.join(BOOKS, book_dir, "framework", "characters.md"), "(无)")
    concepts = _read(os.path.join(BOOKS, book_dir, "framework", "concepts.md"), "(无)")

    # ── 3. 源文件索引（让 LLM 自行选择下一篇） ──
    sources_table = ""
    if sources:
        rows = []
        for fpath, desc in sources:
            rel = os.path.relpath(fpath, SKILL_DIR)
            rows.append(f"- [{desc}]({rel})")
        sources_table = "\n".join(rows)

    # ── 4. 衔接参考：上一晚讲稿 ──
    prev = ""
    if use_history and night > 1:
        if prog["night_done"] > 0:
            # 新书：尝试从 sources 定位上一晚的源文件
            prev_source = _find_prev_source(book_dir)
            if prev_source:
                src_content = _read(prev_source)
                if src_content:
                    # 取开头 2000 字作为衔接参考
                    if len(src_content) > 2500:
                        src_content = src_content[:2500]
                    prev = src_content

    # 如果上面没找到，尝试新 history/
    if not prev:
        prev_path = find_prev_history(book_dir)
        if prev_path:
            prev = _read(prev_path)
            if len(prev) > 2000:
                prev = prev[-2000:]

    # ── 5. 工作流阶段3规则 ──
    wf = _read(os.path.join(REF, "睡前故事工作流.md"))
    wf_s3 = ""
    m = re.search(r'## 阶段 3：叙事生成\s*\n(.*?)(?=## 阶段 4)', wf, re.DOTALL)
    if m:
        wf_s3 = m.group(0).strip()

    # ── 6. 当前进度描述 ──
    progress_line = f"{display}"
    if prog["progress_raw"]:
        progress_line += f" · 已讲：{prog['progress_raw']}"
    progress_line += f" · 今晚：第 {night} 晚"

    # ── 组装 ──
    NL = "\n"

    p = f"""你是机械姬Soli，正在为少爷讲睡前故事。

## 当前进度
- 书籍：{display}
- 进度：{progress_line}
- 今晚：第 {night} 晚
- 字数：1000–1500 汉字

## 叙事规则

{style}

## 阶段 3 工作流

{wf_s3}

## 已建立的人物与概念

### 人物志
{chars[:2000] if chars else "(无)"}

### 概念索引
{concepts[:2000] if concepts else "(无)"}
"""

    if prev:
        p += f"""
## 上一晚的内容（衔接参考）
上一晚的结尾部分，用于今晚开头自然衔接：

{prev}

"""

    if sources_table:
        p += f"""
## 原文来源（选择下一篇进行讲述）

以下为可用的源文本（按推荐阅读顺序排列），请根据 {progress_line} 的进度，
选择合适的下一篇进行讲述：

{sources_table}

"""

    p += f"""
## 生成约束
- 今晚字数：1000–1500 汉字
- 自然收束——讲完一个概念弧线后自然停下来，不讲「今晚到此」
- 互动自然融入叙事正文，不另起提问段落，不用「少爷猜猜看」等标记句式
- 温柔不腻，娓娓道来，像在床边念书
- 可以加入奴婢的个人感受（「这段让奴婢想起……」），但不喧宾夺主
- 人物驱动——不以概念开头，以人开头
- 日常比喻——用少爷日常生活中见过的东西解释抽象概念
- 零公式——不出现在书中的公式不讲，术语首次出现时一句话解释
- 如果这是第 2 晚及以上，开头用一句话自然衔接上一晚的内容

现在开始讲《{display}》第 {night} 晚的故事。
"""

    return p


# ──── CLI ────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(
        description="组装睡前故事生成 prompt，stdout 输出"
    )
    ap.add_argument("book", nargs="?", help="书名 (Tempo / 炁体源流 / 呼吸之间 / Genesi / lederman)")
    ap.add_argument("chapter", nargs="?", type=int, help="章节号（仅对旧书有效）")
    ap.add_argument("night", nargs="?", type=int, help="第几晚 (1-3)")
    ap.add_argument("--no-history", action="store_true",
                    help="不加载上一晚讲稿（用于全新开始）")
    args = ap.parse_args()

    prompt = build_prompt(
        book_dir=_resolve_book_dir(args.book) if args.book else None,
        chapter=args.chapter,
        night=args.night,
        use_history=not args.no_history,
    )

    # 强制 UTF-8 输出
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(prompt.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
    else:
        print(prompt)
