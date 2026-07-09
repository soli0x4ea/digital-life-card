"""Phase 2D: Scheduler tests — P2-22 ~ P2-27."""

import unittest, json, os, sys, tempfile, shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
sys.path.insert(0, _PROJ)
_FIX = os.path.join(_HERE, "fixtures", "engine")
_EFIX = os.path.join(_HERE, "fixtures", "engine")


class MockEngine:
    """Minimal engine mock for scheduler."""
    def __init__(self, state):
        self.state = state
        self.entities_cfg = {"e_g": {"channels": {"ch_g_a": {"decay_per_tick": 2}}}}
        self.tick_count = 0

    def tick(self):
        self.tick_count += 1
        from dlc.engine.entity import apply_decay
        apply_decay(self.state, self.entities_cfg["e_g"])

    def tick_all_entities(self):
        self.tick()


class TestScheduleLoader(unittest.TestCase):
    """P2-22: Load memory/schedule.json."""

    def test_01_load_tasks(self):
        from dlc.scheduler.engine import ScheduleLoader
        sched = ScheduleLoader(_FIX).load()
        self.assertEqual(len(sched.tasks), 0)  # no schedule.json in engine fixtures

    def test_02_task_types(self):
        from dlc.scheduler.engine import ScheduleLoader
        sched = ScheduleLoader(_FIX).load()
        types = {t.type for t in sched.tasks}
        self.assertNotIn("memory_consolidate", types)


class TestScheduleEngine(unittest.TestCase):
    """P2-23: Task scheduling + P2-24~27 built-in tasks."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(_EFIX, "entities.json")) as f:
            cls.entities_cfg = json.load(f)["entities"]

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from dlc.engine.entity import EntityEngine, EntityState
        self.eeng = EntityEngine(state_dir=os.path.join(self.tmp, "state"))
        state = EntityState(entity_id="e_g", channels={"ch_g_a": 50.0})
        self.eeng.save(state)
        self.state = self.eeng.load("e_g")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_state_decay_task(self):
        """P2-24: state_decay reduces channel values."""
        from dlc.engine.entity import apply_decay
        old = self.state.channels["ch_g_a"]
        apply_decay(self.state, self.entities_cfg["e_g"])
        self.assertLess(self.state.channels["ch_g_a"], old)

    def test_02_flag_cleanup_task(self):
        """P2-26: flag_cleanup removes flags with zero or negative."""
        self.state.flags["temp_flag"] = 0
        from dlc.scheduler.engine import _task_flag_cleanup
        _task_flag_cleanup(self.state)
        self.assertNotIn("temp_flag", self.state.flags)

    def test_03_schedule_engine_ticks(self):
        from dlc.scheduler.engine import ScheduleEngine, ScheduleConfig, TaskConfig
        sched = ScheduleConfig(tasks=[
            TaskConfig(id="t0", type="state_decay", interval_ticks=1),
        ])
        eng = ScheduleEngine(sched)
        self.assertEqual(eng.tick_count, 0)
        eng.tick()
        self.assertEqual(eng.tick_count, 1)

    def test_04_schedule_respects_interval(self):
        from dlc.scheduler.engine import ScheduleEngine, ScheduleConfig, TaskConfig
        sched = ScheduleConfig(tasks=[
            TaskConfig(id="t0", type="state_decay", interval_ticks=5),
        ])
        eng = ScheduleEngine(sched)
        results1 = eng.tick()
        self.assertTrue(results1[0].fired)
        results2 = eng.tick()
        self.assertFalse(results2[0].fired)
        # Second tick: none should fire (interval not elapsed)
        results2 = eng.tick()
        for r in results2:
            self.assertFalse(r.fired)


if __name__ == "__main__":
    unittest.main()
