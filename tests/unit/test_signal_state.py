#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


# 腳本住在 skill 底下，不是可 import 的套件路徑 —— 這支測試一律起子行程跑它們，
# 路徑從**本檔案**推出來（同 conftest.load_script 的理由：mutmut 會把整棵樹複製進
# `mutants/`，寫死 repo 路徑就會載到原檔）。
SCRIPTS = Path(__file__).resolve().parents[2] / "skills/skill-evolution/improve/scripts"
SCRIPT = SCRIPTS / "signal_state.py"
CAPTURE_CORE = SCRIPTS / "capture-signal-core.sh"


class SignalStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.queue = self.root / "signal-queue.md"
        self.memory = self.root / "memory"
        self.queue.write_text("# Signal Queue\n\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_state(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=check,
        )

    def capture(self, gap: str = "reusable gap") -> str:
        result = self.run_state(
            "capture",
            "--queue", str(self.queue),
            "--memory-dir", str(self.memory),
            "--timestamp", "2026-07-13T12:00:00+08:00",
            "--target-skill", "demo-skill",
            "--type", "S2",
            "--source", "unit test",
            "--gap", gap,
        )
        return result.stdout.strip()

    def read_jsonl(self, name: str) -> list[dict]:
        path = self.memory / name
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def test_capture_shares_id_and_keeps_raw_status_as_capture_snapshot(self) -> None:
        signal_id = self.capture()
        queue_text = self.queue.read_text()
        raw = self.read_jsonl("signals.jsonl")
        graph = json.loads((self.memory / "skill-graph.json").read_text())

        self.assertIn(f"- **signal_id**: {signal_id}", queue_text)
        self.assertIn("- **status**: pending", queue_text)
        self.assertIn("- **memory_sync**: synced", queue_text)
        self.assertEqual(raw[0]["signal_id"], signal_id)
        self.assertEqual(raw[0]["status"], "pending")
        self.assertEqual(raw[0]["status_semantics"], "captured_at_ingest")
        self.assertEqual(graph["signals"][0]["status_source"], "signal-queue.md")

    def test_prepare_and_resolve_are_idempotent_without_mutating_raw_evidence(self) -> None:
        signal_id = self.capture()
        common = ["--queue", str(self.queue), "--memory-dir", str(self.memory), "--signal-id", signal_id]
        self.run_state("prepare", *common, "--candidate-id", "candidate_abc")
        self.run_state(
            "transition", *common,
            "--to", "resolved",
            "--decision-by", "unit-test",
            "--candidate-id", "candidate_abc",
        )
        # Retry after a crash at the caller boundary must not duplicate decisions.
        self.run_state(
            "transition", *common,
            "--to", "resolved",
            "--decision-by", "unit-test",
            "--candidate-id", "candidate_abc",
        )

        queue_text = self.queue.read_text()
        raw = self.read_jsonl("signals.jsonl")
        transitions = self.read_jsonl("transitions.jsonl")
        graph = json.loads((self.memory / "skill-graph.json").read_text())
        self.assertIn("- **status**: resolved", queue_text)
        self.assertIn("- **memory_sync**: synced", queue_text)
        self.assertEqual(raw[0]["status"], "pending")
        self.assertEqual(len(transitions), 1)
        self.assertEqual(graph["signals"][0]["status"], "resolved")

    def test_resolve_requires_matching_apply_intent(self) -> None:
        signal_id = self.capture()
        result = self.run_state(
            "transition",
            "--queue", str(self.queue),
            "--memory-dir", str(self.memory),
            "--signal-id", signal_id,
            "--to", "resolved",
            "--decision-by", "unit-test",
            "--candidate-id", "not-prepared",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matching --candidate-id", result.stderr)
        self.assertIn("- **status**: pending", self.queue.read_text())

    def test_prepare_requires_explicit_supersede_for_candidate_change(self) -> None:
        signal_id = self.capture()
        common = ["--queue", str(self.queue), "--memory-dir", str(self.memory), "--signal-id", signal_id]
        self.run_state("prepare", *common, "--candidate-id", "candidate_old")
        conflict = self.run_state("prepare", *common, "--candidate-id", "candidate_new", check=False)
        self.assertNotEqual(conflict.returncode, 0)
        self.run_state(
            "prepare", *common,
            "--candidate-id", "candidate_new",
            "--supersede-candidate-id", "candidate_old",
        )
        queue_text = self.queue.read_text()
        self.assertIn("- **apply_intent**: candidate_new", queue_text)
        self.assertIn("- **superseded_apply_intent**: candidate_old", queue_text)

    def test_duplicate_selected_id_fails_without_mutation(self) -> None:
        signal_id = self.capture()
        original = self.queue.read_text()
        # Append a second real entry carrying the same id.
        block = original[original.index("## ["):]
        self.queue.write_text(original + "\n" + block)
        before = self.queue.read_text()
        result = self.run_state(
            "reconcile",
            "--queue", str(self.queue),
            "--memory-dir", str(self.memory),
            "--signal-id", signal_id,
            "--apply",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.queue.read_text(), before)

    def test_unique_legacy_entry_can_be_adopted(self) -> None:
        gap = "legacy exact gap"
        signal_id = self.capture(gap)
        queue_text = self.queue.read_text()
        queue_text = queue_text.replace(f"- **signal_id**: {signal_id}\n", "")
        queue_text = queue_text.replace("- **memory_sync**: synced\n", "")
        self.queue.write_text(queue_text)

        result = self.run_state(
            "adopt-legacy",
            "--queue", str(self.queue),
            "--memory-dir", str(self.memory),
            "--timestamp", "2026-07-13T12:00:00+08:00",
            "--target-skill", "demo-skill",
            "--gap", gap,
        )
        self.assertEqual(result.stdout.strip(), signal_id)
        self.assertIn(f"- **signal_id**: {signal_id}", self.queue.read_text())
        self.assertIn("- **memory_sync**: synced", self.queue.read_text())

    def project_queue(self, skill: str) -> Path:
        queue = self.root / ".agents" / "skills" / "improve" / "signal-queue.md"
        queue.parent.mkdir(parents=True)
        queue.write_text("# Signal Queue\n")
        (queue.parent.parent / skill).mkdir()
        return queue

    def run_capture(self, message: str) -> None:
        # AGENTS_SKILLS_HOME 一定要指回 temp：今天只因為 capture-signal-core.sh:17 先走
        # project queue 分支才沒外洩，那個分支一壞，這支測試會在轉紅之前先寫進開發者**真正的**
        # ~/.agents/skills/improve/signal-queue.md。
        subprocess.run(
            ["bash", str(CAPTURE_CORE)],
            input=message,
            text=True,
            cwd=self.root,
            check=True,
            env={**os.environ, "AGENTS_SKILLS_HOME": str(self.root / "fallback-home")},
        )

    def test_stop_hook_core_uses_queue_authoritative_capture(self) -> None:
        project_queue = self.project_queue("hook-demo")
        self.run_capture("Result complete.\n<<GAP hook-demo: reusable hook gap>>\n")
        queue_text = project_queue.read_text()
        raw_path = project_queue.parent / "memory" / "signals.jsonl"
        self.assertIn("## [", queue_text)
        self.assertIn("] hook-demo", queue_text)
        self.assertIn("- **signal_id**: sig_", queue_text)
        self.assertIn("- **memory_sync**: synced", queue_text)
        raw = [json.loads(line) for line in raw_path.read_text().splitlines() if line.strip()]
        self.assertEqual(raw[0]["target_skill"], "hook-demo")
        self.assertEqual(raw[0]["status_semantics"], "captured_at_ingest")

    def test_a_gap_naming_a_skill_that_does_not_exist_is_dropped(self) -> None:
        # doc-echo guard：2026-09-16 Stop hook 把文件裡「示範 marker 長什麼樣」的散文
        # 當成真訊號吃下去，六筆垃圾進 queue 只能手動退掉。skill 目錄不存在就不是訊號。
        # 散文 marker 排在真訊號**前面**：擋掉的那筆若讓整個迴圈提早收工（continue 寫成
        # break），後面真的缺口就會跟著無聲消失 —— 正是這個 commit 要修的那種靜默丟失。
        project_queue = self.project_queue("hook-demo")
        self.run_capture(
            "格式是 <<GAP skill-name: 一句話>>，例如 <<GAP no-such-skill: 缺了什麼>>。\n"
            "<<GAP hook-demo: 真的缺口>>\n"
        )
        queue_text = project_queue.read_text()
        self.assertIn("] hook-demo", queue_text)
        self.assertIn("真的缺口", queue_text)
        self.assertNotIn("skill-name", queue_text)
        raw = [
            json.loads(line)
            for line in (project_queue.parent / "memory" / "signals.jsonl").read_text().splitlines()
            if line.strip()
        ]
        self.assertEqual([record["target_skill"] for record in raw], ["hook-demo"])


if __name__ == "__main__":
    unittest.main()
