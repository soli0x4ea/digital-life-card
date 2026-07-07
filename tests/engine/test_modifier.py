#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engine/modifier.py — 16 modifiers, intensity, strain_mult, lock, batch."""

import os, sys, unittest

_scripts_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts"
)
sys.path.insert(0, _scripts_dir)

from engine.modifier import (
    apply_modifier, apply_modifiers_batch, list_modifier_ids,
    get_modifier_config, ModifierResult, _compute_delta,
)
from engine.entity import load_entity, reset_entity, get_channel, set_flag


class TestModifierConfig(unittest.TestCase):
    """Configuration validation tests."""

    def test_01_16_modifiers_registered(self):
        ids = list_modifier_ids()
        self.assertEqual(len(ids), 16, f"Expected 16, got {len(ids)}: {ids}")

    def test_02_all_configs_loadable(self):
        for mid in list_modifier_ids():
            cfg = get_modifier_config(mid)
            self.assertIn("target_entity", cfg)

    def test_03_no_pain_in_labels(self):
        for mid in list_modifier_ids():
            cfg = get_modifier_config(mid)
            combined = cfg.get("label", "") + cfg.get("description", "")
            self.assertNotIn("pain", combined.lower(), f"{mid} contains 'pain'")


class TestDeltaComputation(unittest.TestCase):
    """Tests for _compute_delta."""

    def test_04_positive_no_random(self):
        d = _compute_delta(base=10, random_range=0, intensity=1, strain_mult=1.0, decimal_precision=0)
        self.assertEqual(d, 10)

    def test_05_negative_no_random(self):
        d = _compute_delta(base=-5, random_range=0, intensity=1, strain_mult=1.0, decimal_precision=0)
        self.assertEqual(d, -5)

    def test_06_intensity_multiplier(self):
        d = _compute_delta(base=10, random_range=0, intensity=3, strain_mult=1.0, decimal_precision=0)
        self.assertEqual(d, 30)

    def test_07_strain_mult(self):
        d = _compute_delta(base=10, random_range=0, intensity=1, strain_mult=2.0, decimal_precision=0)
        self.assertEqual(d, 20)

    def test_08_random_range(self):
        for _ in range(20):
            d = _compute_delta(base=15, random_range=5, intensity=1, strain_mult=1.0, decimal_precision=0)
            self.assertGreaterEqual(d, 10)
            self.assertLessEqual(d, 20)

    def test_09_float_precision(self):
        d = _compute_delta(base=0.02, random_range=0, intensity=1, strain_mult=1.0, decimal_precision=2)
        self.assertEqual(d, 0.02)


