"""Phase 1C: Simplified engine tests — P1-13 ~ P1-19."""

import unittest, json, os, sys, tempfile, shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
sys.path.insert(0, _PROJ)

_FIX = os.path.join(_HERE, "fixtures", "engine")


def _setup_engine():
    """Create a minimal engine context with fixture configs."""
    from dlc.engine.entity import EntityState, EntityEngine
    tmp = tempfile.mkdtemp()
    eng = EntityEngine(state_dir=tmp)
    # Create e_g entity from fixture
    with open(os.path.join(_FIX, "entities.json")) as f:
        entities_cfg = json.load(f)
    for eid, ecfg in entities_cfg["entities"].items():
        channels = {k: float(v.get("initial", 0)) for k, v in ecfg["channels"].items()}
        flags = {k: 0 for k in ecfg.get("flags", {})}
        eng.save(EntityState(entity_id=eid, channels=channels, flags=flags))
    return eng, tmp


# ═══════════════════════════════════════════════════════════════
# P1-13~15: Modifier effect types
# ═══════════════════════════════════════════════════════════════

class TestModifierEffects(unittest.TestCase):
    """P1-13 add, P1-14 set, P1-15 flag_toggle."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(_FIX, "modifiers.json")) as f:
            cls.modifiers_cfg = json.load(f)["modifiers"]

    def setUp(self):
        self.eng, self.tmp = _setup_engine()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_add_effect_increases_channel(self):
        from dlc.engine.modifier import calc_delta
        delta = calc_delta({"type": "add", "base": 3, "random": 2})
        self.assertGreaterEqual(delta, 3)
        self.assertLessEqual(delta, 5)

    def test_02_apply_add_modifier(self):
        from dlc.engine.modifier import apply_effect
        state = self.eng.load("e_g")
        orig_a = state.channels.get("ch_g_a", 0)
        apply_effect(state, "ch_g_a", self.modifiers_cfg["mod_eg_av_add"]["effects"]["ch_g_a"])
        self.assertGreater(state.channels["ch_g_a"], orig_a)

    def test_03_set_effect_sets_exact(self):
        from dlc.engine.modifier import apply_effect
        state = self.eng.load("e_g")
        apply_effect(state, "ch_g_s", {"type": "set", "base": 50, "random": 0})
        self.assertEqual(state.channels["ch_g_s"], 50.0)

    def test_04_flag_toggle_flips(self):
        from dlc.engine.modifier import apply_flag_toggle
        state = self.eng.load("e_g")
        self.assertEqual(state.flags.get("ch_g_flag_01", 0), 0)
        apply_flag_toggle(state, "ch_g_flag_01")
        self.assertEqual(state.flags["ch_g_flag_01"], 1)
        apply_flag_toggle(state, "ch_g_flag_01")
        self.assertEqual(state.flags["ch_g_flag_01"], 0)

    def test_05_apply_modifier_full_pipeline(self):
        from dlc.engine.modifier import apply_modifier
        state = self.eng.load("e_g")
        result = apply_modifier(state, self.modifiers_cfg["mod_eg_av_add"])
        self.assertTrue(result.applied)
        self.assertEqual(len(result.deltas), 2)
        self.assertIn("ch_g_a", result.deltas)
        self.assertIn("ch_g_v", result.deltas)

    def test_06_apply_modifier_unknown_type_noop(self):
        from dlc.engine.modifier import apply_modifier
        state = self.eng.load("e_g")
        result = apply_modifier(state, {
            "target_entity": "e_g",
            "effects": {"ch_g_a": {"type": "unknown", "base": 1, "random": 0}}
        })
        self.assertFalse(result.applied)


# ═══════════════════════════════════════════════════════════════
# P1-16~17: Threshold detection
# ═══════════════════════════════════════════════════════════════

class TestThresholdDetection(unittest.TestCase):
    """P1-16 rising, P1-17 falling."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(_FIX, "thresholds.json")) as f:
            cls.thresholds = json.load(f)["thresholds"]

    def setUp(self):
        self.eng, self.tmp = _setup_engine()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_rising_triggers(self):
        from dlc.engine.threshold import check_thresholds, ThresholdEvent
        state = self.eng.load("e_g")
        state.channels["ch_g_a"] = 70.0
        events = check_thresholds(state, self.thresholds)
        ids = [e.event_id for e in events]
        self.assertIn("ev_g_a_warn", ids)

    def test_02_below_threshold_no_trigger(self):
        from dlc.engine.threshold import check_thresholds
        state = self.eng.load("e_g")
        state.channels["ch_g_a"] = 30.0
        events = check_thresholds(state, self.thresholds)
        self.assertEqual(len(events), 0)

    def test_03_multiple_thresholds_trigger(self):
        from dlc.engine.threshold import check_thresholds
        state = self.eng.load("e_g")
        state.channels["ch_g_a"] = 95.0
        events = check_thresholds(state, self.thresholds)
        ids = [e.event_id for e in events]
        self.assertIn("ev_g_a_warn", ids)
        self.assertIn("ev_g_a_crit", ids)

    def test_04_falling_below_noop(self):
        """Operator >= should NOT trigger when value drops below threshold."""
        from dlc.engine.threshold import check_thresholds
        state = self.eng.load("e_g")
        state.channels["ch_g_a"] = 50.0  # below 60
        events = check_thresholds(state, self.thresholds)
        self.assertEqual(len(events), 0)

    def test_05_peak_event_triggers(self):
        from dlc.engine.threshold import check_thresholds
        state = self.eng.load("e_g")
        state.channels["ch_g_v"] = 100.0
        events = check_thresholds(state, self.thresholds)
        ids = [e.event_id for e in events]
        self.assertIn("ev_g_v_peak", ids)


