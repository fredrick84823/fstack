#!/usr/bin/env python3
"""每週 skill miner 的 gate 與 queue 寫入。

模型那一步（cluster-sessions.sh）不在這裡測：這裡釘的是模型**之後**的判斷 ——
transcript 證明 session 已經叫用了某支 skill，就不能變成新候選，不管模型怎麼說。
2026-11-03 的實驗裡 22 群有 21 群是這種，這條 gate 壞掉的症狀是 queue 被既有 skill 灌滿。
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/skill-evolution/improve/scripts"))
import skill_miner  # noqa: E402


def session(i: int, skills: list[str]) -> dict:
    return {"id": f"s{i}", "session": f"proj/{i:08d}", "project": "proj",
            "date": f"2026-10-2{i}", "prompts": ["x"], "skills": skills}


def cluster(ids: list[int], existing: str | None = None, name: str = "weekly-thing") -> dict:
    return {"name": name, "task": "t", "session_ids": [f"s{i}" for i in ids],
            "existing_skill": existing, "steps": ["a", "b"], "invoker_hints": ["做那個"], "reason": "r"}


class JudgeTest(unittest.TestCase):
    INSTALLED = {"report-to-pm", "describe-pr"}

    def judge(self, clusters, sessions):
        return skill_miner.judge(clusters, sessions, self.INSTALLED)

    def test_uncovered_task_is_new_candidate(self):
        entries, dropped = self.judge([cluster([1, 2, 3])], [session(i, []) for i in (1, 2, 3)])
        self.assertEqual([(e["name"], e["kind"], e["hit_count"]) for e in entries], [("weekly-thing", "new", 3)])
        self.assertEqual(dropped, [])

    def test_skill_the_sessions_used_overrides_a_model_null(self):
        sessions = [session(i, ["describe-pr"]) for i in (1, 2, 3)]
        entries, dropped = self.judge([cluster([1, 2, 3])], sessions)
        self.assertEqual(entries, [])
        self.assertEqual(dropped[0]["why"], "covered by describe-pr")

    def test_covered_task_done_without_the_skill_is_bypass(self):
        sessions = [session(i, []) for i in (1, 2, 3)] + [session(4, ["report-to-pm"])]
        entries, _ = self.judge([cluster([1, 2, 3, 4], existing="report-to-pm")], sessions)
        self.assertEqual(len(entries), 1)
        self.assertEqual((entries[0]["name"], entries[0]["kind"], entries[0]["hit_count"]),
                         ("bypass:report-to-pm", "bypassed", 3))
        self.assertNotIn("proj/00000004", entries[0]["sessions"])

    def test_bypass_needs_three_sessions(self):
        sessions = [session(1, []), session(2, ["report-to-pm"]), session(3, ["report-to-pm"])]
        entries, dropped = self.judge([cluster([1, 2, 3], existing="report-to-pm")], sessions)
        self.assertEqual(entries, [])
        self.assertEqual(dropped[0]["why"], "covered by report-to-pm")

    def test_unknown_or_repeated_ids_do_not_count(self):
        entries, dropped = self.judge([cluster([1, 1, 2, 9])], [session(i, []) for i in (1, 2)])
        self.assertEqual(entries, [])
        self.assertEqual(dropped[0]["why"], "2 sessions")

    def test_invented_skill_name_is_ignored(self):
        entries, _ = self.judge([cluster([1, 2, 3], existing="no-such-skill")], [session(i, []) for i in (1, 2, 3)])
        self.assertEqual(entries[0]["kind"], "new")


class QueueTest(unittest.TestCase):
    def test_rendered_entry_reads_back_as_pending(self):
        entries, _ = skill_miner.judge([cluster([1, 2, 3])], [session(i, []) for i in (1, 2, 3)], set())
        text = "<!--\n## [x] example\n\n- **status**: pending\n-->\n" + "\n" + skill_miner.render_entry(
            entries[0], "2026-11-03T10:00:00+08:00", "2026-11-03")
        self.assertIn("weekly-thing", skill_miner.pending_names(text))
        self.assertIn("  1. a\n  2. b\n", text)

    def test_description_reads_folded_frontmatter(self):
        text = "---\nname: x\ndescription: >\n  第一行\n  第二行\nother: y\n---\n"
        self.assertEqual(skill_miner.description(text), "第一行 第二行")


class StaleTest(unittest.TestCase):
    def test_only_unused_or_old_skills_listed(self):
        day = 86400
        now = 100 * day
        report = skill_miner.stale_report(["fresh", "old", "never"], {"fresh": now - day, "old": now - 40 * day},
                                          now, now - 90 * day)
        self.assertIn("- old：", report)
        self.assertIn("- never：", report)
        self.assertNotIn("fresh", report)


if __name__ == "__main__":
    unittest.main()
