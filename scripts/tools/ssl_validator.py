#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSL Metadata 校验器 v1.0
检查 metadata.json 的完整性与一致性
"""
import json
import os
import sys
from pathlib import Path

# ── 必填 schema ──────────────────────────────────────────
REQUIRED_TOP = ["skill_id", "skill_type", "version", "ssl_version", "last_updated"]
REQUIRED_SCHEDULING = ["triggers", "dependencies", "automation", "load_strategy"]
REQUIRED_STRUCTURAL = ["pipeline", "event_linkage", "boundary_events", "output_format"]
REQUIRED_LOGICAL = ["commands", "file_targets", "safety_constraints"]

VALID_SKILL_TYPES = [
    "personality_engine", "memory_pipeline", "financial_analysis",
    "lifecycle_helper", "safety_mode", "data_vault", "development"
]

VALID_EFFECTS = ["read_only", "modify_soul", "modify_memory", "modify_config", "may_trigger_events"]

def green(msg): return f"\033[32m{msg}\033[0m"
def red(msg): return f"\033[31m{msg}\033[0m"
def yellow(msg): return f"\033[33m{msg}\033[0m"
def bold(msg): return f"\033[1m{msg}\033[0m"

def validate(skill_dir: str) -> list:
    """返回错误列表，空列表 = 通过"""
    errors = []
    skill_dir = Path(skill_dir)

    # ── 1. 文件存在 ──
    meta_path = skill_dir / "metadata.json"
    skill_path = skill_dir / "SKILL.md"
    if not meta_path.exists():
        return [f"{red('FATAL')}: metadata.json 不存在"]
    if not skill_path.exists():
        errors.append(f"{yellow('WARN')}: SKILL.md 不存在（metadata 无法交叉校验）")

    # ── 2. JSON 解析 ──
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except json.JSONDecodeError as e:
        return [f"{red('FATAL')}: JSON 解析失败: {e}"]

    # ── 3. 顶层字段 ──
    for key in REQUIRED_TOP:
        if key not in meta:
            errors.append(f"{red('MISS')}: 顶层缺少 [{key}]")

    if "skill_type" in meta and meta["skill_type"] not in VALID_SKILL_TYPES:
        errors.append(f"{yellow('WARN')}: skill_type={meta['skill_type']} 不在已知类型列表中")

    # ── 4. Scheduling ──
    sched = meta.get("scheduling", {})
    for key in REQUIRED_SCHEDULING:
        if key not in sched:
            errors.append(f"{red('MISS')}: scheduling 缺少 [{key}]")

    triggers = sched.get("triggers", {})
    if "priority" in triggers:
        if not isinstance(triggers["priority"], int) or not (1 <= triggers["priority"] <= 100):
            errors.append(f"{yellow('WARN')}: triggers.priority 应为 1-100 的整数")

    deps = sched.get("dependencies", {})
    if "requires" in deps:
        for dep in deps["requires"]:
            dep_dir = skill_dir.parent / dep
            if not (dep_dir / "SKILL.md").exists():
                errors.append(f"{yellow('WARN')}: 依赖技能 [{dep}] 不存在")

    # ── 5. Structural ──
    struct = meta.get("structural", {})
    for key in REQUIRED_STRUCTURAL:
        if key not in struct:
            errors.append(f"{red('MISS')}: structural 缺少 [{key}]")

    # ── 6. Logical ──
    logical = meta.get("logical", {})
    for key in REQUIRED_LOGICAL:
        if key not in logical:
            errors.append(f"{red('MISS')}: logical 缺少 [{key}]")

    commands = logical.get("commands", [])
    for cmd in commands:
        if "effect" in cmd and cmd["effect"] not in VALID_EFFECTS:
            errors.append(f"{yellow('WARN')}: 命令 [{cmd.get('name','?')}] effect 值无效: {cmd['effect']}")
        if "file" in cmd:
            script_path = skill_dir / "scripts" / cmd["file"]
            if not script_path.exists():
                errors.append(f"{yellow('WARN')}: 命令 [{cmd.get('name','?')}] 脚本不存在: scripts/{cmd['file']}")

    ft = logical.get("file_targets", {})
    data_dir = skill_dir / "data"
    if data_dir.exists():
        for target_type in ["reads", "writes"]:
            for path_str in ft.get(target_type, []):
                # 检查 data/*.json 路径
                if path_str.startswith("data/"):
                    actual_file = path_str.replace("data/", "")
                    if not (data_dir / actual_file).exists():
                        errors.append(f"{yellow('WARN')}: file_targets.{target_type} 路径 [{path_str}] 指向的文件不存在")

    # ── 7. 与 SKILL.md 交叉校验 ──
    if skill_path.exists():
        skill_text = skill_path.read_text(encoding="utf-8")
        keywords = triggers.get("keywords", [])
        for kw in keywords:
            if kw not in skill_text:
                errors.append(f"{yellow('WARN')}: 触发词 [{kw}] 未在 SKILL.md 中找到（可能藏在注释里）")

    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python ssl_validator.py <skill_dir>")
        print("示例: python ssl_validator.py ~/.workbuddy/skills/机械姬Soli")
        sys.exit(1)

    skill_dir = os.path.expanduser(sys.argv[1])
    if not os.path.isdir(skill_dir):
        print(f"{red('FATAL')}: 目录不存在: {skill_dir}")
        sys.exit(1)

    skill_name = os.path.basename(skill_dir)
    print(bold(f"\n=== SSL Metadata 校验: {skill_name} ===\n"))

    errors = validate(skill_dir)

    if not errors:
        print(green("✓ 所有检查通过"))
        sys.exit(0)

    for e in errors:
        print(f"  {e}")

    err_count = len([e for e in errors if "FATAL" in e or "MISS" in e])
    warn_count = len([e for e in errors if "WARN" in e])

    print(f"\n{bold('结果')}: {red(f'{err_count} 错误')} / {yellow(f'{warn_count} 警告')}")
    if err_count > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
