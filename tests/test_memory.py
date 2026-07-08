"""Phase 2B: Memory system tests — P2-09 ~ P2-16."""

import unittest, json, os, sys, tempfile, shutil, time

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
sys.path.insert(0, _PROJ)
_FIX = os.path.join(_HERE, "fixtures", "memory")


# ═══════════════════════════════════════════════════════════════
# P2-09: Memory architecture loader
# ═══════════════════════════════════════════════════════════════

class TestArchitectureLoader(unittest.TestCase):

    def test_01_load_layers(self):
        from dlc.memory.core import MemoryArchitecture, load_architecture
        arch = load_architecture(_FIX)
        self.assertEqual(len(arch.layers), 3)
        self.assertEqual(arch.layers[0].id, "working")

    def test_02_ttl_parsed(self):
        from dlc.memory.core import load_architecture
        arch = load_architecture(_FIX)
        self.assertEqual(arch.layers[0].ttl_seconds, 3600)
        self.assertIsNone(arch.layers[2].ttl_seconds)

    def test_03_capacity_parsed(self):
        from dlc.memory.core import load_architecture
        arch = load_architecture(_FIX)
        self.assertEqual(arch.layers[0].capacity, 100)
        self.assertEqual(arch.layers[1].capacity, 1000)

    def test_04_promotion_threshold(self):
        from dlc.memory.core import load_architecture
        arch = load_architecture(_FIX)
        self.assertEqual(arch.layers[1].promotion_threshold, 10)
        self.assertIsNone(arch.layers[2].promotion_threshold)

    def test_05_consolidation_config(self):
        from dlc.memory.core import load_architecture
        arch = load_architecture(_FIX)
        self.assertEqual(arch.consolidation["interval_seconds"], 3600)


# ═══════════════════════════════════════════════════════════════
# P2-10: Memory CRUD
# ═══════════════════════════════════════════════════════════════

class TestMemoryCRUD(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from dlc.memory.core import load_architecture
        cls.arch = load_architecture(_FIX)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.memory.core import MemoryStore
        self.store = MemoryStore(self.tmp, self.arch)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_write_and_read(self):
        mid = self.store.write("working", "hello world", tags=["test"])
        entry = self.store.read(mid)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.content, "hello world")
        self.assertEqual(entry.layer_id, "working")

    def test_02_write_auto_timestamp(self):
        mid = self.store.write("working", "x")
        entry = self.store.read(mid)
        self.assertGreater(entry.created_at, 0)

    def test_03_list_by_layer(self):
        self.store.write("working", "a")
        self.store.write("working", "b")
        self.store.write("short_term", "c")
        entries = self.store.list_layer("working")
        self.assertEqual(len(entries), 2)

    def test_04_update_content(self):
        mid = self.store.write("working", "old")
        self.store.update(mid, content="new")
        entry = self.store.read(mid)
        self.assertEqual(entry.content, "new")

    def test_05_delete(self):
        mid = self.store.write("working", "x")
        self.store.delete(mid)
        self.assertIsNone(self.store.read(mid))

    def test_06_capacity_enforced(self):
        """Write more than capacity → oldest evicted."""
        # Create arch with capacity=3
        from dlc.memory.core import MemoryArchitecture, LayerConfig
        small = MemoryArchitecture(
            layers=[LayerConfig("working", "WM", 3600, 3, 5)],
            consolidation={"interval_seconds": 3600, "max_per_cycle": 10}
        )
        from dlc.memory.core import MemoryStore
        tmp2 = tempfile.mkdtemp()
        try:
            store = MemoryStore(tmp2, small)
            store.write("working", "oldest")
            store.write("working", "mid")
            store.write("working", "newest")
            store.write("working", "overflow")  # should evict "oldest"
            entries = store.list_layer("working")
            self.assertEqual(len(entries), 3)
            contents = [e.content for e in entries]
            self.assertNotIn("oldest", contents)
            self.assertIn("overflow", contents)
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)

    def test_07_increment_access_count(self):
        mid = self.store.write("working", "x")
        self.store.read(mid)  # access #1
        self.store.read(mid)  # access #2
        entry = self.store.read(mid)  # access #3
        self.assertGreaterEqual(entry.access_count, 3)


# ═══════════════════════════════════════════════════════════════
# P2-11: TTL auto-expiry
# ═══════════════════════════════════════════════════════════════

