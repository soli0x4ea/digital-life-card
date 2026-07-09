"""Phase 3: L3 Integration tests — P3-20 ~ P3-23 (v2.6.0)."""

import unittest, os, sys, tempfile, shutil, json

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
sys.path.insert(0, _PROJ)
_CARDS = os.path.join(_PROJ, "cards", "demo-l3")
_CFIX_ENG = os.path.join(_HERE, "fixtures", "engine")
_CFIX_INT = os.path.join(_HERE, "fixtures", "interaction")


def _exec_cmd(cmd, state, modifiers_cfg, narratives_cfg):
    """Execute all effects of a command config."""
    from dlc.interaction.commands import execute_command, CommandResult
    for effect in cmd.effects:
        result = execute_command(effect, state, modifiers_cfg, narratives_cfg)
        if not result.success:
            return result
    return CommandResult(success=True, output="")


def _setup_entity_state(tmp, entities_cfg):
    """Create EntityEngine with entities from config."""
    from dlc.engine.entity import EntityEngine, EntityState
    eng = EntityEngine(state_dir=os.path.join(tmp, "state"))
    for eid, ecfg in entities_cfg.items():
        ch = {k: float(v.get("initial", 0)) for k, v in ecfg["channels"].items()}
        fl = {k: 0 for k in ecfg.get("flags", {})}
        eng.save(EntityState(entity_id=eid, channels=ch, flags=fl))
    return eng


# ═══════════════════════════════════════════════════════════════
# P3-20: L3 Card Load + Validate
# ═══════════════════════════════════════════════════════════════

class TestL3CardSmoke(unittest.TestCase):
    """P3-20: L3 demo card — load and validate."""

    def test_01_card_loads_as_l3(self):
        from dlc.loader import load_card
        cfg = load_card(_CARDS)
        self.assertEqual(cfg.card_id, "demo-l3")
        self.assertEqual(cfg.complexity_level, "L3")

    def test_02_all_modules_enabled(self):
        from dlc.loader import load_card, resolve_modules
        cfg = load_card(_CARDS)
        mods = resolve_modules(cfg)
        for m in ["identity", "body", "engine", "memory", "behavior", "interaction", "vault"]:
            self.assertIn(m, mods, f"Module {m} should be enabled")

    def test_03_interaction_configs_exist(self):
        from dlc.loader import load_card
        cfg = load_card(_CARDS)
        imod = cfg.modules["interaction"]
        self.assertTrue(os.path.isfile(os.path.join(_CARDS, imod["commands"])))
        self.assertTrue(os.path.isfile(os.path.join(_CARDS, imod["items"])))

    def test_04_card_validates_clean(self):
        from dlc.loader import load_card
        from dlc.validate import validate_card
        cfg = load_card(_CARDS)
        errors = validate_card(cfg._raw)
        self.assertEqual(errors, [])


# ═══════════════════════════════════════════════════════════════
# P3-21: Command system integration
# ═══════════════════════════════════════════════════════════════

