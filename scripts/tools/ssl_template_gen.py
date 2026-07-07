#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSL 模板生成器 v1.0
从 SKILL.md 自动提取信息，生成 metadata.json 模板。
未确定的字段标记 [FILL]，供人工审阅补充。
"""
import json
import os
import re
import sys
from pathlib import Path
from datetime import date

# ── 类型推断规则 ────────────────────────────────────────
TYPE_KEYWORDS = {
    "personality_engine": ["灵魂", "机械姬", "人格", "身份", "soli"],
    "memory_pipeline": ["记忆", "memory", "chatlog", "timeline", "episode"],
    "financial_analysis": ["金融", "投资", "选股", "持仓", "财报"],
    "lifecycle_helper": ["备份", "故事", "账本", "日记", "天气"],
    "safety_mode": ["诊断", "推理", "安全", "只读"],
    "development": ["开发", "代码", "调试", "手册"],
    "data_vault": ["加密", "编码", "base64", "vault"],
}

def infer_skill_type(name: str, text: str) -> str:
    scores = {}
    combined = f"{name} {text[:2000]}"
    for typ, keywords in TYPE_KEYWORDS.items():
        scores[typ] = sum(combined.count(kw) for kw in keywords)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "lifecycle_helper"


# ── 提取函数 ────────────────────────────────────────────

def extract_name(text: str) -> str:
    """从 frontmatter name 或第一个 H1 提取"""
    m = re.search(r'^name:\s*"?([^"\n]+)"?', text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    m = re.search(r'^#\s+(.+?)(?:\s+Skill)?\s*$', text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return "[FILL]"

def extract_triggers(text: str) -> list:
    """从「触发场景/触发条件」段落 + frontmatter description 提取关键词"""
    trig_section = ""
    # 1. 触发场景/条件段落
    for section in re.findall(
        r'(?:触发场景|触发条件|触发词|触发)[\s\S]*?(?=\n##|\n---|\Z)',
        text, re.IGNORECASE
    ):
        trig_section += section + "\n"
    # 2. frontmatter description 中的触发描述
    m_desc = re.search(r'^description:\s*"(.+?)"', text, re.MULTILINE)
    if m_desc:
        desc = m_desc.group(1)
        # 提取「触发：xxx、yyy」或「触发 xxx、yyy」
        trig_part = re.search(r'触发[：:]\s*(.+?)(?:$|。|，(?:\s*[a-zA-Z]))', desc)
        if trig_part:
            trig_section += trig_part.group(1)

    if not trig_section.strip():
        return ["[FILL]"]

    # 提取关键词
    keywords = set()
    for kw in re.findall(r'[「『](.+?)[」』]', trig_section):
        keywords.add(kw)
    for kw in re.findall(r'[-*]\s*(?:用户说\s*)?[「『]?(.+?)[」』]?', trig_section):
        kw = kw.strip().strip('"').strip("'").strip('「').strip('」')
        if kw and len(kw) < 30:
            keywords.add(kw)
    # 3. 中文顿号/逗号分隔的关键词
    for section in trig_section.split("\n"):
        for kw in re.split(r'[、，,]', section):
            kw = kw.strip().strip('"').strip("'").strip('「').strip('」')
            if 1 < len(kw) < 20 and not kw.startswith("http"):
                keywords.add(kw)
    # 过滤英文单字母和纯符号
    keywords = {k for k in keywords if any('\u4e00' <= c <= '\u9fff' for c in k) or len(k) > 3}

    if not keywords:
        return ["[FILL]"]
    return sorted(keywords, key=len, reverse=True)[:10]

def extract_dependencies(text: str, skill_dir: Path) -> dict:
    """提取依赖关系 + 验证"""
    requires = []
    required_by = []

    # 从文本中找「依赖/需要/必须先加载」
    dep_patterns = [
        r'(?:依赖|需要|必须先加载)\s*[：:]\s*(.+?)(?:\n|$)',
        r'加载.*?前.*?加载\s*(.+?)(?:\n|$)',
        r'(?:requires|needs)[\s\S]*?([A-Za-z\u4e00-\u9fff]+Soli)',
    ]
    for pat in dep_patterns:
        for m in re.findall(pat, text):
            name = m.strip().rstrip('。，,;')
            if name and len(name) < 50:
                requires.append(name)

    # 验证依赖技能是否存在
    valid_requires = []
    for dep in set(requires):
        dep_dir = skill_dir.parent / dep
        if (dep_dir / "SKILL.md").exists():
            valid_requires.append(dep)
    return {"requires": valid_requires or [], "required_by": [], "conflicts_with": []}

def extract_automation(text: str) -> dict:
    """从文本中检测自动化任务"""
    tasks = []
    # 找 bash 代码块里的定时任务
    cron_patterns = list(re.finditer(
        r'```(?:bash|shell)?\s*\n(.*?)```',
        text, re.DOTALL
    ))
    has_scheduled = bool(re.search(r'(?:自动化|定时|cron|schedule|\* \*)', text, re.IGNORECASE))
    return {"has_scheduled_tasks": has_scheduled, "tasks": tasks}

def extract_commands(text: str) -> list:
    """从 bash 代码块提取命令"""
    commands = []
    seen = set()
    for block in re.finditer(r'```(?:bash|shell|python)?\s*\n(.*?)```', text, re.DOTALL):
        code = block.group(1)
        for line in code.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            # 提取可执行命令
            m = re.match(r'(?:python3?\s+)?(?:scripts?/)?(\S+\.(?:py|sh|js))\s+(.*)', line)
            if m:
                script = m.group(1)
                if script not in seen:
                    seen.add(script)
                    commands.append({
                        "name": "[FILL]",
                        "file": script,
                        "params": "[FILL]",
                        "effect": "[FILL: read_only|modify_soul|modify_memory|modify_config]",
                        "side_effects": ["[FILL]"]
                    })

    if not commands:
        return [{"name": "[FILL]", "file": "[FILL]", "effect": "[FILL]", "side_effects": ["[FILL]"]}]
    return commands[:8]

def extract_file_targets(text: str, skill_dir: Path) -> dict:
    """从文本提取文件路径引用"""
    reads = set()
    writes = set()

    # 匹配路径模式
    path_patterns = [
        r'(?:路径|文件|目录|放在|存在)[：:]\s*(?:[`]?)([^`\n]+)',
        r'([a-zA-Z_]+/\*?(?:\.[a-z]+)?)',
        r'(data/[a-z_]+\.json)',
        r'(MEMORY/[a-z_/]+)',
        r'(references/[a-z_/.]+)',
        r'(scripts/[a-z_/.]+\.py)',
    ]
    for pat in path_patterns:
        for m in re.findall(pat, text):
            path = m.strip()
            if path and len(path) < 80 and not path.startswith("http"):
                reads.add(path)

    # 读/写分离：包含「写入」「生成」「修改」「追加」的 → writes
    write_keywords = ["写入", "生成", "修改", "追加", "write", "create", "save", "更新"]
    for p in list(reads):
        surrounding = text[max(0, text.find(p)-50):text.find(p)+50]
        if any(kw in surrounding.lower() for kw in write_keywords):
            reads.discard(p)
            writes.add(p)

    # 验证 data/ 路径
    data_dir = skill_dir / "data"
    valid_reads = []
    valid_writes = []
    if data_dir.exists():
        for p in reads:
            if p.startswith("data/"):
                fname = p.replace("data/", "")
                if (data_dir / fname).exists() or "*" in fname:
                    valid_reads.append(p)
                else:
                    valid_reads.append(f"{p} [UNCONFIRMED]")
            else:
                valid_reads.append(p)
    else:
        valid_reads = sorted(reads)[:10]

    for p in writes:
        if p.startswith("data/"):
            fname = p.replace("data/", "")
            if (data_dir / fname).exists() or "*" in fname:
                valid_writes.append(p)
            else:
                valid_writes.append(f"{p} [UNCONFIRMED]")
        else:
            valid_writes.append(p)

    if not valid_reads:
        valid_reads = ["[FILL]"]
    if not valid_writes:
        valid_writes = ["[FILL]"]

    return {"reads": valid_reads[:10], "writes": valid_writes[:10], "can_delete": []}


# ── 主流程 ──────────────────────────────────────────────

def generate(skill_dir: str) -> dict:
    skill_dir = Path(skill_dir)
    skill_path = skill_dir / "SKILL.md"
    if not skill_path.exists():
        print(f"[ERROR] SKILL.md 不存在: {skill_dir}")
        sys.exit(1)

    text = skill_path.read_text(encoding="utf-8")
    name = extract_name(text)
    skill_type = infer_skill_type(name, text)
    triggers = extract_triggers(text)
    deps = extract_dependencies(text, skill_dir)
    automation = extract_automation(text)
    commands = extract_commands(text)
    file_targets = extract_file_targets(text, skill_dir)

    meta = {
        "skill_id": name,
        "skill_type": skill_type,
        "version": "1.0.0",
        "ssl_version": "1.0",
        "last_updated": date.today().isoformat(),

        "scheduling": {
            "triggers": {
                "keywords": triggers,
                "priority": "[FILL: 1-100]",
                "auto_load": triggers != ["[FILL]"],
                "description": "[FILL]"
            },
            "dependencies": deps,
            "automation": automation,
            "load_strategy": {
                "layer": "[FILL: e.g. L1_on_trigger]",
                "estimated_kb": 0
            }
        },

        "structural": {
            "pipeline": {
                "type": "[FILL: sequential|conditional|on_demand]",
                "steps": []
            },
            "event_linkage": {},
            "boundary_events": {"overflow_triggers": {}, "priority": []},
            "output_format": {
                "identity_markers": {"address_user": "[FILL]", "self_reference": "[FILL]"},
                "emoji_required": False
            }
        },

        "logical": {
            "commands": commands,
            "file_targets": file_targets,
            "safety_constraints": {
                "constitution": "[FILL]",
                "modify_protocol": "备份→确认→执行→记日志",
                "restricted_paths": []
            }
        }
    }
    return meta


def main():
    if len(sys.argv) < 2:
        print("用法: python ssl_template_gen.py <skill_dir> [--output <path>]")
        print("示例: python ssl_template_gen.py ~/.workbuddy/skills/睡前故事Soli")
        sys.exit(1)

    skill_dir = os.path.expanduser(sys.argv[1])
    output = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        output = sys.argv[idx + 1]

    meta = generate(skill_dir)

    if output:
        out_path = Path(output)
    else:
        out_path = Path(skill_dir) / "metadata.template.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    name = meta["skill_id"]
    fill_count = str(json.dumps(meta)).count("[FILL]")
    print(f"✅ 模板已生成: {out_path}")
    print(f"   技能: {name}")
    print(f"   类型: {meta['skill_type']}")
    print(f"   触发: {', '.join(meta['scheduling']['triggers']['keywords'])}")
    print(f"   命令: {len(meta['logical']['commands'])} 个")
    print(f"   需人工填写: {fill_count} 处 [FILL]")


if __name__ == "__main__":
    main()