class TestMemoryTTL(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from dlc.memory.core import load_architecture
        cls.arch = load_architecture(_FIX)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.memory.core import MemoryStore
        self.store = MemoryStore(self.tmp, self.arch)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_persistent_entry_stays(self):
        """Permanent entry (layer with no TTL) stays."""
        mid = self.store.write("long_term", "forever")
        expired = self.store.expire()
        self.assertEqual(len(expired), 0)
        self.assertIsNotNone(self.store.read(mid))

    def test_02_expired_entry_removed(self):
        """Entry past TTL should be removed by expire()."""
        mid = self.store.write("working", "old")
        # Manipulate created_at to simulate age
        raw = self.store._load_raw(mid)
        raw.created_at = time.time() - 7200  # 2 hours ago
        self.store._save(raw)
        expired = self.store.expire()
        self.assertIn(mid, [e.id for e in expired])
        self.assertIsNone(self.store.read(mid))


# ═══════════════════════════════════════════════════════════════
# P2-12: Memory promotion
# ═══════════════════════════════════════════════════════════════

class TestMemoryPromotion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from dlc.memory.core import load_architecture
        cls.arch = load_architecture(_FIX)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.memory.core import MemoryStore
        self.store = MemoryStore(self.tmp, self.arch)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_promote_not_enough_access(self):
        mid = self.store.write("working", "low")
        r = self.store.promote(mid)
        self.assertFalse(r)

    def test_02_promote_after_enough_access(self):
        mid = self.store.write("working", "high")
        entry = self.store._load_raw(mid)
        entry.access_count = 10  # exceeds threshold of 5
        self.store._save(entry)
        r = self.store.promote(mid)
        self.assertTrue(r)
        promoted = self.store.read(mid)
        self.assertEqual(promoted.layer_id, "short_term")

    def test_03_promote_top_layer_noop(self):
        mid = self.store.write("long_term", "top")
        r = self.store.promote(mid)
        self.assertFalse(r)


# ═══════════════════════════════════════════════════════════════
# P2-13: Search + P2-14: Memory write interface
# ═══════════════════════════════════════════════════════════════

class TestMemorySearch(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from dlc.memory.core import load_architecture
        cls.arch = load_architecture(_FIX)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.memory.core import MemoryStore
        self.store = MemoryStore(self.tmp, self.arch)
        self.store.write("working", "hello world", tags=["greeting"])
        self.store.write("working", "goodbye", tags=["farewell"])
        self.store.write("short_term", "hello again", tags=["greeting"])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_search_by_keyword(self):
        results = self.store.search("hello")
        self.assertEqual(len(results), 2)

    def test_02_search_by_tag(self):
        results = self.store.search("", tags=["greeting"])
        self.assertEqual(len(results), 2)

    def test_03_search_layer_scoped(self):
        results = self.store.search("hello", layers=["working"])
        self.assertEqual(len(results), 1)

    def test_04_search_empty_returns_nothing(self):
        results = self.store.search("nonexistent")
        self.assertEqual(len(results), 0)

    def test_05_search_ranked_by_access(self):
        entries = self.store.list_layer("working")
        self.store.read(entries[0].id)
        self.store.read(entries[0].id)  # boost access
        results = self.store.search("hello")
        self.assertGreaterEqual(len(results), 1)


# ═══════════════════════════════════════════════════════════════
# P2-15: Memory consolidation
# ═══════════════════════════════════════════════════════════════

class TestMemoryConsolidation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from dlc.memory.core import load_architecture
        cls.arch = load_architecture(_FIX)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.memory.core import MemoryStore
        self.store = MemoryStore(self.tmp, self.arch)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_consolidate_promotes_eligible(self):
        """consolidate() should promote entries that meet threshold."""
        for i in range(6):
            mid = self.store.write("working", f"entry_{i}")
            e = self.store._load_raw(mid)
            e.access_count = 10
            self.store._save(e)
        summary = self.store.consolidate()
        self.assertGreaterEqual(summary["promoted"], 1)

    def test_02_consolidate_expires_stale(self):
        """consolidate() should expire TTL'd entries."""
        mid = self.store.write("working", "stale")
        e = self.store._load_raw(mid)
        e.created_at = time.time() - 7200
        self.store._save(e)
        summary = self.store.consolidate()
        self.assertGreaterEqual(summary["expired"], 1)


# ═══════════════════════════════════════════════════════════════
# P2-16: Memory context injection
# ═══════════════════════════════════════════════════════════════

class TestContextInjection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from dlc.memory.core import load_architecture
        cls.arch = load_architecture(_FIX)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.memory.core import MemoryStore
        self.store = MemoryStore(self.tmp, self.arch)
        self.store.write("short_term", "用户喜欢咖啡", importance=0.8)
        self.store.write("short_term", "项目截止日期周五", importance=0.9)
        self.store.write("long_term", "用户母语是中文", importance=1.0)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_inject_formats_context(self):
        from dlc.memory.core import inject_memory_context
        entries = self.store.search("", layers=["short_term", "long_term"])
        prompt = inject_memory_context(entries, max_entries=3)
        self.assertIn("咖啡", prompt)
        self.assertIn("周五", prompt)

    def test_02_inject_respects_max_entries(self):
        from dlc.memory.core import inject_memory_context
        entries = self.store.search("")
        prompt = inject_memory_context(entries, max_entries=2)
        lines = prompt.strip().split("\n")
        self.assertLessEqual(len(lines), 4)  # header + 2 entries + trailing newline

    def test_03_inject_empty_returns_empty(self):
        from dlc.memory.core import inject_memory_context
        prompt = inject_memory_context([])
        self.assertEqual(prompt, "")


if __name__ == "__main__":
    unittest.main()
