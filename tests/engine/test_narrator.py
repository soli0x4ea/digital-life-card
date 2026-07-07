#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for engine/narrator.py — event rendering, severity, toggle, disabled mode."""

import os, sys, unittest

_scripts_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts"
)
sys.path.insert(0, _scripts_dir)

from engine.narrator import (
    render_event, render_event_auto, render_report,
    is_narrator_enabled, toggle_narrator,
    list_event_ids, get_event_config,
)
from engine.threshold import ThresholdReport, ThresholdEvent
from engine.entity import reset_entity, list_entities, set_channel
from engine.threshold import check_thresholds


class TestNarratorConfig(unittest.TestCase):
    """Configuration validation."""

    def test_01_7_events_registered(self):
        ids = list_event_ids()
        self.assertEqual(len(ids), 7)

    def test_02_all_configs_loadable(self):
        for eid in list_event_ids():
            cfg = get_event_config(eid)
            self.assertIn("severity", cfg)
            self.assertIn("texts", cfg)

    def test_03_no_pain_in_texts(self):
        for eid in list_event_ids():
            cfg = get_event_config(eid)
            for level, text in cfg["texts"].items():
                self.assertNotIn("pain", text.lower(), f"{eid}.{level}")

    def test_04_narrator_enabled_by_default(self):
        self.assertTrue(is_narrator_enabled())


class TestNarratorRendering(unittest.TestCase):
    """Event rendering tests."""

    def test_05_render_warning(self):
        text = render_event("ev_eg_a_warn", "mild")
        self.assertIsNotNone(text)
        self.assertIn("白板", text)

    def test_06_render_critical(self):
        text = render_event("ev_eg_a_crit", "intense")
        self.assertIsNotNone(text)

    def test_07_render_ecstasy(self):
        text = render_event("ev_eg_v_peak", "intense")
        self.assertIsNotNone(text)

    def test_08_render_clearing(self):
        text = render_event("ev_eg_s_clear", "medium")
        self.assertIsNotNone(text)

    def test_09_unknown_event_returns_none(self):
        text = render_event("ev_nonexistent")
        self.assertIsNone(text)

    def test_10_missing_severity_falls_back(self):
        text = render_event("ev_eg_a_warn", "extreme")
        self.assertIsNotNone(text)
        self.assertIn("白板", text)

    def test_11_auto_severity_works(self):
        """Auto severity picks appropriate level for channel value."""
        text = render_event_auto("ev_eg_a_crit", channel_value=99)
        self.assertIsNotNone(text)

    def test_12_disabled_returns_none(self):
        toggle_narrator(False)
        try:
            text = render_event("ev_eg_a_warn")
            self.assertIsNone(text)
        finally:
            toggle_narrator(True)

    def test_13_toggle_roundtrip(self):
        toggle_narrator(False)
        self.assertFalse(is_narrator_enabled())
        toggle_narrator(True)
        self.assertTrue(is_narrator_enabled())


class TestNarratorReport(unittest.TestCase):
    """Integration: threshold report → rendered text."""

    def setUp(self):
        for eid in list_entities():
            reset_entity(eid)

    def tearDown(self):
        for eid in list_entities():
            reset_entity(eid)

    def test_14_empty_report_no_text(self):
        report = ThresholdReport(entity_id="e_g")
        texts = render_report(report)
        self.assertEqual(len(texts), 0)

    def test_15_warning_report_renders(self):
        set_channel("e_g", "ch_g_a", 85)
        report = check_thresholds("e_g")
        texts = render_report(report)
        self.assertGreater(len(texts), 0)

    def test_16_critical_report_renders_with_prefix(self):
        set_channel("e_g", "ch_g_a", 100)
        report = check_thresholds("e_g")
        texts = render_report(report)
        self.assertGreater(len(texts), 0)
        self.assertTrue(any("[CRITICAL]" in t for t in texts),
                       f"No CRITICAL prefix in: {texts}")


def _is_intense(event_id, value):
    """Helper to determine if auto-sensitivity picks intense."""
    from engine.narrator import _pick_severity
    return _pick_severity(event_id, value) == "intense"


if __name__ == "__main__":
    unittest.main(verbosity=2)
