"""Threshold checking engine — zero domain semantics.

All threshold rules are defined in data/engine/thresholds.json.
This module loads the rules and evaluates them against entity state.

Public API:
    check_thresholds(entity_id) -> ThresholdReport
        Evaluate all thresholds for a given entity.
        Returns a report with triggered events and suggestions.

    check_all_thresholds() -> list[ThresholdReport]
        Evaluate thresholds for all entities.

    check_single_threshold(entity_id, threshold_id) -> ThresholdEvent | None
        Check exactly one threshold.

    list_threshold_ids() -> list[str]
    get_threshold_config(threshold_id) -> dict

All functions have complete type annotations. No narrative text anywhere.
"""

import os
from typing import Any
from dataclasses import dataclass, field

from .entity import load_entity, list_entities, get_channel
from .persistence import read_json


# ── Config loading ────────────────────────────────────────────

_THRESHOLDS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "engine", "thresholds.json"
)

_THRESHOLDS: dict[str, dict] = {}


def _load_configs() -> dict[str, dict]:
    """Lazy-load threshold configurations."""
    global _THRESHOLDS
    if not _THRESHOLDS:
        raw = read_json(_THRESHOLDS_PATH)
        _THRESHOLDS = raw.get("thresholds", {})
    return _THRESHOLDS


def list_threshold_ids() -> list[str]:
    """List all available threshold IDs."""
    return list(_load_configs().keys())


def get_threshold_config(threshold_id: str) -> dict:
    """Retrieve the full configuration for a single threshold."""
    cfgs = _load_configs()
    if threshold_id not in cfgs:
        raise KeyError(f"Unknown threshold: {threshold_id}")
    return cfgs[threshold_id]


# ── Data structures ───────────────────────────────────────────

@dataclass
class ThresholdEvent:
    """A single triggered threshold event."""
    threshold_id: str
    entity_id: str
    channel: str
    event_id: str
    event_type: str          # "warning" | "critical" | "ecstasy" | "clearing"
    current_value: float
    threshold_value: float
    operator: str
    triggered: bool = True   # Always True when returned from check


@dataclass
class ThresholdReport:
    """Report from checking all thresholds for one entity."""
    entity_id: str
    triggered: list[ThresholdEvent] = field(default_factory=list)
    warnings: list[ThresholdEvent] = field(default_factory=list)
    criticals: list[ThresholdEvent] = field(default_factory=list)
    ecstasies: list[ThresholdEvent] = field(default_factory=list)
    clearings: list[ThresholdEvent] = field(default_factory=list)

    @property
    def has_events(self) -> bool:
        return len(self.triggered) > 0

    @property
    def worst_event_type(self) -> str | None:
        """Return the most severe event type triggered, or None."""
        if self.ecstasies:
            return "ecstasy"
        if self.clearings:
            return "clearing"
        if self.criticals:
            return "critical"
        if self.warnings:
            return "warning"
        return None


# ── Core checking logic ───────────────────────────────────────

_OPERATORS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">":  lambda a, b: a > b,
    "<":  lambda a, b: a < b,
    "==": lambda a, b: a == b,
}


def check_single_threshold(entity_id: str, threshold_id: str) -> ThresholdEvent | None:
    """Check one threshold against current entity state.

    Returns a ThresholdEvent if triggered, None otherwise.
    """
    cfg = get_threshold_config(threshold_id)
    if cfg["entity"] != entity_id:
        return None

    channel = cfg["channel"]
    operator = cfg["operator"]
    t_value = cfg["value"]

    current = get_channel(entity_id, channel)
    op_fn = _OPERATORS.get(operator)
    if op_fn is None:
        return None

    if op_fn(current, t_value):
        return ThresholdEvent(
            threshold_id=threshold_id,
            entity_id=entity_id,
            channel=channel,
            event_id=cfg["event_id"],
            event_type=cfg["event_type"],
            current_value=current,
            threshold_value=t_value,
            operator=operator,
        )
    return None


def check_thresholds(entity_id: str) -> ThresholdReport:
    """Evaluate all thresholds for a given entity.

    Only runs thresholds whose entity field matches entity_id.
    Returns a ThresholdReport with categorized events.
    """
    report = ThresholdReport(entity_id=entity_id)

    for tid, cfg in _load_configs().items():
        if cfg.get("entity") != entity_id:
            continue

        event = check_single_threshold(entity_id, tid)
        if event is None:
            continue

        report.triggered.append(event)
        etype = event.event_type
        if etype == "warning":
            report.warnings.append(event)
        elif etype == "critical":
            report.criticals.append(event)
        elif etype == "ecstasy":
            report.ecstasies.append(event)
        elif etype == "clearing":
            report.clearings.append(event)

    return report


def check_all_thresholds() -> list[ThresholdReport]:
    """Evaluate thresholds for all known entities.

    Returns one report per entity that has thresholds configured.
    """
    reports = []
    for eid in list_entities():
        report = check_thresholds(eid)
        if report.has_events:
            reports.append(report)
    return reports
