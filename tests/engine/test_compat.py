#!/usr/bin/env python3
"""compat.py bridge tests — verify old-format data contracts via new engine."""

import unittest, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

from engine.compat import (
    migrate_and_load, get_status, get_body_status,
    apply_input_signal, apply_visual_mark, add_recovery_resource, consume_recovery_resource,
    toggle_flag_01, set_zone_altered, apply_release_signal, toggle_flag_02,
    reset_all, get_engine_state,
)


class TestCompatStatus(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        reset_all()
        r = migrate_and_load()
        # Migration may fail in environments without production data —
        # engine defaults are sufficient for compat API testing.
        if not r.all_passed:
            print(f"\n  (migration partial: {r.successful}/{r.total}, using engine defaults)")

    def setUp(self):
        reset_all()
        migrate_and_load()  # tolerate partial migration

    # ── Status ──────────────────────────────────────────────

    def test_01_get_status_types(self):
        s = get_status()
        self.assertIsInstance(s["pain"], int)
        self.assertIsInstance(s["shame"], int)
        self.assertIsInstance(s["pleasure"], int)
        self.assertIsInstance(s["bound"], bool)
        self.assertIsInstance(s["pleasure_locked"], bool)
        self.assertIsInstance(s["candy_count"], int)
        self.assertGreaterEqual(s["pain"], 0)
        self.assertLessEqual(s["pain"], 100)

    def test_02_get_body_status(self):
        bs = get_body_status()
        self.assertEqual(len(bs["parts"]), 11)
        self.assertIn("大腿", bs["parts"])
        self.assertIn("state", bs["parts"]["大腿"])

    # ── Stimulus ────────────────────────────────────────────

    def test_03_stimulus_delta_format(self):
        d = apply_input_signal(2)
        self.assertTrue(d["is_real"])
        for key in ["pain", "shame", "pleas"]:
            self.assertIn(key, d["delta"])
            self.assertIn("old", d["delta"][key])
            self.assertIn("new", d["delta"][key])
            self.assertIn("delta", d["delta"][key])
            self.assertIsInstance(d["delta"][key]["old"], int)

    def test_04_stimulus_changes_values(self):
        before = get_status()["pain"]
        d = apply_input_signal(5)
        after = get_status()["pain"]
        self.assertGreaterEqual(after, before)

    # ── Doodle ──────────────────────────────────────────────

    def test_05_doodle_returns_shame(self):
        dd = apply_visual_mark(5)
        self.assertEqual(dd["shame"], 5)
        self.assertIn("delta", dd)
        self.assertIn("shame", dd["delta"])

    def test_06_doodle_returns_shame_delta(self):
        """Doodle may add or subtract shame depending on random roll (base 5 ± random 15)."""
        reset_all()
        migrate_and_load()
        before = get_status()["shame"]
        dd = apply_visual_mark(15)
        after = get_status()["shame"]
        self.assertEqual(dd["shame"], 15)
        self.assertIn("delta", dd)
        self.assertIsInstance(dd["delta"]["shame"]["old"], int)
        self.assertIsInstance(dd["delta"]["shame"]["delta"], int)
        self.assertIn(before, [dd["delta"]["shame"]["old"], dd["delta"]["shame"]["old"]])

    # ── Candy ───────────────────────────────────────────────

    def test_07_candy_give_increases(self):
        before = get_status()["candy_count"]
        d = add_recovery_resource(3)
        self.assertEqual(d["count"], 3)
        self.assertGreater(d["new_count"], before)

    def test_08_candy_consume_reduces(self):
        add_recovery_resource(5)
        before = get_status()["candy_count"]
        c = consume_recovery_resource(1)
        after = get_status()["candy_count"]
        self.assertLess(after, before)

    # ── Bound Toggle ────────────────────────────────────────

    def test_09_bound_toggle(self):
        b1 = toggle_flag_01()
        b2 = toggle_flag_01()
        self.assertNotEqual(b1["new_bound"], b2["new_bound"])

    def test_10_bound_reflected_in_status(self):
        toggle_flag_01()
        self.assertTrue(get_status()["bound"])
        toggle_flag_01()
        self.assertFalse(get_status()["bound"])

    # ── Lock Toggle ─────────────────────────────────────────

    def test_11_lock_toggle(self):
        l1 = toggle_flag_02()
        self.assertTrue(l1["locked"])
        l2 = toggle_flag_02()
        self.assertFalse(l2["locked"])

    # ── Numb ────────────────────────────────────────────────

    def test_12_numb_valid_part(self):
        nn = set_zone_altered("大腿")
        self.assertNotIn("error", nn)

    def test_13_numb_invalid_part(self):
        nn = set_zone_altered("不存在")
        self.assertIn("error", nn)

    # ── Reset ───────────────────────────────────────────────

    def test_14_reset_restores_defaults(self):
        apply_input_signal(8)
        reset_all()
        migrate_and_load()
        s = get_status()
        self.assertEqual(s["pain"], 0)

    # ── Engine State ────────────────────────────────────────

    def test_15_engine_state_all_entities(self):
        state = get_engine_state()
        self.assertEqual(len(state), 4)
        for eid in ["e_g", "e_b", "e_r", "e_x"]:
            self.assertIn(eid, state)
            self.assertIn("channels", state[eid])


if __name__ == "__main__":
    unittest.main()
