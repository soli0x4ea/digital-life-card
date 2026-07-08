"""Phase 2E: L2 Integration tests — P2-28 ~ P2-30."""

import unittest, os, sys, tempfile, shutil, json

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
sys.path.insert(0, _PROJ)
_CARDS = os.path.join(_PROJ, "cards", "demo-l2")
_CFIX_MEM = os.path.join(_HERE, "fixtures", "memory")
_CFIX_BEH = os.path.join(_HERE, "fixtures", "behavior")
_CFIX_ENG = os.path.join(_HERE, "fixtures", "engine")


class TestL2CardSmoke(unittest.TestCase):
    """P2-28: L2 demo card — smoke test."""

    def test_01_card_loads(self):
        from dlc.loader import load_card
        cfg = load_card(_CARDS)
        self.assertEqual(cfg.card_id, "demo-l2")
        self.assertEqual(cfg.complexity_level, "L2")

    def test_02_all_modules_enabled(self):
        from dlc.loader import load_card, resolve_modules
        cfg = load_card(_CARDS)
        mods = resolve_modules(cfg)
        self.assertIn("identity", mods)
        self.assertIn("body", mods)
        self.assertIn("engine", mods)
        self.assertIn("memory", mods)
        self.assertIn("behavior", mods)

    def test_03_card_validates(self):
        from dlc.loader import load_card
        from dlc.validate import validate_card
        cfg = load_card(_CARDS)
        errors = validate_card(cfg._raw)
        self.assertEqual(errors, [])


class TestL2FullPipeline(unittest.TestCase):
    """P2-30: L2 end-to-end pipeline."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(_CFIX_ENG, "entities.json")) as f:
            cls.entities_cfg = json.load(f)["entities"]
        with open(os.path.join(_CFIX_ENG, "modifiers.json")) as f:
            cls.modifiers_cfg = json.load(f)["modifiers"]

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.engine.entity import EntityEngine, EntityState
        from dlc.memory.core import MemoryArchitecture, LayerConfig, MemoryStore
        # Engine
        self.eeng = EntityEngine(state_dir=os.path.join(self.tmp, "state"))
        state = EntityState(entity_id="e_g",
                           channels={"ch_g_a": 80.0, "ch_g_s": 20.0, "ch_g_v": 30.0},
                           flags={"ch_g_flag_01": 0})
        self.eeng.save(state)
        self.state = self.eeng.load("e_g")
        # Memory
        arch = MemoryArchitecture(
            layers=[LayerConfig("working", "WM", 3600, 100, 5)],
            consolidation={"interval_seconds": 3600, "max_per_cycle": 10}
        )
        self.store = MemoryStore(os.path.join(self.tmp, "mem"), arch)
        # LWS
        from dlc.behavior.lws import LWSLoader
        self.ruleset = LWSLoader(_CFIX_BEH).load()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_stimulus_changes_state(self):
        from dlc.engine.modifier import apply_modifier
        orig = self.state.channels["ch_g_a"]
        apply_modifier(self.state, self.modifiers_cfg["mod_eg_av_add"])
        self.assertGreater(self.state.channels["ch_g_a"], orig)

    def test_02_threshold_fires_on_high_value(self):
        from dlc.engine.threshold import check_thresholds
        import json
        with open(os.path.join(_CFIX_ENG, "thresholds.json")) as f:
            thresholds = json.load(f)["thresholds"]
        self.state.channels["ch_g_a"] = 90.0
        events = check_thresholds(self.state, thresholds)
        self.assertGreater(len(events), 0)

    def test_03_memory_writes_and_searches(self):
        self.store.write("working", "刺激事件：通道A升至90", tags=["stimulus"])
        results = self.store.search("刺激")
        self.assertEqual(len(results), 1)

    def test_04_lws_evaluates_and_generates_prompt(self):
        from dlc.behavior.lws import evaluate_active_rules, generate_lws_prompt
        active = evaluate_active_rules(self.ruleset, self.state)
        prompt = generate_lws_prompt(self.ruleset, active, state=self.state)
        self.assertIn("[核心原则]", prompt)

    def test_05_full_pipeline_roundtrip(self):
        """刺激→状态→阈值→叙事→记忆→LWS 完整闭环"""
        from dlc.engine.modifier import apply_modifier
        import json
        with open(os.path.join(_CFIX_ENG, "thresholds.json")) as f:
            thresholds = json.load(f)["thresholds"]
        from dlc.engine.threshold import check_thresholds
        from dlc.engine.narrator import render_events
        with open(os.path.join(_CFIX_ENG, "narratives.json")) as f:
            narratives = json.load(f)["events"]
        from dlc.behavior.lws import evaluate_active_rules, generate_lws_prompt

        # 1. Apply stimulus
        apply_modifier(self.state, self.modifiers_cfg["mod_eg_av_add"])
        # 2. Check thresholds
        events = check_thresholds(self.state, thresholds)
        # 3. Render narratives
        texts = render_events(events, narratives, state=self.state)
        # 4. Write to memory
        for t in texts:
            self.store.write("working", t, tags=["event"])
        # 5. Generate LWS prompt
        active = evaluate_active_rules(self.ruleset, self.state)
        prompt = generate_lws_prompt(self.ruleset, active, state=self.state)
        self.assertIn("[核心原则]", prompt)
        # Memory should have entries
        self.assertGreater(len(self.store.search("")), 0)


if __name__ == "__main__":
    unittest.main()
