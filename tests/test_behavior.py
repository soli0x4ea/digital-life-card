"""Phase 2C: LWS Behavior rules tests — P2-17 ~ P2-21."""

import unittest, json, os, sys, tempfile, shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
sys.path.insert(0, _PROJ)
_FIX = os.path.join(_HERE, "fixtures", "behavior")


class TestLWSLoader(unittest.TestCase):
    """P2-17: Load behavior/lws_rules.json."""

    def test_01_load_rules(self):
        from dlc.behavior.lws import LWSLoader
        ruleset = LWSLoader(_FIX).load()
        self.assertEqual(len(ruleset.core_principles), 3)
        self.assertEqual(len(ruleset.rules), 3)

    def test_02_principles_content(self):
        from dlc.behavior.lws import LWSLoader
        ruleset = LWSLoader(_FIX).load()
        self.assertIn("诚实", ruleset.core_principles[0])


class TestLWSConditionEval(unittest.TestCase):
    """P2-18: Rule condition evaluation."""

    @classmethod
    def setUpClass(cls):
        from dlc.behavior.lws import LWSLoader
        cls.ruleset = LWSLoader(_FIX).load()

    def setUp(self):
        from dlc.engine.entity import EntityState
        self.state = EntityState(entity_id="e_g")
        self.state.channels["ch_g_a"] = 80.0
        self.state.channels["ch_g_v"] = 20.0

    def test_01_channel_min_condition(self):
        from dlc.behavior.lws import evaluate_active_rules
        active = evaluate_active_rules(self.ruleset, self.state)
        ids = [r.id for r in active]
        self.assertIn("pain_warning", ids)

    def test_02_flag_set_condition(self):
        from dlc.behavior.lws import evaluate_active_rules
        self.state.flags["ch_g_flag_01"] = 1
        active = evaluate_active_rules(self.ruleset, self.state)
        ids = [r.id for r in active]
        self.assertIn("flag01_behavior", ids)

    def test_03_flag_not_set_not_active(self):
        from dlc.behavior.lws import evaluate_active_rules
        active = evaluate_active_rules(self.ruleset, self.state)
        ids = [r.id for r in active]
        self.assertNotIn("flag01_behavior", ids)

    def test_04_channel_max_condition(self):
        from dlc.behavior.lws import evaluate_active_rules
        active = evaluate_active_rules(self.ruleset, self.state)
        ids = [r.id for r in active]
        self.assertIn("low_priority", ids)


class TestLWSPriority(unittest.TestCase):
    """P2-19: Priority sorting + P2-20 Prompt injection + P2-21 Core principles."""

    @classmethod
    def setUpClass(cls):
        from dlc.behavior.lws import LWSLoader
        cls.ruleset = LWSLoader(_FIX).load()

    def setUp(self):
        from dlc.engine.entity import EntityState
        self.state = EntityState(entity_id="e_g")
        self.state.channels["ch_g_a"] = 80.0
        self.state.channels["ch_g_v"] = 20.0
        self.state.flags["ch_g_flag_01"] = 1

    def test_01_active_rules_sorted_by_priority(self):
        from dlc.behavior.lws import evaluate_active_rules
        active = evaluate_active_rules(self.ruleset, self.state)
        self.assertEqual(active[0].id, "flag01_behavior")  # prio 8
        self.assertEqual(active[-1].id, "low_priority")     # prio 2

    def test_02_generate_prompt_includes_principles(self):
        from dlc.behavior.lws import evaluate_active_rules, generate_lws_prompt
        active = evaluate_active_rules(self.ruleset, self.state)
        prompt = generate_lws_prompt(self.ruleset, active)
        self.assertIn("[核心原则]", prompt)
        self.assertIn("诚实", prompt)

    def test_03_generate_prompt_includes_rule_templates(self):
        from dlc.behavior.lws import evaluate_active_rules, generate_lws_prompt
        active = evaluate_active_rules(self.ruleset, self.state)
        prompt = generate_lws_prompt(self.ruleset, active)
        self.assertIn("flag_01 已激活", prompt)

    def test_04_prompt_variable_interpolation(self):
        from dlc.behavior.lws import evaluate_active_rules, generate_lws_prompt
        active = evaluate_active_rules(self.ruleset, self.state)
        prompt = generate_lws_prompt(self.ruleset, active, state=self.state)
        self.assertIn("80.0", prompt)  # ch_g_a value interpolated

    def test_05_core_principles_always_present(self):
        """P2-21: Core principles injected regardless of active rules."""
        from dlc.behavior.lws import evaluate_active_rules, generate_lws_prompt
        self.state.channels["ch_g_a"] = 0.0
        self.state.channels["ch_g_v"] = 100.0
        self.state.flags = {}
        active = evaluate_active_rules(self.ruleset, self.state)
        prompt = generate_lws_prompt(self.ruleset, active)
        self.assertIn("[核心原则]", prompt)
        self.assertEqual(len(active), 0)


if __name__ == "__main__":
    unittest.main()
