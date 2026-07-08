"""DLC Protocol v1.0 — Runtime Context.

P0-21: CardRuntimeContext.

Encapsulates card configuration + resolved configs + runtime state
into a single context object that engine modules can depend on.
"""

import os

from dlc.resolver import ConfigResolver


class CardRuntimeContext:
    """Contextual wrapper for a loaded digital life card.

    Provides:
    - Card metadata (card_id, complexity_level, etc.)
    - Config file loading via resolver
    - Shortcut properties for engine configs
    - Card-scoped state directory

    Usage:
        ctx = CardRuntimeContext("/path/to/card_dir")
        entities = ctx.entities
        modifiers = ctx.modifiers
        state_file = os.path.join(ctx.state_dir, "e_g.json")
    """

    def __init__(self, card_dir: str):
        self._card_dir = os.path.abspath(card_dir)
        self.resolver = ConfigResolver(card_dir)
        self._ensure_state_dir()

    # ── Card metadata ────────────────────────────────────────

    @property
    def card_id(self) -> str:
        return self.resolver.card_id

    @property
    def card(self) -> dict:
        return self.resolver.card

    @property
    def complexity_level(self) -> str:
        return self.card.get("complexity_level", "L0")

    # ── Engine config shortcuts ──────────────────────────────

    @property
    def entities(self) -> dict:
        """Shortcut for engine/entities.json."""
        return self._load_if_enabled("engine", "entities")

    @property
    def modifiers(self) -> dict:
        """Shortcut for engine/modifiers.json."""
        return self._load_if_enabled("engine", "modifiers")

    @property
    def thresholds(self) -> dict:
        """Shortcut for engine/thresholds.json."""
        return self._load_if_enabled("engine", "thresholds")

    @property
    def narratives(self) -> dict:
        """Shortcut for engine/narratives.json."""
        return self._load_if_enabled("engine", "narratives")

    # ── Generic config access ────────────────────────────────

    def load_engine_config(self, sub_key: str) -> dict:
        """Load an engine sub-config by key.

        Example: ctx.load_engine_config("entities") → entities.json content.
        """
        return self.resolver.load_config("engine", sub_key)

    # ── State directory ──────────────────────────────────────

    @property
    def state_dir(self) -> str:
        return self.resolver.state_dir

    # ── Internal ─────────────────────────────────────────────

    def _ensure_state_dir(self):
        os.makedirs(self.state_dir, exist_ok=True)

    def _load_if_enabled(self, module: str, sub_key: str):
        """Try to load; return {} if module disabled."""
        try:
            return self.resolver.load_config(module, sub_key)
        except Exception:
            return {}
