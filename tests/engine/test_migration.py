#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for engine/migration.py — fixture-based, environment-independent."""

import os, sys, unittest

_scripts_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts"
)
sys.path.insert(0, _scripts_dir)

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

from engine.migration import (
    migrate_all, migrate_e_g, migrate_e_b, migrate_e_r, migrate_e_x,
    MigrationReport, EntityMigrationResult,
    _STATE_MAP, _AREA_MAP, _TRAITS,
    _PROD_SKILL,
)
from engine.entity import load_entity, get_channel, reset_entity, list_entities
from engine.modifier import apply_modifier
from engine.threshold import check_thresholds

# ── Helper: temporarily override production path ──────────────

_original_prod = _PROD_SKILL

def _set_fixture(name: str):
    """Point migration to a fixture directory instead of production."""
    import engine.migration as m
    m._PROD_SKILL = os.path.join(_FIXTURES, name)

def _restore_prod():
    import engine.migration as m
    m._PROD_SKILL = _original_prod


class TestMigrationFixtures(unittest.TestCase):
    """Tests with fixed, known fixture data — environment independent."""

    def setUp(self):
        for eid in list_entities():
            reset_entity(eid)

    def tearDown(self):
        for eid in list_entities():
            reset_entity(eid)

    # ── Fixture 1: mid_state ──────────────────────────────

    def test_01_mid_state_e_g(self):
        """mid_state: A=30 S=45 V=60, bound=true, locked=false."""
        _set_fixture("mid_state")
        try:
            migrate_e_g()
            self.assertEqual(get_channel("e_g", "ch_g_a"), 30)
            self.assertEqual(get_channel("e_g", "ch_g_s"), 45)
            self.assertEqual(get_channel("e_g", "ch_g_v"), 60)
            e = load_entity("e_g")
            self.assertEqual(e.flags.get("ch_g_bound"), 1)
            self.assertEqual(e.flags.get("ch_g_locked"), 0)
        finally:
            _restore_prod()

    def test_02_mid_state_e_r(self):
        """mid_state: candy count=12."""
        _set_fixture("mid_state")
        try:
            migrate_e_r()
            self.assertEqual(get_channel("e_r", "ch_r_count"), 12)
        finally:
            _restore_prod()

    def test_03_mid_state_e_x(self):
        """mid_state: area=a → int 1."""
        _set_fixture("mid_state")
        try:
            migrate_e_x()
            self.assertEqual(get_channel("e_x", "ch_x_area"), 1)
        finally:
            _restore_prod()

    def test_04_mid_state_e_b(self):
        """mid_state: 11 zones, 1 numb, 1 broken."""
        _set_fixture("mid_state")
        try:
            migrate_e_b()
            ch = load_entity("e_b").channels
            self.assertEqual(len(ch), 11)
            # 手臂=numb=1, 小腿=broken=2
            self.assertEqual(ch.get("ch_b_04"), 1)  # 手臂
            self.assertEqual(ch.get("ch_b_03"), 2)  # 小腿
            self.assertEqual(ch.get("ch_b_01"), 0)  # 大腿=active
        finally:
            _restore_prod()

    # ── Fixture 2: edge_state ─────────────────────────────

    def test_05_edge_state_e_g(self):
        """edge_state: A=85 S=95 V=15, bound=true, locked=true."""
        _set_fixture("edge_state")
        try:
            migrate_e_g()
            self.assertEqual(get_channel("e_g", "ch_g_a"), 85)
            self.assertEqual(get_channel("e_g", "ch_g_s"), 95)
            self.assertEqual(get_channel("e_g", "ch_g_v"), 15)
            e = load_entity("e_g")
            self.assertEqual(e.flags.get("ch_g_bound"), 1)
            self.assertEqual(e.flags.get("ch_g_locked"), 1)
        finally:
            _restore_prod()

    def test_06_edge_state_threshold_warning(self):
        """edge_state A=85 should trigger warning at ≥80."""
        _set_fixture("edge_state")
        try:
            migrate_e_g()
            report = check_thresholds("e_g")
            self.assertTrue(report.has_events)
            self.assertTrue(any(e.event_id == "ev_eg_a_warn" for e in report.warnings))
        finally:
            _restore_prod()

    def test_07_edge_state_e_r(self):
        """edge_state: candy=1, near empty."""
        _set_fixture("edge_state")
        try:
            migrate_e_r()
            self.assertEqual(get_channel("e_r", "ch_r_count"), 1)
        finally:
            _restore_prod()

    # ── Golden case: locked state freezes V ────────────────

    def test_08_edge_locked_freezes_v(self):
        """edge_state: locked=true → stim should NOT increase V."""
        _set_fixture("edge_state")
        try:
            migrate_e_g()
            v_before = get_channel("e_g", "ch_g_v")
            apply_modifier("mod_eg_av_add", intensity=5)
            v_after = get_channel("e_g", "ch_g_v")
            self.assertEqual(v_after, v_before)
        finally:
            _restore_prod()

    # ── Golden case: bound = 2x strain ────────────────────

    def test_09_edge_bound_strain(self):
        """edge_state: bound=true → stim with strain_mult=2 should double effect."""
        _set_fixture("edge_state")
        try:
            migrate_e_g()
            a_before = get_channel("e_g", "ch_g_a")
            apply_modifier("mod_eg_av_add", intensity=1, strain_mult=2.0)
            a_after = get_channel("e_g", "ch_g_a")
            delta = a_after - a_before
            # base=15 * 1 * 2.0 = 30 ± random, min bound is 30-10=20
            self.assertGreaterEqual(delta, 10)
        finally:
            _restore_prod()

    def test_10_all_migrate_runs(self):
        """migrate_all should succeed with mid_state fixture."""
        _set_fixture("mid_state")
        try:
            report = migrate_all()
            self.assertEqual(report.successful, 4)
        finally:
            _restore_prod()

    def test_11_migrate_all_runs_edge(self):
        """migrate_all should succeed with edge_state fixture."""
        _set_fixture("edge_state")
        try:
            report = migrate_all()
            self.assertEqual(report.successful, 4)
        finally:
            _restore_prod()


class TestMappingTables(unittest.TestCase):
    """Static mapping table validation."""

    def test_state_map_values(self):
        self.assertEqual(_STATE_MAP["active"], 0)
        self.assertEqual(_STATE_MAP["numb"], 1)
        self.assertEqual(_STATE_MAP["broken"], 2)

    def test_area_map_values(self):
        self.assertEqual(_AREA_MAP["v"], 0)
        self.assertEqual(_AREA_MAP["a"], 1)
        self.assertEqual(_AREA_MAP["u"], 2)

    def test_traits_keys(self):
        self.assertEqual(len(_TRAITS), 5)
        for k in ["ch_g_comp", "ch_g_dest", "ch_g_p_seek", "ch_g_cur", "ch_g_loy"]:
            self.assertIn(k, _TRAITS)


class TestMigrationReport(unittest.TestCase):
    """Report dataclass tests."""

    def test_all_passed(self):
        r = MigrationReport(successful=4, failed=0, total=4)
        self.assertTrue(r.all_passed)

    def test_not_all_passed(self):
        r = MigrationReport(successful=3, failed=1, total=4)
        self.assertFalse(r.all_passed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
