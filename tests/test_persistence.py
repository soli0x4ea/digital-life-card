"""P0-23 ~ P0-26: Persistence layer tests.

Phase 0d: StateManager + export/import + backup mechanism.
"""

import unittest, json, os, sys, tempfile, shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_card_dir(base, card_id="test-persist"):
    """Create a minimal card directory with card.json."""
    card_dir = os.path.join(base, card_id)
    os.makedirs(card_dir, exist_ok=True)
    card_data = {
        "protocol_version": "1.0.0",
        "card_id": card_id,
        "card_name": "Persistence Test",
        "complexity_level": "L1",
        "author": "test",
        "created_at": "2026-07-08",
        "updated_at": "2026-07-08",
        "modules": {
            "identity": {"enabled": True, "profile": "identity/profile.json"},
            "body": {"enabled": True, "anatomy": "body/anatomy.json"},
            "engine": {"enabled": True,
                       "entities": "engine/entities.json",
                       "modifiers": "engine/modifiers.json",
                       "thresholds": "engine/thresholds.json",
                       "narratives": "engine/narratives.json"}
        }
    }
    # Create minimal config files
    for path, content in [
        ("identity/profile.json", {"name": "Test"}),
        ("body/anatomy.json", {"parts": []}),
        ("engine/entities.json", {"entities": {}}),
        ("engine/modifiers.json", {"modifiers": {}}),
        ("engine/thresholds.json", {"thresholds": {}}),
        ("engine/narratives.json", {"events": {}}),
    ]:
        full = os.path.join(card_dir, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            json.dump(content, f)
    with open(os.path.join(card_dir, "card.json"), "w", encoding="utf-8") as f:
        json.dump(card_data, f, indent=2)
    return card_dir


# ── Increment 1: StateManager ──────────────────────────────────

class TestStateManager(unittest.TestCase):
    """P0-23: StateManager — card-scoped state read/write."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_write_and_read_state(self):
        from dlc.context import CardRuntimeContext
        from dlc.persistence import StateManager

        card_dir = _make_card_dir(self.tmp)
        ctx = CardRuntimeContext(card_dir)
        sm = StateManager(ctx)

        data = {"ch_g_a": 0, "ch_g_s": 50, "ch_g_v": 30}
        sm.write("e_g", data)

        loaded = sm.read("e_g")
        self.assertEqual(loaded, data)

    def test_02_read_missing_returns_none(self):
        from dlc.context import CardRuntimeContext
        from dlc.persistence import StateManager

        card_dir = _make_card_dir(self.tmp)
        ctx = CardRuntimeContext(card_dir)
        sm = StateManager(ctx)

        self.assertIsNone(sm.read("nonexistent"))

    def test_03_delete_state(self):
        from dlc.context import CardRuntimeContext
        from dlc.persistence import StateManager

        card_dir = _make_card_dir(self.tmp)
        ctx = CardRuntimeContext(card_dir)
        sm = StateManager(ctx)

        sm.write("e_temp", {"x": 1})
        self.assertIsNotNone(sm.read("e_temp"))

        sm.delete("e_temp")
        self.assertIsNone(sm.read("e_temp"))

    def test_04_list_states(self):
        from dlc.context import CardRuntimeContext
        from dlc.persistence import StateManager

        card_dir = _make_card_dir(self.tmp)
        ctx = CardRuntimeContext(card_dir)
        sm = StateManager(ctx)

        sm.write("e_g", {"a": 0})
        sm.write("e_b", {"b": 1})
        sm.write("e_t", {"t": 2})

        states = sm.list_states()
        self.assertIn("e_g", states)
        self.assertIn("e_b", states)
        self.assertIn("e_t", states)

    def test_05_default_on_missing(self):
        from dlc.context import CardRuntimeContext
        from dlc.persistence import StateManager

        card_dir = _make_card_dir(self.tmp)
        ctx = CardRuntimeContext(card_dir)
        sm = StateManager(ctx)

        default = {"ch_g_a": 0, "ch_g_s": 0, "ch_g_v": 0}
        result = sm.read("e_g", default=default)
        self.assertEqual(result, default)


# ── Increment 2: Export / Import ────────────────────────────────

class TestStateExportImport(unittest.TestCase):
    """P0-24 + P0-25: export_state() / import_state()."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_export_result_is_dict(self):
        from dlc.context import CardRuntimeContext
        from dlc.persistence import StateManager

        card_dir = _make_card_dir(self.tmp)
        ctx = CardRuntimeContext(card_dir)
        sm = StateManager(ctx)

        sm.write("e_g", {"ch_g_a": 10, "ch_g_s": 20})
        sm.write("e_b", {"zone_head": 0})

        exported = sm.export_state()
        self.assertIsInstance(exported, dict)
        self.assertIn("entities", exported)
        self.assertIn("e_g", exported["entities"])
        self.assertIn("e_b", exported["entities"])

    def test_02_round_trip_preserves_data(self):
        from dlc.context import CardRuntimeContext
        from dlc.persistence import StateManager

        card_dir_a = _make_card_dir(self.tmp, "export-test-a")
        ctx_a = CardRuntimeContext(card_dir_a)
        sm_a = StateManager(ctx_a)

        original = {
            "e_g": {"ch_g_a": 42, "ch_g_s": 17, "ch_g_v": 99},
            "e_b": {"zone_head": 3, "zone_chest": 7},
        }
        for k, v in original.items():
            sm_a.write(k, v)

        exported = sm_a.export_state()

        # Import into a different card
        card_dir_b = _make_card_dir(self.tmp, "import-test-b")
        ctx_b = CardRuntimeContext(card_dir_b)
        sm_b = StateManager(ctx_b)

        sm_b.import_state(exported)

        for k, v in original.items():
            loaded = sm_b.read(k)
            self.assertEqual(loaded, v)

    def test_03_export_includes_metadata(self):
        from dlc.context import CardRuntimeContext
        from dlc.persistence import StateManager

        card_dir = _make_card_dir(self.tmp)
        ctx = CardRuntimeContext(card_dir)
        sm = StateManager(ctx)

        sm.write("e_g", {"ch_g_a": 0})
        exported = sm.export_state()

        self.assertIn("card_id", exported)
        self.assertEqual(exported["card_id"], "test-persist")
        self.assertIn("exported_at", exported)
        self.assertIn("protocol_version", exported)


# ── Increment 3: Backup mechanism ──────────────────────────────

class TestStateBackup(unittest.TestCase):
    """P0-26: State backup mechanism."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_backup_creates_file(self):
        from dlc.context import CardRuntimeContext
        from dlc.persistence import StateManager

        card_dir = _make_card_dir(self.tmp)
        ctx = CardRuntimeContext(card_dir)
        sm = StateManager(ctx)

        sm.write("e_g", {"ch_g_a": 10})
        backup_path = sm.backup()

        self.assertTrue(os.path.isfile(backup_path))
        self.assertTrue(backup_path.endswith(".dlc-state"))

    def test_02_backup_contains_all_states(self):
        from dlc.context import CardRuntimeContext
        from dlc.persistence import StateManager

        card_dir = _make_card_dir(self.tmp)
        ctx = CardRuntimeContext(card_dir)
        sm = StateManager(ctx)

        sm.write("e_g", {"a": 1})
        sm.write("e_b", {"b": 2})

        backup_path = sm.backup()
        with open(backup_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("e_g", data.get("entities", {}))
        self.assertIn("e_b", data.get("entities", {}))

    def test_03_restore_from_backup(self):
        from dlc.context import CardRuntimeContext
        from dlc.persistence import StateManager

        card_dir = _make_card_dir(self.tmp)
        ctx = CardRuntimeContext(card_dir)
        sm = StateManager(ctx)

        sm.write("e_g", {"ch_g_a": 100})
        backup_path = sm.backup()

        # Modify state
        sm.write("e_g", {"ch_g_a": 0})

        # Restore from backup
        sm.restore(backup_path)
        restored = sm.read("e_g")
        self.assertEqual(restored, {"ch_g_a": 100})

    def test_04_backup_and_restore_are_symmetric(self):
        from dlc.context import CardRuntimeContext
        from dlc.persistence import StateManager

        card_dir = _make_card_dir(self.tmp)
        ctx = CardRuntimeContext(card_dir)
        sm = StateManager(ctx)

        original = {
            "e_g": {"ch_g_a": 1, "ch_g_s": 2, "ch_g_v": 3},
            "e_b": {"zone_a": 10, "zone_b": 20},
            "e_r": {"candy": 5},
        }
        for k, v in original.items():
            sm.write(k, v)

        backup_path = sm.backup()

        # Wipe all state
        for k in original:
            sm.delete(k)

        # Restore
        sm.restore(backup_path)

        for k, v in original.items():
            self.assertEqual(sm.read(k), v)


if __name__ == "__main__":
    unittest.main()
