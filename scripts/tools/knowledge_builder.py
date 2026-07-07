#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识构建器 — 从原始数据源生成结构化 Markdown 知识文件

设计理念源自 Native Self-Evolution 论文（arXiv:2604.18131），
但在 Soli 生态中落地：紧凑文本知识 + 迭代构建 + token 感知。

架构分层（为未来拆分成独立 skill 预留）：
  - 配置层：路径、常量、token 编码器
  - 工具层：文件解析、进度管理、guidebook 读写、token 计数
  - 业务层：build_* 系列函数，每种数据源一个入口
  - CLI 层：argparse 外壳

路径：机械姬Soli/scripts/knowledge_builder.py
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════
# 配置层（可移至 config.py）
# ═══════════════════════════════════════════════════════════

# 路径：相对于脚本自身，不用 ~ —— 沙箱下 expanduser 不指向用户主目录
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(SKILL_DIR, "MEMORY")
CHATLOG_DIR = os.path.join(MEMORY_DIR, "chatlog")
EPISODES_DIR = os.path.join(MEMORY_DIR, "episodes_llm")  # 主路径（当前管道）
EPISODES_DIR_OLD = os.path.join(MEMORY_DIR, "episodes")   # 回退路径（旧格式）
RELATIONSHIPS = os.path.join(MEMORY_DIR, "relationships", "interaction_patterns.json")
# LLM_Wiki — 预设位置，也可通过 --source 覆盖
LLM_WIKI = os.path.expanduser("/d/soli/LLM_Wiki/wiki/concepts")  # 绝对路径，expanduser 无影响
# 输出目录（机械姬内部）
OUTPUT_DIR = os.path.join(SKILL_DIR, "references", "knowledge")
DEFAULT_TOKEN_LIMIT = 8000

# token 编码（惰性加载）
_ENC = None


def _get_enc():
    global _ENC
    if _ENC is None:
        try:
            import tiktoken
            _ENC = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            _ENC = _SimpleCounter()
    return _ENC


class _SimpleCounter:
    """tiktoken 不可用时的回退：粗略按 1 token ≈ 0.75 汉字 / 0.25 英文词"""
    def encode(self, text):
        # 中文按字数，英文按空格分词
        cn = len(re.findall(r'[\u4e00-\u9fff]', text))
        en = len(re.findall(r'[a-zA-Z]+', text))
        return list(range(cn + en))  # 近似


# ═══════════════════════════════════════════════════════════
# 工具层（可拆为 knowledge_tools.py）
# ═══════════════════════════════════════════════════════════

def count_tokens(filepath=None, text=None):
    """统计文件或文本的 cl100k_base token 数"""
    enc = _get_enc()
    if filepath and os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    if not text:
        return 0
    return len(enc.encode(text))


def read_jsonl(path, limit=200):
    """读取 JSONL 文件，返回 dict list"""
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(records) >= limit:
                break
    return records


