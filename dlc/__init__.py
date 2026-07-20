"""DLC Protocol v3.0 — Three-Module Architecture.

State Machine (MCP) → Narrative IDs → Narrative Assembly → stdout → LLM
"""

# P0: Foundation
from dlc.loader import (
    load_card, check_version, CardConfig, CardLoadError,
    resolve_modules, detect_complexity, check_dependencies,
)
from dlc.validate import validate_card, validate_module
from dlc.resolver import ConfigResolver, ResolverError
from dlc.context import CardRuntimeContext
from dlc.persistence import StateManager

# Engine: pure computation (entity + modifier + threshold)
from dlc.engine import (
    EntityState, EntityEngine, apply_decay,
    ModifierResult, calc_delta, apply_effect, apply_flag_toggle, apply_modifier,
    clamp_channel, tick_timed_effects,
    ThresholdEvent, check_thresholds,
)

# v3.0: State Machine (MCP → narrative IDs)
from dlc.sm import StateMachineEngine

# v3.0: Narrative Assembly (IDs → lookup → stdout)
from dlc.narrative import NarrativeAssembly

# Interaction: command matching + effect execution
from dlc.interaction import (
    CommandConfig, CommandSet, CommandLoader, CommandResult,
    match_command, execute_command, parse_input, generate_help,
    ItemConfig, ItemLoader, Inventory,
)

# Memory: local file system (no MCP)
from dlc.memory import (
    ChatlogStore, TimelineStore, MemorySearch, record_chat,
)

__all__ = [
    # Foundation
    "load_card", "check_version", "CardConfig", "CardLoadError",
    "resolve_modules", "detect_complexity", "check_dependencies",
    "validate_card", "validate_module",
    "ConfigResolver", "ResolverError", "CardRuntimeContext", "StateManager",
    # Engine
    "EntityState", "EntityEngine", "apply_decay",
    "ModifierResult", "calc_delta", "apply_effect", "apply_flag_toggle", "apply_modifier",
    "clamp_channel", "tick_timed_effects",
    "ThresholdEvent", "check_thresholds",
    # v3.0
    "StateMachineEngine", "NarrativeAssembly",
    # Interaction
    "CommandConfig", "CommandSet", "CommandLoader", "CommandResult",
    "match_command", "execute_command", "parse_input", "generate_help",
    "ItemConfig", "ItemLoader", "Inventory",
    # Memory
    "ChatlogStore", "TimelineStore", "MemorySearch", "record_chat",
]