class TestCommandIntegration(unittest.TestCase):
    """P3-21: Commands + engine + state pipeline (v2.6.0, no memory effect)."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(_CFIX_ENG, "entities.json")) as f:
            cls.entities_cfg = json.load(f)["entities"]
        with open(os.path.join(_CFIX_ENG, "modifiers.json")) as f:
            cls.modifiers_cfg = json.load(f)["modifiers"]
        with open(os.path.join(_CFIX_ENG, "narratives.json")) as f:
            cls.narratives_cfg = json.load(f)["events"]

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.eng = _setup_entity_state(self.tmp, self.entities_cfg)
        self.state = self.eng.load("e_g")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_command_affects_state(self):
        from dlc.interaction.commands import CommandLoader, match_command, _mark_used, execute_command
        cfg = CommandLoader(_CFIX_INT).load()
        cmd = match_command("激活", cfg)
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.id, "cmd_set_flag")
        self.assertEqual(self.state.flags.get("ch_g_flag_01", 0), 0)
        _mark_used(cmd.id, tick=0)
        for effect in cmd.effects:
            execute_command(effect, self.state, self.modifiers_cfg, self.narratives_cfg)
        self.assertEqual(self.state.flags["ch_g_flag_01"], 1)

    def test_02_help_lists_all_commands(self):
        from dlc.interaction.commands import CommandLoader, generate_help
        cfg = CommandLoader(_CFIX_INT).load()
        text = generate_help(cfg)
        for c in cfg.commands:
            self.assertIn(c.id, text)


# ═══════════════════════════════════════════════════════════════
# P3-22: Item system integration
# ═══════════════════════════════════════════════════════════════

class TestItemIntegration(unittest.TestCase):
    """P3-22: Items + engine state pipeline."""

    @classmethod
    def setUpClass(cls):
        from dlc.interaction.items import ItemLoader
        cls.items = ItemLoader(_CFIX_INT).load()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_consumable_use_then_save_load(self):
        from dlc.interaction.items import Inventory
        potion = next(i for i in self.__class__.items if i.id == "item_potion")
        inv1 = Inventory(state_dir=self.tmp)
        inv1.add(potion, qty=5)
        inv1.use("item_potion", _now=1000.0)
        inv1.save()
        inv2 = Inventory(state_dir=self.tmp)
        inv2.register(potion)
        inv2.load()
        self.assertEqual(inv2.count("item_potion"), 4)

    def test_02_permanent_item_effects_in_active(self):
        from dlc.interaction.items import Inventory
        badge = next(i for i in self.__class__.items if i.id == "item_badge")
        inv = Inventory(state_dir=self.tmp)
        inv.add(badge, qty=1)
        inv.use("item_badge")
        effects = inv.active_effects()
        self.assertTrue(len(effects) > 0)

    def test_03_equipped_persistence_and_effects(self):
        from dlc.interaction.items import Inventory
        charm = next(i for i in self.__class__.items if i.id == "item_charm")
        inv1 = Inventory(state_dir=self.tmp)
        inv1.add(charm, qty=1)
        inv1.use("item_charm")
        inv1.save()
        inv2 = Inventory(state_dir=self.tmp)
        inv2.register(charm)
        inv2.load()
        self.assertTrue(inv2.is_equipped("item_charm"))
        self.assertTrue(len(inv2.active_effects()) > 0)


# ═══════════════════════════════════════════════════════════════
# P3-23: End-to-end L3 pipeline
# ═══════════════════════════════════════════════════════════════

class TestL3EndToEnd(unittest.TestCase):
    """P3-23: Full L3 pipeline: commands + items + vault."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(_CFIX_ENG, "entities.json")) as f:
            cls.entities_cfg = json.load(f)["entities"]
        with open(os.path.join(_CFIX_ENG, "modifiers.json")) as f:
            cls.modifiers_cfg = json.load(f)["modifiers"]
        with open(os.path.join(_CFIX_ENG, "narratives.json")) as f:
            cls.narratives_cfg = json.load(f)["events"]

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.eng = _setup_entity_state(self.tmp, self.entities_cfg)
        self.state = self.eng.load("e_g")
        from dlc.interaction.items import ItemLoader, Inventory
        items = ItemLoader(_CFIX_INT).load()
        self.inv = Inventory(state_dir=self.tmp)
        for it in items:
            self.inv.register(it)
        self.inv.add(items[0], qty=3)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_full_vault_cycle(self):
        from dlc.vault import Vault
        vault_dir = os.path.join(self.tmp, "vault")
        v = Vault(vault_dir, max_attempts=3, lockout_seconds=10)
        v.write({"api_token": "abc123", "user_id": "demo-l3"}, "master-pass")
        data = v.read("master-pass")
        self.assertEqual(data["api_token"], "abc123")
        with self.assertRaises(ValueError):
            v.read("wrong")
        data = v.read("master-pass")
        self.assertEqual(data["user_id"], "demo-l3")

    def test_02_command_then_item_pipeline(self):
        from dlc.interaction.commands import CommandLoader, match_command, _mark_used, execute_command
        cfg = CommandLoader(_CFIX_INT).load()
        cmd = match_command("激活", cfg)
        self.assertEqual(self.state.flags.get("ch_g_flag_01", 0), 0)
        _mark_used(cmd.id, tick=0)
        for effect in cmd.effects:
            execute_command(effect, self.state, self.modifiers_cfg, self.narratives_cfg)
        self.assertEqual(self.state.flags["ch_g_flag_01"], 1)
        self.assertEqual(self.inv.count("item_potion"), 3)
        self.inv.use("item_potion", _now=1000.0)
        self.assertEqual(self.inv.count("item_potion"), 2)

    def test_03_item_inventory_persists_across_instances(self):
        from dlc.interaction.items import Inventory
        items = list(self.inv._items.values())
        self.inv.add(items[1], qty=1)
        self.inv.use("item_charm")
        self.inv.save()
        inv2 = Inventory(state_dir=self.tmp)
        for it in items:
            inv2.register(it)
        inv2.load()
        self.assertTrue(inv2.is_equipped("item_charm"))
        self.assertEqual(inv2.count("item_potion"), 3)


if __name__ == "__main__":
    unittest.main()
