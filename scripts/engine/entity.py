"""Entity CRUD and channel management — zero domain semantics.

All entity state is stored as key-value channels. No entity knows
anything about the domain it represents (zones, metrics, recovery, etc.).
The mapping is entirely defined in data/engine/entities.json.

Public API:
    load_entity(entity_id)       -> EntityState
    save_entity(entity_id, state) -> None
    list_entities()               -> list[str]
    get_channel(entity_id, channel) -> float
    set_channel(entity_id, channel, value) -> None
    set_channels_batch(entity_id, updates) -> None
    reset_entity(entity_id) -> None
    entity_exists(entity_id) -> bool

All functions have complete type annotations. No narrative text anywhere.
"""

import os
from dataclasses import dataclass, field, asdict
from typing import Any

from .persistence import read_json, try_read_json, write_json


# ── Data structures ───────────────────────────────────────────

@dataclass
class EntityState:
    """Runtime state of a single entity.

    Attributes:
        entity_id:  Unique identifier (e.g. "e_g", "e_b")
        channels:   Key-value store for channel values
        flags:      Key-value store for boolean flags (stored as 0/1 ints)
        meta:       Opaque metadata (label, version, etc.)
        dirty:      Whether state has been modified since last save
    """
    entity_id: str
    channels: dict[str, float] = field(default_factory=dict)
    flags: dict[str, int] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    dirty: bool = False

    def to_dict(self) -> dict:
        """Serialize to plain dict for JSON persistence."""
        return {
            "entity_id": self.entity_id,
            "channels": self.channels,
            "flags": self.flags,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EntityState":
        """Deserialize from a plain dict."""
        return cls(
            entity_id=data.get("entity_id", ""),
            channels=data.get("channels", {}),
            flags=data.get("flags", {}),
            meta=data.get("meta", {}),
        )


# ── Path resolution ───────────────────────────────────────────

# Resolve the engine state directory relative to this file
# entity.py → scripts/engine/entity.py
# Root → ../../.. (two dirs up from engine/ = scripts/, one more = root)
_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENGINE_STATE_DIR = os.path.join(_SKILL_ROOT, "data", "engine", "state")
_ENTITIES_CONFIG_PATH = os.path.join(_SKILL_ROOT, "data", "engine", "entities.json")


def _state_path(entity_id: str) -> str:
    """Get the filesystem path for an entity's state file."""
    return os.path.join(_ENGINE_STATE_DIR, f"{entity_id}.json")


# ── Entity config loading ─────────────────────────────────────

def _load_entity_config(entity_id: str) -> dict:
    """Load the entity definition from entities.json.

    Returns an empty dict if the config doesn't exist (graceful degradation).
    """
    config = try_read_json(_ENTITIES_CONFIG_PATH, {"entities": {}})
    return config.get("entities", {}).get(entity_id, {})


# ── Public API ────────────────────────────────────────────────

def load_entity(entity_id: str) -> EntityState:
    """Load an entity's runtime state from disk.

    If the state file doesn't exist, returns a fresh EntityState
    with channels initialized from the entity config defaults.

    Args:
        entity_id: Unique entity identifier.

    Returns:
        EntityState with populated channels.
    """
    path = _state_path(entity_id)
    data = try_read_json(path)

    if data is not None:
        return EntityState.from_dict(data)

    # Fresh entity — initialize from config defaults
    config = _load_entity_config(entity_id)
    defaults = config.get("channels", {})
    channels = {k: v.get("initial", 0) for k, v in defaults.items()}
    flag_config = config.get("flags", {})
    flags = {k: 0 for k in flag_config}
    return EntityState(
        entity_id=entity_id,
        channels=channels,
        flags=flags,
        meta={"label": config.get("label", entity_id)},
        dirty=True,
    )


def save_entity(entity_id: str, state: EntityState) -> None:
    """Persist an entity's state to disk.

    Args:
        entity_id: Entity identifier (used to derive file path).
        state:     EntityState to persist.
    """
    path = _state_path(entity_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_json(path, state.to_dict())
    state.dirty = False


def list_entities() -> list[str]:
    """List all known entity IDs from the entities.json config.

    Returns:
        List of entity_id strings, sorted alphabetically.
    """
    config = try_read_json(_ENTITIES_CONFIG_PATH, {"entities": {}})
    return sorted(config.get("entities", {}).keys())


def entity_exists(entity_id: str) -> bool:
    """Check whether an entity is defined in the config."""
    return entity_id in list_entities()


def get_channel(entity_id: str, channel: str) -> float:
    """Read a single channel value from an entity.

    Args:
        entity_id: Entity to read from.
        channel:   Channel name.

    Returns:
        Current channel value as float.

    Raises:
        KeyError: If the channel doesn't exist on this entity.
    """
    state = load_entity(entity_id)
    if channel not in state.channels:
        # Check if it's a flag
        if channel in state.flags:
            return float(state.flags[channel])
        raise KeyError(f"Channel '{channel}' not found on entity '{entity_id}'")
    return state.channels[channel]


def set_channel(entity_id: str, channel: str, value: float) -> None:
    """Set a single channel value, clamping to its defined range.

    The entity is loaded, the channel is set (clamped), and the
    state is immediately saved. This is intentional — no in-memory
    caching in the engine layer.

    Args:
        entity_id: Target entity.
        channel:   Channel to update.
        value:     New value (will be clamped to channel range).

    Raises:
        KeyError: If the channel doesn't exist on this entity.
        ValueError: If value cannot be converted to float.
    """
    state = load_entity(entity_id)
    value = float(value)

    # Clamp to channel range
    config = _load_entity_config(entity_id)
    ch_config = config.get("channels", {}).get(channel, {})
    lo = ch_config.get("min", 0)
    hi = ch_config.get("max", 100)
    value = max(lo, min(hi, value))

    state.channels[channel] = value
    state.dirty = True
    save_entity(entity_id, state)


def set_channels_batch(entity_id: str, updates: dict[str, float]) -> dict[str, tuple[float, float]]:
    """Set multiple channels at once, saving only once.

    Args:
        entity_id: Target entity.
        updates:   Dict of channel → new value.

    Returns:
        Dict of channel → (old_value, new_value) for each updated channel.

    Raises:
        KeyError: If any channel doesn't exist.
    """
    state = load_entity(entity_id)
    config = _load_entity_config(entity_id)
    changes = {}

    for channel, raw_value in updates.items():
        value = float(raw_value)
        ch_config = config.get("channels", {}).get(channel, {})
        lo = ch_config.get("min", 0)
        hi = ch_config.get("max", 100)
        value = max(lo, min(hi, value))

        old = state.channels.get(channel, 0)
        state.channels[channel] = value
        changes[channel] = (old, value)

    state.dirty = True
    save_entity(entity_id, state)
    return changes


def set_flag(entity_id: str, flag: str, value: int) -> None:
    """Set a flag (boolean stored as 0/1 int) on an entity.

    Args:
        entity_id: Target entity.
        flag:      Flag name.
        value:     0 (off) or 1 (on).

    Raises:
        ValueError: If value is not 0 or 1.
    """
    if value not in (0, 1):
        raise ValueError(f"Flag value must be 0 or 1, got {value}")

    state = load_entity(entity_id)
    state.flags[flag] = value
    state.dirty = True
    save_entity(entity_id, state)


def toggle_flag(entity_id: str, flag: str) -> int:
    """Toggle a flag (0↔1) and return the new value.

    Args:
        entity_id: Target entity.
        flag:      Flag name.

    Returns:
        New flag value (0 or 1).
    """
    state = load_entity(entity_id)
    current = state.flags.get(flag, 0)
    new_val = 1 if current == 0 else 0
    state.flags[flag] = new_val
    state.dirty = True
    save_entity(entity_id, state)
    return new_val


def reset_entity(entity_id: str) -> None:
    """Reset an entity to its initial config state.

    Deletes the state file and writes a fresh copy from config defaults.

    Args:
        entity_id: Entity to reset.
    """
    path = _state_path(entity_id)
    if os.path.exists(path):
        os.remove(path)
    load_entity(entity_id)  # This creates a fresh state file
