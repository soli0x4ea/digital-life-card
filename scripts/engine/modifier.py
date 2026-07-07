"""Modifier application engine — zero domain semantics.

All modifier rules are defined in data/engine/modifiers.json.
This module loads the rules and applies them to entity state.

Public API:
    apply_modifier(entity_id, modifier_id, **params) -> dict
        Apply a modifier with optional parameters (intensity, zone, etc.)
        Returns {applied: int, delta_detail: dict}

    apply_modifiers_batch(entity_id, modifier_specs) -> dict
        Apply multiple modifiers in one batch. Single disk read/write.
        Returns {applied: int, total_delta: dict, details: list[dict]}

    list_modifier_ids() -> list[str]
    get_modifier_config(modifier_id) -> dict

All functions have complete type annotations. No narrative text anywhere.
"""

import json, os, random
from typing import Any
from dataclasses import dataclass, field

from .entity import load_entity, save_entity, set_channels_batch, get_channel, set_channel, toggle_flag, set_flag, reset_entity
from .persistence import read_json


# ── Config loading ────────────────────────────────────────────

_MODIFIERS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "engine", "modifiers.json"
)

_MODIFIERS: dict[str, dict] = {}


def _load_configs() -> dict[str, dict]:
    """Lazy-load modifier configurations."""
    global _MODIFIERS
    if not _MODIFIERS:
        raw = read_json(_MODIFIERS_PATH)
        _MODIFIERS = raw.get("modifiers", {})
    return _MODIFIERS


def list_modifier_ids() -> list[str]:
    """List all available modifier IDs."""
    return list(_load_configs().keys())


def get_modifier_config(modifier_id: str) -> dict:
    """Retrieve the full configuration for a single modifier."""
    cfgs = _load_configs()
    if modifier_id not in cfgs:
        raise KeyError(f"Unknown modifier: {modifier_id}")
    return cfgs[modifier_id]


# ── Core application logic ────────────────────────────────────

@dataclass
class ModifierResult:
    """Result of a single modifier application."""
    modifier_id: str
    target_entity: str
    effect_type: str          # "add" | "set" | "state_set" | "batch_restore" | "flag_toggle"
    deltas: dict[str, float]  = field(default_factory=dict)
    raw_delta: float = 0.0
    intensity: int = 1
    strain_mult: float = 1.0
    note: str = ""


def _compute_delta(base: float, random_range: float, intensity: int,
                   strain_mult: float, decimal_precision: int) -> float:
    """Compute a single delta value from modifier effect config.

    Args:
        base:       Base delta value
        random_range: ±random variance range
        intensity:  Multiplier (1-10 typically)
        strain_mult: Additional multiplier (e.g. bound = 2x)
        decimal_precision: Round to N decimal places (0 = int)
    """
    if random_range > 0:
        raw = (base + random.uniform(-random_range, random_range)) * intensity * strain_mult
    else:
        raw = base * intensity * strain_mult

    if decimal_precision == 0:
        return round(raw)
    return round(raw, decimal_precision)


def _get_channel_precision(modifier_id: str, channel: str) -> int:
    """Determine decimal precision for a channel based on modifier config.
    Flag channels => int (0), float traits => 2, metrics => 0 (int).
    """
    # Heuristic: channels starting with ch_g_comp/dest/p_seek/cur/loy are floats
    _float_channels = {"ch_g_comp", "ch_g_dest", "ch_g_p_seek", "ch_g_cur", "ch_g_loy"}
    if channel in _float_channels:
        return 2
    return 0


