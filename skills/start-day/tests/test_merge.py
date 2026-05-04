"""Tests for merge.py — conflict resolution, dedup, cycle detection."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from merge import CircularDependencyError, merge

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestMergeNoConflict(unittest.TestCase):
    def setUp(self):
        data = _load("tasks_no_conflict.json")
        self.tasks = merge(data["gsheet"], data["github"], data["heptabase"])

    def test_deduped_to_one(self):
        self.assertEqual(len(self.tasks), 1)

    def test_three_sources_present(self):
        kinds = {s["kind"] for s in self.tasks[0]["sources"]}
        self.assertEqual(kinds, {"gsheet", "github_pr", "heptabase"})

    def test_no_conflict(self):
        self.assertIsNone(self.tasks[0]["conflict"])

    def test_card_id_preserved(self):
        self.assertEqual(self.tasks[0]["card_id"], "card-abc")

    def test_status_from_pr(self):
        self.assertEqual(self.tasks[0]["status"], "in-progress")


class TestMergeConflictGsheetDonePrOpen(unittest.TestCase):
    def setUp(self):
        data = _load("tasks_conflict_gsheet_done_pr_open.json")
        self.tasks = merge(data["gsheet"], data["github"], data["heptabase"])

    def test_single_task(self):
        self.assertEqual(len(self.tasks), 1)

    def test_pr_wins_status(self):
        self.assertEqual(self.tasks[0]["status"], "in-progress")

    def test_conflict_message_set(self):
        self.assertIsNotNone(self.tasks[0]["conflict"])
        self.assertIn("PR #99", self.tasks[0]["conflict"])


class TestMergeHeptabaseOnly(unittest.TestCase):
    def setUp(self):
        data = _load("tasks_heptabase_only.json")
        self.tasks = merge(data["gsheet"], data["github"], data["heptabase"])

    def test_two_tasks(self):
        self.assertEqual(len(self.tasks), 2)

    def test_depends_on_preserved(self):
        task_with_dep = next(t for t in self.tasks if t.get("depends_on"))
        self.assertIn("implement auth module", task_with_dep["depends_on"])

    def test_no_conflict(self):
        for t in self.tasks:
            self.assertIsNone(t["conflict"])


class TestMergeCircularDep(unittest.TestCase):
    def test_raises_on_cycle(self):
        data = _load("tasks_circular_dep.json")
        with self.assertRaises(CircularDependencyError):
            merge(data["gsheet"], data["github"], data["heptabase"])


class TestMergeEmpty(unittest.TestCase):
    def test_all_empty(self):
        self.assertEqual(merge([], [], []), [])


if __name__ == "__main__":
    unittest.main()
