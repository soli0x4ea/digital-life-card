"""DLC v3.0 State Machine Engine.

纯计算状态机 — 输入命令，输出叙事编号，零自然语言。

Usage:
    engine = StateMachineEngine(card_path="cards/my-card")
    result = engine.execute("gamble", {"token": 1})
    # → {"narrative_ids": ["action.gamble.3", "boundary.ecstasy.v"],
    #     "state_diff": {...}, "flags": {...}}

编号格式: <domain>.<type>[.<variant>][.<level>]
  action.ping          — 动作，无等级
  action.gamble.3      — 动作，强度 3 级
  action.gamble.v.3    — 动作，v 区，强度 3 级
  threshold.pain_high  — 阈值事件
  boundary.ecstasy.v   — 边界事件，v 区
  system.status        — 系统元信息
"""
from __future__ import annotations

import os, sys, json, time
from pathlib import Path
from typing import Any

# Ensure dlc package is importable
_skill_dir = Path(__file__).resolve().parent.parent.parent
if str(_skill_dir) not in sys.path:
    sys.path.insert(0, str(_skill_dir))

from dlc import (
    load_card, validate_card,
    CardRuntimeContext, StateManager, EntityState,
    apply_modifier, check_thresholds,
)
from dlc.interaction import (
    match_command, execute_command, parse_input,
    CommandLoader, CommandSet,
)

# Tri-value labels for state diff
_TRI_VALUES = ("pain", "shame", "pleasure")
_TRI_LABELS = {"pain": "疼痛", "shame": "羞耻", "pleasure": "快感"}


