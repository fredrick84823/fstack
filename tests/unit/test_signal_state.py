#!/usr/bin/env python3

from __future__ import annotations

import json
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

    def test_stop_hook_core_uses_queue_authoritative_capture(self) -> None:
        project_queue = self.root / ".agents" / "skills" / "improve" / "signal-queue.md"
        project_queue.parent.mkdir(parents=True)
        project_queue.write_text("# Signal Queue\n")
        (project_queue.parent.parent / "hook-demo").mkdir()
        subprocess.run(
            ["bash", str(CAPTURE_CORE)],
            input="Result complete.\n<<GAP hook-demo: reusable hook gap>>\n<<GAP skill-name: 一句話描述缺口>>\n",
            text=True,
            cwd=self.root,
            check=True,
        )
        queue_text = project_queue.read_text()
        raw_path = project_queue.parent / "memory" / "signals.jsonl"
        self.assertIn("## [", queue_text)
        self.assertIn("] hook-demo", queue_text)
        # doc-echo guard: the quoted template is not an installed skill, so it is dropped
        self.assertNotIn("skill-name", queue_text)
        self.assertIn("- **signal_id**: sig_", queue_text)
        self.assertIn("- **memory_sync**: synced", queue_text)
        raw = [json.loads(line) for line in raw_path.read_text().splitlines() if line.strip()]
        self.assertEqual(raw[0]["target_skill"], "hook-demo")
        self.assertEqual(raw[0]["status_semantics"], "captured_at_ingest")


if __name__ == "__main__":
    unittest.main()
