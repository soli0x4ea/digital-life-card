"""Phase 3A: Command system tests — P3-01 ~ P3-03 (v2.6.0)."""

import unittest, json, os, sys, tempfile, shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
sys.path.insert(0, _PROJ)
_FIX = os.path.join(_HERE, "fixtures", "interaction")
_EFIX = os.path.join(_HERE, "fixtures", "engine")


def _setup_cmd_env():
    """Create engine (no memory store) for command execution tests."""
    from dlc.engine.entity import EntityEngine, EntityState
    tmp = tempfile.mkdtemp()
    eeng = EntityEngine(state_dir=os.path.join(tmp, "state"))
    with open(os.path.join(_EFIX, "entities.json")) as f:
        entities = json.load(f)["entities"]
    for eid, ecfg in entities.items():
        ch = {k: float(v.get("initial", 0)) for k, v in ecfg["channels"].items()}
        fl = {k: 0 for k in ecfg.get("flags", {})}
        eeng.save(EntityState(entity_id=eid, channels=ch, flags=fl))
    state = eeng.load("e_g")
    # Modifiers
    with open(os.path.join(_EFIX, "modifiers.json")) as f:
        modifiers = json.load(f)["modifiers"]
    # Narratives
    with open(os.path.join(_EFIX, "narratives.json")) as f:
        narratives = json.load(f)["events"]
    return tmp, state, modifiers, narratives


# ═══════════════════════════════════════════════════════════════
# P3-01: Command config loader
# ═══════════════════════════════════════════════════════════════

class TestCommandLoader(unittest.TestCase):

    def test_01_load_commands(self):
        from dlc.interaction.commands import CommandLoader
        cfg = CommandLoader(_FIX).load()
        self.assertEqual(len(cfg.commands), 3)

    def test_02_command_fields(self):
        from dlc.interaction.commands import CommandLoader
        cfg = CommandLoader(_FIX).load()
        c = cfg.commands[0]
        self.assertEqual(c.id, "cmd_status")
        self.assertIn("状态", c.triggers)
        self.assertEqual(c.effects[0]["type"], "narrative")

    def test_03_cooldown_parsed(self):
        from dlc.interaction.commands import CommandLoader
        cfg = CommandLoader(_FIX).load()
        self.assertEqual(cfg.commands[1].cooldown_seconds, 30)
        self.assertEqual(cfg.commands[2].cooldown_seconds, 60)


# ═══════════════════════════════════════════════════════════════
# P3-02: Trigger word matching
# ═══════════════════════════════════════════════════════════════

class TestTriggerMatcher(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from dlc.interaction.commands import CommandLoader
        cls.cfg = CommandLoader(_FIX).load()

    def test_01_exact_trigger_match(self):
        from dlc.interaction.commands import match_command
        cmd = match_command("状态", self.cfg)
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.id, "cmd_status")

    def test_02_substring_trigger_match(self):
        from dlc.interaction.commands import match_command
        cmd = match_command("帮我查一下身体", self.cfg)
        self.assertIsNotNone(cmd)

    def test_03_no_match_returns_none(self):
        from dlc.interaction.commands import match_command
        cmd = match_command("xyzzy_nonexistent", self.cfg)
        self.assertIsNone(cmd)

    def test_04_first_match_wins(self):
        from dlc.interaction.commands import match_command
        cmd = match_command("恢复", self.cfg)
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.id, "cmd_heal")


# ═══════════════════════════════════════════════════════════════
# P3-03: Command effect executor
# ═══════════════════════════════════════════════════════════════

class TestCommandExecutor(unittest.TestCase):

    def setUp(self):
        self.tmp, self.state, self.modifiers, self.narratives = _setup_cmd_env()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_modifier_effect(self):
        from dlc.interaction.commands import execute_command
        old = self.state.channels["ch_g_a"]
        result = execute_command(
            {"type": "modifier", "modifier_id": "mod_eg_av_add", "intensity": 1},
            self.state, self.modifiers, self.narratives
        )
        self.assertTrue(result.success)
        self.assertNotEqual(self.state.channels["ch_g_a"], old)

    def test_02_narrative_effect(self):
        from dlc.interaction.commands import execute_command
        result = execute_command(
            {"type": "narrative", "event_id": "ev_g_a_warn"},
            self.state, self.modifiers, self.narratives
        )
        self.assertTrue(result.success)
        self.assertIsNotNone(result.output)

    def test_03_state_flag_set_effect(self):
        from dlc.interaction.commands import execute_command
        result = execute_command(
            {"type": "state", "action": "flag_set", "flag": "ch_g_flag_01"},
            self.state, self.modifiers, self.narratives
        )
        self.assertTrue(result.success)
        self.assertEqual(self.state.flags["ch_g_flag_01"], 1)


