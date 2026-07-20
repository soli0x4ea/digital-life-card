"""DLC v3.0 Engine — pure computation layer (no NL output).

Entity state management + modifier calculation + threshold detection.
Narrative rendering is handled externally by dlc/narrative/assembly.py.
"""

from .entity import EntityState, EntityEngine, apply_decay
from .modifier import (
    ModifierResult, calc_delta, apply_effect, apply_flag_toggle, apply_modifier,
    clamp_channel, tick_timed_effects, maybe_auto_trigger,
)
from .threshold import ThresholdEvent, check_thresholds

__all__ = [
    "EntityState", "EntityEngine", "apply_decay",
    "ModifierResult", "calc_delta", "apply_effect", "apply_flag_toggle", "apply_modifier",
    "clamp_channel", "tick_timed_effects", "maybe_auto_trigger",
    "ThresholdEvent", "check_thresholds",
]
