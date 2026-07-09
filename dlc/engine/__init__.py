"""DLC Engine — public API."""

from .entity import EntityState, EntityEngine, apply_decay
from .modifier import (
    ModifierResult, calc_delta, apply_effect, apply_flag_toggle, apply_modifier,
    tick_timed_effects, maybe_auto_trigger,
)
from .threshold import ThresholdEvent, check_thresholds
from .narrator import render_event, render_events

__all__ = [
    "EntityState", "EntityEngine", "apply_decay",
    "ModifierResult", "calc_delta", "apply_effect", "apply_flag_toggle", "apply_modifier",
    "tick_timed_effects", "maybe_auto_trigger",
    "ThresholdEvent", "check_thresholds",
    "render_event", "render_events",
]