# ═══════════════════════════════════════════════════════════════
# P3-04: Command cooldown
# ═══════════════════════════════════════════════════════════════

class TestCommandCooldown(unittest.TestCase):

    def test_01_within_cooldown_blocked(self):
        from dlc.interaction.commands import _is_cooling, _mark_used
        from dlc.interaction.commands import CommandLoader
        cfg = CommandLoader(_FIX).load()
        cmd = cfg.commands[0]  # cooldown_seconds=5
        _mark_used(cmd.id, tick=0)
        self.assertTrue(_is_cooling(cmd, tick=1))

    def test_02_after_cooldown_allowed(self):
        from dlc.interaction.commands import _mark_used, _is_cooling
        from dlc.interaction.commands import CommandLoader
        cfg = CommandLoader(_FIX).load()
        cmd = cfg.commands[0]
        _mark_used(cmd.id, tick=0)
        self.assertFalse(_is_cooling(cmd, tick=6))

    def test_03_no_cooldown_config_always_allowed(self):
        from dlc.interaction.commands import _is_cooling
        from dlc.interaction.commands import CommandLoader
        cfg = CommandLoader(_FIX).load()
        cmd = cfg.commands[1]  # no cooldown (cmd_set_flag is index 2)
        self.assertFalse(_is_cooling(cmd, tick=0))


# ═══════════════════════════════════════════════════════════════
# P3-05: Command prefix parsing
# ═══════════════════════════════════════════════════════════════

class TestPrefixParsing(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from dlc.interaction.commands import CommandLoader
        cls.cfg = CommandLoader(_FIX).load()

    def test_01_slash_prefix_detected(self):
        from dlc.interaction.commands import parse_input
        cmd, args = parse_input("/状态", self.cfg)
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.id, "cmd_status")

    def test_02_slash_with_args(self):
        from dlc.interaction.commands import parse_input
        cmd, args = parse_input("/heal 3", self.cfg)
        self.assertIsNotNone(cmd)

    def test_03_no_slash_still_matches(self):
        from dlc.interaction.commands import parse_input
        cmd, args = parse_input("状态", self.cfg)
        self.assertIsNotNone(cmd)


# ═══════════════════════════════════════════════════════════════
# P3-06: Help system
# ═══════════════════════════════════════════════════════════════

class TestHelpSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from dlc.interaction.commands import CommandLoader
        cls.cfg = CommandLoader(_FIX).load()

    def test_01_help_includes_all_commands(self):
        from dlc.interaction.commands import generate_help
        text = generate_help(self.cfg)
        self.assertIn("cmd_status", text)
        self.assertIn("cmd_heal", text)

    def test_02_help_includes_triggers(self):
        from dlc.interaction.commands import generate_help
        text = generate_help(self.cfg)
        self.assertIn("状态", text)

    def test_03_help_is_string(self):
        from dlc.interaction.commands import generate_help
        text = generate_help(self.cfg)
        self.assertGreater(len(text), 50)


# ═══════════════════════════════════════════════════════════════
# P3-07~09: Item system core (loader + inventory + use)
# ═══════════════════════════════════════════════════════════════

class TestItemLoader(unittest.TestCase):
    """P3-07: Load interaction/items.json."""

    def test_01_load_items(self):
        from dlc.interaction.items import ItemLoader
        items = ItemLoader(_FIX).load()
        self.assertEqual(len(items), 5)

    def test_02_item_types(self):
        from dlc.interaction.items import ItemLoader
        items = ItemLoader(_FIX).load()
        types = {i.type for i in items}
        self.assertIn("consumable", types)
        self.assertIn("equippable", types)
        self.assertIn("permanent", types)