def apply_modifier(modifier_id: str, intensity: int = 1,
                   zone: str | None = None,
                   strain_mult: float = 1.0) -> ModifierResult:
    """Apply a single modifier to its target entity.

    Args:
        modifier_id:  Key in modifiers.json (e.g. "mod_eg_av_add")
        intensity:    Multiplier (1-10). Clamped to config range.
        zone:         For zone modifiers, which zone to target
        strain_mult:  External multiplier (e.g. bound = 2.0 from caller context)

    Returns:
        ModifierResult with applied deltas and metadata.
    """
    cfg = get_modifier_config(modifier_id)
    target_entity = cfg["target_entity"]

    # Clamp intensity to configured range
    irange = cfg.get("intensity_range", [1, 1])
    intensity = max(irange[0], min(irange[1], intensity))

    mtype = cfg.get("type", "channel")
    result = ModifierResult(
        modifier_id=modifier_id,
        target_entity=target_entity,
        effect_type=mtype,
        intensity=intensity,
        strain_mult=strain_mult,
    )

    # ── flag_toggle ─────────────────────────────────────────
    if mtype == "flag_toggle":
        flag = cfg["flag"]
        entity = load_entity(target_entity)
        current = entity.flags.get(flag, 0)
        toggle_flag(target_entity, flag)
        new_val = 1 - current
        result.deltas = {flag: float(new_val - current)}
        result.raw_delta = new_val - current
        result.note = f"{flag}: {current}→{new_val}"
        return result

    # ── state_set (zone) ────────────────────────────────
    if mtype == "state_set":
        if not zone:
            raise ValueError(f"modifier {modifier_id} requires a 'zone' parameter")
        target_value = cfg["target_value"]
        entity = load_entity(target_entity)
        old_val = entity.channels.get(zone, 0)
        set_channel(target_entity, zone, target_value)
        result.deltas = {zone: float(target_value - old_val)}
        result.raw_delta = target_value - old_val
        result.note = f"{zone}: {old_val}→{target_value}"
        return result

    # ── batch_restore ────────────────────────────────────────
    if mtype == "batch_restore":
        max_r = cfg.get("max_restore", 5)
        entity = load_entity(target_entity)
        # Find numbed/broken zones (value > 0)
        damaged = [(ch, v) for ch, v in entity.channels.items() if v > 0]
        to_restore = damaged[:max_r]
        updates = {ch: 0.0 for ch, _ in to_restore}
        if updates:
            set_channels_batch(target_entity, updates)
        result.deltas = {ch: float(-v) for ch, v in to_restore}
        result.raw_delta = -sum(v for _, v in to_restore)
        result.note = f"restored {len(to_restore)}/{len(damaged)} zones"
        return result

    # ── channel effects (add/set) ────────────────────────────
    entity = load_entity(target_entity)
    effects = cfg.get("effects", {})

    # Check if locked flag is set (freezes Metric V)
    if target_entity == "e_g" and entity.flags.get("ch_g_locked", 0) == 1:
        locked_channels = {"ch_g_v"}
        effects = {ch: eff for ch, eff in effects.items() if ch not in locked_channels}

    deltas: dict[str, float] = {}
    raw_total = 0.0

    for channel, eff in effects.items():
        etype = eff.get("type", "add")
        base = eff.get("base", 0)
        rng = eff.get("random", 0)
        prec = _get_channel_precision(modifier_id, channel)
        old_val = entity.channels.get(channel, 0)

        if etype == "set":
            # "set" type: intensity IS the target value (or base * intensity)
            target = base * intensity if base != 0 else intensity
            target = max(0, target)  # never negative
            delta = target - old_val
        else:
            # "add" type: compute delta from base + random range
            delta = _compute_delta(base, rng, intensity, strain_mult, prec)

        deltas[channel] = delta
        raw_total += delta

    if deltas:
        # Apply all deltas as batch (target = current + delta works for both add and set)
        entity = load_entity(target_entity)
        batch_updates = {}
        for channel, delta in deltas.items():
            curr = entity.channels.get(channel, 0)
            # For "set" type effects, delta is target - old_val (already computed above)
            # For "add" type effects, delta is the raw computed delta
            batch_updates[channel] = max(0, curr + delta)
        set_channels_batch(target_entity, batch_updates)

    result.deltas = deltas
    result.raw_delta = raw_total
    return result


def apply_modifiers_batch(modifier_specs: list[dict]) -> list[ModifierResult]:
    """Apply multiple modifiers in order. Each modifier loads/saves its entity.

    Args:
        modifier_specs: List of dicts, each with at minimum {"modifier": "id"}
                        Optional keys: intensity, zone, strain_mult

    Returns:
        List of ModifierResult, one per spec.
    """
    results = []
    for spec in modifier_specs:
        mid = spec["modifier"]
        intensity = spec.get("intensity", 1)
        zone = spec.get("zone", None)
        strain_mult = spec.get("strain_mult", 1.0)
        try:
            r = apply_modifier(mid, intensity=intensity, zone=zone, strain_mult=strain_mult)
        except (KeyError, ValueError) as e:
            r = ModifierResult(
                modifier_id=mid,
                target_entity="?",
                effect_type="error",
                note=str(e),
            )
        results.append(r)
    return results