# ═══════════════════════════════════════════════════════════════
# P1-18: Narrative rendering
# ═══════════════════════════════════════════════════════════════

class TestNarrativeRendering(unittest.TestCase):
    """P1-18: Event → narrative text mapping."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(_FIX, "narratives.json")) as f:
            cls.narratives = json.load(f)["events"]

    def test_01_render_warning_medium(self):
        from dlc.engine.narrator import render_event
        text = render_event("ev_g_a_warn", self.narratives, "warning")
        self.assertIn("Metric A", text)

    def test_02_render_critical_intense(self):
        from dlc.engine.narrator import render_event
        text = render_event("ev_g_a_crit", self.narratives, "critical")
        self.assertIn("⛔", text)

    def test_03_unknown_event_returns_empty(self):
        from dlc.engine.narrator import render_event
        text = render_event("nonexistent", self.narratives, "warning")
        self.assertEqual(text, "")

    def test_04_severity_fallback_to_intense(self):
        from dlc.engine.narrator import render_event
        text = render_event("ev_g_a_warn", self.narratives, "unknown")
        self.assertIn("⚠", text)


# ═══════════════════════════════════════════════════════════════
# P1-19: State natural decay
# ═══════════════════════════════════════════════════════════════

class TestStateDecay(unittest.TestCase):
    """P1-19: Natural decay of channel values per tick."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(_FIX, "entities.json")) as f:
            cls.entities_cfg = json.load(f)["entities"]

    def setUp(self):
        self.eng, self.tmp = _setup_engine()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_decay_reduces_channel(self):
        from dlc.engine.entity import apply_decay
        state = self.eng.load("e_g")
        state.channels["ch_g_a"] = 50.0
        apply_decay(state, self.entities_cfg["e_g"])
        self.assertLess(state.channels["ch_g_a"], 50.0)

    def test_02_decay_does_not_go_below_zero(self):
        from dlc.engine.entity import apply_decay
        state = self.eng.load("e_g")
        state.channels["ch_g_a"] = 0.5
        apply_decay(state, self.entities_cfg["e_g"])
        self.assertGreaterEqual(state.channels["ch_g_a"], 0)

    def test_03_no_decay_config_no_change(self):
        from dlc.engine.entity import apply_decay
        state = self.eng.load("e_g")
        state.channels["ch_g_s"] = 30.0
        apply_decay(state, self.entities_cfg["e_g"])  # ch_g_s has no decay_per_tick
        self.assertEqual(state.channels["ch_g_s"], 30.0)


# ═══════════════════════════════════════════════════════════════
# P2-01: state_set effect (timed state with auto-restore)
# ═══════════════════════════════════════════════════════════════

