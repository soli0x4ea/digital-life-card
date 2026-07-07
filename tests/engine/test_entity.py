#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engine/entity.py — CRUD, clamp, flags, batch, reset, config validation."""

import os, sys, json, unittest

_scripts_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts"
)
sys.path.insert(0, _scripts_dir)

from engine.entity import (
    EntityState,
    list_entities,
    load_entity,
    save_entity,
    get_channel,
    set_channel,
    set_channels_batch,
    toggle_flag,
    set_flag,
    reset_entity,
    _load_entity_config,
)

_STATE_DIR = os.path.join(_scripts_dir, "..", "data", "engine", "state")


class TestEntityConfig(unittest.TestCase):
    """Tests for entity configuration loading."""

    def test_01_configs_load(self):
        """All 4 entities have valid configs."""
        for eid in ["e_g", "e_b", "e_r", "e_x"]:
            cfg = _load_entity_config(eid)
            self.assertIn("channels", cfg or {})
            self.assertIn("label", cfg or {})

    def test_02_e_g_has_8_channels_2_flags(self):
        cfg = _load_entity_config("e_g")
        self.assertEqual(len(cfg["channels"]), 8)
        self.assertEqual(len(cfg.get("flags", {})), 2)

    def test_03_e_b_has_11_zones(self):
        cfg = _load_entity_config("e_b")
        self.assertEqual(len(cfg["channels"]), 11)

    def test_04_no_pain_in_config_keys(self):
        """D3-1: channel keys must not contain 'pain'."""
        for eid in ["e_g", "e_b", "e_r", "e_x"]:
            cfg = _load_entity_config(eid)
            for ch in cfg.get("channels", {}):
                self.assertNotIn("pain", ch.lower(), f"{eid}.{ch} contains 'pain'")
            for fl in cfg.get("flags", {}):
                self.assertNotIn("pain", fl.lower(), f"{eid} flag {fl} contains 'pain'")


class TestEntityCRUD(unittest.TestCase):
    """Tests for entity create/read/update/delete lifecycle."""

    def setUp(self):
        for eid in list_entities():
            reset_entity(eid)

    def tearDown(self):
        for eid in list_entities():
            reset_entity(eid)

    # ── 5. Fresh load uses config defaults ────────────
    def test_05_fresh_e_g_defaults(self):
        e = load_entity("e_g")
        self.assertEqual(e.channels["ch_g_a"], 0)
        self.assertEqual(e.channels["ch_g_comp"], 0.94)
        self.assertEqual(e.channels["ch_g_p_seek"], 0.85)
        self.assertEqual(e.flags.get("ch_g_bound"), 0)
        self.assertEqual(e.flags.get("ch_g_locked"), 0)

    def test_06_fresh_e_b_all_zero(self):
        e = load_entity("e_b")
        for ch in e.channels:
            self.assertEqual(e.channels[ch], 0, f"e_b.{ch} not zero")

    def test_07_fresh_e_r_default(self):
        e = load_entity("e_r")
        self.assertEqual(e.channels["ch_r_count"], 15)

    def test_08_fresh_e_x_default(self):
        e = load_entity("e_x")
        self.assertEqual(e.channels["ch_x_area"], 0)
        self.assertEqual(e.channels["ch_x_count"], 0)

    # ── 6. set_channel + get_channel ──────────────────
    def test_09_set_get_roundtrip(self):
        set_channel("e_g", "ch_g_a", 50)
        self.assertEqual(get_channel("e_g", "ch_g_a"), 50)

    # ── 7. Clamp — upper bound ───────────────────────
    def test_10_clamp_upper(self):
        set_channel("e_g", "ch_g_a", 200)
        self.assertEqual(get_channel("e_g", "ch_g_a"), 100)

    # ── 8. Clamp — lower bound ───────────────────────
    def test_11_clamp_lower(self):
        set_channel("e_g", "ch_g_a", -10)
        self.assertEqual(get_channel("e_g", "ch_g_a"), 0)

    # ── 9. Clamp — float channel ─────────────────────
    def test_12_clamp_float(self):
        set_channel("e_g", "ch_g_comp", 1.5)
        self.assertEqual(get_channel("e_g", "ch_g_comp"), 1.0)
        set_channel("e_g", "ch_g_comp", -0.5)
        self.assertEqual(get_channel("e_g", "ch_g_comp"), 0.0)

    # ── 10. Batch operation ──────────────────────────
    def test_13_batch_set(self):
        set_channels_batch("e_g", {"ch_g_a": 70, "ch_g_s": 30, "ch_g_v": 50})
        self.assertEqual(get_channel("e_g", "ch_g_a"), 70)
        self.assertEqual(get_channel("e_g", "ch_g_s"), 30)
        self.assertEqual(get_channel("e_g", "ch_g_v"), 50)

    # ── 11. Flag set ─────────────────────────────────
    def test_14_flag_set(self):
        set_flag("e_g", "ch_g_bound", 1)
        self.assertEqual(get_channel("e_g", "ch_g_bound"), 1)
        val = load_entity("e_g").flags.get("ch_g_bound")
        self.assertEqual(val, 1)

    # ── 12. Flag toggle ──────────────────────────────
    def test_15_flag_toggle(self):
        set_flag("e_g", "ch_g_bound", 1)
        toggle_flag("e_g", "ch_g_bound")
        self.assertEqual(get_channel("e_g", "ch_g_bound"), 0)
        toggle_flag("e_g", "ch_g_bound")
        self.assertEqual(get_channel("e_g", "ch_g_bound"), 1)

    # ── 13. Reset entity ─────────────────────────────
    def test_16_reset_entity(self):
        set_channel("e_g", "ch_g_a", 99)
        set_flag("e_g", "ch_g_bound", 1)
        reset_entity("e_g")
        e = load_entity("e_g")
        self.assertEqual(e.channels["ch_g_a"], 0)
        self.assertEqual(e.flags.get("ch_g_bound"), 0)

    # ── 14. Save + reload persistence ────────────────
    def test_17_save_reload_persists(self):
        e = load_entity("e_g")
        e.channels["ch_g_a"] = 42
        e.flags["ch_g_bound"] = 1
        e.dirty = True
        save_entity(e.entity_id, e)
        e2 = load_entity("e_g")
        self.assertEqual(e2.channels["ch_g_a"], 42)
        self.assertEqual(e2.flags.get("ch_g_bound"), 1)

    # ── 15. EntityState from_dict → to_dict ──────────
    def test_18_to_from_dict(self):
        d = {
            "entity_id": "e_g",
            "channels": {"ch_g_a": 30, "ch_g_v": 50},
            "flags": {"ch_g_bound": 1},
            "meta": {"label": "test"},
            "dirty": True,
        }
        e = EntityState.from_dict(d)
        self.assertEqual(e.entity_id, "e_g")
        self.assertEqual(e.channels["ch_g_a"], 30)
        self.assertEqual(e.flags["ch_g_bound"], 1)
        d2 = e.to_dict()
        self.assertEqual(d2["entity_id"], "e_g")
        self.assertEqual(d2["channels"]["ch_g_a"], 30)

    # ── 16. Body zone clamp (0-5) ────────────────────
    def test_19_body_zone_clamp(self):
        set_channel("e_b", "ch_b_01", 3)
        self.assertEqual(get_channel("e_b", "ch_b_01"), 2)
        set_channel("e_b", "ch_b_01", -1)
        self.assertEqual(get_channel("e_b", "ch_b_01"), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
