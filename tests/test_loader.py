import unittest
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture_path(name):
    return os.path.join(_FIXTURES, name)


class TestCardLoader(unittest.TestCase):
    """DLC Card Loader — card.json parsing and version checking."""

    # ── RED: tests that will fail until implementation exists ──

    def test_01_load_valid_card(self):
        from dlc.loader import load_card

        cfg = load_card(_fixture_path("valid_card.json"))
        self.assertEqual(cfg.protocol_version, "1.0.0")
        self.assertEqual(cfg.card_name, "Test Minimal Card")
        self.assertEqual(cfg.complexity_level, "L0")

    def test_02_missing_file_raises(self):
        from dlc.loader import load_card, CardLoadError

        with self.assertRaises(CardLoadError):
            load_card(_fixture_path("nonexistent.json"))

    def test_03_invalid_json_raises(self):
        from dlc.loader import load_card, CardLoadError

        invalid_path = _fixture_path("invalid.json")
        with open(invalid_path, "w") as f:
            f.write("{not json}")
        try:
            with self.assertRaises(CardLoadError):
                load_card(invalid_path)
        finally:
            os.remove(invalid_path)

    def test_04_version_compatible(self):
        from dlc.loader import check_version

        # 1.0.0 engine loading 1.0.0 card → OK
        result = check_version("1.0.0", "1.0.0")
        self.assertIsNone(result)  # None = compatible

    def test_05_version_minor_compatible(self):
        from dlc.loader import check_version

        # 1.1.0 engine loading 1.0.0 card → OK (minor bump backward compat)
        result = check_version("1.1.0", "1.0.0")
        self.assertIsNone(result)

    def test_06_version_major_incompatible(self):
        from dlc.loader import check_version

        # 2.0.0 card requires engine >= 2.0.0, but we're 1.0.0
        result = check_version("1.0.0", "2.0.0")
        self.assertIsNotNone(result)
        self.assertIn("major", result.lower())

    def test_07_required_fields_validated(self):
        from dlc.loader import load_card, CardLoadError

        missing_fields = _fixture_path("missing_fields.json")
        with open(missing_fields, "w") as f:
            json.dump({"card_name": "No version field"}, f)
        try:
            with self.assertRaises(CardLoadError):
                load_card(missing_fields)
        finally:
            os.remove(missing_fields)

    def test_08_parses_all_top_level_fields(self):
        from dlc.loader import load_card

        cfg = load_card(_fixture_path("valid_card.json"))
        self.assertEqual(cfg.card_id, "00000000-0000-4000-a000-000000000001")
        self.assertEqual(cfg.author, "test")
        self.assertIn("test", cfg.tags)
        self.assertEqual(
            cfg.engine_requirements["min_engine_version"], "1.0.0"
        )

    def test_09_modules_parsed_as_dict(self):
        from dlc.loader import load_card

        cfg = load_card(_fixture_path("valid_card.json"))
        self.assertIn("identity", cfg.modules)
        self.assertTrue(cfg.modules["identity"]["enabled"])
        self.assertFalse(cfg.modules["body"]["enabled"])


class TestModuleIndex(unittest.TestCase):
    """P0-03: Module index resolver."""

    def test_01_enabled_modules_listed(self):
        from dlc.loader import resolve_modules

        cfg = _load_card("valid_card.json")
        enabled = resolve_modules(cfg)
        self.assertIn("identity", enabled)
        self.assertNotIn("body", enabled)
        self.assertNotIn("engine", enabled)

    def test_02_all_modules_l3(self):
        from dlc.loader import resolve_modules

        cfg = _load_card("l3_card.json")
        enabled = resolve_modules(cfg)
        expected = {"identity", "body", "engine", "memory",
                    "behavior", "interaction", "vault"}
        self.assertEqual(set(enabled.keys()), expected)

    def test_03_module_paths_resolved(self):
        from dlc.loader import resolve_modules

        cfg = _load_card("l3_card.json")
        enabled = resolve_modules(cfg)
        self.assertEqual(
            enabled["identity"]["profile"],
            "identity/profile.json"
        )
        self.assertEqual(
            enabled["engine"]["entities"],
            "engine/entities.json"
        )

    def test_04_disabled_submodules_return_none(self):
        from dlc.loader import resolve_modules

        cfg = _load_card("l3_card.json")
        # speech is explicitly set so won't be None in this fixture.
        # Test with valid_card where speech is null:
        cfg2 = _load_card("valid_card.json")
        enabled = resolve_modules(cfg2)
        self.assertIsNone(enabled["identity"].get("speech"))


class TestComplexityLevel(unittest.TestCase):
    """P0-04: Complexity level detection."""

    def test_01_detect_l0(self):
        from dlc.loader import detect_complexity, resolve_modules

        cfg = _load_card("valid_card.json")
        modules = resolve_modules(cfg)
        level = detect_complexity(modules)
        self.assertEqual(level, "L0")

    def test_02_detect_l3(self):
        from dlc.loader import detect_complexity, resolve_modules

        cfg = _load_card("l3_card.json")
        modules = resolve_modules(cfg)
        level = detect_complexity(modules)
        self.assertEqual(level, "L3")

    def test_03_override_still_respected(self):
        """card.json complexity_level overrides auto-detection."""
        from dlc.loader import load_card

        cfg = load_card(_fixture_path("l3_card.json"))
        # L3 card declares L3 explicitly
        self.assertEqual(cfg.complexity_level, "L3")


def _load_card(name):
    from dlc.loader import load_card
    return load_card(_fixture_path(name))


class TestDependencyIntegrity(unittest.TestCase):
    """P0-05: Module dependency integrity checks."""

    def test_01_no_engine_without_body(self):
        from dlc.loader import check_dependencies, resolve_modules

        # Simulate: engine enabled, body disabled
        fake_modules = {
            "identity": {"profile": "x"},
            "engine": {"entities": "x", "modifiers": "x",
                       "thresholds": "x", "narratives": "x"},
        }
        errors = check_dependencies(fake_modules)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("body" in e.lower() for e in errors))

    def test_02_valid_l3_no_warnings(self):
        from dlc.loader import check_dependencies, resolve_modules

        cfg = _load_card("l3_card.json")
        modules = resolve_modules(cfg)
        errors = check_dependencies(modules)
        self.assertEqual(errors, [])

    def test_03_behavior_needs_engine(self):
        from dlc.loader import check_dependencies

        fake = {"identity": {"profile": "x"}, "behavior": {"lws_rules": "x"}}
        errors = check_dependencies(fake)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("engine" in e.lower() for e in errors))

    def test_04_memory_needs_engine(self):
        from dlc.loader import check_dependencies

        fake = {"identity": {"profile": "x"}, "memory": {"architecture": "x"}}
        errors = check_dependencies(fake)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("engine" in e.lower() for e in errors))


if __name__ == "__main__":
    unittest.main()
