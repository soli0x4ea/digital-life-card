"""DLC Engine — Narrator layer.

P1-18: narrative rendering
P2-06: condition filtering (flag_set/flag_unset)
P2-07: priority sorting
P2-08: 3-tier narrative (mild/medium/intense)
"""

from .entity import EntityState

# Severity → text tier mapping (from protocol: critical→intense, warning→medium, else→mild)
_SEVERITY_TIER = {
    "critical": "intense",
    "peak":     "intense",
    "clearing": "intense",
    "warning":  "medium",
}


def _check_condition(ev_cfg: dict, state: EntityState | None) -> bool:
    """P2-06: Check if event condition (flag_set/flag_unset) is satisfied."""
    if state is None:
        return True
    condition = ev_cfg.get("condition", {})
    flag_set = condition.get("flag_set")
    flag_unset = condition.get("flag_unset")
    if flag_set and state.flags.get(flag_set, 0) != 1:
        return False
    if flag_unset and state.flags.get(flag_unset, 0) != 0:
        return False
    return True


def render_event(
    event_id: str,
    narratives: dict[str, dict],
    severity: str = "warning",
    state: EntityState | None = None,
) -> str:
    """Render narrative text for a triggered event.

    Args:
        event_id: The event ID from threshold config.
        narratives: The narratives.json "events" dict.
        severity: Event severity.
        state: Optional entity state for condition checking (P2-06).

    Returns:
        Narrative text string, or "" if the event has no config, no texts,
        or its condition is not met.
    """
    ev = narratives.get(event_id)
    if not ev:
        return ""

    # P2-06: Condition check
    if not _check_condition(ev, state):
        return ""

    tier = _SEVERITY_TIER.get(severity, "intense")
    texts = ev.get("texts", {})
    return texts.get(tier) or texts.get("medium") or texts.get("mild") or ""


def render_events(
    events: list,
    narratives: dict[str, dict],
    state: EntityState | None = None,
) -> list[str]:
    """P2-07+P2-08: Render multiple threshold events with priority sorting.

    Events are sorted by priority (higher first), defaulting to 0.
    Each event's severity determines the text tier used.

    Returns list of rendered text strings, filtered to non-empty.
    """
    # Attach priority from narrative config
    scored = []
    for ev in events:
        ev_cfg = narratives.get(ev.event_id, {})
        priority = ev_cfg.get("priority", 0)
        scored.append((priority, ev))

    # P2-07: Sort by priority descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # P2-08: Render each, skipping empty results
    result = []
    for _, ev in scored:
        text = render_event(ev.event_id, narratives, ev.event_type, state)
        if text:
            result.append(text)
    return result
