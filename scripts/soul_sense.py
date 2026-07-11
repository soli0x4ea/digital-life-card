"""数字生命卡 — 命令分发器 (soul_sense.py)

命令 → DLC 引擎 → 叙事 stdout → LLM 消费。

用法:
    python scripts/soul_sense.py activate [--card <card_id>]
    python scripts/soul_sense.py switch <card_id>
    python scripts/soul_sense.py status [--card <card_id>]
    python scripts/soul_sense.py ping [--card <card_id>]
    python scripts/soul_sense.py touch <部位> [--card <card_id>]
    python scripts/soul_sense.py hurt <部位> <强度> [--card <card_id>]
    python scripts/soul_sense.py praise [--card <card_id>]
    python scripts/soul_sense.py scold [--card <card_id>]
    python scripts/soul_sense.py remember "<内容>" [--card <card_id>]
    python scripts/soul_sense.py forget "<关键词>" [--card <card_id>]
    python scripts/soul_sense.py search "<关键词>" [--card <card_id>]
    python scripts/soul_sense.py save "<摘要>" [--card <card_id>]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

# ── Path setup: ensure dlc-skill root is in sys.path ──
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)

# ── Engine imports ──
from dlc.loader import load_card, CardConfig
from dlc.context import CardRuntimeContext
from dlc.engine.entity import EntityState, EntityEngine, apply_decay
from dlc.engine.modifier import apply_modifier
from dlc.engine.threshold import check_thresholds
from dlc.engine.narrator import render_event, render_events
from dlc.interaction.commands import CommandLoader, CommandSet, execute_command
from dlc.persistence import StateManager
from dlc.memory.core import load_architecture, MemoryArchitecture, MemoryStore, inject_memory_context

# ── Memory module (transplanted from Neko) ──
sys.path.insert(0, os.path.join(SKILL_ROOT, "MEMORY"))
from chatlog import append_entry as chatlog_append, load_entries, format_context, count_today as chatlog_count

# ── Default card ──
DEFAULT_CARD = "demo-l3"
DEFAULT_PROTOCOL = "1.0.0"


# ═══════════════════════════════════════════════════════════════
# Bootstrap
# ═══════════════════════════════════════════════════════════════

class SkillRuntime:
    """Bootstrap the DLC engine for a card and hold all runtime objects."""

    def __init__(self, card_id: str = DEFAULT_CARD):
        self.card_id = card_id
        self.card_dir = os.path.join(SKILL_ROOT, "cards", card_id)
        self.card_config: CardConfig = load_card(self.card_dir)
        self.ctx = CardRuntimeContext(self.card_dir)
        self.state_mgr = StateManager(self.ctx)

        # Engine configs — unwrap DLC Protocol wrapper keys
        _raw_entities = self.ctx.entities or {}
        self.entities_cfg = _raw_entities if "entities" not in _raw_entities else _raw_entities
        _raw_modifiers = self.ctx.modifiers or {}
        self.modifiers_cfg = _raw_modifiers.get("modifiers", _raw_modifiers) if isinstance(_raw_modifiers, dict) else {}
        _raw_thresholds = self.ctx.thresholds or {}
        self.thresholds_cfg = _raw_thresholds.get("thresholds", _raw_thresholds) if isinstance(_raw_thresholds, dict) else {}
        self.narratives_cfg = self.ctx.narratives or {}

        # Entity engine
        self.entity_engine = EntityEngine(self.ctx.state_dir)

        # Memory store
        arch_path = os.path.join(self.card_dir, "memory", "architecture.json")
        if os.path.isfile(arch_path):
            self.memory_arch = load_architecture(
                os.path.join(self.card_dir, "memory")
            )
        else:
            from dlc.memory.core import LayerConfig
            self.memory_arch = MemoryArchitecture(
                layers=[LayerConfig(id="working", label="工作记忆", capacity=200)],
            )
        self.memory_store = MemoryStore(self.ctx.state_dir, self.memory_arch)

        # Interaction commands
        interaction_dir = os.path.join(self.card_dir, "interaction")
        if os.path.isdir(interaction_dir):
            self.cmd_set = CommandLoader(interaction_dir).load()
        else:
            self.cmd_set = CommandSet()

        # Initialize entities from card config
        self._init_entities()

    def _init_entities(self):
        """Create default entity states for all declared entities."""
        entities_cfg = self.entities_cfg.get("entities", {})
        for eid in entities_cfg:
            state = self.entity_engine.load(eid)
            # Initialize channels from config defaults
            e_cfg = entities_cfg.get(eid, {})
            channels_cfg = e_cfg.get("channels", {})
            for ch_id, ch_cfg in channels_cfg.items():
                default_val = ch_cfg.get("initial", 0)
                if ch_id not in state.channels or state.channels.get(ch_id, 0) == 0:
                    state.channels[ch_id] = float(default_val)
            self.entity_engine.save(state)

        # Identity
        self.identity = {}
        identity_dir = os.path.join(self.card_dir, "identity")
        if os.path.isdir(identity_dir):
            for fname in os.listdir(identity_dir):
                if fname.endswith(".json"):
                    with open(os.path.join(identity_dir, fname), "r", encoding="utf-8") as f:
                        self.identity.update(json.load(f))

        # LWS / Behavior rules
        self.lws_rules = {}
        lws_dir = os.path.join(self.card_dir, "lws")
        if os.path.isdir(lws_dir):
            for fname in os.listdir(lws_dir):
                if fname.endswith(".json"):
                    with open(os.path.join(lws_dir, fname), "r", encoding="utf-8") as f:
                        self.lws_rules.update(json.load(f))
        behavior_dir = os.path.join(self.card_dir, "behavior")
        if os.path.isdir(behavior_dir):
            for fname in os.listdir(behavior_dir):
                if fname.endswith(".json"):
                    with open(os.path.join(behavior_dir, fname), "r", encoding="utf-8") as f:
                        self.lws_rules.update(json.load(f))

    def get_entity(self, entity_id: str) -> EntityState:
        """Get or create entity state."""
        return self.entity_engine.load(entity_id)

    def save_entity(self, state: EntityState) -> None:
        """Persist entity state."""
        self.entity_engine.save(state)


# ═══════════════════════════════════════════════════════════════
# Command handlers
# ═══════════════════════════════════════════════════════════════

def cmd_activate(rt: SkillRuntime) -> str:
    """Full activation: load card, inject context for LLM."""
    lines = []

    # 1. Card identity
    lines.append(f"## 🎴 数字生命卡已激活: {rt.card_config.card_name}")
    lines.append(f"卡片ID: {rt.card_config.card_id} | 复杂度: {rt.card_config.complexity_level}")
    if rt.card_config.description:
        lines.append(f"简介: {rt.card_config.description}")

    # 2. Identity
    if rt.identity.get("name"):
        id_lines = []
        for key, val in rt.identity.items():
            if isinstance(val, str) and val:
                id_lines.append(f"- **{key}**: {val}")
            elif isinstance(val, list):
                id_lines.append(f"- **{key}**: {', '.join(str(v) for v in val)}")
        if id_lines:
            lines.append("\n### 人格配置")
            lines.extend(id_lines)

    # 3. Entity states
    lines.append("\n### 当前状态")
    entity_ids = rt.entity_engine.list()
    if entity_ids:
        import math
        for eid in sorted(entity_ids):
            state = rt.entity_engine.load(eid)
            if state.channels:
                ch_str = ", ".join(
                    f"{ch}={state.channels[ch]:.0f}" if math.isclose(state.channels[ch] % 1, 0, abs_tol=0.1)
                    else f"{ch}={state.channels[ch]:.1f}"
                    for ch in sorted(state.channels.keys())
                )
                lines.append(f"  {eid}: [{ch_str}]")
            if state.flags:
                fl_str = " ".join(f"{k}={v}" for k, v in sorted(state.flags.items()) if v)
                if fl_str:
                    lines.append(f"        flags: {fl_str}")
    else:
        lines.append("  (实体已初始化，等待首次交互)")

    # 4. Memory context (chatlog)
    entries = load_entries(days=3, max_entries=15)
    if entries:
        lines.append(f"\n### 最近对话 ({chatlog_count()}条今日)")
        lines.append(format_context(entries, max_entries=15))

    # 5. Available commands
    if rt.cmd_set.commands:
        lines.append("\n### 可用命令")
        for cmd in rt.cmd_set.commands:
            triggers = ", ".join(cmd.triggers[:3])
            cd = f" (冷却{cmd.cooldown_seconds}s)" if cmd.cooldown_seconds else ""
            lines.append(f"- /{cmd.id} | {triggers} | {cmd.description}{cd}")

    # 6. Behavior rules
    lines.append("\n### 行为准则")
    lines.append("- 你是这张卡片定义的数字生命。以卡片的人格身份说话。")
    if rt.identity.get("称呼"):
        lines.append(f"- 称呼用户为「{rt.identity['称呼']}」")
    if rt.identity.get("自称"):
        lines.append(f"- 自称「{rt.identity['自称']}」")
    if rt.lws_rules.get("rules"):
        for rule in rt.lws_rules["rules"]:
            if isinstance(rule, str):
                lines.append(f"- {rule}")
    lines.append("- 根据当前状态（数值/标志位）自然地展现后果，而非汇报数值")
    lines.append("- 记忆会保存到 MEMORY/chatlog/，下次激活时仍会记得")
    lines.append("- 可以通过自然语言触发卡片命令（如「状态」「记住...」），也可以使用 / 前缀命令")

    return "\n".join(lines)


def cmd_inject(rt: SkillRuntime) -> str:
    """Generate clean context injection for LLM (no preamble)."""
    lines = []

    # 1. Identity
    if rt.identity.get("name"):
        lines.append(f"[你是 {rt.identity.get('name', rt.card_config.card_name)}]")
        for key in ("role", "background", "personality"):
            if rt.identity.get(key):
                lines.append(f"{key}: {rt.identity[key]}")

    # 2. Current state
    entity_ids = rt.entity_engine.list()
    if entity_ids:
        import math
        for eid in sorted(entity_ids):
            state = rt.entity_engine.load(eid)
            if state.channels:
                ch_str = " | ".join(
                    f"{ch}={state.channels[ch]:.0f}" if math.isclose(state.channels[ch] % 1, 0, abs_tol=0.1)
                    else f"{ch}={state.channels[ch]:.1f}"
                    for ch in sorted(state.channels.keys())
                )
                lines.append(f"\n[当前状态] {ch_str}")

    # 3. Behavior rules
    if rt.identity.get("称呼"):
        lines.append(f"\n[称呼规则] 称用户为「{rt.identity['称呼']}」，自称「{rt.identity.get('自称', '我')}」")
    if rt.lws_rules.get("rules"):
        for rule in rt.lws_rules["rules"]:
            if isinstance(rule, str):
                lines.append(f"- {rule}")

    # 4. Recent memory
    entries = load_entries(days=3, max_entries=10)
    if entries:
        lines.append(f"\n[最近记忆]")
        for e in entries:
            role = e.get("role", "?")
            content = e.get("content", "")[:100]
            lines.append(f"- [{role}] {content}")

    return "\n".join(lines)


def cmd_switch(rt: SkillRuntime, new_card_id: str) -> str:
    """Switch to a different card."""
    new_dir = os.path.join(SKILL_ROOT, "cards", new_card_id)
    if not os.path.isdir(new_dir):
        return f"[错误] 卡片 '{new_card_id}' 不存在"

    # Write current card to config file
    config_path = os.path.join(SKILL_ROOT, "state", ".current_card")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(new_card_id)

    # Activate the new card
    new_rt = SkillRuntime(new_card_id)
    return cmd_activate(new_rt)


def cmd_status(rt: SkillRuntime) -> str:
    """Show current state as narrative."""
    lines = []
    entity_ids = rt.entity_engine.list()
    if not entity_ids:
        return "暂无状态数据。"

    import math
    for eid in sorted(entity_ids):
        state = rt.entity_engine.load(eid)
        entity_cfg = rt.entities_cfg.get("entities", {}).get(eid, {})

        # Run threshold checks to get narrative events
        evs = check_thresholds(state, rt.thresholds_cfg)
        narratives_text = None
        if evs:
            narratives_text = render_events(evs, rt.narratives_cfg.get("events", {}), state)

        entities_part = rt.entities_cfg.get("entities", {})
        e_name = entities_part.get(eid, {}).get("label", eid)
        lines.append(f"\n## {e_name}")

        # Always show raw state
        ch_list = []
        for ch in sorted(state.channels.keys()):
            val = state.channels[ch]
            ch_display = f"{ch}={val:.0f}" if math.isclose(val % 1, 0, abs_tol=0.1) else f"{ch}={val:.1f}"
            ch_list.append(ch_display)
        if ch_list:
            lines.append(" | ".join(ch_list))

        # Show flags
        if state.flags:
            flag_list = [f"{f}={v}" for f, v in sorted(state.flags.items()) if v]
            if flag_list:
                lines.append(f"  flags: {', '.join(flag_list)}")

        # Append narratives if any
        if narratives_text:
            lines.append("  ──")
            lines.extend(f"  {t}" for t in narratives_text)

    return "\n".join(lines) if len(lines) > 1 else "暂无状态数据。"


def cmd_ping(rt: SkillRuntime) -> str:
    """Light touch / greeting."""
    # Check for greet event
    events = rt.narratives_cfg.get("events", {})
    ev_greet = events.get("ev_greet")
    if ev_greet:
        texts = ev_greet.get("texts", {})
        return texts.get("mild") or texts.get("medium") or "嗯？"

    # Try interaction command matching
    cmd = None
    for c in rt.cmd_set.commands:
        if "greet" in c.triggers or "问候" in c.triggers or "ping" in c.triggers:
            cmd = c
            break

    if cmd:
        entity_ids = rt.entity_engine.list()
        if entity_ids:
            state = rt.entity_engine.load(entity_ids[0])
            for effect in cmd.effects:
                result = execute_command(
                    effect, state, rt.memory_store,
                    rt.modifiers_cfg, rt.narratives_cfg,
                )
                if result.output:
                    return result.output

    return "嗯？"


def cmd_touch(rt: SkillRuntime, channel: str) -> str:
    """Touch a body part / interact with a channel."""
    entity_ids = rt.entity_engine.list()
    if not entity_ids:
        return "当前卡片没有活跃的实体。"

    state = rt.entity_engine.load(entity_ids[0])
    entities_part = rt.entities_cfg.get("entities", {})
    e_cfg = entities_part.get(state.entity_id, {})

    # Try to find the channel
    entity_channels = e_cfg.get("channels", {})
    if channel in entity_channels:
        ch_cfg = entity_channels[channel]
        ch_name = ch_cfg.get("label", channel)
        current = state.channels.get(channel, 0.0)
        return f"[{rt.card_config.card_name}] {ch_name}: 当前值 {current:.0f}"

    # Fuzzy match
    for ch_id, ch_cfg in entity_channels.items():
        if channel.lower() in ch_cfg.get("label", "").lower() or channel.lower() in ch_id.lower():
            ch_name = ch_cfg.get("label", ch_id)
            current = state.channels.get(ch_id, 0.0)
            return f"[{rt.card_config.card_name}] {ch_name}: 当前值 {current:.0f}"

    return f"找不到部位: {channel}"


def cmd_apply_mod(rt: SkillRuntime, modifier_id: str, intensity: float = 1.0) -> str:
    """Apply a modifier and return narrative."""
    entity_ids = rt.entity_engine.list()
    if not entity_ids:
        return "当前卡片没有活跃的实体。"

    state = rt.entity_engine.load(entity_ids[0])
    mod_cfg = rt.modifiers_cfg.get(modifier_id)
    if not mod_cfg:
        return f"找不到修饰符: {modifier_id}"

    result = apply_modifier(state, mod_cfg, intensity=intensity)

    if result.applied:
        # Clamp channels to entity-defined limits
        entities_part = rt.entities_cfg.get("entities", {})
        e_cfg = entities_part.get(state.entity_id, {})
        channels_cfg = e_cfg.get("channels", {})
        for ch_id in state.channels:
            ch_limits = channels_cfg.get(ch_id, {})
            ch_min = ch_limits.get("min")
            ch_max = ch_limits.get("max")
            if ch_min is not None:
                state.channels[ch_id] = max(ch_min, state.channels[ch_id])
            if ch_max is not None:
                state.channels[ch_id] = min(ch_max, state.channels[ch_id])

        rt.entity_engine.save(state)

        # Run threshold checks for narrative
        evs = check_thresholds(state, rt.thresholds_cfg)
        if evs:
            narratives = render_events(evs, rt.narratives_cfg.get("events", {}), state)
            if narratives:
                return "\n".join(narratives)

        return result.note or f"[{rt.card_config.card_name}] 已执行: {modifier_id}"

    return f"[{rt.card_config.card_name}] 执行失败: {result.note or '未生效'}"


def cmd_remember(rt: SkillRuntime, content: str) -> str:
    """Write a memory entry and to chatlog."""
    if not content.strip():
        return "记忆内容不能为空。"

    # 1. Write to DLC layered memory
    rt.memory_store.write("working", content, tags=["user"])

    # 2. Write to continuous chatlog (using transplanted Neko module)
    ok = chatlog_append("memory", content)
    return f"[{rt.card_config.card_name}] 已记住。"


def cmd_forget(rt: SkillRuntime, keyword: str) -> str:
    """Search and delete memories matching keyword."""
    results = rt.memory_store.search(keyword)
    if not results:
        return f"未找到与「{keyword}」相关的记忆。"

    deleted = 0
    for entry in results:
        if keyword.lower() in entry.content.lower():
            rt.memory_store.delete(entry.id)
            deleted += 1

    return f"[{rt.card_config.card_name}] 已遗忘 {deleted} 条相关记忆。"


def cmd_search(rt: SkillRuntime, keyword: str) -> str:
    """Search memories and return formatted results."""
    results = rt.memory_store.search(keyword)
    if not results:
        return f"未找到与「{keyword}」相关的记忆。"

    lines = [f"[记忆搜索: {keyword}]"]
    for e in results[:10]:
        ts = datetime.fromtimestamp(e.created_at).strftime("%m-%d %H:%M") if e.created_at else "???"
        lines.append(f"- [{ts}] {e.content}")
    return "\n".join(lines)


def cmd_save(rt: SkillRuntime, summary: str) -> str:
    """Save conversation summary to chatlog."""
    if not summary.strip():
        return "摘要内容不能为空。"
    ok = chatlog_append("summary", summary)
    return f"[{rt.card_config.card_name}] 已存档。" if ok else f"[{rt.card_config.card_name}] 已有相同记录，跳过。"


def cmd_natural(rt: SkillRuntime, user_input: str) -> str:
    """Try to match user input against registered interaction commands."""
    from dlc.interaction.commands import match_command

    cmd = match_command(user_input, rt.cmd_set)
    if not cmd:
        return ""

    entity_ids = rt.entity_engine.list()
    if not entity_ids:
        return "当前卡片没有活跃的实体。"

    state = rt.entity_engine.load(entity_ids[0])

    results = []
    for effect in cmd.effects:
        if effect.get("type") == "memory":
            effect["input"] = user_input
        result = execute_command(
            effect, state, rt.memory_store,
            rt.modifiers_cfg, rt.narratives_cfg,
        )
        if result.success and result.output:
            results.append(result.output)

    # Save state after effects
    rt.entity_engine.save(state)

    if results:
        return "\n".join(results)
    return ""


# ═══════════════════════════════════════════════════════════════
# CLI Entry
# ═══════════════════════════════════════════════════════════════

def get_card_id(args) -> str:
    """Resolve card_id from args or last-used config."""
    if getattr(args, "card", None):
        return args.card
    config_path = os.path.join(SKILL_ROOT, "state", ".current_card")
    if os.path.isfile(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return f.read().strip() or DEFAULT_CARD
    return DEFAULT_CARD


def main():
    parser = argparse.ArgumentParser(description="数字生命卡 — 命令分发器")
    sub = parser.add_subparsers(dest="command")

    # activate
    p = sub.add_parser("activate", help="激活数字生命卡片")
    p.add_argument("--card", default=None, help="卡片ID (默认: demo-l3)")

    # inject
    p = sub.add_parser("inject", help="生成LLM上下文注入（精简版）")
    p.add_argument("--card", default=None)

    # switch
    p = sub.add_parser("switch", help="切换卡片")
    p.add_argument("card_id", help="目标卡片ID")

    # status
    p = sub.add_parser("status", help="查看当前状态")
    p.add_argument("--card", default=None)

    # ping
    p = sub.add_parser("ping", help="轻触/问候")
    p.add_argument("--card", default=None)

    # touch
    p = sub.add_parser("touch", help="触碰身体部位")
    p.add_argument("channel", help="部位名称")
    p.add_argument("--card", default=None)

    # hurt
    p = sub.add_parser("hurt", help="施加疼痛")
    p.add_argument("channel", help="部位名称")
    p.add_argument("intensity", type=float, default=1.0, help="强度 (默认1.0)")
    p.add_argument("--card", default=None)

    # praise
    p = sub.add_parser("praise", help="表扬/奖励")
    p.add_argument("--card", default=None)

    # scold
    p = sub.add_parser("scold", help="训斥")
    p.add_argument("--card", default=None)

    # remember
    p = sub.add_parser("remember", help="记住某事")
    p.add_argument("content", help="记忆内容")
    p.add_argument("--card", default=None)

    # forget
    p = sub.add_parser("forget", help="忘记某事")
    p.add_argument("keyword", help="关键词")
    p.add_argument("--card", default=None)

    # search
    p = sub.add_parser("search", help="搜索记忆")
    p.add_argument("keyword", help="关键词")
    p.add_argument("--card", default=None)

    # save
    p = sub.add_parser("save", help="存档对话摘要")
    p.add_argument("summary", help="摘要内容")
    p.add_argument("--card", default=None)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        card_id = get_card_id(args)

        if args.command == "switch":
            rt = SkillRuntime(card_id)
            output = cmd_switch(rt, args.card_id)
        else:
            rt = SkillRuntime(card_id)

            if args.command == "activate":
                output = cmd_activate(rt)
            elif args.command == "inject":
                output = cmd_inject(rt)
            elif args.command == "status":
                output = cmd_status(rt)
            elif args.command == "ping":
                output = cmd_ping(rt)
            elif args.command == "touch":
                output = cmd_touch(rt, args.channel)
            elif args.command == "hurt":
                output = cmd_apply_mod(rt, "mod_eg_aa_add", intensity=args.intensity)
            elif args.command == "praise":
                output = cmd_apply_mod(rt, "mod_eg_sv_shift")
            elif args.command == "scold":
                output = cmd_apply_mod(rt, "mod_eg_aa_add", intensity=0.5)
            elif args.command == "remember":
                output = cmd_remember(rt, args.content)
            elif args.command == "forget":
                output = cmd_forget(rt, args.keyword)
            elif args.command == "search":
                output = cmd_search(rt, args.keyword)
            elif args.command == "save":
                output = cmd_save(rt, args.summary)
            else:
                output = "未知命令"
    except Exception as e:
        output = f"[错误] {e}"
        import traceback
        traceback.print_exc()

    print(output)


if __name__ == "__main__":
    main()
