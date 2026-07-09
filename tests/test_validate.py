"""P0-07 ~ P0-15: JSON Schema validation tests.

Phase 0b: 8 module schemas + jsonschema validation engine.
"""

import unittest, json, os, sys

# Ensure dlc/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SCHEMAS  = os.path.join(os.path.dirname(__file__), "..", "dlc", "schemas")
PYTHON   = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "..", "..",
    ".workbuddy", "binaries", "python", "envs", "default", "Scripts", "python.exe"
)

# ── Helpers ─────────────────────────────────────────────────────

def _load_json(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as f:
        return json.load(f)


def _load_schema(name):
    with open(os.path.join(SCHEMAS, name), "r", encoding="utf-8") as f:
        return json.load(f)

# ── Increment 1: card.json root schema ──────────────────────────

class TestCardRootSchema(unittest.TestCase):
    """P0-07 + P0-15: card.json root schema + validation engine."""

    def test_01_root_schema_exists(self):
        """card.schema.json must be a valid JSON file."""
        schema = _load_schema("card.schema.json")
        self.assertIsInstance(schema, dict)
        self.assertIn("$schema", schema)

    def test_02_valid_card_passes(self):
        """A correct card.json must pass schema validation."""
        from dlc.validate import validate_card

        card = _load_json("valid_card.json")
        errors = validate_card(card)
        self.assertEqual(errors, [])

    def test_03_missing_protocol_version_fails(self):
        """card.json without protocol_version must fail."""
        from dlc.validate import validate_card

        card = _load_json("valid_card.json")
        del card["protocol_version"]
        errors = validate_card(card)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("protocol_version" in e for e in errors))

    def test_04_invalid_complexity_level_fails(self):
        """card.json with bad complexity_level must fail."""
        from dlc.validate import validate_card

        card = _load_json("valid_card.json")
        card["complexity_level"] = "L99"
        errors = validate_card(card)
        self.assertGreater(len(errors), 0)

    def test_05_missing_card_id_fails(self):
        """card.json without card_id must fail."""
        from dlc.validate import validate_card

        card = _load_json("valid_card.json")
        del card["card_id"]
        errors = validate_card(card)
        self.assertGreater(len(errors), 0)

    def test_06_unknown_top_level_field_warns(self):
        """Unknown top-level fields should not break validation
        (forward compatibility) but should be noted."""
        from dlc.validate import validate_card

        card = _load_json("valid_card.json")
        card["future_field"] = "hello"
        # Additional properties should NOT break validation
        # (jsonschema default allows them unless additionalProperties=false)
        errors = validate_card(card)
        self.assertEqual(errors, [])

    def test_07_l3_card_passes(self):
        """L3 card with all modules should validate clean."""
        from dlc.validate import validate_card

        card = _load_json("l3_card.json")
        errors = validate_card(card)
        self.assertEqual(errors, [])

    def test_08_empty_modules_is_valid(self):
        """card.json with modules={} should pass (L0 minimum)."""
        from dlc.validate import validate_card

        card = {
            "protocol_version": "1.0.0",
            "card_id": "test-empty",
            "card_name": "Empty Card",
            "complexity_level": "L0",
            "author": "test",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-01",
            "modules": {},
        }
        errors = validate_card(card)
        self.assertEqual(errors, [])


# ── Increment 2: module schemas ─────────────────────────────────

class TestIdentitySchema(unittest.TestCase):
    """P0-08: identity module schema."""

    def test_01_enabled_true_valid(self):
        from dlc.validate import validate_module
        data = {"enabled": True, "profile": "identity/profile.json",
                "personality": "identity/personality.json"}
        errors = validate_module(data, "identity.schema.json")
        self.assertEqual(errors, [])

    def test_02_missing_enabled_fails(self):
        from dlc.validate import validate_module
        errors = validate_module({}, "identity.schema.json")
        self.assertGreater(len(errors), 0)

    def test_03_bad_profile_path_fails(self):
        from dlc.validate import validate_module
        data = {"enabled": True, "profile": "wrong/path.json"}
        errors = validate_module(data, "identity.schema.json")
        self.assertGreater(len(errors), 0)

    def test_04_speech_can_be_null(self):
        from dlc.validate import validate_module
        data = {"enabled": True, "personality": "identity/personality.json",
                "speech": None}
        errors = validate_module(data, "identity.schema.json")
        self.assertEqual(errors, [])


class TestBodySchema(unittest.TestCase):
    """P0-10: body module schema."""

    def test_01_enabled_true_valid(self):
        from dlc.validate import validate_module
        data = {"enabled": True, "anatomy": "body/anatomy.json",
                "zones": "body/zones.json"}
        errors = validate_module(data, "body.schema.json")
        self.assertEqual(errors, [])


class TestEngineSchema(unittest.TestCase):
    """P0-11: engine module schema."""

    def test_01_all_configs_valid(self):
        from dlc.validate import validate_module
        data = {"enabled": True,
                "entities": "engine/entities.json",
                "modifiers": "engine/modifiers.json",
                "thresholds": "engine/thresholds.json",
                "narratives": "engine/narratives.json"}
        errors = validate_module(data, "engine.schema.json")
        self.assertEqual(errors, [])


class TestMemorySchema(unittest.TestCase):
    """P0-12: memory module schema."""

    def test_01_valid_architecture(self):
        from dlc.validate import validate_module
        data = {"enabled": True}
        errors = validate_module(data, "memory.schema.json")
        self.assertEqual(errors, [])


class TestBehaviorSchema(unittest.TestCase):
    """P0-13: behavior module schema."""

    def test_01_valid_lws(self):
        from dlc.validate import validate_module
        data = {"enabled": True, "lws_rules": "behavior/lws_rules.json"}
        errors = validate_module(data, "behavior.schema.json")
        self.assertEqual(errors, [])


class TestInteractionSchema(unittest.TestCase):
    """P0-14: interaction module schema."""

    def test_01_valid_commands_items(self):
        from dlc.validate import validate_module
        data = {"enabled": True,
                "commands": "interaction/commands.json",
                "items": "interaction/items.json"}
        errors = validate_module(data, "interaction.schema.json")
        self.assertEqual(errors, [])


class TestVaultSchema(unittest.TestCase):
    """vault module schema."""

    def test_01_valid_secrets(self):
        from dlc.validate import validate_module
        data = {"enabled": True, "secrets": "vault/secrets.json"}
        errors = validate_module(data, "vault.schema.json")
        self.assertEqual(errors, [])


class TestFullCardValidation(unittest.TestCase):
    """P0-15: full card.json + all module schemas validation."""

    def test_01_l0_minimal_valid(self):
        from dlc.validate import validate_card
        card = _load_json("valid_card.json")
        errors = validate_card(card)
        self.assertEqual(errors, [])

    def test_02_l3_full_valid(self):
        from dlc.validate import validate_card
        card = _load_json("l3_card.json")
        errors = validate_card(card)
        self.assertEqual(errors, [])

    def test_03_disabled_module_no_error(self):
        """Disabled modules don't need config paths."""
        from dlc.validate import validate_card
        card = _load_json("valid_card.json")
        # body is disabled — that's fine
        self.assertFalse(card["modules"]["body"]["enabled"])
        errors = validate_card(card)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