class TestStateSetEffect(unittest.TestCase):
    """P2-01: state_set effect type — set+timed+auto-restore."""

    def setUp(self):
        self.eng, self.tmp = _setup_engine()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_state_set_saves_original(self):
        """state_set should save the original value before setting."""
        from dlc.engine.modifier import apply_effect
        state = self.eng.load("e_g")
        orig = state.channels["ch_g_a"]
        effect = {"type": "state_set", "base": 90, "random": 0, "duration_ticks": 3}
        apply_effect(state, "ch_g_a", effect)
        self.assertEqual(state.channels["ch_g_a"], 90.0)
        self.assertIn("_state_set", state.meta)
        self.assertIn("ch_g_a", state.meta["_state_set"])
        self.assertEqual(state.meta["_state_set"]["ch_g_a"]["original"], orig)

    def test_02_tick_decrements_duration(self):
        """tick_timed_effects should decrement remaining ticks."""
        from dlc.engine.modifier import apply_effect, tick_timed_effects
        state = self.eng.load("e_g")
        apply_effect(state, "ch_g_a", {"type": "state_set", "base": 90, "random": 0, "duration_ticks": 3})
        self.assertEqual(state.meta["_state_set"]["ch_g_a"]["remaining"], 3)
        tick_timed_effects(state)
        self.assertEqual(state.meta["_state_set"]["ch_g_a"]["remaining"], 2)

    def test_03_auto_restore_on_expiry(self):
        """When remaining hits 0, original value should be restored."""
        from dlc.engine.modifier import apply_effect, tick_timed_effects
        state = self.eng.load("e_g")
        orig = state.channels["ch_g_a"]
        apply_effect(state, "ch_g_a", {"type": "state_set", "base": 90, "random": 0, "duration_ticks": 2})
        self.assertEqual(state.channels["ch_g_a"], 90.0)
        tick_timed_effects(state)  # remaining 1
        self.assertEqual(state.channels["ch_g_a"], 90.0)
        tick_timed_effects(state)  # remaining 0 → restore
        self.assertEqual(state.channels["ch_g_a"], orig)

    def test_04_state_set_cleanup_after_restore(self):
        """After restore, meta entry should be cleaned up."""
        from dlc.engine.modifier import apply_effect, tick_timed_effects
        state = self.eng.load("e_g")
        apply_effect(state, "ch_g_a", {"type": "state_set", "base": 90, "random": 0, "duration_ticks": 1})
        tick_timed_effects(state)
        self.assertNotIn("ch_g_a", state.meta.get("_state_set", {}))

    def test_05_state_set_overwrite_resets_timer(self):
        """A second state_set on same channel resets the timer."""
        from dlc.engine.modifier import apply_effect, tick_timed_effects
        state = self.eng.load("e_g")
        orig = state.channels["ch_g_a"]
        apply_effect(state, "ch_g_a", {"type": "state_set", "base": 90, "random": 0, "duration_ticks": 5})
        tick_timed_effects(state)  # remaining 4
        apply_effect(state, "ch_g_a", {"type": "state_set", "base": 99, "random": 0, "duration_ticks": 2})
        self.assertEqual(state.channels["ch_g_a"], 99.0)
        self.assertEqual(state.meta["_state_set"]["ch_g_a"]["remaining"], 2)
        # Original is still the first original (before state_set was applied)
        self.assertEqual(state.meta["_state_set"]["ch_g_a"]["original"], orig)

    def test_06_no_state_set_ticks_nothing(self):
        """tick_timed_effects on state without _state_set should be no-op."""
        from dlc.engine.modifier import tick_timed_effects
        state = self.eng.load("e_g")
        tick_timed_effects(state)  # should not crash
        self.assertEqual(state.meta.get("_state_set", {}), {})


# ═══════════════════════════════════════════════════════════════
# P2-02: batch_restore effect
# ═══════════════════════════════════════════════════════════════

class TestBatchRestoreEffect(unittest.TestCase):
    """P2-02: batch_restore effect type — restore N damaged channels."""

    def setUp(self):
        self.eng, self.tmp = _setup_engine()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_batch_restore_single(self):
        """batch_restore(1) should restore 1 state_set channel."""
        from dlc.engine.modifier import apply_effect
        state = self.eng.load("e_g")
        orig_a = state.channels["ch_g_a"]
        apply_effect(state, "ch_g_a", {"type": "state_set", "base": 90, "random": 0, "duration_ticks": 3})
        # Now ch_g_a is modified
        apply_effect(state, "ch_g_a", {"type": "batch_restore", "count": 1})
        self.assertEqual(state.channels["ch_g_a"], orig_a)
        self.assertNotIn("ch_g_a", state.meta.get("_state_set", {}))

    def test_02_batch_restore_multiple(self):
        """batch_restore(2) should restore 2 oldest state_set channels."""
        from dlc.engine.modifier import apply_effect
        state = self.eng.load("e_g")
        orig_a = state.channels["ch_g_a"]
        orig_s = state.channels["ch_g_s"]
        apply_effect(state, "ch_g_a", {"type": "state_set", "base": 90, "random": 0, "duration_ticks": 3})
        apply_effect(state, "ch_g_s", {"type": "state_set", "base": 80, "random": 0, "duration_ticks": 3})
        apply_effect(state, "ch_g_a", {"type": "batch_restore", "count": 2})
        self.assertEqual(state.channels["ch_g_a"], orig_a)
        self.assertEqual(state.channels["ch_g_s"], orig_s)

    def test_03_batch_restore_count_exceeds(self):
        """batch_restore with count > affected channels restores all."""
        from dlc.engine.modifier import apply_effect
        state = self.eng.load("e_g")
        orig = state.channels["ch_g_a"]
        apply_effect(state, "ch_g_a", {"type": "state_set", "base": 90, "random": 0, "duration_ticks": 3})
        apply_effect(state, "ch_g_a", {"type": "batch_restore", "count": 99})
        self.assertEqual(state.channels["ch_g_a"], orig)

    def test_04_batch_restore_noop_on_clean(self):
        """batch_restore on state with no state_set should be no-op."""
        from dlc.engine.modifier import apply_effect
        state = self.eng.load("e_g")
        apply_effect(state, "ch_g_a", {"type": "batch_restore", "count": 1})
        # nothing changed
        self.assertEqual(len(state.meta.get("_state_set", {})), 0)