class TestInventory(unittest.TestCase):
    """P3-08: Inventory CRUD with max_quantity."""

    @classmethod
    def setUpClass(cls):
        from dlc.interaction.items import ItemLoader
        cls.items = ItemLoader(_FIX).load()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.interaction.items import Inventory
        self.inv = Inventory(state_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_add_item(self):
        self.inv.add(self.items[0], qty=3)
        count = self.inv.count("item_potion")
        self.assertEqual(count, 3)

    def test_02_add_exceeds_max(self):
        self.inv.add(self.items[0], qty=100)
        count = self.inv.count("item_potion")
        self.assertEqual(count, 20)  # capped at max_quantity

    def test_03_remove_item(self):
        self.inv.add(self.items[0], qty=5)
        self.inv.remove("item_potion", qty=2)
        self.assertEqual(self.inv.count("item_potion"), 3)

    def test_04_use_consumable(self):
        self.inv.add(self.items[0], qty=2)
        result = self.inv.use("item_potion")
        self.assertTrue(result)
        self.assertEqual(self.inv.count("item_potion"), 1)

    def test_05_use_equippable_equips(self):
        self.inv.add(self.items[1], qty=1)
        self.inv.use("item_charm")
        self.assertTrue(self.inv.is_equipped("item_charm"))

    def test_06_equippable_unequip(self):
        self.inv.add(self.items[1], qty=1)
        self.inv.use("item_charm")
        self.inv.unequip("item_charm")
        self.assertFalse(self.inv.is_equipped("item_charm"))


# ═══════════════════════════════════════════════════════════════
# P3-10: Consumable logic — cooldown + consume_on_use
# ═══════════════════════════════════════════════════════════════

class TestConsumableLogic(unittest.TestCase):
    """P3-10: consumable cooldown blocking and consumption."""

    @classmethod
    def setUpClass(cls):
        from dlc.interaction.items import ItemLoader
        cls.items = ItemLoader(_FIX).load()
        cls.potion = next(i for i in cls.items if i.id == "item_potion")
        cls.elixir = next(i for i in cls.items if i.id == "item_elixir")
        cls.scroll = next(i for i in cls.items if i.id == "item_scroll")
        cls.charm = next(i for i in cls.items if i.id == "item_charm")
        cls.badge = next(i for i in cls.items if i.id == "item_badge")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.interaction.items import Inventory
        self.inv = Inventory(state_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_consumable_uses_one_per_call(self):
        self.inv.add(self.potion, qty=5)
        self.inv.use("item_potion", _now=100.0)
        self.assertEqual(self.inv.count("item_potion"), 4)
        self.inv.use("item_potion", _now=111.0)  # after cooldown (10s)
        self.assertEqual(self.inv.count("item_potion"), 3)

    def test_02_consumable_cannot_use_when_empty(self):
        result = self.inv.use("item_potion")
        self.assertFalse(result)

    def test_03_cooldown_blocks_reuse(self):
        self.inv.add(self.elixir, qty=5)
        r1 = self.inv.use("item_elixir", _now=100.0)
        self.assertTrue(r1)
        r2 = self.inv.use("item_elixir", _now=102.0)  # only 2s elapsed, cooldown=5s
        self.assertFalse(r2)

    def test_04_cooldown_expires_allows_reuse(self):
        self.inv.add(self.elixir, qty=5)
        self.inv.use("item_elixir", _now=100.0)
        r2 = self.inv.use("item_elixir", _now=106.0)  # 6s elapsed > 5s cooldown
        self.assertTrue(r2)

    def test_05_no_cooldown_config_allows_spam(self):
        self.inv.add(self.scroll, qty=10)
        r1 = self.inv.use("item_scroll")
        r2 = self.inv.use("item_scroll")
        self.assertTrue(r1)
        self.assertTrue(r2)


# ═══════════════════════════════════════════════════════════════
# P3-11: Permanent items — use does not consume
# ═══════════════════════════════════════════════════════════════

class TestPermanentItems(unittest.TestCase):
    """P3-11: permanent type items are never consumed."""

    @classmethod
    def setUpClass(cls):
        from dlc.interaction.items import ItemLoader
        cls.items = ItemLoader(_FIX).load()
        cls.badge = next(i for i in cls.items if i.id == "item_badge")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.interaction.items import Inventory
        self.inv = Inventory(state_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_permanent_use_does_not_consume(self):
        self.inv.add(self.badge, qty=1)
        r = self.inv.use("item_badge")
        self.assertTrue(r)
        self.assertEqual(self.inv.count("item_badge"), 1)

    def test_02_permanent_use_always_succeeds(self):
        self.inv.add(self.badge, qty=1)
        r1 = self.inv.use("item_badge")
        r2 = self.inv.use("item_badge")
        r3 = self.inv.use("item_badge")
        self.assertTrue(r1)
        self.assertTrue(r2)
        self.assertTrue(r3)

    def test_03_permanent_use_no_quantity(self):
        """Using permanent item without adding it still should not crash."""
        r = self.inv.use("item_badge")
        self.assertFalse(r)  # not in inventory, can't use


# ═══════════════════════════════════════════════════════════════
# P3-12: Equippable items — effects on equip / off on unequip
# ═══════════════════════════════════════════════════════════════

class TestEquippableEffects(unittest.TestCase):
    """P3-12: equippable effects apply/remove on equip/unequip."""

    @classmethod
    def setUpClass(cls):
        from dlc.interaction.items import ItemLoader
        cls.items = ItemLoader(_FIX).load()
        cls.charm = next(i for i in cls.items if i.id == "item_charm")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.interaction.items import Inventory
        self.inv = Inventory(state_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_equipped_item_effects_accessible(self):
        self.inv.add(self.charm, qty=1)
        self.inv.use("item_charm")
        active = self.inv.active_effects()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["modifier_id"], "mod_eg_av_add")

    def test_02_unequip_removes_effects(self):
        self.inv.add(self.charm, qty=1)
        self.inv.use("item_charm")
        self.inv.unequip("item_charm")
        active = self.inv.active_effects()
        self.assertEqual(len(active), 0)

    def test_03_requip_restores_effects(self):
        self.inv.add(self.charm, qty=1)
        self.inv.use("item_charm")       # equip
        self.inv.unequip("item_charm")    # unequip
        self.inv.use("item_charm")        # re-equip
        active = self.inv.active_effects()
        self.assertEqual(len(active), 1)

    def test_04_cannot_equip_without_owning(self):
        self.inv.use("item_charm")
        self.assertFalse(self.inv.is_equipped("item_charm"))


# ═══════════════════════════════════════════════════════════════
# P3-13: Rarity system — 5 levels
# ═══════════════════════════════════════════════════════════════

class TestRaritySystem(unittest.TestCase):
    """P3-13: 5-tier rarity enum and display."""

    def test_01_rarity_levels_defined(self):
        from dlc.interaction.items import RARITY_LEVELS
        self.assertEqual(len(RARITY_LEVELS), 5)
        self.assertEqual(RARITY_LEVELS[0], "common")
        self.assertEqual(RARITY_LEVELS[4], "legendary")

    def test_02_rarity_display_name(self):
        from dlc.interaction.items import RARITY_DISPLAY
        self.assertEqual(RARITY_DISPLAY["common"], "普通")
        self.assertEqual(RARITY_DISPLAY["legendary"], "传说")

    def test_03_loaded_items_have_rarity(self):
        from dlc.interaction.items import ItemLoader
        items = ItemLoader(_FIX).load()
        rarities = {i.rarity for i in items}
        self.assertIn("common", rarities)
        self.assertIn("rare", rarities)
        self.assertIn("legendary", rarities)
        self.assertIn("epic", rarities)
        self.assertIn("uncommon", rarities)

    def test_04_invalid_rarity_defaults(self):
        from dlc.interaction.items import ItemConfig
        item = ItemConfig(id="test", rarity="mythic")  # invalid
        from dlc.interaction.items import _validate_rarity
        self.assertEqual(_validate_rarity(item.rarity), "common")


# ═══════════════════════════════════════════════════════════════
# P3-14: Inventory persistence — save / load
# ═══════════════════════════════════════════════════════════════

class TestInventoryPersistence(unittest.TestCase):
    """P3-14: save and load inventory to/from disk."""

    @classmethod
    def setUpClass(cls):
        from dlc.interaction.items import ItemLoader
        cls.items = ItemLoader(_FIX).load()
        cls.potion = next(i for i in cls.items if i.id == "item_potion")
        cls.charm = next(i for i in cls.items if i.id == "item_charm")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_save_and_load_restores_slots(self):
        from dlc.interaction.items import Inventory
        inv1 = Inventory(state_dir=self.tmp)
        inv1.add(self.potion, qty=5)
        inv1.add(self.charm, qty=1)
        inv1.save()

        inv2 = Inventory(state_dir=self.tmp)
        inv2.register(self.potion)
        inv2.register(self.charm)
        inv2.load()
        self.assertEqual(inv2.count("item_potion"), 5)
        self.assertEqual(inv2.count("item_charm"), 1)

    def test_02_save_and_load_restores_equipped(self):
        from dlc.interaction.items import Inventory
        inv1 = Inventory(state_dir=self.tmp)
        inv1.add(self.charm, qty=1)
        inv1.use("item_charm")  # equip
        inv1.save()

        inv2 = Inventory(state_dir=self.tmp)
        inv2.register(self.charm)
        inv2.load()
        self.assertTrue(inv2.is_equipped("item_charm"))

    def test_03_load_empty_dir_returns_empty(self):
        from dlc.interaction.items import Inventory
        inv = Inventory(state_dir=self.tmp)
        inv.load()  # should not crash, inventory stays empty
        self.assertEqual(inv.count("item_potion"), 0)

    def test_04_save_then_load_preserves_cooldown_state(self):
        from dlc.interaction.items import Inventory
        inv1 = Inventory(state_dir=self.tmp)
        elixir = next(i for i in self.__class__.items if i.id == "item_elixir")
        inv1.add(elixir, qty=3)
        inv1.use("item_elixir", _now=100.0)
        inv1.save()

        inv2 = Inventory(state_dir=self.tmp)
        inv2.register(elixir)
        inv2.load()
        r = inv2.use("item_elixir", _now=101.0)
        self.assertFalse(r)


if __name__ == "__main__":
    unittest.main()
