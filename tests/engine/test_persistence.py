#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for engine/persistence.py — atomic write, backup rotation, BOM compatibility."""

import os, sys, json, tempfile, unittest

# Ensure engine/ is importable
_scripts_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts"
)
sys.path.insert(0, _scripts_dir)

from engine.persistence import atomic_write, read_json, try_read_json


class TestAtomicWrite(unittest.TestCase):
    """Tests for atomic_write and read_json."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.test_path = os.path.join(self.tmpdir, "test.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ── 1. Basic write + read ────────────────────────
    def test_01_write_read_roundtrip(self):
        """Write JSON → read back → verify identical."""
        data = {"key": "value", "num": 42, "list": [1, 2, 3]}
        atomic_write(self.test_path, data)
        reloaded = read_json(self.test_path)
        self.assertEqual(reloaded, data)

    # ── 2. Nested structures ─────────────────────────
    def test_02_nested_json(self):
        """Deeply nested JSON survives atomic write."""
        deep = {"a": {"b": {"c": {"d": [1, 2, {"e": "f"}]}}}}
        atomic_write(self.test_path, deep)
        reloaded = read_json(self.test_path)
        self.assertEqual(reloaded, deep)

    # ── 3. BOM compatibility ─────────────────────────
    def test_03_bom_read(self):
        """read_json handles utf-8-sig (BOM) files."""
        bom_path = os.path.join(self.tmpdir, "bom.json")
        data = {"hello": "world"}
        with open(bom_path, "w", encoding="utf-8-sig") as f:
            json.dump(data, f)
        reloaded = read_json(bom_path)
        self.assertEqual(reloaded, data)

    # ── 4. Backup rotation ───────────────────────────
    def test_04_backup_rotation(self):
        """After 10 writes, at most 5 backups retained."""
        for i in range(10):
            atomic_write(self.test_path, {"iteration": i})
        bak_dir = os.path.join(self.tmpdir, ".backups")
        self.assertTrue(os.path.isdir(bak_dir))
        baks = [f for f in os.listdir(bak_dir) if "test.json" in f]
        self.assertLessEqual(len(baks), 5, f"Expected ≤5 backups, got {len(baks)}")

    # ── 5. Backup content integrity ──────────────────
    def test_05_backup_content(self):
        """Latest backup matches the overwritten data."""
        atomic_write(self.test_path, {"v": 1})
        atomic_write(self.test_path, {"v": 2})
        bak_dir = os.path.join(self.tmpdir, ".backups")
        baks = sorted(os.listdir(bak_dir))
        self.assertGreaterEqual(len(baks), 1)
        # Read the oldest backup (original v:1)
        oldest_bak = os.path.join(bak_dir, baks[0])
        content = read_json(oldest_bak)
        self.assertEqual(content, {"v": 1})

    # ── 6. Directory auto-creation ───────────────────
    def test_06_directory_autocreate(self):
        """atomic_write creates parent directories if missing."""
        deep_path = os.path.join(self.tmpdir, "deep", "nested", "data.json")
        atomic_write(deep_path, {"created": True})
        self.assertTrue(os.path.exists(deep_path))
        self.assertEqual(read_json(deep_path), {"created": True})

    # ── 7. try_read_json fallback ────────────────────
    def test_07_try_read_fallback(self):
        """try_read_json returns default when file missing."""
        result = try_read_json(self.test_path, "fallback_default")
        self.assertEqual(result, "fallback_default")

    def test_08_try_read_valid(self):
        """try_read_json returns data when file exists."""
        atomic_write(self.test_path, {"ok": True})
        result = try_read_json(self.test_path, None)
        self.assertEqual(result, {"ok": True})

    # ── 8. Unicode compatibility ─────────────────────
    def test_09_unicode_content(self):
        """Chinese / emoji survives atomic write roundtrip."""
        data = {"msg": "你好世界", "emoji": "😺🐱"}
        atomic_write(self.test_path, data)
        reloaded = read_json(self.test_path)
        self.assertEqual(reloaded["msg"], "你好世界")
        self.assertEqual(reloaded["emoji"], "😺🐱")


if __name__ == "__main__":
    unittest.main(verbosity=2)
