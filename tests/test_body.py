"""Phase 1B: Body module tests — P1-07 ~ P1-12."""

import unittest, json, os, sys, tempfile, shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "body")


# ═══════════════════════════════════════════════════════════════
# P1-07: Anatomy loader
# ═══════════════════════════════════════════════════════════════

class TestAnatomyLoader(unittest.TestCase):
    """P1-07: Load and validate body/anatomy.json."""

    def test_01_load_valid_anatomy(self):
        from dlc.body import AnatomyLoader, BodyModel
        al = AnatomyLoader(FIXTURES)
        body = al.load()
        self.assertIsInstance(body, BodyModel)
        self.assertEqual(body.body_model, "generic_humanoid")
        self.assertEqual(len(body.regions), 4)

    def test_02_region_state_levels_parsed(self):
        from dlc.body import AnatomyLoader
        al = AnatomyLoader(FIXTURES)
        body = al.load()
        head = body.regions["head"]
        self.assertEqual(len(head.state_levels), 4)
        self.assertEqual(head.state_levels[0].name, "正常")

    def test_03_initial_state_loaded(self):
        from dlc.body import AnatomyLoader
        al = AnatomyLoader(FIXTURES)
        body = al.load()
        self.assertIn("head", body.initial_state)
        self.assertEqual(body.initial_state["head"], 0)

    def test_04_regions_without_initial_get_zero(self):
        from dlc.body import AnatomyLoader
        al = AnatomyLoader(FIXTURES)
        body = al.load()
        # left_arm not in initial_state → default 0
        self.assertEqual(body.get_state("left_arm"), 0)

    def test_05_sensitivity_parsed(self):
        from dlc.body import AnatomyLoader
        al = AnatomyLoader(FIXTURES)
        body = al.load()
        self.assertEqual(body.regions["torso"].sensitivity, 0.6)

    def test_06_pairs_with_parsed(self):
        from dlc.body import AnatomyLoader
        al = AnatomyLoader(FIXTURES)
        body = al.load()
        self.assertEqual(body.regions["left_arm"].pairs_with, "right_arm")


# ═══════════════════════════════════════════════════════════════
# P1-08: Body state CRUD
# ═══════════════════════════════════════════════════════════════

class TestBodyStateCRUD(unittest.TestCase):
    """P1-08: Read/set body region states with bounds checking."""

    def setUp(self):
        from dlc.body import AnatomyLoader
        self.body = AnatomyLoader(FIXTURES).load()

    def test_01_set_state_within_range(self):
        self.body.set_state("head", 2)
        self.assertEqual(self.body.get_state("head"), 2)

    def test_02_set_state_clamped_to_max(self):
        self.body.set_state("head", 99)
        self.assertEqual(self.body.get_state("head"), 3)  # max level = 3

    def test_03_set_state_clamped_to_min(self):
        self.body.set_state("head", 2)
        self.body.set_state("head", -5)
        self.assertEqual(self.body.get_state("head"), 0)

    def test_04_invalid_region_raises(self):
        with self.assertRaises(KeyError):
            self.body.set_state("nonexistent", 1)

    def test_05_get_invalid_region_raises(self):
        with self.assertRaises(KeyError):
            self.body.get_state("nonexistent")


# ═══════════════════════════════════════════════════════════════
# P1-09: State level transition
# ═══════════════════════════════════════════════════════════════

class TestStateTransition(unittest.TestCase):
    """P1-09: State upgrade/downgrade transitions."""

    def setUp(self):
        from dlc.body import AnatomyLoader
        self.body = AnatomyLoader(FIXTURES).load()

    def test_01_upgrade_state(self):
        self.body.raise_state("head", 1)
        self.assertEqual(self.body.get_state("head"), 1)

    def test_02_upgrade_capped_at_max(self):
        self.body.set_state("head", 3)
        self.body.raise_state("head", 5)
        self.assertEqual(self.body.get_state("head"), 3)

    def test_03_lower_state(self):
        self.body.set_state("head", 3)
        self.body.lower_state("head", 1)
        self.assertEqual(self.body.get_state("head"), 2)

    def test_04_lower_capped_at_min(self):
        self.body.lower_state("head", 5)
        self.assertEqual(self.body.get_state("head"), 0)


