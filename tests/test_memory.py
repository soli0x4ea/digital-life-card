"""DLC Memory — dual-core tests (v2.6.0).

ChatlogStore + TimelineStore + MemorySearch + record_chat + importer.
"""

import unittest, os, sys, tempfile, shutil, json

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
sys.path.insert(0, _PROJ)


# ═══════════════════════════════════════════════════════════════
# ChatlogStore
# ═══════════════════════════════════════════════════════════════

class TestChatlogStore(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.memory import ChatlogStore
        self.store = ChatlogStore(self.tmp)
        # Clean up any today's file that may exist
        self.store._today = None

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_append_and_count(self):
        self.store.append("user", "hello")
        self.store.append("assistant", "hi there")
        count = self.store.count_day()
        self.assertEqual(count, 2)

    def test_02_recent(self):
        self.store.append("user", "msg1")
        self.store.append("assistant", "msg2")
        self.store.append("user", "msg3")
        recent = self.store.recent(2)
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0]["content"], "msg2")
        self.assertEqual(recent[1]["content"], "msg3")

    def test_03_search(self):
        self.store.append("user", "hello world")
        self.store.append("assistant", "goodbye")
        results = self.store.search("hello")
        self.assertEqual(len(results), 1)
        results2 = self.store.search("nonexistent")
        self.assertEqual(len(results2), 0)

    def test_04_load_day(self):
        self.store.append("user", "day1")
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        entries = self.store.load_day(today)
        self.assertEqual(len(entries), 1)

    def test_05_empty_store(self):
        count = self.store.count_day()
        self.assertEqual(count, 0)
        recent = self.store.recent(5)
        self.assertEqual(recent, [])
        results = self.store.search("anything")
        self.assertEqual(results, [])


# ═══════════════════════════════════════════════════════════════
# TimelineStore
# ═══════════════════════════════════════════════════════════════

class TestTimelineStore(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.memory import TimelineStore
        self.store = TimelineStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_write_and_read(self):
        self.store.write("2026-07-09-12", summary="user said hello")
        entries = self.store.recent(5)
        self.assertEqual(len(entries), 1)
        self.assertIn("hello", entries[0]["summary"])

    def test_02_multiple_hours(self):
        self.store.write("2026-07-09-10", summary="morning")
        self.store.write("2026-07-09-12", summary="noon")
        self.store.write("2026-07-09-14", summary="afternoon")
        entries = self.store.recent(5)
        self.assertEqual(len(entries), 3)

    def test_03_same_hour_overwrites(self):
        self.store.write("2026-07-09-12", summary="first")
        self.store.write("2026-07-09-12", summary="second")
        entries = self.store.recent(5)
        self.assertEqual(len(entries), 1)
        self.assertIn("second", entries[0]["summary"])

    def test_04_empty_store(self):
        entries = self.store.recent(5)
        self.assertEqual(entries, [])


# ═══════════════════════════════════════════════════════════════
# MemorySearch
# ═══════════════════════════════════════════════════════════════

class TestMemorySearch(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.memory import ChatlogStore, TimelineStore, MemorySearch
        self.chatlog = ChatlogStore(os.path.join(self.tmp, "chatlog"))
        self.timeline = TimelineStore(os.path.join(self.tmp, "timeline"))
        self.search = MemorySearch(self.chatlog, self.timeline)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_search_across_stores(self):
        self.chatlog.append("user", "hello world")
        self.timeline.write("2026-07-09-12", summary="greeting from user")
        results = self.search.search("hello")
        self.assertIsInstance(results, dict)
        self.assertIn("chatlog", results)

    def test_02_no_results(self):
        results = self.search.search("nonexistent_keyword_xyz")
        self.assertIsInstance(results, dict)


# ═══════════════════════════════════════════════════════════════
# record_chat
# ═══════════════════════════════════════════════════════════════

class TestRecordChat(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.memory import ChatlogStore, TimelineStore
        self.chatlog = ChatlogStore(os.path.join(self.tmp, "chatlog"))
        self.timeline = TimelineStore(os.path.join(self.tmp, "timeline"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_writes_both_sides(self):
        from dlc.memory import record_chat
        record_chat(self.chatlog, self.timeline,
                    user_id="user", user_message="hello",
                    assistant_id="bot", assistant_message="hi there")
        count = self.chatlog.count_day()
        self.assertEqual(count, 2)

    def test_02_syncs_timeline(self):
        from dlc.memory import record_chat
        record_chat(self.chatlog, self.timeline,
                    user_id="user", user_message="test msg",
                    assistant_id="bot", assistant_message="ok")
        tl = self.timeline.recent(5)
        self.assertGreaterEqual(len(tl), 1)

    def test_03_chatlog_content_is_clean(self):
        from dlc.memory import record_chat
        record_chat(self.chatlog, self.timeline,
                    user_id="user", user_message="hello",
                    assistant_id="bot", assistant_message="hi there")
        recent = self.chatlog.recent(2)
        self.assertEqual(recent[0]["role"], "user")
        self.assertEqual(recent[0]["content"], "hello")
        self.assertEqual(recent[1]["role"], "bot")
        self.assertEqual(recent[1]["content"], "hi there")


# ═══════════════════════════════════════════════════════════════
# Importer
# ═══════════════════════════════════════════════════════════════

class TestImporter(unittest.TestCase):

    def test_01_import_from_soli_format(self):
        from dlc.memory import ChatlogStore, import_chatlog
        tmp = tempfile.mkdtemp()
        try:
            soli_dir = os.path.join(tmp, "soli_dir")
            os.makedirs(soli_dir)
            entries = [
                {"ts": "2026-07-09T12:00:00+08:00", "role": "user", "content": "hello"},
                {"ts": "2026-07-09T12:01:00+08:00", "role": "assistant", "content": "hi"},
            ]
            src_file = os.path.join(soli_dir, "2026-07-09.jsonl")
            with open(src_file, "w", encoding="utf-8") as f:
                for e in entries:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            dst = ChatlogStore(os.path.join(tmp, "out"))
            result = import_chatlog(soli_dir, dst)
            self.assertIsInstance(result, dict)
            count = dst.count_day()
            self.assertGreater(count, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
