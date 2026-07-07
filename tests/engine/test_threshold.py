#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engine/threshold.py — 7 thresholds, event classification, multi-entity."""

import os, sys, unittest

_scripts_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts"
)
sys.path.insert(0, _scripts_dir)

from engine.threshold import (
    check_thresholds, check_all_thresholds, check_single_threshold,
    list_threshold_ids, get_threshold_config, ThresholdReport, ThresholdEvent,
)
from engine.modifier import apply_modifier
from engine.entity import reset_entity, get_channel, set_channel, load_entity


class TestThresholdConfig(unittest.TestCase):
    """Configuration validation tests."""

    def test_01_7_thresholds_registered(self):
        ids = list_threshold_ids()
        self.assertEqual(len(ids), 7)

    def test_02_all_configs_loadable(self):
        for tid in list_threshold_ids():
            cfg = get_threshold_config(tid)
            self.assertIn("entity", cfg)
            self.assertIn("channel", cfg)
            self.assertIn("event_id", cfg)

    def test_03_no_pain_in_labels(self):
        for tid in list_threshold_ids():
            cfg = get_threshold_config(tid)
            combined = cfg.get("label", "") + cfg.get("description", "")
            self.assertNotIn("pain", combined.lower(), f"{tid} contains 'pain'")


class TestThresholdTrigger(unittest.TestCase):
    """Threshold triggering and event classification tests."""

    def setUp(self):
        for eid in ["e_g", "e_b", "e_r", "e_x"]:
            reset_entity(eid)

    def tearDown(self):
        for eid in ["e_g", "e_b", "e_r", "e_x"]:
            reset_entity(eid)

    # ── 4. No thresholds at baseline ────────────────────────
    def test_04_empty_at_baseline(self):
        report = check_thresholds("e_g")
        self.assertFalse(report.has_events)

    # ── 5. Warning triggers at ≥80 ──────────────────────────
    def test_05_warning_triggers(self):
        set_channel("e_g", "ch_g_a", 80)
        report = check_thresholds("e_g")
        self.assertTrue(report.has_events)
        self.assertEqual(len(report.warnings), 1)
        self.assertEqual(report.warnings[0].event_id, "ev_g_a_high")
        self.assertEqual(len(report.criticals), 0)

    # ── 6. Critical triggers at ≥100 ────────────────────────
    def test_06_critical_triggers(self):
        set_channel("e_g", "ch_g_a", 100)
        report = check_thresholds("e_g")
        self.assertGreaterEqual(len(report.criticals), 1)
        self.assertTrue(any(e.event_id == "ev_g_a_max" for e in report.criticals))

    # ── 7. Warning + critical both trigger when ≥100 ────────
    def test_07_warning_and_critical_both_trigger(self):
        set_channel("e_g", "ch_g_a", 100)
        report = check_thresholds("e_g")
        self.assertGreaterEqual(len(report.warnings), 1)
        self.assertGreaterEqual(len(report.criticals), 1)

    # ── 8. Worst event type is critical ─────────────────────
    def test_08_worst_event_critical(self):
        set_channel("e_g", "ch_g_a", 100)
        report = check_thresholds("e_g")
        self.assertEqual(report.worst_event_type, "critical")

    # ── 9. Ecstasy event (Metric V max) ─────────────────────
    def test_09_ecstasy_type(self):
        set_channel("e_g", "ch_g_v", 100)
        report = check_thresholds("e_g")
        self.assertGreaterEqual(len(report.ecstasies), 1)
        self.assertEqual(report.worst_event_type, "ecstasy")
        self.assertTrue(any(e.event_id == "ev_g_v_max" for e in report.ecstasies))

    # ── 10. Clearing event (Metric S max) ───────────────────
    def test_10_clearing_type(self):
        set_channel("e_g", "ch_g_s", 100)
        report = check_thresholds("e_g")
        self.assertGreaterEqual(len(report.clearings), 1)
        self.assertEqual(report.worst_event_type, "clearing")
        self.assertTrue(any(e.event_id == "ev_g_s_max" for e in report.clearings))

    # ── 11. Recovery empty threshold ────────────────────────
    def test_11_recovery_empty(self):
        set_channel("e_r", "ch_r_count", 0)
        report = check_thresholds("e_r")
        self.assertTrue(report.has_events)
        self.assertTrue(any(e.event_id == "ev_r_empty" for e in report.triggered))

    def test_12_recovery_not_empty(self):
        set_channel("e_r", "ch_r_count", 5)
        report = check_thresholds("e_r")
        self.assertFalse(report.has_events)

    # ── 13. Single threshold check ──────────────────────────
    def test_13_single_check(self):
        set_channel("e_g", "ch_g_s", 90)
        event = check_single_threshold("e_g", "thr_g_s_warn")
        self.assertIsNotNone(event)
        self.assertEqual(event.event_id, "ev_g_s_high")
        self.assertEqual(event.current_value, 90)
        self.assertEqual(event.event_type, "warning")

    def test_14_single_check_no_trigger(self):
        event = check_single_threshold("e_g", "thr_g_s_warn")
        self.assertIsNone(event)

    # ── 14. All entities check ──────────────────────────────
    def test_15_check_all(self):
        set_channel("e_g", "ch_g_a", 95)
        set_channel("e_r", "ch_r_count", 0)
        reports = check_all_thresholds()
        self.assertGreaterEqual(len(reports), 2)
        e_g_report = next((r for r in reports if r.entity_id == "e_g"), None)
        e_r_report = next((r for r in reports if r.entity_id == "e_r"), None)
        self.assertIsNotNone(e_g_report)
        self.assertIsNotNone(e_r_report)
        self.assertTrue(e_g_report.has_events)
        self.assertTrue(e_r_report.has_events)

    # ── 15. ThresholdEvent dataclass fields ─────────────────
    def test_16_event_fields(self):
        set_channel("e_g", "ch_g_s", 85)
        event = check_single_threshold("e_g", "thr_g_s_warn")
        self.assertEqual(event.entity_id, "e_g")
        self.assertEqual(event.channel, "ch_g_s")
        self.assertEqual(event.threshold_value, 80)
        self.assertEqual(event.operator, ">=")
        self.assertTrue(event.triggered)

    # ── 16. ThresholdReport properties ──────────────────────
    def test_17_empty_report(self):
        report = ThresholdReport(entity_id="e_g")
        self.assertFalse(report.has_events)
        self.assertIsNone(report.worst_event_type)

    # ── 17. All three metric warnings ───────────────────────
    def test_18_triple_warning(self):
        set_channel("e_g", "ch_g_a", 85)
        set_channel("e_g", "ch_g_s", 85)
        set_channel("e_g", "ch_g_v", 85)
        report = check_thresholds("e_g")
        self.assertEqual(len(report.warnings), 3)
        self.assertEqual(report.worst_event_type, "warning")


if __name__ == "__main__":
    unittest.main(verbosity=2)