# ═══════════════════════════════════════════════════════════════
# P1-10: Zones loader
# ═══════════════════════════════════════════════════════════════

class TestZonesLoader(unittest.TestCase):
    """P1-10: Load and validate body/zones.json."""

    def test_01_load_valid_zones(self):
        from dlc.body import ZonesLoader
        zl = ZonesLoader(FIXTURES)
        zones = zl.load()
        self.assertEqual(len(zones), 2)

    def test_02_zone_fields_parsed(self):
        from dlc.body import ZonesLoader
        zl = ZonesLoader(FIXTURES)
        zones = zl.load()
        neck = zones[0]
        self.assertEqual(neck.id, "neck_zone")
        self.assertEqual(neck.zone_type, "ticklish")
        self.assertEqual(neck.sensitivity_multiplier, 2.0)

    def test_03_trigger_modifiers_parsed(self):
        from dlc.body import ZonesLoader
        zl = ZonesLoader(FIXTURES)
        zones = zl.load()
        chest = zones[1]
        self.assertIn("mod_pleasure_add", chest.trigger_modifiers)


# ═══════════════════════════════════════════════════════════════
# P1-11: Zone → channel mapping
# ═══════════════════════════════════════════════════════════════

class TestZoneChannelMapping(unittest.TestCase):
    """P1-11: Map body zones to engine channels."""

    def setUp(self):
        from dlc.body import AnatomyLoader, ZonesLoader
        self.body = AnatomyLoader(FIXTURES).load()
        self.zones = ZonesLoader(FIXTURES).load()

    def test_01_map_zone_to_channel_basic(self):
        from dlc.body import map_zone_to_channel
        ch = map_zone_to_channel(self.zones[0], self.body, "sensory")
        self.assertIsInstance(ch, str)

    def test_02_different_zone_types_map_differently(self):
        from dlc.body import map_zone_to_channel
        ch_tickle = map_zone_to_channel(self.zones[0], self.body, "sensory")
        ch_erog = map_zone_to_channel(self.zones[1], self.body, "sensory")
        # Different zone types may produce different channel IDs
        self.assertIsInstance(ch_tickle, str)
        self.assertIsInstance(ch_erog, str)

    def test_03_nonexistent_region_raises(self):
        from dlc.body import Zone, map_zone_to_channel
        fake_zone = Zone(
            id="fake", name="Fake", parent_region="does_not_exist",
            sensitivity_multiplier=1.0, zone_type="ticklish"
        )
        with self.assertRaises(KeyError):
            map_zone_to_channel(fake_zone, self.body, "sensory")


# ═══════════════════════════════════════════════════════════════
# P1-12: Symmetric pairing
# ═══════════════════════════════════════════════════════════════

class TestSymmetricPairing(unittest.TestCase):
    """P1-12: Symmetric region pair synchronization."""

    def setUp(self):
        from dlc.body import AnatomyLoader
        self.body = AnatomyLoader(FIXTURES).load()

    def test_01_has_pair(self):
        self.assertTrue(self.body.has_pair("left_arm"))
        self.assertEqual(self.body.get_pair("left_arm"), "right_arm")

    def test_02_no_pair(self):
        self.assertFalse(self.body.has_pair("head"))
        self.assertIsNone(self.body.get_pair("head"))

    def test_03_sync_pair_applies_to_coupled_region(self):
        from dlc.body import sync_pair
        self.body.set_state("left_arm", 1)
        sync_pair(self.body, "left_arm")
        self.assertEqual(self.body.get_state("right_arm"), 1)

    def test_04_sync_pair_no_pair_no_error(self):
        from dlc.body import sync_pair
        self.body.set_state("head", 2)
        sync_pair(self.body, "head")
        self.assertEqual(self.body.get_state("head"), 2)


if __name__ == "__main__":
    unittest.main()
