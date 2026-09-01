"""Tests for fetch_github._filter_prs_within_window."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from fetch_github import _filter_prs_within_window  # noqa: E402

# Cutoff = 2026-04-27T00:00:00Z (simulated "7 days before May 4")
CUTOFF = "2026-04-27T00:00:00Z"

MERGED_MARCH = {
    "number": 43,
    "state": "MERGED",
    "mergedAt": "2026-03-10T09:59:49Z",
    "updatedAt": "2026-04-30T08:04:25Z",  # bumped by CI — must NOT slip through
    "title": "old merged PR",
    "url": "https://github.com/test/repo/pull/43",
}
MERGED_RECENT = {
    "number": 60,
    "state": "MERGED",
    "mergedAt": "2026-04-27T03:35:46Z",
    "updatedAt": "2026-04-27T03:35:50Z",
    "title": "recent merged PR",
    "url": "https://github.com/test/repo/pull/60",
}
OPEN_RECENT = {
    "number": 61,
    "state": "OPEN",
    "mergedAt": None,
    "updatedAt": "2026-04-28T10:00:00Z",
    "title": "open recent PR",
    "url": "https://github.com/test/repo/pull/61",
}
OPEN_OLD = {
    "number": 30,
    "state": "OPEN",
    "mergedAt": None,
    "updatedAt": "2026-03-01T10:00:00Z",
    "title": "open old PR",
    "url": "https://github.com/test/repo/pull/30",
}


class TestFilterPrsWithinWindow(unittest.TestCase):
    def test_old_merged_pr_with_recent_updatedAt_is_excluded(self):
        """mergedAt (March) beats updatedAt (April 30) — must be filtered out."""
        result = _filter_prs_within_window([MERGED_MARCH], CUTOFF)
        self.assertEqual(result, [])

    def test_recently_merged_pr_included(self):
        result = _filter_prs_within_window([MERGED_RECENT], CUTOFF)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["number"], 60)

    def test_open_recent_pr_included(self):
        result = _filter_prs_within_window([OPEN_RECENT], CUTOFF)
        self.assertEqual(len(result), 1)

    def test_open_old_pr_excluded(self):
        result = _filter_prs_within_window([OPEN_OLD], CUTOFF)
        self.assertEqual(result, [])

    def test_mixed_list(self):
        prs = [MERGED_MARCH, MERGED_RECENT, OPEN_RECENT, OPEN_OLD]
        result = _filter_prs_within_window(prs, CUTOFF)
        numbers = [pr["number"] for pr in result]
        self.assertNotIn(43, numbers, "Old merged PR (March) must be excluded")
        self.assertNotIn(30, numbers, "Old open PR must be excluded")
        self.assertIn(60, numbers)
        self.assertIn(61, numbers)

    def test_no_date_fields_passes_through(self):
        """PR with no date info should not crash and should be included."""
        pr = {"number": 99, "state": "OPEN", "title": "no date", "url": "http://x"}
        result = _filter_prs_within_window([pr], CUTOFF)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