class TestModifierApplication(unittest.TestCase):
    """End-to-end modifier application tests."""

    def setUp(self):
        for eid in ["e_g", "e_b", "e_r", "e_x"]:
            reset_entity(eid)

    def tearDown(self):
        for eid in ["e_g", "e_b", "e_r", "e_x"]:
            reset_entity(eid)

    # ── 10. Primary stimulus (add, with random) ────────────
    def test_10_stim_primary(self):
        r = apply_modifier("mod_stim_primary", intensity=3)
        self.assertEqual(r.effect_type, "channel")
        self.assertIn("ch_g_a", r.deltas)
        self.assertGreaterEqual(get_channel("e_g", "ch_g_a"), 30)   # 15*3 - 5*3 = 30 min
        self.assertLessEqual(get_channel("e_g", "ch_g_a"), 60)      # 15*3 + 5*3 = 60 max

    # ── 11. Cleanse stimulus (negative + positive) ─────────
    def test_11_cleanse(self):
        # First add some shame
        apply_modifier("mod_stim_primary", intensity=4)
        old_s = get_channel("e_g", "ch_g_s")
        r = apply_modifier("mod_stim_cleanse", intensity=5)
        new_s = get_channel("e_g", "ch_g_s")
        # S should decrease (negative base)
        self.assertIn("ch_g_s", r.deltas)
        self.assertIn("ch_g_v", r.deltas)

    # ── 12. Doodle shame ───────────────────────────────────
    def test_12_doodle(self):
        r = apply_modifier("mod_doodle_shame", intensity=1)
        self.assertIn("ch_g_s", r.deltas)
        new_s = get_channel("e_g", "ch_g_s")
        self.assertGreaterEqual(new_s, 0)
        self.assertLessEqual(new_s, 20)

    # ── 13. LWS signal ─────────────────────────────────────
    def test_13_lws(self):
        r = apply_modifier("mod_lws_signal", intensity=2)
        self.assertIn("ch_g_a", r.deltas)
        a = get_channel("e_g", "ch_g_a")
        self.assertGreaterEqual(a, 0)
        self.assertLessEqual(a, 80)

    # ── 14. Time decay ─────────────────────────────────────
    def test_14_time_decay(self):
        set_flag("e_g", "ch_g_locked", 0)
        apply_modifier("mod_stim_primary", intensity=3)
        a_before = get_channel("e_g", "ch_g_a")
        r = apply_modifier("mod_time_decay", intensity=1)
        a_after = get_channel("e_g", "ch_g_a")
        self.assertLess(a_after, a_before)

    # ── 15. Flag toggle (bound) ────────────────────────────
    def test_15_bound_toggle(self):
        r = apply_modifier("mod_bound_toggle")
        self.assertEqual(r.effect_type, "flag_toggle")
        self.assertEqual(r.note, "ch_g_bound: 0→1")
        e = load_entity("e_g")
        self.assertEqual(e.flags.get("ch_g_bound"), 1)
        apply_modifier("mod_bound_toggle")
        e2 = load_entity("e_g")
        self.assertEqual(e2.flags.get("ch_g_bound"), 0)

    # ── 16. Flag toggle (lock) ─────────────────────────────
    def test_16_lock_toggle(self):
        r = apply_modifier("mod_lock_toggle")
        self.assertEqual(r.effect_type, "flag_toggle")
        e = load_entity("e_g")
        self.assertEqual(e.flags.get("ch_g_locked"), 1)

    # ── 17. Strain multiplier (bound = 2x) ────────────────
    def test_17_bound_strain(self):
        set_flag("e_g", "ch_g_bound", 1)
        r = apply_modifier("mod_stim_primary", intensity=1, strain_mult=2.0)
        a = get_channel("e_g", "ch_g_a")
        # strain_mult=2 → base 15*2=30 ± random
        self.assertGreaterEqual(a, 20)
        self.assertLessEqual(a, 40)

    # ── 18. Lock prevents Metric V change ──────────────────
    def test_18_lock_freezes_v(self):
        set_flag("e_g", "ch_g_locked", 1)
        v_before = get_channel("e_g", "ch_g_v")
        r = apply_modifier("mod_stim_primary", intensity=5)
        v_after = get_channel("e_g", "ch_g_v")
        # Primary stimulus affects ch_g_a AND ch_g_v → with lock, V unchanged
        self.assertEqual(v_after, v_before)
        self.assertNotIn("ch_g_v", r.deltas)

    # ── 19. Body zone state_set ────────────────────────────
    def test_19_body_zone_numb(self):
        r = apply_modifier("mod_b_numb", zone="ch_b_03")
        self.assertEqual(r.effect_type, "state_set")
        self.assertEqual(get_channel("e_b", "ch_b_03"), 1)

    def test_20_body_zone_break(self):
        apply_modifier("mod_b_numb", zone="ch_b_05")
        r = apply_modifier("mod_b_break", zone="ch_b_05")
        self.assertEqual(get_channel("e_b", "ch_b_05"), 2)

    # ── 20. Body batch_restore ─────────────────────────────
    def test_21_batch_restore(self):
        apply_modifier("mod_b_numb", zone="ch_b_01")
        apply_modifier("mod_b_numb", zone="ch_b_02")
        apply_modifier("mod_b_numb", zone="ch_b_03")
        r = apply_modifier("mod_b_restore")
        self.assertEqual(r.effect_type, "batch_restore")
        self.assertIn("restored 3/3", r.note)
        for ch in ["ch_b_01", "ch_b_02", "ch_b_03"]:
            self.assertEqual(get_channel("e_b", ch), 0)

    # ── 21. Recovery add/consume ───────────────────────────
    def test_22_recovery_add_consume(self):
        r = apply_modifier("mod_r_add", intensity=3)
        self.assertEqual(get_channel("e_r", "ch_r_count"), 18)  # 15 + 3
        r = apply_modifier("mod_r_consume", intensity=1)
        self.assertEqual(get_channel("e_r", "ch_r_count"), 17)

    # ── 22. Recovery set ───────────────────────────────────
    def test_23_recovery_set(self):
        r = apply_modifier("mod_r_set", intensity=50)
        self.assertEqual(get_channel("e_r", "ch_r_count"), 50)

    # ── 23. Zone switch ────────────────────────────────────
    def test_24_zone_switch(self):
        r = apply_modifier("mod_x_switch", intensity=1)
        self.assertEqual(r.effect_type, "channel")
        self.assertEqual(get_channel("e_x", "ch_x_area"), 1)

    # ── 24. Stimulus record ────────────────────────────────
    def test_25_stimulus_record(self):
        for _ in range(5):
            apply_modifier("mod_x_record")
        self.assertEqual(get_channel("e_x", "ch_x_count"), 5)

    # ── 25. Batch apply ────────────────────────────────────
    def test_26_batch_apply(self):
        specs = [
            {"modifier": "mod_stim_primary", "intensity": 2},
            {"modifier": "mod_doodle_shame", "intensity": 1},
            {"modifier": "mod_bound_toggle"},
        ]
        results = apply_modifiers_batch(specs)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].modifier_id, "mod_stim_primary")
        self.assertEqual(results[2].modifier_id, "mod_bound_toggle")
        a = get_channel("e_g", "ch_g_a")
        self.assertGreaterEqual(a, 20)  # 15*2 - 5*2 = 20 min

    # ── 26. Clamp prevents overflow ────────────────────────
    def test_27_clamp_prevents_overflow(self):
        for _ in range(10):
            apply_modifier("mod_stim_primary", intensity=10)
        a = get_channel("e_g", "ch_g_a")
        self.assertLessEqual(a, 100)

    # ── 27. Intensity range clamping ───────────────────────
    def test_28_intensity_range_clamp(self):
        r = apply_modifier("mod_time_decay", intensity=999)
        self.assertEqual(r.intensity, 1)  # clamped to [1,1]


if __name__ == "__main__":
    unittest.main(verbosity=2)