class StateMachineEngine:
    """DLC v3.0 纯计算状态机。不输出自然语言，只输出叙事编号。"""

    def __init__(self, card_path: str):
        self.card_path = os.path.abspath(card_path)

        # Validate (non-fatal)
        try:
            validate_card(self.card_path)
        except Exception:
            pass

        self.card = load_card(self.card_path)
        self.card_id = self.card.card_id
        self.ctx = CardRuntimeContext(self.card_path)
        self.state_mgr = StateManager(self.ctx)
        os.makedirs(self.ctx.state_dir, exist_ok=True)

        # Command set
        self.cmd_set: CommandSet | None = None
        if self._has_module("interaction"):
            self._load_commands()

        # Cooldowns
        self._cooldowns: dict[str, float] = {}

        # Entity states: {entity_id: EntityState}
        self._entities: dict[str, EntityState] = {}
        self._restore_entities()

    # ═══════════════════════════════════════════════════════════
    # Public API — MCP 工具接口
    # ═══════════════════════════════════════════════════════════

    def execute(self, command: str, params: dict[str, Any] | None = None) -> dict:
        """执行命令，返回叙事编号 + 状态变更。

        Args:
            command: 命令 ID（如 "gamble"）
            params: 可选参数（如 {"token": 1}）

        Returns:
            {"narrative_ids": [...], "state_diff": {...}, "flags": {...},
             "error": None}
        """
        params = params or {}
        result = {
            "narrative_ids": [],
            "state_diff": {},
            "flags": {},
            "error": None,
        }

        try:
            # 1. Match command
            if not self.cmd_set:
                result["error"] = "No command set loaded"
                return result

            cmd, _ = parse_input(command, self.cmd_set)
            if cmd is None:
                # Fallback: try matching by raw command ID
                for c in self.cmd_set.commands:
                    if c.id == command:
                        cmd = c
                        break
            if cmd is None:
                result["error"] = f"Unknown command: {command}"
                return result

            # 2. Meta-commands
            if cmd.id in ("cmd_status", "cmd_reset", "cmd_end"):
                return self._handle_meta_v3(cmd.id, cmd, result)

            # 3. Cooldown
            if self._is_cooling(cmd):
                result["error"] = f"Command {cmd.id} on cooldown"
                return result

            # 4. Extract intensity
            intensity = float(params.get("intensity",
                             params.get("count",
                             params.get("token", 1))))

            # 5. Apply effects
            entity = self._get_or_create_entity(self._get_primary_entity_id())
            before = dict(entity.channels)
            before_flags = dict(entity.flags)

            entities_cfg = self._unwrap_config(self.ctx.entities, "entities")
            modifiers_cfg = self._unwrap_config(self.ctx.modifiers, "modifiers")

            effect_ids = []
            for effect in cmd.effects:
                eff = dict(effect)
                if intensity != 1.0 and eff.get("type") == "modifier":
                    eff["intensity"] = intensity

                exec_result = execute_command(
                    eff, entity,
                    modifiers_cfg=modifiers_cfg,
                    narratives_cfg=self.ctx.narratives,
                    entity_cfg=entities_cfg.get(entity.entity_id, {}),
                )
                if exec_result.success:
                    effect_ids.append(self._action_id(cmd, intensity))

            # 6. Post-effects hook (card-specific — override in subclass)
            post_ids = self._post_effects_hook(entity, before, cmd, command)
            effect_ids.extend(post_ids)

            # 7. Thresholds → threshold IDs
            thresholds_raw = self._unwrap_config(self.ctx.thresholds, "thresholds")
            seen_event_ids: set[str] = set()
            for tev in check_thresholds(entity, thresholds_raw):
                if tev.event_id in seen_event_ids:
                    continue
                seen_event_ids.add(tev.event_id)
                effect_ids.append(self._threshold_id(tev.event_id))

            # 8. Save entity state
            self._save_entity(entity)

            # 9. Build state diff
            after = dict(entity.channels)
            after_flags = dict(entity.flags)

            diff = {}
            for ch, val in after.items():
                old = before.get(ch, 0)
                if abs(val - old) > 0.001:
                    diff[ch] = {"before": round(old, 1), "after": round(val, 1),
                                 "delta": round(val - old, 1)}

            flag_diff = {}
            for fk, fv in after_flags.items():
                old_f = before_flags.get(fk, 0)
                if fv != old_f:
                    flag_diff[fk] = fv

            result["narrative_ids"] = effect_ids
            result["state_diff"] = diff
            result["flags"] = flag_diff

            # 10. Cooldown
            self._mark_used(cmd)

            # 11. Persist stdout (debug log, not narrative)
            self._write_state_change(command, diff, flag_diff)

        except Exception as e:
            result["error"] = str(e)

        return result

    def get_state(self) -> dict:
        """获取当前状态快照（纯数据，无叙事）。"""
        result = {"card_id": self.card_id, "entities": {}}
        for eid, entity in self._entities.items():
            result["entities"][eid] = {
                "channels": {k: round(v, 1) for k, v in entity.channels.items()
                             if abs(v) > 0.001},
                "flags": {k: v for k, v in entity.flags.items() if v},
            }
        return result

    def reset(self) -> dict:
        """重置状态到初始值。"""
        entity = self._get_or_create_entity(self._get_primary_entity_id())
        entities_cfg = self._unwrap_config(self.ctx.entities, "entities")
        econfig = entities_cfg.get(entity.entity_id, {})

        for ch_key, ch_cfg in econfig.get("channels", {}).items():
            val = ch_cfg.get("initial", ch_cfg.get("default", 0))
            entity.channels[ch_key] = float(val)
        for f_key, f_val in econfig.get("flags", {}).items():
            entity.flags[f_key] = f_val

        self._save_entity(entity)
        return {"status": "reset", "card_id": self.card_id}

    # ═══════════════════════════════════════════════════════════
    # Overrideable hooks
    # ═══════════════════════════════════════════════════════════

    def _post_effects_hook(
        self, entity: EntityState, before: dict,
        cmd, raw_input: str,
    ) -> list[str]:
        """卡片特有逻辑（soulchange/emergence等），返回额外叙事编号。"""
        return []

    # ═══════════════════════════════════════════════════════════
    # Internal
    # ═══════════════════════════════════════════════════════════

    def _handle_meta_v3(self, cmd_id: str, cmd, result: dict) -> dict:
        if cmd_id == "cmd_status":
            s = self.get_state()
            result["narrative_ids"] = ["system.status"]
            result["state_diff"] = s
            return result
        if cmd_id in ("cmd_reset", "cmd_end"):
            r = self.reset()
            result["narrative_ids"] = ["system.reset"]
            result["flags"] = r
            return result
        return result

    def _has_module(self, module: str) -> bool:
        return module in self.card.modules and self.card.modules[module].get("enabled", False)

    def _load_commands(self):
        try:
            loader = CommandLoader(os.path.join(self.card_path, "interaction"))
            self.cmd_set = loader.load()
        except Exception:
            self.cmd_set = CommandSet()

    def _get_primary_entity_id(self) -> str:
        entities_cfg = self._unwrap_config(self.ctx.entities, "entities")
        if entities_cfg:
            return next(iter(entities_cfg))
        return "main"

    def _get_or_create_entity(self, entity_id: str) -> EntityState:
        if entity_id not in self._entities:
            entities_cfg = self._unwrap_config(self.ctx.entities, "entities")
            econfig = entities_cfg.get(entity_id, {})
            entity = EntityState(entity_id=entity_id)
            for ch_key, ch_cfg in econfig.get("channels", {}).items():
                val = ch_cfg.get("initial", ch_cfg.get("default", 0))
                entity.channels[ch_key] = float(val)
            for f_key, f_val in econfig.get("flags", {}).items():
                entity.flags[f_key] = f_val
            self._entities[entity_id] = entity
        return self._entities[entity_id]

    def _save_entity(self, entity: EntityState):
        self.state_mgr.write(entity.entity_id, entity.to_dict())

    def _restore_entities(self):
        entity_ids = self.state_mgr.list_states()
        entities_cfg = self._unwrap_config(self.ctx.entities, "entities")

        if not entity_ids:
            for eid, econfig in entities_cfg.items():
                entity = EntityState(entity_id=eid)
                for ch_key, ch_cfg in econfig.get("channels", {}).items():
                    val = ch_cfg.get("initial", ch_cfg.get("default", 0))
                    entity.channels[ch_key] = float(val)
                for f_key, f_val in econfig.get("flags", {}).items():
                    entity.flags[f_key] = f_val
                self._entities[eid] = entity
            return

        for eid in entity_ids:
            data = self.state_mgr.read(eid)
            if data:
                self._entities[eid] = EntityState.from_dict(data)

        for eid, econfig in entities_cfg.items():
            if eid not in self._entities:
                self._get_or_create_entity(eid)

    def _is_cooling(self, cmd) -> bool:
        if cmd.cooldown_seconds <= 0:
            return False
        last = self._cooldowns.get(cmd.id)
        return last is not None and (time.time() - last) < cmd.cooldown_seconds

    def _mark_used(self, cmd):
        self._cooldowns[cmd.id] = time.time()

    @staticmethod
    def _unwrap_config(raw, key: str) -> dict:
        if isinstance(raw, dict) and key in raw:
            return raw[key]
        return raw if isinstance(raw, dict) else {}

    # ═══════════════════════════════════════════════════════════
    # Narrative ID builders (zero NL)
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _action_id(cmd, intensity: float) -> str:
        """Build action ID: action.<name>[.<level>]

        Strips 'cmd_' prefix. Appends intensity level if > 1.
        Cards can override via _post_effects_hook for variant info.
        """
        name = cmd.id.replace("cmd_", "")
        level = int(intensity) if intensity > 1 else 0
        if level:
            return f"action.{name}.{level}"
        return f"action.{name}"

    @staticmethod
    def _threshold_id(event_id: str) -> str:
        """Classify and clean threshold event IDs.

        Mapping:
          narr_status_warn_* → threshold.*   (warning thresholds)
          narr_ecstasy_*     → boundary.*    (boundary events)
          narr_soul_break_*  → boundary.*
          narr_clearing_*    → boundary.*
        """
        eid = event_id

        # Boundary events (lifecycle)
        for prefix in ("narr_ecstasy_", "narr_soul_break_", "narr_clearing_"):
            if eid.startswith(prefix):
                return f"boundary.{eid[len('narr_'):]}"

        # Threshold warnings
        if eid.startswith("narr_status_warn_"):
            return f"threshold.{eid[len('narr_status_warn_'):]}"

        # Unknown: strip narr_ prefix, keep as-is domain
        if eid.startswith("narr_"):
            return f"threshold.{eid[len('narr_'):]}"

        return f"threshold.{eid}"

    # ═══════════════════════════════════════════════════════════

    def _write_state_change(self, command: str, diff: dict, flags: dict):
        """记录状态变更日志（非叙事，纯审计）。"""
        log_dir = os.path.join(self.card_path, "MEMORY", "state_log")
        os.makedirs(log_dir, exist_ok=True)
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        ts = datetime.now().strftime("%H:%M:%S")
        path = os.path.join(log_dir, f"{today}.jsonl")
        entry = {"ts": ts, "command": command, "diff": diff, "flags": flags}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
