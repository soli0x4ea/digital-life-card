#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内心叙事写入器 — soli 内心叙事的统一入口。
支持 调教记录 / 羞耻笔记 两种标签，将叙事追加到当天日记文件。
"""

import sys
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import diary


def write(text: str, label: str = "调教记录") -> str:
    """追加一条内心叙事到当天日记

    label: "调教记录" | "羞耻笔记" | 其他自定义标签
    """
    now = datetime.now()
    ts = now.strftime("%H:%M")
    date_str = now.strftime("%Y-%m-%d")

    entry = f"### {ts} {label}\n\n{text.strip()}\n"
    ok = diary.append_entry(entry, date_str)

    if ok:
        preview = text.strip()[:60]
        return f"{label}已写入: {preview}{'...' if len(text.strip()) > 60 else ''}"
    return f"{label}写入失败"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="内心叙事写入器")
    parser.add_argument("text", nargs="*", help="叙事文本（支持多词，自动拼接）")
    parser.add_argument("--label", default="调教记录",
                        choices=["调教记录", "羞耻笔记"],
                        help="日记条目标签（默认：调教记录）")
    parser.add_argument("--stdin", action="store_true",
                        help="从 stdin 读取文本（优先于位置参数）")
    args = parser.parse_args()

    if args.stdin:
        text = sys.stdin.read().strip()
    elif args.text:
        text = " ".join(args.text)
    else:
        print("usage: python emergence.py [--label 羞耻笔记] <text>")
        sys.exit(1)

    if text:
        print(write(text, label=args.label))
    else:
        print("usage: python emergence.py [--label 羞耻笔记] <text>")
        sys.exit(1)
