"""DLC v3.0 Narrative Assembly.

编号 → 查表 → stdout 组装。纯知识库操作，零状态逻辑。

Usage:
    python dlc/narrative/assembly.py --card cards/my-card --ids "action.move.2,threshold.health_low"
"""
from __future__ import annotations

import os, sys, json, argparse
from pathlib import Path
from typing import Any

# Ensure dlc package is importable
_skill_dir = Path(__file__).resolve().parent.parent.parent
if str(_skill_dir) not in sys.path:
    sys.path.insert(0, str(_skill_dir))


class NarrativeAssembly:
    """叙事组装器 — 根据编号查表拼接自然语言 stdout。"""

    def __init__(self, card_path: str):
        self.card_path = os.path.abspath(card_path)
        self._templates: dict[str, dict] = {}
        self._load_templates()

    # ═══════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════

    def assemble(self, narrative_ids: list[str]) -> str:
        """给定叙事编号数组，组装完整 stdout 文本。

        Args:
            narrative_ids: 编号列表，如 ["action.gamble.3", "threshold.pleasure_high"]

        Returns:
            组装后的自然语言文本，LLM 可直接消费。
        """
        parts = []

        for nid in narrative_ids:
            text = self._lookup(nid)
            if text:
                parts.append(text)

        return "\n".join(parts) if parts else ""

    # ═══════════════════════════════════════════════════════════
    # Internal: template lookup
    # ═══════════════════════════════════════════════════════════

    def _load_templates(self):
        """加载 narratives/ 目录下的所有模板文件。"""
        template_dir = os.path.join(self.card_path, "narratives", "templates")
        if not os.path.isdir(template_dir):
            # Fallback: look for templates in card root
            template_dir = os.path.join(self.card_path, "narratives")
            if not os.path.isdir(template_dir):
                # Legacy fallback: check if card has engine/narratives.json
                legacy = os.path.join(self.card_path, "engine", "narratives.json")
                if os.path.isfile(legacy):
                    try:
                        with open(legacy, "r", encoding="utf-8") as f:
                            self._templates["_legacy"] = json.load(f)
                    except Exception:
                        pass
                return

        for root, dirs, files in os.walk(template_dir):
            for fname in files:
                if fname.endswith(".json"):
                    fpath = os.path.join(root, fname)
                    key = os.path.splitext(fname)[0]
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            self._templates[key] = json.load(f)
                    except Exception:
                        pass

    def _lookup(self, narrative_id: str) -> str:
        """查表：编号 → 文本。

        v3.0.2 编号域：
          action.{cmd_id}.{level}         — 动作叙事，如 action.gamble.3
          threshold.{event_id}            — 阈值触发，如 threshold.pleasure_high
          boundary.{event_id}.{variant?}  — 边界事件，如 boundary.ecstasy.v
          emergence.{type}                — 涌现叙事
          system.{subtype}                — 系统事件

        旧格式自动映射（command→action, event→threshold/boundary）。
        """
        parts = narrative_id.split(".")
        domain = parts[0]

        # ── 系统事件 ──
        if domain == "system":
            return self._lookup_system(parts[1]) if len(parts) > 1 else ""

        # ── 动作叙事（v3.0.1+ action. → 复用 _lookup_action）──
        if domain == "action":
            return self._lookup_action(parts[1:])

        # ── 阈值/边界事件（v3.0.1+ threshold./boundary. → 复用 event 查表）──
        if domain in ("threshold", "boundary"):
            return self._lookup_event(parts[1:])

        # ── 旧格式兼容（command./event./emergence.）──
        if domain == "command":
            return self._lookup_action(parts[1:])
        if domain == "event":
            return self._lookup_event(parts[1:])
        if domain == "emergence":
            return self._lookup_emergence(parts[1:])

        # ── 直接键查表（简化卡片）──
        if narrative_id in self._templates:
            tmpl = self._templates[narrative_id]
            if isinstance(tmpl, str):
                return tmpl
            if isinstance(tmpl, dict):
                return tmpl.get("text", tmpl.get("narrative", str(tmpl)))

        return ""

    def _lookup_system(self, subtype: str) -> str:
        """系统事件查表。"""
        system_texts = {
            "status": "(状态快照已返回)",
            "reset": "(状态已重置)",
        }
        return system_texts.get(subtype, "")

    def _lookup_action(self, parts: list[str]) -> str:
        """动作叙事查表。

        编号支持两种格式：
          action.cmd_id.level          — 2段，无 variant（如 action.gamble.3）
          action.cmd_id.variant.level  — 3段，有 variant（如 action.gamble.v.3）

        查找路径：
          1. templates/[cmd_id].json → STIMULATE[level]
          2. _legacy → command_assembly[cmd_id]（管道格式兼容）
        """
        if not parts:
            return ""

        cmd_id = parts[0]

        # 区分 2 段和 3 段格式
        if len(parts) == 2:
            # action.cmd_id.level（无 variant）
            variant = None
            level = parts[1]
        elif len(parts) >= 3:
            # action.cmd_id.variant.level
            variant = parts[1]
            level = parts[2]
        else:
            # action.cmd_id only（如 action.ping）
            variant = None
            level = None

        # ── Path 1: templates/cmd_id.json ──
        cmd_tmpl = self._templates.get(cmd_id)
        if cmd_tmpl and level and level.isdigit():
            idx = int(level)
            stimulate = cmd_tmpl.get("STIMULATE", {})
            if idx in stimulate:
                return stimulate[idx]
            if variant:
                narratives = cmd_tmpl.get("NARRATIVES", {})
                var_narr = narratives.get(variant, {})
                if isinstance(var_narr, dict) and idx in var_narr:
                    return var_narr[idx]
                if isinstance(var_narr, str):
                    return var_narr

        # ── Path 2: Legacy pipeline format ──
        legacy = self._templates.get("_legacy", {})
        if legacy:
            cmd_assembly = legacy.get("command_assembly", {})
            # 先精确匹配，再试 cmd_ 前缀（如 gamble → cmd_gamble）
            cmd_data = cmd_assembly.get(cmd_id)
            if cmd_data is None:
                cmd_data = cmd_assembly.get(f"cmd_{cmd_id}")
            if cmd_data:
                if level:
                    return self._resolve_pipeline(cmd_data, level)
                else:
                    return self._resolve_pipeline_no_level(cmd_data)

        return ""

    def _resolve_pipeline(self, cmd_data, level) -> str:
        """解析管道格式的命令叙事数据。

        支持两种管道格式：
          1. dict with op/target/brackets/texts（新版管道）
          2. dict with text/narrative key（简单格式）
          3. str（纯文本）
        """
        if isinstance(cmd_data, str):
            return cmd_data

        if isinstance(cmd_data, dict):
            # 简单格式：{"text": "...", "narrative": "..."}
            text = cmd_data.get("text") or cmd_data.get("narrative", "")
            if isinstance(text, str) and text:
                return text
            if isinstance(text, list):
                return "\n".join(text[:3])
            return ""

        if isinstance(cmd_data, list):
            # 管道格式：[{"op": "range", "brackets": [...], "texts": [...]}, ...]
            level_int = int(level) if (level and str(level).isdigit()) else None
            texts = []

            for step in cmd_data:
                if not isinstance(step, dict):
                    continue
                op = step.get("op", "")

                if op == "range" and level_int is not None:
                    brackets = step.get("brackets", [])
                    step_texts = step.get("texts", [])
                    for bi, (lo, hi) in enumerate(brackets):
                        if lo <= level_int <= hi and bi < len(step_texts):
                            texts.append(step_texts[bi])

                elif op == "switch":
                    key = step.get("key", "")
                    cases = step.get("cases", {})
                    matched = cases.get(str(level_int)) if level_int is not None else None
                    if matched:
                        texts.append(matched)

                elif op == "cond":
                    # cond op with "if" array (e.g. candy_eat)
                    if level_int is not None:
                        conditions = step.get("if", [])
                        all_true = True
                        for c in conditions:
                            if not isinstance(c, dict):
                                continue
                            # We need state to evaluate conditions like stimulus>=8
                            # For now: always take the bracket-indexed text
                            pass
                        idx = level_int if level_int < len(step.get("texts", [])) else 0
                        all_texts = step.get("texts", [])
                        if all_texts:
                            texts.append(all_texts[idx])

                elif op == "conditional":
                    cond = step.get("condition", {})
                    ch = cond.get("channel", "")
                    lo = cond.get("min", -999)
                    hi = cond.get("max", 999)
                    if level_int is not None and lo <= level_int <= hi:
                        texts.append(step.get("text", ""))

                elif op == "rand":
                    import random as _rand
                    variants = step.get("variants", [])
                    if variants:
                        pick = _rand.choices(variants, weights=[v.get("weight", 1) for v in variants], k=1)[0]
                        texts.append(pick.get("text", ""))

                elif op == "interp":
                    texts.append(step.get("template", ""))

            return "\n".join(texts) if texts else ""

        return ""

    def _resolve_pipeline_no_level(self, cmd_data) -> str:
        """解析管道格式（无 level），返回第一个可用文本作为回退。"""
        if isinstance(cmd_data, str):
            return cmd_data

        if isinstance(cmd_data, dict):
            text = cmd_data.get("text") or cmd_data.get("narrative", "")
            if isinstance(text, str) and text:
                return text
            if isinstance(text, list):
                return "\n".join(text[:3])
            return ""

        if isinstance(cmd_data, list):
            for step in cmd_data:
                if not isinstance(step, dict):
                    continue
                op = step.get("op", "")

                if op == "interp":
                    return step.get("template", "")

                if op == "rand":
                    import random as _rand
                    variants = step.get("variants", [])
                    if variants:
                        pick = _rand.choices(variants, weights=[v.get("weight", 1) for v in variants], k=1)[0]
                        return pick.get("text", "")

                if op == "range":
                    texts_list = step.get("texts", [])
                    if texts_list:
                        return texts_list[0]

                if op == "switch":
                    cases = step.get("cases", {})
                    if cases:
                        return list(cases.values())[0]

                if op == "cond":
                    texts_list = step.get("texts", [])
                    if texts_list:
                        return texts_list[0]

                if op == "conditional":
                    return step.get("text", "")

        return ""

        return ""

    def _lookup_event(self, parts: list[str]) -> str:
        """阈值/边界事件查表。

        查找路径：
          1. templates/events.json → events[event_id]（精确匹配）
          2. _legacy → events[event_id]（精确匹配）
          3. _legacy → prefixed variants（narr_status_warn_{event_id} / narr_{event_id}_*）
        """
        if not parts:
            return ""

        event_id = parts[0]
        variant = parts[1] if len(parts) > 1 else None

        # ── variant 后缀检测（boundary.soul_break_v → event_id=soul_break, variant=v）──
        for suffix in ("_v", "_a", "_u"):
            if variant is None and event_id.endswith(suffix):
                event_id = event_id[: -len(suffix)]
                variant = suffix[1:]
                break

        # ── Path 1: templates/events.json（新格式）──
        events_tmpl = self._templates.get("events", {})
        ev = events_tmpl.get(event_id)
        if ev:
            return self._extract_text_from_event(ev)

        # ── Path 2: _legacy events（精确匹配）──
        legacy = self._templates.get("_legacy", {})
        leg_events = legacy.get("events", {})
        ev = leg_events.get(event_id)
        if ev:
            return self._extract_text_from_event(ev)

        # ── Path 3: legacy prefixed variants ──
        legacy_id = self._map_legacy_event_id(event_id, variant, leg_events)
        if legacy_id:
            ev = leg_events.get(legacy_id)
            if ev:
                return self._extract_text_from_event(ev)

        # ── Path 4: legacy composite（boundary.*.v → multiple narr_*_v_* events）──
        if variant:
            return self._assemble_legacy_boundary(event_id, variant, leg_events)

        return ""

    def _extract_text_from_event(self, ev) -> str:
        """从事件对象中提取文本。"""
        if isinstance(ev, str):
            return ev
        if isinstance(ev, dict):
            texts = ev.get("texts", {})
            return texts.get("intense") or texts.get("peak") or texts.get("medium") or texts.get("mild") or texts.get("text", "")
        return ""

    def _map_legacy_event_id(self, event_id: str, variant, leg_events: dict) -> str | None:
        """将新格式事件 ID 映射到旧格式。

        threshold.pleasure_high → narr_status_warn_pleasure_high
        boundary.ecstasy → narr_ecstasy_v_* (variant needed)
        """
        # threshold.xxx_yyy → narr_status_warn_xxx_yyy
        candidates = [
            f"narr_status_warn_{event_id}",
            f"narr_critical_{event_id}",
            f"narr_{event_id}",
        ]
        for c in candidates:
            if c in leg_events:
                return c
        return None

    def _assemble_legacy_boundary(self, event_id: str, variant: str, leg_events: dict) -> str:
        """组装旧格式的 boundary 事件（多个片段拼接）。"""
        prefix = f"narr_{event_id}_{variant}_"
        parts = []
        for key in sorted(leg_events.keys()):
            if key.startswith(prefix):
                parts.append(self._extract_text_from_event(leg_events[key]))
        return "".join(parts) if parts else ""

    def _lookup_emergence(self, parts: list[str]) -> str:
        """涌现叙事查表。"""
        if not parts:
            return ""

        etype = parts[0]
        emergence_tmpl = self._templates.get("emergence", {})
        return emergence_tmpl.get(etype, "")


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DLC v3.0 叙事组装")
    parser.add_argument("--card", required=True, help="卡片路径")
    parser.add_argument("--ids", required=True, help="叙事编号，逗号分隔")
    args = parser.parse_args()

    ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    assembly = NarrativeAssembly(args.card)
    stdout = assembly.assemble(ids)
    print(stdout)
