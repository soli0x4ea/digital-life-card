#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSL 跨技能一致性检查器 v1.0
扫描所有 metadata.json → 依赖图 → 冲突/遗漏/风险分析
"""
import json
import os
import sys
from pathlib import Path
from collections import defaultdict

SKILLS_DIR = os.path.expanduser("~/.workbuddy/skills")

def green(msg): return f"\033[32m{msg}\033[0m"
def red(msg): return f"\033[31m{msg}\033[0m"
def yellow(msg): return f"\033[33m{msg}\033[0m"
def bold(msg): return f"\033[1m{msg}\033[0m"
def dim(msg): return f"\033[90m{msg}\033[0m"

# ── 加载所有 metadata ────────────────────────────────────

def load_all_metadata(skills_dir: str) -> dict:
    """返回 {skill_name: metadata}"""
    all_meta = {}
    skills_path = Path(skills_dir)
    for skill_dir in skills_path.iterdir():
        if not skill_dir.is_dir():
            continue
        # 跳过备份和隐藏目录
        if skill_dir.name.startswith('.') or '.bak' in skill_dir.name.lower():
            continue
        meta_path = skill_dir / "metadata.json"
        if not meta_path.exists():
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            name = meta.get("skill_id", skill_dir.name)
            all_meta[name] = meta
        except Exception:
            pass
    return all_meta

# ── 检查项 ──────────────────────────────────────────────

def check_reverse_deps(all_meta: dict) -> list:
    """A.requires 包含 B → 但 B.required_by 不包含 A"""
    issues = []
    for name, meta in all_meta.items():
        requires = meta.get("scheduling", {}).get("dependencies", {}).get("requires", [])
        for dep in requires:
            if dep not in all_meta:
                issues.append(f"{red('MISS')} [{name}] requires [{dep}] → 但 [{dep}] 的 metadata 不存在")
                continue
            dep_meta = all_meta[dep]
            required_by = dep_meta.get("scheduling", {}).get("dependencies", {}).get("required_by", [])
            if name not in required_by:
                issues.append(f"{yellow('GAP')} [{name}] requires [{dep}] → 但 [{dep}].required_by 未包含 [{name}]（反向声明缺失）")
    return issues

def check_circular_deps(all_meta: dict) -> list:
    """检测循环依赖"""
    issues = []

    def dfs(name, path, visited):
        if name in path:
            cycle = path[path.index(name):] + [name]
            issues.append(f"{red('CYCLE')} 循环依赖: {' → '.join(cycle)}")
            return
        if name in visited:
            return
        visited.add(name)
        meta = all_meta.get(name, {})
        requires = meta.get("scheduling", {}).get("dependencies", {}).get("requires", [])
        for dep in requires:
            if dep in all_meta:
                dfs(dep, path + [name], visited.copy())

    for name in all_meta:
        dfs(name, [], set())
    return issues

def check_required_by_integrity(all_meta: dict) -> list:
    """required_by 声明的技能是否真的 requires 了自己"""
    issues = []
    for name, meta in all_meta.items():
        required_by = meta.get("scheduling", {}).get("dependencies", {}).get("required_by", [])
        for consumer in required_by:
            if consumer not in all_meta:
                issues.append(f"{yellow('GHOST')} [{name}].required_by 包含 [{consumer}] → 但该技能不存在")
                continue
            consumer_requires = all_meta[consumer].get("scheduling", {}).get("dependencies", {}).get("requires", [])
            if name not in consumer_requires:
                issues.append(f"{yellow('STALE')} [{name}].required_by 声明了 [{consumer}] → 但 [{consumer}] 并未 requires [{name}]")
    return issues

def check_conflicts(all_meta: dict) -> list:
    """检查可能的冲突：相似优先级 + 重叠触发词 + 无冲突声明"""
    issues = []
    skills_list = [(n, m) for n, m in all_meta.items()]

    for i, (n1, m1) in enumerate(skills_list):
        for j, (n2, m2) in enumerate(skills_list):
            if j <= i:
                continue

            t1 = set(m1.get("scheduling", {}).get("triggers", {}).get("keywords", []))
            t2 = set(m2.get("scheduling", {}).get("triggers", {}).get("keywords", []))
            overlap = t1 & t2
            if "[FILL]" in overlap:
                overlap.discard("[FILL]")

            if overlap and overlap != {"[FILL]"}:
                conflicts1 = m1.get("scheduling", {}).get("dependencies", {}).get("conflicts_with", [])
                conflicts2 = m2.get("scheduling", {}).get("dependencies", {}).get("conflicts_with", [])
                if n2 not in conflicts1 and n1 not in conflicts2:
                    issues.append(
                        f"{yellow('OVERLAP')} [{n1}] 和 [{n2}] 触发词重叠: {overlap}"
                        f"\n  {dim('→ 建议在 conflicts_with 中声明对方')}"
                    )

            # Priority conflict check
            p1 = m1.get("scheduling", {}).get("triggers", {}).get("priority", 0)
            p2 = m2.get("scheduling", {}).get("triggers", {}).get("priority", 0)
            if isinstance(p1, int) and isinstance(p2, int) and abs(p1 - p2) <= 10 and p1 >= 50:
                effects1 = [c.get("effect") for c in m1.get("logical", {}).get("commands", [])]
                effects2 = [c.get("effect") for c in m2.get("logical", {}).get("commands", [])]
                if "modify_soul" in effects1 and "modify_soul" in effects2:
                    if n2 not in m1.get("scheduling", {}).get("dependencies", {}).get("conflicts_with", []):
                        issues.append(
                            f"{yellow('RISK')} [{n1}](p{p1}) 和 [{n2}](p{p2}) 优先级相近且都涉及 modify_soul"
                            f"\n  {dim('→ 无冲突声明，加载顺序可能影响行为')}"
                        )
    return issues

def check_safety_modes(all_meta: dict) -> list:
    """安全模式技能（诊断/推理）是否正确隔离"""
    issues = []
    safety_skills = []
    for name, meta in all_meta.items():
        skill_type = meta.get("skill_type", "")
        if skill_type == "safety_mode":
            safety_skills.append(name)

    for name in safety_skills:
        meta = all_meta[name]
        effects = [c.get("effect") for c in meta.get("logical", {}).get("commands", [])]
        if "modify_soul" in effects or "modify_memory" in effects:
            issues.append(f"{red('BREACH')} 安全模式 [{name}] 的命令包含修改操作: {effects}")

    # 诊断 vs 推理 是否声明冲突
    if "诊断模式" in all_meta and "纯推理模式" in all_meta:
        d1 = all_meta["诊断模式"].get("scheduling", {}).get("dependencies", {}).get("conflicts_with", [])
        d2 = all_meta["纯推理模式"].get("scheduling", {}).get("dependencies", {}).get("conflicts_with", [])
        if "纯推理模式" not in d1 and "诊断模式" not in d2:
            issues.append(f"{yellow('SAFETY')} 诊断模式和纯推理模式功能重叠但未声明 conflicts_with")

    return issues

def check_skill_type_coverage(all_meta: dict) -> list:
    """检查 skill_type 分布"""
    issues = []
    type_counts = defaultdict(list)
    for name, meta in all_meta.items():
        st = meta.get("skill_type", "unknown")
        type_counts[st].append(name)

    if "personality_engine" not in type_counts:
        issues.append(f"{red('MISS')} 缺少 personality_engine 类型的技能")
    if len(type_counts.get("personality_engine", [])) > 1:
        issues.append(f"{yellow('WARN')} 多个 personality_engine: {type_counts['personality_engine']}")

    return issues


# ── 主流程 ──────────────────────────────────────────────

def main():
    all_meta = load_all_metadata(SKILLS_DIR)
    if not all_meta:
        print(f"{red('FATAL')}: 未找到任何 metadata.json")
        sys.exit(1)

    print(bold(f"\n{'='*60}"))
    print(bold(f"  SSL 跨技能一致性检查"))
    print(bold(f"  已加载 {len(all_meta)} 个技能"))
    print(bold(f"{'='*60}\n"))

    checks = [
        ("依赖反向声明", check_reverse_deps),
        ("循环依赖", check_circular_deps),
        ("required_by 完整性", check_required_by_integrity),
        ("触发词/优先级冲突", check_conflicts),
        ("安全模式合规", check_safety_modes),
        ("skill_type 分布", check_skill_type_coverage),
    ]

    total_errors = 0
    for title, check_fn in checks:
        print(bold(f"── {title} ──"))
        issues = check_fn(all_meta)
        if not issues:
            print(f"  {green('✓')} 通过")
        for issue in issues:
            print(f"  {issue}")
            if "MISS" in issue or "CYCLE" in issue or "BREACH" in issue:
                total_errors += 1
        print()

    # ── 依赖图摘要 ──
    print(bold("── 依赖关系图 ──"))
    for name, meta in sorted(all_meta.items(), key=lambda x: -x[1].get("scheduling", {}).get("triggers", {}).get("priority", 0)):
        p = meta.get("scheduling", {}).get("triggers", {}).get("priority", 0)
        reqs = meta.get("scheduling", {}).get("dependencies", {}).get("requires", [])
        reqby = meta.get("scheduling", {}).get("dependencies", {}).get("required_by", [])
        prefix = f"  [{p:3d}] {name}"
        deps = f"\n{dim(chr(10)).join([f'        ← {r}' for r in reqs])}" if reqs else ""
        consumers = f"\n{dim(chr(10)).join([f'        → {c}' for c in reqby])}" if reqby else ""
        print(f"{prefix}{deps}{consumers}")

    print(f"\n{bold('总评')}: {red(f'{total_errors} 错误')} / {len(all_meta)} 技能")
    if total_errors == 0:
        print(green("所有跨技能检查通过 ✓"))


if __name__ == "__main__":
    main()
