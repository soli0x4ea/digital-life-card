"""Phase 1D: Integration tests — P1-20 L0 demo, P1-21 L1 demo, P1-22 E2E."""

import unittest, os, sys, tempfile, shutil, json

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
sys.path.insert(0, _PROJ)

CARDS = os.path.join(_PROJ, "cards")


def _load_card(card_name):
    """Load a card from cards/ directory with full validation."""
    from dlc.loader import load_card, resolve_modules, check_dependencies
    from dlc.validate import validate_card
    card_dir = os.path.join(CARDS, card_name)
    cfg = load_card(card_dir)
    errors = validate_card(cfg._raw)
    if errors:
        raise ValueError(f"Card validation failed: {errors}")
    return cfg, resolve_modules(cfg)


# ═══════════════════════════════════════════════════════════════
# P1-20: L0 minimal card demo
# ═══════════════════════════════════════════════════════════════

class TestL0DemoCard(unittest.TestCase):
    """P1-20: L0 card loads, generates system prompt, can be used."""

    def test_01_card_loads_and_passes_validation(self):
        cfg, modules = _load_card("demo-l0")
        self.assertEqual(cfg.complexity_level, "L0")
        self.assertEqual(cfg.card_name, "Demo L0 — 纯对话角色")

    def test_02_only_identity_enabled(self):
        _, modules = _load_card("demo-l0")
        self.assertIn("identity", modules)
        self.assertNotIn("body", modules)
        self.assertNotIn("engine", modules)

    def test_03_profile_loads(self):
        from dlc.identity import ProfileLoader
        pl = ProfileLoader(os.path.join(CARDS, "demo-l0", "identity"))
        profile = pl.load()
        self.assertEqual(profile.name, "小助手")
        self.assertEqual(profile.welcome_message, "你好！我是小助手，有什么可以帮你的？")

    def test_04_system_prompt_generated(self):
        from dlc.identity import ProfileLoader, PersonalityLoader, Speech
        from dlc.identity import generate_system_prompt
        id_dir = os.path.join(CARDS, "demo-l0", "identity")
        profile = ProfileLoader(id_dir).load()
        personality = PersonalityLoader(id_dir).load()
        prompt = generate_system_prompt(profile, personality, Speech(speech_style="neutral", address_user=["用户"]))
        self.assertIn("小助手", prompt)
        self.assertIn("AI助手", prompt)
        self.assertGreater(len(prompt), 100)

    def test_05_welcome_triggers_once(self):
        from dlc.identity import ProfileLoader, get_welcome_message
        id_dir = os.path.join(CARDS, "demo-l0", "identity")
        profile = ProfileLoader(id_dir).load()
        tmp = tempfile.mkdtemp()
        try:
            msg = get_welcome_message(profile, tmp)
            self.assertEqual(msg, "你好！我是小助手，有什么可以帮你的？")
            msg2 = get_welcome_message(profile, tmp)
            self.assertIsNone(msg2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# P1-21: L1 basic card demo
# ═══════════════════════════════════════════════════════════════

class TestL1DemoCard(unittest.TestCase):
    """P1-21: L1 card: stimulus → state change → narrative feedback."""

    def test_01_card_loads_and_passes_validation(self):
        cfg, modules = _load_card("demo-l1")
        self.assertEqual(cfg.complexity_level, "L1")

    def test_02_identity_body_engine_all_enabled(self):
        _, modules = _load_card("demo-l1")
        self.assertIn("identity", modules)
        self.assertIn("body", modules)
        self.assertIn("engine", modules)

    def test_03_engine_configs_loadable(self):
        from dlc.resolver import ConfigResolver
        card_dir = os.path.join(CARDS, "demo-l1")
        resolver = ConfigResolver(card_dir)
        entities = resolver.load_config("engine", "entities")
        self.assertIn("e_g", entities.get("entities", {}))
        modifiers = resolver.load_config("engine", "modifiers")
        self.assertIn("mod_eg_av_add", modifiers.get("modifiers", {}))
        thresholds = resolver.load_config("engine", "thresholds")
        self.assertIn("thr_g_a_warn", thresholds.get("thresholds", {}))

    def test_04_full_pipeline_stimulus_to_narrative(self):
        """Apply stimulus → state changes → threshold triggers → narrative output."""
        from dlc.context import CardRuntimeContext
        from dlc.engine.entity import EntityEngine, EntityState
        from dlc.engine.modifier import apply_modifier
        from dlc.engine.threshold import check_thresholds
        from dlc.engine.narrator import render_event

        card_dir = os.path.join(CARDS, "demo-l1")
        ctx = CardRuntimeContext(card_dir)

        # Setup engine
        eng = EntityEngine(state_dir=ctx.state_dir)
        entities_cfg = ctx.entities
        modifiers_cfg = ctx.modifiers.get("modifiers", {})
        thresholds_cfg = ctx.thresholds.get("thresholds", {})
        narratives_cfg = ctx.narratives.get("events", {})

        # Init entity
        e_g = entities_cfg["entities"]["e_g"]
        chans = {k: float(v.get("initial", 0)) for k, v in e_g["channels"].items()}
        state = EntityState(entity_id="e_g", channels=chans, flags={"ch_g_flag_01": 0})

        # Apply modifier (stimulus)
        result = apply_modifier(state, modifiers_cfg["mod_eg_av_add"])
        self.assertTrue(result.applied)
        self.assertGreater(state.channels.get("ch_g_a", 0), 0)

        # Set a high value to trigger threshold
        state.channels["ch_g_a"] = 70.0
        events = check_thresholds(state, thresholds_cfg)
        warn_events = [e for e in events if e.event_id == "ev_g_a_warn"]
        self.assertGreaterEqual(len(warn_events), 1)

        # Render narrative
        for ev in events:
            text = render_event(ev.event_id, narratives_cfg, ev.event_type)
            self.assertIsInstance(text, str)
            if ev.event_id == "ev_g_a_warn":
                self.assertIn("Metric A", text)

    def test_05_body_model_integrated(self):
        """Body model loads and maps to engine context."""
        from dlc.body import AnatomyLoader, BodyModel
        from dlc.context import CardRuntimeContext

        card_dir = os.path.join(CARDS, "demo-l1")
        # Body config is loaded via resolver
        from dlc.resolver import ConfigResolver
        resolver = ConfigResolver(card_dir)
        body_dir = os.path.join(card_dir, "body")
        al = AnatomyLoader(body_dir)
        body = al.load()
        self.assertIsInstance(body, BodyModel)
        self.assertEqual(body.body_model, "simple")
        self.assertIn("core", body.regions)


# ═══════════════════════════════════════════════════════════════
# P1-22: End-to-end tests
# ═══════════════════════════════════════════════════════════════

class TestEndToEnd(unittest.TestCase):
    """P1-22: Card load → validate → identity → body → engine full chain."""

    def test_01_l0_full_chain(self):
        """L0 card: load → validate → identity → prompt → welcome."""
        card_dir = os.path.join(CARDS, "demo-l0")
        from dlc.loader import load_card
        from dlc.validate import validate_card
        from dlc.identity import ProfileLoader, PersonalityLoader, Speech
        from dlc.identity import generate_system_prompt, get_welcome_message

        cfg = load_card(card_dir)
        errors = validate_card(cfg._raw)
        self.assertEqual(errors, [])

        id_dir = os.path.join(card_dir, "identity")
        profile = ProfileLoader(id_dir).load()
        personality = PersonalityLoader(id_dir).load()
        speech = Speech(speech_style="中性", address_user=["用户"])
        prompt = generate_system_prompt(profile, personality, speech)
        self.assertIn(profile.name, prompt)

        from dlc.context import CardRuntimeContext
        ctx = CardRuntimeContext(card_dir)
        # Use a temp dir to avoid persisted welcome flag from prior runs
        tmp = tempfile.mkdtemp()
        try:
            msg = get_welcome_message(profile, tmp)
            self.assertIsNotNone(msg)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_02_l1_full_chain(self):
        """L1 card: load → validate → body → engine → stimulus pipeline."""
        card_dir = os.path.join(CARDS, "demo-l1")
        from dlc.loader import load_card
        from dlc.validate import validate_card
        from dlc.identity import ProfileLoader, PersonalityLoader
        from dlc.body import AnatomyLoader
        from dlc.context import CardRuntimeContext
        from dlc.engine.entity import EntityEngine, EntityState
        from dlc.engine.modifier import apply_modifier
        from dlc.engine.threshold import check_thresholds
        from dlc.engine.narrator import render_event

        # Validate
        cfg = load_card(card_dir)
        errors = validate_card(cfg._raw)
        self.assertEqual(errors, [])

        # Identity
        id_dir = os.path.join(card_dir, "identity")
        profile = ProfileLoader(id_dir).load()
        self.assertEqual(profile.name, "感知体")

        # Body
        body = AnatomyLoader(os.path.join(card_dir, "body")).load()
        self.assertEqual(body.get_state("core"), 0)

        # Engine full pipeline
        ctx = CardRuntimeContext(card_dir)
        eng = EntityEngine(state_dir=ctx.state_dir)
        e_g = ctx.entities["entities"]["e_g"]
        chans = {k: float(v.get("initial", 0)) for k, v in e_g["channels"].items()}
        state = EntityState(entity_id="e_g", channels=chans)

        modifiers_cfg = ctx.modifiers.get("modifiers", {})
        thresholds_cfg = ctx.thresholds.get("thresholds", {})
        narratives_cfg = ctx.narratives.get("events", {})

        # Stimulus →叙事 完整闭环
        apply_modifier(state, modifiers_cfg["mod_eg_av_add"])
        state.channels["ch_g_a"] = 95
        events = check_thresholds(state, thresholds_cfg)
        self.assertGreaterEqual(len(events), 2)

        texts = [render_event(e.event_id, narratives_cfg, e.event_type) for e in events]
        self.assertTrue(any("⛔" in t for t in texts))


if __name__ == "__main__":
    unittest.main()
