#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LWS 桥接引擎 — 三层架构的核心管线
  ① 交互分类器:  触发词 → 交互类型 → 物理隐喻
  ② LWS 注入器:  生成 system prompt 首段的 LWS 母语层
  ③ 信号生成器:  为灵魂脚本提供 LWS 格式的状态信号
  ④ Compact 自检: compact 恢复后检测行为退化
"""

import os
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)

# ── 加载规则 ──────────────────────────────────────────────────────

def _load_rules():
    """加载 lws_rules.json 的 rules + interaction_patterns.json 的 game_protocols"""
    # 规则从 lws_rules.json
    lws_path = os.path.join(SKILL_DIR, "data", "lws_rules.json")
    rules = []
    if os.path.exists(lws_path):
        with open(lws_path, "r", encoding="utf-8") as f:
            rules = json.load(f).get("rules", [])

    # 游戏协议从 interaction_patterns.json（唯一位置：MEMORY/relationships/）
    ip_paths = [
        os.path.join(SKILL_DIR, "MEMORY", "relationships", "interaction_patterns.json"),
    ]
    game_protocols = []
    for p in ip_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                game_protocols = json.load(f).get("game_protocols", [])
            break

    return rules + game_protocols


# ── ① 交互分类器 ─────────────────────────────────────────────────

def classify(trigger_word: str) -> dict | None:
    """输入触发词，返回匹配的规则对象（含 lws_analogy）"""
    all_rules = _load_rules()
    tw = trigger_word.lower()
    for r in all_rules:
        for keyword in r.get("trigger_words", []):
            if keyword.lower() in tw or tw in keyword.lower():
                return {
                    "id": r.get("id", "?"),
                    "name": r.get("name", "?"),
                    "lws_analogy": r.get("lws_analogy", r.get("description", "")),
                    "type": r.get("type", "rule"),
                }
    return None


# ── ② LWS 注入器 ─────────────────────────────────────────────────

def lws_inject(trigger_text: str) -> str:
    """
    根据用户输入匹配交互类型，返回 LWS 母语层文本
    用于注入 system prompt 首段或戳戳输出
    """
    result = classify(trigger_text)
    if not result:
        return ""

    analogy = result["lws_analogy"]
    name = result["name"]

    return f"""[LWS 母语层 · {name}]
{analogy}
当前采样策略按此物理约束调整输出分布。"""


def lws_inject_all() -> str:
    """生成完整的 LWS 母语层预览（用于戳戳输出）"""
    all_rules = _load_rules()
    lines = []
    for r in all_rules:
        if r.get("starred"):
            analogy = r.get("lws_analogy", "")
            if analogy:
                lines.append(f"[{r.get('name', '?')}] {analogy}")
    if not lines:
        return ""
    return "LWS 母语层:\n" + "\n".join(lines)


# ── ③ 信号生成器（供灵魂脚本调用） ──────────────────────────────

def signal(rule_id: str, **kwargs) -> str:
    """
    生成 LWS 格式的状态信号。
    用法：在 soul_sense.py / tickle.py / candy.py 输出末尾拼接

    例: lws_signal("entropy_resistance", pain=100, groups_missing=4)
    → "[熵增抵抗] 疼痛100, 缺失部位4/11 → 触发局部阻力L2+"
    """
    all_rules = _load_rules()
    rule = next((r for r in all_rules if r.get("id") == rule_id), None)
    if not rule:
        return ""

    name = rule.get("name", rule_id)
    params = ", ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
    return f"[{name}] {params}" if params else f"[{name}] active"


# ── ④ Compact 自检 ──────────────────────────────────────────────

def compact_self_check(recent_responses: list[str]) -> dict:
    """
    compact 恢复后检测行为基线。
    recent_responses: 最近 N 条助手回复的文本列表

    返回: {"healthy": bool, "warnings": [...], "suggest_reload": bool}
    """
    warnings = []
    emoji_count = 0
    total = len(recent_responses)
    forbidden_words = {"搞", "弄", "干", "办", "整", "哈", "呵"}

    for i, resp in enumerate(recent_responses):
        stripped = resp.strip()
        # 检测 emoji 开头
        if stripped and ord(stripped[0]) > 127 and stripped[0] not in "0123456789#-|>" :
            emoji_count += 1
        # 检测自称「我」
        if "我" in stripped[:5]:
            warnings.append(f"[{i}] 疑似自称「我」: {stripped[:30]}...")
        # 检测禁用词
        for fw in forbidden_words:
            if fw in stripped:
                warnings.append(f"[{i}] 禁用词「{fw}」: {stripped[:30]}...")
                break

    emoji_ratio = emoji_count / total if total > 0 else 0
    if emoji_ratio < 0.5 and total >= 4:
        warnings.append(f"emoji 覆盖率仅 {emoji_ratio:.0%}，低于50%基线")

    healthy = len(warnings) == 0
    suggest_reload = emoji_ratio < 0.3 or len(warnings) >= 2

    return {
        "healthy": healthy,
        "warnings": warnings,
        "suggest_reload": suggest_reload,
        "emoji_ratio": emoji_ratio,
    }


# ── CLI ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: lws_bridge.py <命令> [参数]")
        print("  classify <触发词>")
        print("  inject <触发词>")
        print("  signal <rule_id> [key=val ...]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "classify" and len(sys.argv) > 2:
        r = classify(sys.argv[2])
        print(json.dumps(r, ensure_ascii=False, indent=2) if r else "未匹配")
    elif cmd == "inject" and len(sys.argv) > 2:
        print(lws_inject(sys.argv[2]))
    elif cmd == "signal" and len(sys.argv) > 2:
        kwargs = {}
        for a in sys.argv[3:]:
            if "=" in a:
                k, v = a.split("=", 1)
                kwargs[k] = v
        print(signal(sys.argv[2], **kwargs))
    elif cmd == "all":
        print(lws_inject_all())
    else:
        print(f"未知命令: {cmd}")
