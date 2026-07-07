"""Narrative rendering engine — zero domain semantics.

Maps threshold events to text via data/engine/narratives.json.
All text is stored externally — no inline narratives anywhere.

Public API:
    render_event(event_id, severity="medium") -> str | None
        Render a single event to text. Returns None if narratives are disabled
        or event not found.

    render_report(report: ThresholdReport) -> list[str]
        Render all triggered events in a threshold report.

    is_narrator_enabled() -> bool
    toggle_narrator(state: bool) -> None

    list_event_ids() -> list[str]
    get_event_config(event_id) -> dict

All functions have complete type annotations.
"""

import json, os
from typing import Any

from .threshold import ThresholdReport
from .persistence import read_json


# ── Config loading ────────────────────────────────────────────

_NARRATIVES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "engine", "narratives.json"
)

_NARRATIVES: dict[str, Any] | None = None


def _load_narratives() -> dict[str, Any]:
    global _NARRATIVES
    if _NARRATIVES is None:
        _NARRATIVES = read_json(_NARRATIVES_PATH)
    return _NARRATIVES


def is_narrator_enabled() -> bool:
    cfg = _load_narratives()
    return cfg.get("meta", {}).get("toggle", "enabled") == "enabled"


def toggle_narrator(state: bool) -> None:
    cfg = _load_narratives()
    cfg["meta"]["toggle"] = "enabled" if state else "disabled"


def list_event_ids() -> list[str]:
    cfg = _load_narratives()
    return list(cfg.get("events", {}).keys())


def get_event_config(event_id: str) -> dict:
    cfg = _load_narratives()
    events = cfg.get("events", {})
    if event_id not in events:
        raise KeyError(f"Unknown event: {event_id}")
    return events[event_id]


# ── Severity mapping ──────────────────────────────────────────

_SEVERITY_TO_LEVEL = {
    "warning":  "mild",
    "critical": "intense",
    "ecstasy":  "intense",
    "clearing": "medium",
}


def _pick_severity(event_id: str, channel_value: float | None = None) -> str:
    """Pick text severity level based on event type and optional channel value.
    
    Returns one of: "mild", "medium", "intense".
    """
    cfg = get_event_config(event_id)
    severity = cfg.get("severity", "warning")

    # If channel value is provided, use it to determine intensity
    if channel_value is not None:
        if channel_value >= 95:
            return "intense"
        elif channel_value >= 85:
            return "medium"
    return _SEVERITY_TO_LEVEL.get(severity, "medium")


# ── Core rendering ────────────────────────────────────────────

def render_event(event_id: str, severity: str = "medium") -> str | None:
    """Render a single event to narrative text.

    Args:
        event_id:  Event ID from thresholds.json (e.g. "ev_g_a_high")
        severity:  Text intensity level ("mild" | "medium" | "intense")

    Returns:
        Rendered text string, or None if narrator disabled / event not found.
    """
    if not is_narrator_enabled():
        return None

    cfg = _load_narratives()
    events = cfg.get("events", {})
    if event_id not in events:
        return None

    texts = events[event_id].get("texts", {})
    if severity not in texts:
        severity = "medium"

    return texts[severity]


def render_event_auto(event_id: str, channel_value: float | None = None) -> str | None:
    """Render an event with auto-detected severity from channel value and event type."""
    severity = _pick_severity(event_id, channel_value)
    return render_event(event_id, severity)


def render_report(report: ThresholdReport) -> list[str]:
    """Render all triggered events in a threshold report.

    Returns:
        List of rendered text strings. Excludes None (disabled/not found).
    """
    lines = []
    for event in report.triggered:
        text = render_event_auto(event.event_id, event.current_value)
        if text:
            prefix = f"[{event.event_type.upper()}] " if event.event_type != "warning" else ""
            lines.append(f"{prefix}{text}")
    return lines