# ═══════════════════════════════════════════════════════════════
# P2-03: Auto-trigger + P2-04: Cooldown
# ═══════════════════════════════════════════════════════════════

class TestAutoTriggerAndCooldown(unittest.TestCase):

    def setUp(self):
        self.eng, self.tmp = _setup_engine()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_cooldown_blocks_within_period(self):
        from dlc.engine.modifier import apply_modifier
        state = self.eng.load("e_g")
        mod = {"label": "test_mod", "target_entity": "e_g", "cooldown_ticks": 3,
               "effects": {"ch_g_a": {"type": "add", "base": 1, "random": 0}}}
        r1 = apply_modifier(state, mod, tick=0)
        self.assertTrue(r1.applied)
        r2 = apply_modifier(state, mod, tick=1)
        self.assertFalse(r2.applied)

    def test_02_cooldown_allows_after_expiry(self):
        from dlc.engine.modifier import apply_modifier
        state = self.eng.load("e_g")
        mod = {"label": "test_mod", "target_entity": "e_g", "cooldown_ticks": 2,
               "effects": {"ch_g_a": {"type": "add", "base": 1, "random": 0}}}
        apply_modifier(state, mod, tick=0)
        r = apply_modifier(state, mod, tick=3)
        self.assertTrue(r.applied)

    def test_03_auto_trigger_100pct_fires(self):
        from dlc.engine.modifier import maybe_auto_trigger
        state = self.eng.load("e_g")
        r = maybe_auto_trigger(state, "mod_eg_av_add",
            {"trigger_probability": 1.0},
            {"mod_eg_av_add": {"target_entity": "e_g",
             "effects": {"ch_g_a": {"type": "add", "base": 1, "random": 0}}}})
        self.assertTrue(r.applied)

    def test_04_auto_trigger_0pct_never_fires(self):
        from dlc.engine.modifier import maybe_auto_trigger
        state = self.eng.load("e_g")
        r = maybe_auto_trigger(state, "mod_eg_av_add",
            {"trigger_probability": 0.0},
            {"mod_eg_av_add": {"target_entity": "e_g",
             "effects": {"ch_g_a": {"type": "add", "base": 1, "random": 0}}}})
        self.assertFalse(r.applied)

    def test_05_cooldown_shared_with_auto_trigger(self):
        from dlc.engine.modifier import apply_modifier, maybe_auto_trigger
        state = self.eng.load("e_g")
        mod_cfg = {"target_entity": "e_g", "cooldown_ticks": 5,
                   "effects": {"ch_g_a": {"type": "add", "base": 1, "random": 0}}}
        mods = {"mod_test": mod_cfg}
        apply_modifier(state, mod_cfg, tick=0)
        r = maybe_auto_trigger(state, "mod_test",
            {"trigger_probability": 1.0}, mods, tick=1)
        self.assertFalse(r.applied)


# ═══════════════════════════════════════════════════════════════
# P2-05: Threshold cooldown + rearm
# ═══════════════════════════════════════════════════════════════

