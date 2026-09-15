#!/usr/bin/env python3
"""SessionEnd GAP 分類器的單元測試。

這支分類器的價值全在**它不做什麼**：不對沒呼叫 skill 的 session 花錢、不對自動化
session 出手、不讓同一個 gap 佔兩個 queue 位子、不讓一個壞 session 灌爆 queue。
所以這裡每一條測試釘的都是一條「沒發生」，而「沒發生」最容易假綠 —— 一個永遠回
空的分類器會讓半數斷言自動成立。

擋假綠的方式是 stub validator **把每次呼叫記在檔案上**：斷言打在「模型被呼叫了幾次、
帶什麼 skill 進去」，不是只看 queue 的結果。把 `skills_used` 改成永遠回 `[]`，
結果斷言照樣綠，呼叫記錄那條會紅。

transcript fixture 取自真實 transcript（tagtoo-mcp-servers，2026-08）去識別化後裁切：
envelope 欄位保留真實鍵集，payload 全部換掉。用真料換來的一個發現是
**人類打的字是 `content: <str>` 且 `isMeta: false`**，`text` block 反而是系統注入的
skill 本體 —— 憑印象寫的 fixture 會把兩者寫反，於是 `user_messages` 抓到注入的
skill 說明、抓不到使用者的修正，而測試全綠。
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills/skill-evolution/improve/scripts"
CLASSIFIER = SCRIPTS / "session_classifier.py"
STATE = SCRIPTS / "signal_state.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

WITH_SKILLS = FIXTURES / "session-with-skills.jsonl"
WITHOUT_SKILLS = FIXTURES / "session-without-skills.jsonl"
SDK_CLI = FIXTURES / "session-sdk-cli.jsonl"

# 每次呼叫附到 log，再吐一筆 accept。log 讓「模型有沒有被呼叫」變成可斷言的事實。
STUB_VALIDATOR = """#!/usr/bin/env bash
printf '%s\\n' "$1" >> "$IMPROVE_STUB_LOG"
cat <<JSON
{"verdict":"accept","target_skill":"$1","gap":"$IMPROVE_STUB_GAP","evidence_quote":"不對，未結案的項目沒有被帶進索引","risk_class":"S2"}
JSON
"""

# 同一個 gap 文字（去掉空白差異後相同）用來驗去重。
REJECTING_VALIDATOR = """#!/usr/bin/env bash
printf '%s\\n' "$1" >> "$IMPROVE_STUB_LOG"
echo '{"verdict":"reject","target_skill":"'"$1"'","gap":"","evidence_quote":"","risk_class":"S3"}'
"""


class SessionClassifierTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.queue = self.root / ".agents/skills/improve/signal-queue.md"
        self.queue.parent.mkdir(parents=True)
        self.queue.write_text("# Signal Queue\n\n")
        self.memory = self.queue.parent / "memory"
        self.log = self.root / "validator-calls.log"
        self.log.write_text("")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_validator(self, body: str = STUB_VALIDATOR) -> Path:
        path = self.root / "stub-validate.sh"
        path.write_text(body)
        path.chmod(0o755)
        return path

    def run_classifier(
        self,
        transcript: Path,
        *,
        env_extra: dict[str, str] | None = None,
        validator: Path | None = None,
        gap: str = "索引沒有帶出未結案狀態",
        args: list[str] | None = None,
    ) -> dict:
        env = {
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(self.root),
            "AGENTS_SKILLS_HOME": str(self.root / ".agents/skills"),
            "CLAUDE_CODE_ENTRYPOINT": "cli",
            "CLAUDE_CODE_SESSION_ATTENDED": "1",
            "IMPROVE_VALIDATOR": str(validator or self.write_validator()),
            "IMPROVE_STUB_LOG": str(self.log),
            "IMPROVE_STUB_GAP": gap,
        }
        env.update(env_extra or {})
        payload = json.dumps({
            "session_id": "fixture",
            "transcript_path": str(transcript),
            "cwd": str(self.root),
            "hook_event_name": "SessionEnd",
            "reason": "other",
        })
        completed = subprocess.run(
            [sys.executable, str(CLASSIFIER), *(args or [])],
            input=payload,
            text=True,
            capture_output=True,
            env=env,
            check=True,
        )
        return json.loads(completed.stdout)

    def validator_calls(self) -> list[str]:
        return [line for line in self.log.read_text().splitlines() if line.strip()]

    def queue_entries(self) -> list[str]:
        return [block for block in self.queue.read_text().split("## [") if "**signal_id**" in block]

    def raw_records(self) -> list[dict]:
        path = self.memory / "signals.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    # --- transcript 解析 -----------------------------------------------------

    def test_skill_calls_come_out_in_call_order_and_subagent_calls_do_not(self) -> None:
        report = self.run_classifier(WITH_SKILLS)
        # fixture 裡有一筆 isSidechain 的 research-codebase —— subagent 用的 skill
        # 不是這個 session 的歸因對象。
        self.assertEqual(report["skills"], ["generate-meeting-notes", "create-handoff"])

    def test_the_user_correction_reaches_the_validator_but_slash_commands_do_not(self) -> None:
        # excerpt 是 validator 唯一的證據來源；把 /model 的展開或注入的 skill 本體
        # 當成「使用者說的話」，precision-first 的引用規則就失去意義。
        import importlib.util

        spec = importlib.util.spec_from_file_location("sc", CLASSIFIER)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows = module.read_transcript(WITH_SKILLS)
        messages = module.user_messages(rows)

        self.assertIn("不對，未結案的項目沒有被帶進索引，每次都要我自己講一遍", messages)
        joined = "\n".join(messages)
        self.assertNotIn("<command-name>", joined)
        self.assertNotIn("<local-command-stdout>", joined)
        self.assertNotIn("Base directory for this skill", joined)

    # --- 不呼叫模型的那條路 --------------------------------------------------

    def test_a_session_that_called_no_skill_never_reaches_the_model(self) -> None:
        report = self.run_classifier(WITHOUT_SKILLS)
        self.assertEqual(report["skipped"], "no skill invoked")
        self.assertEqual(report["captured"], [])
        # 這條是整支腳本的成本前提：沒有 skill 呼叫就不該有任何一次 validator 呼叫。
        self.assertEqual(self.validator_calls(), [])
        self.assertEqual(self.queue_entries(), [])

    # --- 自動化 session 一律跳過 ---------------------------------------------

    def test_every_automation_marker_stops_the_run_before_the_model(self) -> None:
        for env_extra, expected in (
            ({"IMPROVE_CLASSIFIER_DISABLE": "1"}, "disabled by IMPROVE_CLASSIFIER_DISABLE"),
            ({"CLAUDE_CODE_SESSION_ATTENDED": "0"}, "unattended session"),
            ({"CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}, "non-interactive entrypoint: sdk-cli"),
            ({"CLAUDE_CODE_CHILD_SESSION": "1"}, "child session"),
        ):
            with self.subTest(env_extra=env_extra):
                self.log.write_text("")
                report = self.run_classifier(WITH_SKILLS, env_extra=env_extra)
                self.assertEqual(report["skipped"], expected)
                self.assertEqual(self.validator_calls(), [])

    def test_a_claude_p_transcript_is_skipped_even_when_the_environment_says_cli(self) -> None:
        # hook 繼承的環境變數可能是外層 session 的；transcript 自己記著它實際是什麼。
        report = self.run_classifier(SDK_CLI)
        self.assertEqual(report["skipped"], "non-interactive transcript: sdk-cli")
        self.assertEqual(self.validator_calls(), [])

    # --- 上限 N --------------------------------------------------------------

    def test_the_per_session_budget_caps_captures_not_just_the_report(self) -> None:
        report = self.run_classifier(WITH_SKILLS, args=["--max-signals", "1"])
        self.assertEqual(len(report["captured"]), 1)
        self.assertEqual(len(self.queue_entries()), 1)
        # 上限到了就停手，第二個 skill 的 validator 不該再被呼叫一次。
        self.assertEqual(self.validator_calls(), ["generate-meeting-notes"])

    def test_the_budget_is_configurable_from_the_environment(self) -> None:
        report = self.run_classifier(WITH_SKILLS, env_extra={"IMPROVE_MAX_SIGNALS": "2"})
        self.assertEqual(len(report["captured"]), 2)

    # --- 驗證器判否 ----------------------------------------------------------

    def test_a_rejecting_validator_captures_nothing_while_still_being_asked(self) -> None:
        report = self.run_classifier(WITH_SKILLS, validator=self.write_validator(REJECTING_VALIDATOR))
        self.assertEqual(report["captured"], [])
        self.assertEqual(self.queue_entries(), [])
        # 判否不等於沒問 —— 兩個 skill 都該被問過。
        self.assertEqual(self.validator_calls(), ["generate-meeting-notes", "create-handoff"])

    def test_captured_signals_carry_the_quote_the_validator_cited(self) -> None:
        self.run_classifier(WITH_SKILLS, args=["--max-signals", "1"])
        self.assertIn("- **evidence_quote**: 不對，未結案的項目沒有被帶進索引", self.queue.read_text())
        self.assertEqual(self.raw_records()[0]["evidence_quote"], "不對，未結案的項目沒有被帶進索引")

    # --- 去重 ----------------------------------------------------------------

    def test_the_same_gap_twice_adds_a_witness_not_a_second_queue_entry(self) -> None:
        first = self.run_classifier(WITH_SKILLS, args=["--max-signals", "1"])
        second = self.run_classifier(WITH_SKILLS, args=["--max-signals", "1"])

        self.assertEqual(len(self.queue_entries()), 1)
        self.assertEqual(
            first["captured"][0]["signal_id"],
            second["captured"][0]["signal_id"],
            "重複的 gap 應該回到同一個 signal，而不是開新的",
        )
        raw = self.raw_records()
        self.assertEqual(len(raw), 1)
        self.assertEqual(raw[0]["evidence_count"], 2)

    def test_a_different_gap_on_the_same_skill_is_still_its_own_signal(self) -> None:
        # 去重的鍵是 (skill, gap)，不是 skill —— 少了這條，同一個 skill 的第二個
        # 真 gap 會被第一個吃掉。
        self.run_classifier(WITH_SKILLS, args=["--max-signals", "1"], gap="索引沒有帶出未結案狀態")
        self.run_classifier(WITH_SKILLS, args=["--max-signals", "1"], gap="逐字稿超過長度時沒有分段")
        self.assertEqual(len(self.queue_entries()), 2)


class CaptureDedupTest(unittest.TestCase):
    """去重住在 signal_state.py，所以 `<<GAP>>` 那條舊路徑也吃得到同一份規則。"""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.queue = self.root / "signal-queue.md"
        self.memory = self.root / "memory"
        self.queue.write_text("# Signal Queue\n\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def capture(self, gap: str, *, skill: str = "demo-skill", timestamp: str = "2026-09-15T10:00:00+08:00") -> str:
        completed = subprocess.run(
            [
                sys.executable, str(STATE), "capture",
                "--queue", str(self.queue),
                "--memory-dir", str(self.memory),
                "--timestamp", timestamp,
                "--target-skill", skill,
                "--type", "S2",
                "--source", "unit test",
                "--gap", gap,
            ],
            text=True, capture_output=True, check=True,
        )
        return completed.stdout.strip()

    def raw(self) -> list[dict]:
        return [json.loads(line) for line in (self.memory / "signals.jsonl").read_text().splitlines() if line.strip()]

    def test_whitespace_differences_do_not_make_a_new_signal(self) -> None:
        first = self.capture("索引 沒有  帶出未結案狀態")
        # 不同時間戳、同一個 gap：沒有正規化的話 signal_id 會不同，於是開出第二筆。
        second = self.capture("索引沒有帶出未結案狀態".replace("索引", "索引 ").replace("沒有", "沒有  "),
                              timestamp="2026-09-16T11:00:00+08:00")
        self.assertEqual(first, second)
        self.assertEqual(self.queue.read_text().count("- **signal_id**:"), 1)
        self.assertEqual(self.raw()[0]["evidence_count"], 2)

    def test_the_same_gap_on_another_skill_is_another_signal(self) -> None:
        self.capture("同一句描述", skill="skill-a")
        self.capture("同一句描述", skill="skill-b")
        self.assertEqual(self.queue.read_text().count("- **signal_id**:"), 2)

    def test_a_deduped_capture_leaves_the_existing_status_alone(self) -> None:
        # 去重不該是「復活」：已經被判掉的 signal 不能靠再出現一次爬回 pending。
        signal_id = self.capture("會再出現一次的 gap")
        subprocess.run(
            [
                sys.executable, str(STATE), "transition",
                "--queue", str(self.queue), "--memory-dir", str(self.memory),
                "--signal-id", signal_id, "--to", "deferred", "--decision-by", "unit-test",
            ],
            text=True, capture_output=True, check=True,
        )
        self.capture("會再出現一次的 gap", timestamp="2026-09-17T10:00:00+08:00")
        self.assertIn("- **status**: deferred", self.queue.read_text())
        self.assertNotIn("- **status**: pending", self.queue.read_text())
        self.assertEqual(self.raw()[0]["evidence_count"], 2)


if __name__ == "__main__":
    unittest.main()