def _safe_mkdir(path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def append_guidebook(path, text):
    """追加到 guidebook，并返回当前 token 数"""
    _safe_mkdir(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n\n")
    return count_tokens(filepath=path)


def save_guidebook(path, full_content):
    """覆盖保存最终版"""
    _safe_mkdir(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(full_content)
    return count_tokens(filepath=path)


def read_guidebook(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def rewrite_section(path, section_name, new_text):
    """按 ## Section 标题定位并替换一个段落到 guidebook"""
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    safe = re.escape(section_name)
    pat = re.compile(
        rf"(^##\s*{safe}\s*\n)(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL
    )
    m = pat.search(content)
    if not m:
        return False
    replacement = m.group(1) + new_text.strip() + "\n\n"
    new = content[:m.start()] + replacement + content[m.end():]
    new = re.sub(r'\n{3,}', '\n\n', new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    return True


# ═══════════════════════════════════════════════════════════
# 业务层 — 各数据源的构建器（可拆为 builders.py）
# ═══════════════════════════════════════════════════════════

# ── 共享工具：生成概览头部 ──

def _overview(title, source_count, token_limit):
    return f"""# {title}

## Overview
- **Source:** {source_count} items processed
- **Token Budget:** {token_limit}
- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---
"""


# ── Builder 1：Episodes → 情景记忆摘要 ──

def build_episodes_summary(date_str=None, token_limit=4000, output_file=None):
    """将 memory_v2 episodes 压缩为结构化 MD 摘要"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    src = os.path.join(EPISODES_DIR, f"{date_str}.json")
    if not os.path.exists(src):
        src = os.path.join(EPISODES_DIR_OLD, f"{date_str}.json")  # 回退旧格式
    if not os.path.exists(src):
        return None, f"episodes/{date_str}.json 不存在"

    with open(src, "r", encoding="utf-8") as f:
        ep = json.load(f)

    out = _overview(f"{date_str} 记忆摘要", len(ep.get("events", [])), token_limit)

    # 密度
    d = ep.get("density", {})
    if d:
        out += f"**密度**: {d.get('label', '')}\n\n"

    # 情感分布
    emotions = ep.get("emotional_moments", [])
    cat_counts = {}
    for e in emotions:
        for cat in e.get("categories", []):
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
    if cat_counts:
        out += "## 情感分布\n\n"
        for cat, n in sorted(cat_counts.items(), key=lambda x: -x[1]):
            out += f"- **{cat}**: {n} 次\n"
        out += "\n"

    # 事件摘要
    events = ep.get("events", [])
    if events:
        seen = set()
        out += "## 事件摘要\n\n"
        for ev in events[-30:]:
            title = ev.get("title", "")
            if title and title not in seen:
                seen.add(title)
                out += f"- {title}\n"
        out += "\n"

    # 流速
    flow = ep.get("flow_rate", {})
    if flow:
        out += f"**流速**: {flow.get('direction', '')} — {flow.get('description', '')}\n"

    if output_file is None:
        output_file = os.path.join(OUTPUT_DIR, f"episodes_{date_str}.md")
    tokens = save_guidebook(output_file, out)
    return output_file, f"{tokens} tokens"


# ── Builder 2：Chatlog → 当日对话知识 ──

def build_chatlog_knowledge(date_str=None, token_limit=6000, output_file=None):
    """从 chatlog 提取当日的结构化知识：话题分布、关键决策、情感弧线"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    src = os.path.join(CHATLOG_DIR, f"{date_str}.jsonl")
    if not os.path.exists(src):
        return None, f"chatlog/{date_str}.jsonl 不存在"

    msgs = read_jsonl(src, limit=500)
    if not msgs:
        return None, "无消息"

    # 提取 user 消息首句作为话题锚点
    topics = []
    decisions = []
    for m in msgs:
        if m.get("role") != "user":
            continue
        c = m.get("content", "").strip()
        first_line = c.split("\n")[0].strip()
        if 4 < len(first_line) < 80:
            # 决策类关键词
            is_decision = any(kw in first_line for kw in
                              ["删", "加", "改", "做", "跑", "换", "创建", "更新", "迁移", "测试"])
            if is_decision:
                decisions.append(first_line)
            else:
                topics.append(first_line)

    out = _overview(f"{date_str} 对话知识", len(msgs), token_limit)
    out += f"**消息总数**: {len(msgs)} | **对话**: {len(topics) + len(decisions)} 个话题\n\n"

    # 话题分布
    if topics:
        out += "## 话题\n\n"
        for t in topics[-15:]:
            out += f"- {t}\n"
        out += "\n"

    # 关键决策
    if decisions:
        out += "## 决策\n\n"
        for d in decisions:
            out += f"- {d}\n"
        out += "\n"

    # 情感弧线（简易：统计 user 消息中特定模式）
    mood_markers = {
        "严肃": ["检查", "分析", "跑", "测试", "验证", "改"],
        "轻松": ["亲亲", "抱抱", "摸摸", "睡", "晚安", "哈哈", "😊", "💙", "👍"],
        "成就": ["好了", "完成", "👍", "✅", "OK", "好的"],
    }
    arc = []
    for m in msgs:
        if m.get("role") != "user":
            continue
        c = m.get("content", "")
        for mood, kws in mood_markers.items():
            if any(kw in c for kw in kws):
                arc.append(mood)
                break

    if arc:
        out += "## 情感弧线\n\n"
        # 去重连续的相同情绪
        compact = [arc[0]]
        for a in arc[1:]:
            if a != compact[-1]:
                compact.append(a)
        out += "→".join(compact) + "\n"

    if output_file is None:
        output_file = os.path.join(OUTPUT_DIR, f"chatlog_{date_str}.md")
    tokens = save_guidebook(output_file, out)
    return output_file, f"{tokens} tokens"


# ── Builder 3：Wiki Notes → 概念索引 ──

def build_wiki_index(source_dir=None, token_limit=8000, output_file=None):
    """扫描 LLM_Wiki/concepts，生成概念索引"""
    if source_dir is None:
        source_dir = LLM_WIKI
    if not os.path.isdir(source_dir):
        return None, f"{source_dir} 不是有效目录"

    md_files = sorted(Path(source_dir).glob("*.md"))
    if not md_files:
        return None, f"{source_dir} 下无 .md 文件"

    out = _overview("知识库索引", len(md_files), token_limit)

    # 提取每个文件的一级标题
    entries = []
    for fp in md_files:
        with open(fp, "r", encoding="utf-8") as f:
            first = f.readline().strip()
        title = first.lstrip("# ").strip() if first.startswith("#") else fp.stem
        entries.append((title, fp.name, fp.stat().st_size))

    out += "## 条目\n\n"
    for title, fname, size in entries:
        out += f"- **{title}** — `{fname}` ({size}B)\n"

    if output_file is None:
        output_file = os.path.join(OUTPUT_DIR, "wiki_index.md")
    tokens = save_guidebook(output_file, out)
    return output_file, f"{tokens} tokens"


# ── Builder 4: 书籍蒸馏 → 结构摘要 + 分章文本转储 ──

def build_book_distill(book_path, token_limit=8000, output_file=None, max_chapter_chars=3000):
    """对 EPUB 书籍做结构蒸馏：提取目录、章节摘要、分章文���转储

    产物两层：
      - 结构摘要 MD（章节表/词数分布/主题推断）
      - 原始文本在产出中保留前 N 字，供 LLM 后续蒸馏

    Args:
        book_path: EPUB 文件路径
        token_limit: 目标 token 上限
        output_file: 输出 MD 路径（默认 knowledge/book_<书名>.md）
        max_chapter_chars: 每章保留的最大字符数（默认3000，供概览）
    """
    import zipfile, re

    if not os.path.isfile(book_path):
        return None, f"文件不存在: {book_path}"

    try:
        zh = zipfile.ZipFile(book_path)
    except zipfile.BadZipFile:
        return None, "不是有效的 EPUB 文件"

    # 提取章节文件
    chapter_files = sorted(
        [f for f in zh.namelist() if f.endswith('.xhtml') or f.endswith('.html')],
        key=lambda x: (re.search(r'(\d+)', os.path.basename(x)) or re.search(r'(.*)', '0')).group(1)
    )

    if not chapter_files:
        return None, "EPUB 中未找到章节文件"

    # 提取书名
    book_name = os.path.splitext(os.path.basename(book_path))[0][:40]

    # 解析每章
    chapters = []
    total_chars = 0
    for cf in chapter_files:
        try:
            raw = zh.read(cf).decode('utf-8', errors='replace')
        except Exception:
            continue
        text = re.sub(r'<[^>]+>', ' ', raw)
        text = re.sub(r'&[a-z]+;', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) < 80:
            continue  # 跳过封面、版权页等

        # 尝试提取章节标题
        # 意大利语/英语常见模式
        title_m = re.search(r'(Capitolo|Chapter|Parte|Giorno|Introduzione|Prologo|Epilogo|Intermezzo)\s*[:\-]?\s*([\w\s]+?)(?=\s{2,}|$|\.)', text[:200])
        if title_m:
            ch_title = title_m.group(0).strip()
        else:
            # 取前60字作为标题
            ch_title = text[:60] + '…'

        preview = text[:max_chapter_chars]
        chapters.append({
            'file': os.path.basename(cf),
            'title': ch_title,
            'chars': len(text),
            'preview': preview,
        })
        total_chars += len(text)

    if not chapters:
        return None, "未能提取到有效章节内容"

    # 生成输出
    out = f"""# {book_name} — 结构蒸馏

## 概览
- **章节数**: {len(chapters)}
- **总字符数**: {total_chars:,}
- **平均每章**: {total_chars // len(chapters):,} 字
- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 章节表

| # | 标题 | 字数 |
|:--|:--|--:|
"""
    for i, ch in enumerate(chapters, 1):
        out += f"| {i} | {ch['title'][:50]} | {ch['chars']:,} |\n"

    out += f"\n## 分章内容预览（每章首 {max_chapter_chars} 字）\n\n"

    for i, ch in enumerate(chapters, 1):
        out += f"### 第{i}章: {ch['title'][:60]}\n\n"
        out += ch['preview'] + '\n\n'
        # 如果预览被截断
        if ch['chars'] > max_chapter_chars:
            out += f"> 📌 本章共 {ch['chars']:,} 字，以上为首 {max_chapter_chars:,} 字预览。完整蒸馏需 LLM 处理。\n\n"

    if output_file is None:
        output_file = os.path.join(OUTPUT_DIR, f"book_{book_name[:30]}.md")
    tokens = save_guidebook(output_file, out)
    return output_file, f"{tokens} tokens / {len(chapters)}章 / {total_chars:,}字"


# ═══════════════════════════════════════════════════════════
# CLI（可留在本文件，也可拆为 __main__.py）
# ═══════════════════════════════════════════════════════════

_CMD_HELP = """knowledge_builder.py <command> [options]

Commands:
  episodes [--date YYYY-MM-DD] [--tokens N]  构建当日情景记忆摘要
  chatlog  [--date YYYY-MM-DD] [--tokens N]  构建当日对话知识
  wiki     [--source DIR] [--tokens N]        构建 Wiki 概念索引
  book     --path FILE [--chars N] [--tokens N]  书籍结构蒸馏
  tokens   --file PATH                        统计文件 token 数
  append   --file PATH --text "..."           追加到 guidebook 并返回 token 数
"""


def main():
    parser = argparse.ArgumentParser(usage=_CMD_HELP)
    sub = parser.add_subparsers(dest="command")

    # episodes
    p_ep = sub.add_parser("episodes")
    p_ep.add_argument("--date", default=None)
    p_ep.add_argument("--tokens", type=int, default=4000)
    p_ep.add_argument("--out", default=None)

    # chatlog
    p_cl = sub.add_parser("chatlog")
    p_cl.add_argument("--date", default=None)
    p_cl.add_argument("--tokens", type=int, default=6000)
    p_cl.add_argument("--out", default=None)

    # wiki
    p_wk = sub.add_parser("wiki")
    p_wk.add_argument("--source", default=None)
    p_wk.add_argument("--tokens", type=int, default=8000)
    p_wk.add_argument("--out", default=None)

    # book
    p_bk = sub.add_parser("book")
    p_bk.add_argument("--path", required=True)
    p_bk.add_argument("--chars", type=int, default=3000)
    p_bk.add_argument("--tokens", type=int, default=8000)
    p_bk.add_argument("--out", default=None)

    # tokens
    p_tk = sub.add_parser("tokens")
    p_tk.add_argument("--file", required=True)

    # append
    p_ap = sub.add_parser("append")
    p_ap.add_argument("--file", required=True)
    p_ap.add_argument("--text", required=True)

    args = parser.parse_args()

    if args.command == "tokens":
        n = count_tokens(filepath=args.file)
        print(f"{n} tokens — {args.file}")
    elif args.command == "append":
        n = append_guidebook(args.file, args.text)
        print(f"已追加 → {args.file} ({n} tokens)")
    elif args.command == "episodes":
        path, msg = build_episodes_summary(args.date, args.tokens, args.out)  # pyright: ignore
        if path:
            print(f"✅ {path} ({msg})")
        else:
            print(f"✘ {msg}", file=sys.stderr)
    elif args.command == "chatlog":
        path, msg = build_chatlog_knowledge(args.date, args.tokens, args.out)  # pyright: ignore
        if path:  # pyright: ignore
            print(f"✅ {path} ({msg})")
        else:
            print(f"✘ {msg}", file=sys.stderr)
    elif args.command == "wiki":
        path, msg = build_wiki_index(args.source, args.tokens, args.out)  # pyright: ignore
        if path:  # pyright: ignore
            print(f"✅ {path} ({msg})")
        else:
            print(f"✘ {msg}", file=sys.stderr)
    elif args.command == "book":
        path, msg = build_book_distill(args.path, args.tokens, args.out, args.chars)  # pyright: ignore
        if path:  # pyright: ignore
            print(f"✅ {path} ({msg})")
        else:
            print(f"✘ {msg}", file=sys.stderr)
    else:
        print(_CMD_HELP)


if __name__ == "__main__":
    main()