class TestThresholdCooldown(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(_FIX, "thresholds.json")) as f:
            cls.thresholds = json.load(f)["thresholds"]

    def setUp(self):
        self.eng, self.tmp = _setup_engine()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_cooldown_suppresses_repeat(self):
        from dlc.engine.threshold import check_thresholds
        state = self.eng.load("e_g")
        state.channels["ch_g_a"] = 80.0
        # Add cooldown_ticks to a threshold
        thr_w_cd = dict(self.thresholds)
        for v in thr_w_cd.values():
            if v.get("channel") == "ch_g_a":
                v["cooldown_ticks"] = 5
        e1 = check_thresholds(state, thr_w_cd, tick=0)
        self.assertGreater(len(e1), 0)
        e2 = check_thresholds(state, thr_w_cd, tick=1)
        self.assertEqual(len(e2), 0)

    def test_02_cooldown_expires_re_arms(self):
        from dlc.engine.threshold import check_thresholds
        state = self.eng.load("e_g")
        state.channels["ch_g_a"] = 80.0
        check_thresholds(state, self.thresholds, tick=0)
        e2 = check_thresholds(state, self.thresholds, tick=10)
        self.assertGreater(len(e2), 0)

    def test_03_no_cooldown_config_fires_every_time(self):
        from dlc.engine.threshold import check_thresholds
        state = self.eng.load("e_g")
        state.channels["ch_g_a"] = 80.0
        # Use thresholds with no cooldown configured
        thr_no_cd = {k: {**v} for k, v in self.thresholds.items()}
        for v in thr_no_cd.values():
            v.pop("cooldown_ticks", None)
        e1 = check_thresholds(state, thr_no_cd, tick=0)
        e2 = check_thresholds(state, thr_no_cd, tick=1)
        self.assertEqual(len(e1), len(e2))


# ═══════════════════════════════════════════════════════════════
# P2-06: Narrative condition filtering
# P2-07: Narrative priority sorting
# P2-08: 3-tier narrative selection
# ═══════════════════════════════════════════════════════════════

class TestNarrativeExtended(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(_FIX, "narratives.json")) as f:
            cls.narratives = json.load(f)["events"]

    def setUp(self):
        self.eng, self.tmp = _setup_engine()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # P2-06: condition filtering
    def test_01_condition_flag_set_blocks(self):
        """Event with flag_set condition should not render if flag is 0."""
        from dlc.engine.narrator import render_event
        state = self.eng.load("e_g")
        ev = {"texts": {"intense": "blocked"}, "condition": {"flag_set": "ch_g_flag_01"}}
        text = render_event("test_ev", {"test_ev": ev}, "critical", state)
        self.assertEqual(text, "")

    def test_02_condition_flag_set_allows(self):
        """Event with flag_set condition should render if flag is 1."""
        from dlc.engine.narrator import render_event
        state = self.eng.load("e_g")
        state.flags["ch_g_flag_01"] = 1
        ev = {"texts": {"intense": "allowed"}, "condition": {"flag_set": "ch_g_flag_01"}}
        text = render_event("test_ev", {"test_ev": ev}, "critical", state)
        self.assertEqual(text, "allowed")

    def test_03_condition_flag_unset_blocks(self):
        """Event with flag_unset condition should not render if flag is 1."""
        from dlc.engine.narrator import render_event
        state = self.eng.load("e_g")
        state.flags["ch_g_flag_01"] = 1
        ev = {"texts": {"intense": "blocked"}, "condition": {"flag_unset": "ch_g_flag_01"}}
        text = render_event("test_ev", {"test_ev": ev}, "critical", state)
        self.assertEqual(text, "")

    # P2-07: priority sorting
    def test_04_priority_higher_first(self):
        """render_events should return higher priority events first."""
        from dlc.engine.narrator import render_events
        from dlc.engine.threshold import ThresholdEvent
        e1 = ThresholdEvent("t1", "e_g", "ch_g_a", 100, 80, ">=", "ev_1", "critical")
        e2 = ThresholdEvent("t2", "e_g", "ch_g_v", 90, 70, ">=", "ev_2", "warning")
        evs = render_events([e2, e1], {
            "ev_1": {"priority": 10, "texts": {"intense": "HIGH"}},
            "ev_2": {"priority": 1, "texts": {"medium": "LOW"}},
        }, state=self.eng.load("e_g"))
        self.assertEqual(evs[0], "HIGH")
        self.assertEqual(evs[1], "LOW")

    def test_05_no_priority_defaults_to_zero(self):
        """Events without priority should default to 0."""
        from dlc.engine.narrator import render_events
        from dlc.engine.threshold import ThresholdEvent
        e = ThresholdEvent("t", "e_g", "ch_g_a", 100, 80, ">=", "ev_x", "critical")
        evs = render_events([e], {"ev_x": {"texts": {"intense": "OK"}}},
                           state=self.eng.load("e_g"))
        self.assertEqual(evs, ["OK"])


if __name__ == "__main__":
    unittest.main()
