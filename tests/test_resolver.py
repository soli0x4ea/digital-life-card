"""P0-16 + P0-21: ConfigResolver + CardRuntimeContext tests.

Phase 0c: Engine generalization — dynamic config loading.
"""

import unittest, json, os, sys, tempfile, shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _make_card_dir(base, card_data, extra_files=None):
    """Create a temporary card directory with card.json and optional config files."""
    card_dir = os.path.join(base, "test_card")
    os.makedirs(card_dir, exist_ok=True)
    with open(os.path.join(card_dir, "card.json"), "w", encoding="utf-8") as f:
        json.dump(card_data, f, indent=2)
    if extra_files:
        for rel_path, content in extra_files.items():
            full = os.path.join(card_dir, rel_path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                if isinstance(content, str):
                    f.write(content)
                else:
                    json.dump(content, f)
    return card_dir


# ── Increment 1: ConfigResolver ─────────────────────────────────

class TestConfigResolver(unittest.TestCase):
    """P0-16: ConfigResolver — dynamic config path resolution."""

    L0_CARD = {
        "protocol_version": "1.0.0",
        "card_id": "test-basic",
        "card_name": "Test Basic",
        "complexity_level": "L0",
        "author": "test",
        "created_at": "2026-07-08",
        "updated_at": "2026-07-08",
        "modules": {
            "identity": {"enabled": True, "profile": "identity/profile.json"}
        }
    }

    L1_CARD = {
        "protocol_version": "1.0.0",
        "card_id": "test-l1",
        "card_name": "Test L1",
        "complexity_level": "L1",
        "author": "test",
        "created_at": "2026-07-08",
        "updated_at": "2026-07-08",
        "modules": {
            "identity": {"enabled": True, "profile": "identity/profile.json",
                         "personality": "identity/personality.json"},
            "body": {"enabled": True, "anatomy": "body/anatomy.json",
                     "zones": "body/zones.json"},
            "engine": {"enabled": True,
                       "entities": "engine/entities.json",
                       "modifiers": "engine/modifiers.json",
                       "thresholds": "engine/thresholds.json",
                       "narratives": "engine/narratives.json"}
        }
    }

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_load_l0_with_real_files(self):
        """Load an L0 card and resolve its config files."""
        from dlc.resolver import ConfigResolver

        profile_data = {"name": "Test", "age": 1}
        card_dir = _make_card_dir(self.tmp, self.L0_CARD, {
            "identity/profile.json": profile_data,
        })

        resolver = ConfigResolver(card_dir)
        self.assertEqual(resolver.card_id, "test-basic")

        # Resolve profile
        cfg = resolver.load_config("identity", "profile")
        self.assertEqual(cfg, profile_data)

    def test_02_load_l1_with_engine_configs(self):
        """Load an L1 card and resolve engine configs."""
        from dlc.resolver import ConfigResolver

        entities_cfg = {"entities": {"e_test": {"label": "Test"}}}
        modifiers_cfg = {"modifiers": {"mod_test": {}}}
        thresholds_cfg = {"thresholds": {"thr_test": {}}}
        narratives_cfg = {"events": {"ev_test": {"label": "Test"}}}

        card_dir = _make_card_dir(self.tmp, self.L1_CARD, {
            "engine/entities.json": entities_cfg,
            "engine/modifiers.json": modifiers_cfg,
            "engine/thresholds.json": thresholds_cfg,
            "engine/narratives.json": narratives_cfg,
            "identity/profile.json": {"name": "Test"},
            "identity/personality.json": {"traits": []},
            "body/anatomy.json": {"parts": []},
            "body/zones.json": {"zones": []},
        })

        resolver = ConfigResolver(card_dir)
        self.assertEqual(resolver.card_id, "test-l1")

        # Resolve engine configs
        self.assertEqual(resolver.load_config("engine", "entities"), entities_cfg)
        self.assertEqual(resolver.load_config("engine", "modifiers"), modifiers_cfg)
        self.assertEqual(resolver.load_config("engine", "thresholds"), thresholds_cfg)
        self.assertEqual(resolver.load_config("engine", "narratives"), narratives_cfg)

    def test_03_resolver_caches_configs(self):
        """load_config should cache — second call returns same object."""
        from dlc.resolver import ConfigResolver

        card_dir = _make_card_dir(self.tmp, self.L0_CARD, {
            "identity/profile.json": {"name": "Original"},
        })

        resolver = ConfigResolver(card_dir)
        cfg1 = resolver.load_config("identity", "profile")
        cfg2 = resolver.load_config("identity", "profile")
        self.assertIs(cfg1, cfg2)

    def test_04_missing_file_raises(self):
        """Loading a missing config file should raise ResolverError."""
        from dlc.resolver import ConfigResolver, ResolverError

        card_dir = _make_card_dir(self.tmp, self.L0_CARD)  # no files

        resolver = ConfigResolver(card_dir)
        with self.assertRaises(ResolverError):
            resolver.load_config("identity", "profile")

    def test_05_disabled_module_raises(self):
        """Loading a config from a disabled module should raise."""
        from dlc.resolver import ConfigResolver, ResolverError

        card_dir = _make_card_dir(self.tmp, self.L0_CARD, {
            "identity/profile.json": {"name": "OK"},
        })

        resolver = ConfigResolver(card_dir)
        # body is disabled in L0_CARD
        with self.assertRaises(ResolverError):
            resolver.load_config("body", "anatomy")

    def test_06_state_dir_is_card_scoped(self):
        """State directory should be inside the card directory."""
        from dlc.resolver import ConfigResolver

        card_dir = _make_card_dir(self.tmp, self.L0_CARD, {
            "identity/profile.json": {"name": "A"},
        })

        resolver = ConfigResolver(card_dir)
        state = resolver.state_dir
        # State dir should be inside the card directory
        self.assertIn("test_card", state)
        self.assertTrue(state.endswith("state"))

    def test_07_list_enabled_modules(self):
        """Should list all enabled module names."""
        from dlc.resolver import ConfigResolver

        card_dir = _make_card_dir(self.tmp, self.L1_CARD, {
            "identity/profile.json": {"name": ""},
            "identity/personality.json": {"traits": []},
            "body/anatomy.json": {"parts": []},
            "body/zones.json": {"zones": []},
            "engine/entities.json": {"entities": {}},
            "engine/modifiers.json": {"modifiers": {}},
            "engine/thresholds.json": {"thresholds": {}},
            "engine/narratives.json": {"events": {}},
        })

        resolver = ConfigResolver(card_dir)
        modules = resolver.enabled_modules
        self.assertIn("identity", modules)
        self.assertIn("body", modules)
        self.assertIn("engine", modules)
        self.assertNotIn("memory", modules)  # L1 doesn't have memory


# ── Increment 2: CardRuntimeContext ─────────────────────────────

class TestCardRuntimeContext(unittest.TestCase):
    """P0-21: CardRuntimeContext — contextual engine access."""

    L1_CARD = {
        "protocol_version": "1.0.0",
        "card_id": "test-ctx",
        "card_name": "Context Test",
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

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_context_holds_card_and_resolver(self):
        """CardRuntimeContext should wrap card + resolver + state dir."""
        from dlc.context import CardRuntimeContext

        card_dir = _make_card_dir(self.tmp, self.L1_CARD, {
            "identity/profile.json": {"name": "Ctx"},
            "body/anatomy.json": {"parts": []},
            "engine/entities.json": {"entities": {}},
            "engine/modifiers.json": {"modifiers": {}},
            "engine/thresholds.json": {"thresholds": {}},
            "engine/narratives.json": {"events": {}},
        })

        ctx = CardRuntimeContext(card_dir)
        self.assertEqual(ctx.card_id, "test-ctx")
        self.assertIsNotNone(ctx.resolver)

        # Can load configs through context
        cfg = ctx.load_engine_config("entities")
        self.assertIn("entities", cfg)

    def test_02_engine_shortcuts(self):
        """Context should provide shortcut methods for engine configs."""
        from dlc.context import CardRuntimeContext

        entities = {"entities": {"e_test": {"label": "Test"}}}
        modifiers = {"modifiers": {"mod_001": {}}}
        thresholds = {"thresholds": {"thr_001": {}}}
        narratives = {"events": {"ev_001": {"label": "Test"}}}

        card_dir = _make_card_dir(self.tmp, self.L1_CARD, {
            "identity/profile.json": {"name": "S"},
            "body/anatomy.json": {"parts": []},
            "engine/entities.json": entities,
            "engine/modifiers.json": modifiers,
            "engine/thresholds.json": thresholds,
            "engine/narratives.json": narratives,
        })

        ctx = CardRuntimeContext(card_dir)
        self.assertEqual(ctx.entities, entities)
        self.assertEqual(ctx.modifiers, modifiers)
        self.assertEqual(ctx.thresholds, thresholds)
        self.assertEqual(ctx.narratives, narratives)

    def test_03_state_dir_created(self):
        """State directory should be automatically created."""
        from dlc.context import CardRuntimeContext

        card_dir = _make_card_dir(self.tmp, self.L1_CARD, {
            "identity/profile.json": {"name": "S"},
            "body/anatomy.json": {"parts": []},
            "engine/entities.json": {"entities": {}},
            "engine/modifiers.json": {"modifiers": {}},
            "engine/thresholds.json": {"thresholds": {}},
            "engine/narratives.json": {"events": {}},
        })

        ctx = CardRuntimeContext(card_dir)
        self.assertTrue(os.path.isdir(ctx.state_dir))

    def test_04_multi_card_isolation(self):
        """Two CardRuntimeContext instances should have independent states."""
        from dlc.context import CardRuntimeContext

        card_dir_a = _make_card_dir(os.path.join(self.tmp, "a"), self.L1_CARD, {
            "identity/profile.json": {"name": "Alice"},
            "body/anatomy.json": {"parts": []},
            "engine/entities.json": {"entities": {}},
            "engine/modifiers.json": {"modifiers": {}},
            "engine/thresholds.json": {"thresholds": {}},
            "engine/narratives.json": {"events": {}},
        })

        L1_B = dict(self.L1_CARD)
        L1_B["card_id"] = "test-ctx-b"
        L1_B["card_name"] = "Context B"
        card_dir_b = _make_card_dir(os.path.join(self.tmp, "b"), L1_B, {
            "identity/profile.json": {"name": "Bob"},
            "body/anatomy.json": {"parts": []},
            "engine/entities.json": {"entities": {}},
            "engine/modifiers.json": {"modifiers": {}},
            "engine/thresholds.json": {"thresholds": {}},
            "engine/narratives.json": {"events": {}},
        })

        ctx_a = CardRuntimeContext(card_dir_a)
        ctx_b = CardRuntimeContext(card_dir_b)

        # Different card IDs
        self.assertEqual(ctx_a.card_id, "test-ctx")
        self.assertEqual(ctx_b.card_id, "test-ctx-b")

        # Isolated state directories
        self.assertNotEqual(ctx_a.state_dir, ctx_b.state_dir)
        self.assertTrue(os.path.isdir(ctx_a.state_dir))
        self.assertTrue(os.path.isdir(ctx_b.state_dir))


if __name__ == "__main__":
    unittest.main()
