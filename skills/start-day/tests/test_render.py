"""Tests for render.py — markdown output structure."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from render import NO_TASKS_SENTINEL, render_journal_section

TODAY = "2026-05-03"
WEEK_ID = "2026-W18"


def _task(name: str, status: str = "in-progress", depends_on: list | None = None, **kwargs) -> dict:
    return {
        "name": name.lower(),
        "name_raw": name,
        "status": status,
        "sources": [],
        "conflict": None,
        "depends_on": depends_on or [],
        "card_id": None,
        "multi_match_warning": None,
        **kwargs,
    }


class TestRenderEmpty(unittest.TestCase):
    def test_empty_returns_sentinel(self):
        result = render_journal_section([], WEEK_ID, TODAY)
        self.assertEqual(result, NO_TASKS_SENTINEL)


class TestRenderSections(unittest.TestCase):
    def setUp(self):
        tasks = [
            _task("Task Alpha", "in-progress"),
            _task("Task Beta", "completed"),
            _task("Task Gamma", "blocked"),
        ]
        self.md = render_journal_section(tasks, WEEK_ID, TODAY)

    def test_has_header(self):
        self.assertIn(f"# 今日任務看板 — {TODAY} ({WEEK_ID})", self.md)

    def test_has_in_progress_section(self):
        self.assertIn("## 進行中", self.md)
        self.assertIn("Task Alpha", self.md)

    def test_has_completed_section(self):
        self.assertIn("## 已完成", self.md)
        self.assertIn("Task Beta", self.md)

    def test_has_blocked_section(self):
        self.assertIn("## 阻塞", self.md)
        self.assertIn("Task Gamma", self.md)

    def test_no_dep_section_when_no_deps(self):
        self.assertNotIn("## 🔗 依賴關係", self.md)


class TestRenderDependencyTree(unittest.TestCase):
    def setUp(self):
        tasks = [
            _task("Task C", "in-progress", depends_on=["Task A", "Task B"]),
            _task("Task A", "completed"),
            _task("Task B", "in-progress"),
        ]
        self.md = render_journal_section(tasks, WEEK_ID, TODAY)

    def test_dep_section_present(self):
        self.assertIn("## 🔗 依賴關係", self.md)

    def test_dep_tree_shows_task_c(self):
        self.assertIn("Task C", self.md)
        self.assertIn("depends on: Task A", self.md)
        self.assertIn("depends on: Task B", self.md)

    def test_dep_tree_shows_status(self):
        self.assertIn("(completed)", self.md)
        self.assertIn("(in-progress)", self.md)


class TestRenderConflict(unittest.TestCase):
    def test_conflict_shown(self):
        task = _task("My Task", conflict="gsheet 顯示已完成，但 PR #5 尚未 merge")
        md = render_journal_section([task], WEEK_ID, TODAY)
        self.assertIn("⚠️ 衝突", md)
        self.assertIn("PR #5", md)


if __name__ == "__main__":
    unittest.main()
