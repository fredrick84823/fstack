"""Tests for common utilities, especially TZ enforcement and iso_week_id."""
import os
import sys
import time
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import common


class TestNormalizeTaskName(unittest.TestCase):
    def test_strips_wip_prefix(self):
        self.assertEqual(common.normalize_task_name("[WIP] My Task"), "my task")

    def test_strips_urgent_prefix(self):
        self.assertEqual(common.normalize_task_name("[urgent] Fix Bug"), "fix bug")

    def test_strips_wip_suffix(self):
        self.assertEqual(common.normalize_task_name("My Task - WIP"), "my task")

    def test_lowercase(self):
        self.assertEqual(common.normalize_task_name("UPPER CASE"), "upper case")

    def test_collapses_whitespace(self):
        self.assertEqual(common.normalize_task_name("  task  name  "), "task name")

    def test_no_change_plain(self):
        self.assertEqual(common.normalize_task_name("plain task"), "plain task")


class TestIsoWeekId(unittest.TestCase):
    def test_returns_correct_format(self):
        week_id = common.iso_week_id()
        self.assertRegex(week_id, r"^\d{4}-W\d{2}$")

    def test_specific_date(self):
        # 2026-04-30 is week 18 of 2026
        dt = datetime(2026, 4, 30, 9, 0, 0)
        result = common.iso_week_id(dt)
        self.assertEqual(result, "2026-W18")

    def test_utc_env_override(self):
        """Simulates UTC environment — Asia/Taipei TZ must be forced."""
        original_tz = os.environ.get("TZ")
        os.environ["TZ"] = "UTC"
        time.tzset()
        try:
            # Monday 00:30 UTC = Sunday 08:30+8 previous week issue
            # 2026-04-27 (Monday) 00:30 UTC would be week 17 in UTC
            # but Asia/Taipei (UTC+8) it's already April 27 08:30, still week 18
            dt = datetime(2026, 4, 27, 8, 30, 0)
            result = common.iso_week_id(dt)
            # Week 18 starts April 27 in 2026
            self.assertEqual(result, "2026-W18")
        finally:
            if original_tz is not None:
                os.environ["TZ"] = original_tz
            else:
                os.environ.pop("TZ", None)
            time.tzset()


if __name__ == "__main__":
    unittest.main()
