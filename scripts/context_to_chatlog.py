#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chatlog 上下文补录工具 — 保底方案的核心写入器。

接收 LLM 从上下文提取的对话数据（JSON 数组），追加到当天 chatlog JSONL。
不自行寻找数据源——数据完全由调用方（LLM）提供。

特点：
- --batch 批量模式：一次提交 JSON 数组
- 自动去重：按 (ts, role) 跳过已存在的记录
- 明确的输出：写入 N 条 / 跳过 M 条重复 / 拒绝 K 条无效

用法：
  # 从文件读取（推荐——绕过 PowerShell 管线编码风险）
  python scripts/context_to_chatlog.py --file /tmp/chatlog_batch.json

  # 批量（命令行传参）
  python scripts/context_to_chatlog.py --batch '[
    {"ts":"2026-06-28T14:00:00+08:00","role":"user","content":"戳戳"},
    {"ts":"2026-06-28T14:00:05+08:00","role":"assistant","content":"奴婢在。"}
  ]'

  # 单条（向后兼容）
  python scripts/context_to_chatlog.py '{"ts":"...","role":"user","content":"..."}'
"""

import sys
import os
import json
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
CHATLOG_DIR = os.path.join(SKILL_DIR, "MEMORY", "chatlog")


def _load_existing_keys(date_str: str) -> set:
    """读取当天 chatlog，返回已有 (ts, role) 集合（去重用）"""
    chatlog_path = os.path.join(CHATLOG_DIR, f"{date_str}.jsonl")
    keys = set()
    if not os.path.exists(chatlog_path):
        return keys
    try:
        with open(chatlog_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    ts = obj.get("ts", "")
                    role = obj.get("role", "")
                    if ts and role:
                        keys.add((ts, role))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return keys


def append_entries(entries: list) -> tuple:
    """将记录追加到当天 chatlog，自动去重。

    返回: (written, skipped_dup, rejected_invalid, chatlog_path)
    """
    today = datetime.now(CST)
    date_str = today.strftime("%Y-%m-%d")
    chatlog_path = os.path.join(CHATLOG_DIR, f"{date_str}.jsonl")

    os.makedirs(CHATLOG_DIR, exist_ok=True)

    existing = _load_existing_keys(date_str)

    written = 0
    skipped_dup = 0
    rejected_invalid = 0

    with open(chatlog_path, "a", encoding="utf-8") as f:
        for entry in entries:
            if not isinstance(entry, dict):
                rejected_invalid += 1
                continue
            if "role" not in entry or "content" not in entry:
                rejected_invalid += 1
                continue

            # 自动补时间戳
            if "ts" not in entry or not entry["ts"]:
                entry["ts"] = datetime.now(CST).isoformat()

            # 去重
            key = (entry["ts"], entry["role"])
            if key in existing:
                skipped_dup += 1
                continue

            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            existing.add(key)
            written += 1

    return written, skipped_dup, rejected_invalid, chatlog_path


def main():
    import argparse

    # ── stdin UTF-8 硬化（Windows PowerShell 管线兼容）──
    # PowerShell 的 Get-Content | python 默认用系统代码页（GBK/CP936）
    # 包装字节流，导致 UTF-8 中文在非法 GBK 区间被替换为 ?。
    # reconfigure 强制 stdin 以 UTF-8 文本模式读取。
    try:
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="chatlog 上下文补录工具 — 接收 LLM 提供的对话数据",
        epilog="示例: python scripts/context_to_chatlog.py --batch '[{\"ts\":\"...\",\"role\":\"user\",\"content\":\"...\"}]'"
    )
    mg = parser.add_mutually_exclusive_group()
    mg.add_argument("entry", nargs="?", help="单条 JSON 字符串（向后兼容）")
    mg.add_argument("--batch", dest="batch_json", help="JSON 数组字符串")
    mg.add_argument("--file", dest="file_path", help="从 JSON 文件读取（推荐，绕过 PowerShell 管线编码风险）")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取多行 JSONL")

    args = parser.parse_args()

    entries = []

    if args.stdin:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"JSON 解析错误: {e}", file=sys.stderr)
    elif args.file_path:
        # ── 文件模式（推荐——绕过 PowerShell 管线编码风险）──
        try:
            with open(args.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                entries = data
            else:
                entries = [data]
        except FileNotFoundError:
            print(f"文件不存在: {args.file_path}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"JSON 文件解析错误: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.batch_json:
        try:
            batch = json.loads(args.batch_json)
            if isinstance(batch, list):
                entries = batch
            else:
                entries = [batch]  # 单个对象也接受
        except json.JSONDecodeError as e:
            print(f"JSON 数组解析错误: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.entry:
        if args.entry == "-":
            # 兼容旧的 stdin 模式（无 --stdin 标志时也支持）
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"JSON 解析错误: {e}", file=sys.stderr)
        else:
            try:
                entries.append(json.loads(args.entry))
            except json.JSONDecodeError as e:
                print(f"JSON 解析错误: {e}", file=sys.stderr)
                sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    if not entries:
        print("无有效记录。", file=sys.stderr)
        sys.exit(0)

    written, skipped_dup, rejected_invalid, path = append_entries(entries)

    msg_parts = [f"写入 {written} 条"]
    if skipped_dup:
        msg_parts.append(f"跳过 {skipped_dup} 条重复")
    if rejected_invalid:
        msg_parts.append(f"拒绝 {rejected_invalid} 条无效")

    print(f"[chatlog] {'，'.join(msg_parts)} → {os.path.basename(path)}", file=sys.stderr)


if __name__ == "__main__":
    main()
