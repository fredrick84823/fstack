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

# stub 照 #43 出貨的位置參數收：<skill> <gap> <excerpt> <known_signals>。
# 每次呼叫把 skill 附到 log、把 $3/$4 存檔，讓「模型被呼叫幾次」與「它看到了什麼」
# 都變成可斷言的事實 —— 只斷言 queue 結果的話，一個永遠回空的分類器也會綠。
STUB_VALIDATOR = """#!/usr/bin/env bash
printf '%s\\n' "$1" >> "$IMPROVE_STUB_LOG"
printf '%s' "$3" > "$IMPROVE_STUB_EXCERPT"
printf '%s' "$4" > "$IMPROVE_STUB_KNOWN"
if [ "$IMPROVE_STUB_DUPLICATE_OF" = "null" ]; then
  cat <<JSON
{"verdict":"accept","target_skill":"$1","gap":"$IMPROVE_STUB_GAP","duplicate_of":null,"evidence_quote":"不對，未結案的項目沒有被帶進索引","expected":"索引要帶出未結案狀態","actual":"索引只列標題","risk_class":"valid_gap","reason":"使用者原句指名了缺口"}
JSON
else
  # schema 規定 accept 一定 duplicate_of=null —— 重複是帶著 id 的 reject。
  cat <<JSON
{"verdict":"reject","target_skill":"$1","gap":"$IMPROVE_STUB_GAP","duplicate_of":$IMPROVE_STUB_DUPLICATE_OF,"evidence_quote":"","expected":"","actual":"","risk_class":"duplicate","reason":"restates a known signal"}
JSON
fi
"""

REJECTING_VALIDATOR = """#!/usr/bin/env bash
printf '%s\\n' "$1" >> "$IMPROVE_STUB_LOG"
echo '{"verdict":"reject","target_skill":"'"$1"'","gap":"","duplicate_of":null,"evidence_quote":"","expected":"","actual":"","risk_class":"uncertain","reason":"no quotable user sentence"}'
"""

# fail-closed：validate-gap.sh 的 die 走在 jq 之後，所以失敗時 stdout 可能已經有東西。
# 這個 stub 故意「先印一個看起來完好的 accept，再非零退出」—— 只看 stdout 解不解得開的
# 呼叫端會照單全收，只有真的檢查 returncode 的才擋得住。
FAILING_VALIDATOR = """#!/usr/bin/env bash
printf '%s\\n' "$1" >> "$IMPROVE_STUB_LOG"
echo '{"verdict":"accept","target_skill":"'"$1"'","gap":"殘留輸出","duplicate_of":null,"evidence_quote":"x","expected":"x","actual":"x","risk_class":"valid_gap","reason":"stale"}'
echo "validate-gap: claude -p failed (model=...)" >&2
exit 1
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
        self.excerpt = self.root / "validator-excerpt.txt"
        self.known = self.root / "validator-known.txt"

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
        duplicate_of: str | None = None,
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
            "IMPROVE_STUB_EXCERPT": str(self.excerpt),
            "IMPROVE_STUB_KNOWN": str(self.known),
            "IMPROVE_STUB_GAP": gap,
            "IMPROVE_STUB_DUPLICATE_OF": json.dumps(duplicate_of),
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

    def test_each_candidate_is_paired_with_the_skill_that_was_running_when_it_was_said(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("sc", CLASSIFIER)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        pairs = module.candidates(module.read_transcript(WITH_SKILLS))

        # 量過才這樣做：把探針句塞進 gap 欄位請 validator 自己找缺口，實測 0/3 accept；
        # 把所有使用者訊息接成一串 → misroute；單句 → 3/3 accept。所以候選是單句。
        self.assertEqual(pairs, [
            ("generate-meeting-notes", "不對，未結案的項目沒有被帶進索引，每次都要我自己講一遍"),
            ("generate-meeting-notes", "順便把交接文件也生一份"),
            ("create-handoff", "交接文件每次都漏掉驗證步驟那一段"),
        ])
        # 第一句「幫我把這場會議的逐字稿整理成會議記錄」在任何 Skill 呼叫之前，
        # 沒有 skill 可歸因，所以不該變成候選。
        self.assertNotIn("幫我把這場會議的逐字稿整理成會議記錄", [message for _, message in pairs])

    # --- 不呼叫模型的那條路 --------------------------------------------------

    def test_a_session_that_called_no_skill_never_reaches_the_model(self) -> None:
        report = self.run_classifier(WITHOUT_SKILLS)
        self.assertEqual(report["skipped"], "no skill invoked")
        self.assertEqual(report["captured"], [])
        # 這條是整支腳本的成本前提：沒有 skill 呼叫就不該有任何一次 validator 呼叫。
        self.assertEqual(self.validator_calls(), [])
        self.assertEqual(self.queue_entries(), [])

    # --- 自動化 session 一律跳過 ---------------------------------------------

    def test_child_session_marker_is_not_a_gate(self) -> None:
        # 2026-09-16: a plain interactive session carried CLAUDE_CODE_CHILD_SESSION=1, so
        # gating on it skipped every real session. Attended + entrypoint are the gates.
        self.log.write_text("")
        report = self.run_classifier(WITH_SKILLS, env_extra={"CLAUDE_CODE_CHILD_SESSION": "1"})
        self.assertIsNone(report["skipped"])
        self.assertGreater(len(self.validator_calls()), 0)

    def test_every_automation_marker_stops_the_run_before_the_model(self) -> None:
        for env_extra, expected in (
            ({"IMPROVE_CLASSIFIER_DISABLE": "1"}, "disabled by IMPROVE_CLASSIFIER_DISABLE"),
            ({"CLAUDE_CODE_SESSION_ATTENDED": "0"}, "unattended session"),
            ({"CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}, "non-interactive entrypoint: sdk-cli"),
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

    def test_the_per_session_budget_caps_calls_and_spends_them_on_the_latest_turns(self) -> None:
        report = self.run_classifier(WITH_SKILLS, args=["--max-signals", "1"])
        self.assertEqual(report["calls"], 1)
        self.assertEqual(len(report["captured"]), 1)
        self.assertEqual(len(self.queue_entries()), 1)
        # fixture 有三個候選句；額度 1 花在**最後**那一句，因為 session 尾端的修正
        # 才是還值得處理的那個。三句都問一次就是三倍的錢。
        self.assertEqual(self.validator_calls(), ["create-handoff"])

    def test_the_budget_is_configurable_from_the_environment(self) -> None:
        report = self.run_classifier(WITH_SKILLS, env_extra={"IMPROVE_MAX_SIGNALS": "2"})
        self.assertEqual(len(report["captured"]), 2)

    # --- 驗證器判否 ----------------------------------------------------------

    def test_a_rejecting_validator_captures_nothing_while_still_being_asked(self) -> None:
        report = self.run_classifier(WITH_SKILLS, validator=self.write_validator(REJECTING_VALIDATOR))
        self.assertEqual(report["captured"], [])
        self.assertEqual(self.queue_entries(), [])
        # 判否不等於沒問。問的是候選句，不是 skill —— 同一個 skill 有兩句修正就問兩次，
        # 而每一句都帶著「說這句話時正在跑的那個 skill」。
        self.assertEqual(
            self.validator_calls(),
            ["generate-meeting-notes", "generate-meeting-notes", "create-handoff"],
        )

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

    # --- 換句話說的重複：交給驗證器認，不自己寫模糊比對 ------------------------

    def test_the_skills_existing_signals_are_handed_to_the_validator_to_compare_against(self) -> None:
        self.run_classifier(WITH_SKILLS, args=["--max-signals", "1"], gap="索引沒有帶出未結案狀態")
        self.log.write_text("")
        self.run_classifier(WITH_SKILLS, args=["--max-signals", "1"], gap="換一種說法的同一件事")

        known = self.known.read_text()
        # 沒有這一段，驗證器沒有東西可以比對，duplicate_of 永遠只能回 null，
        # 7 月那 43% 換句話說的重複就全部漏回 queue。
        self.assertRegex(known, r"^sig_\S+\t索引沒有帶出未結案狀態$")
        # 位置參數，不是塞在 excerpt 裡 —— #43 的 validate-gap.sh 讀的是 $4。
        self.assertNotIn("KNOWN_SIGNALS", self.excerpt.read_text())

    def test_a_validator_that_cannot_run_captures_nothing(self) -> None:
        # fail-closed：把「驗證器沒跑成」讀成「沒有 gap」是對的，讀成 accept 會在
        # 認證過期那天把每個 session 都收進 queue。
        report = self.run_classifier(WITH_SKILLS, validator=self.write_validator(FAILING_VALIDATOR))
        self.assertEqual(report["captured"], [])
        self.assertEqual(report["deduped"], [])
        self.assertEqual(self.queue_entries(), [])

    def test_a_duplicate_of_verdict_adds_a_witness_instead_of_a_queue_entry(self) -> None:
        first = self.run_classifier(WITH_SKILLS, args=["--max-signals", "1"])
        existing = first["captured"][0]["signal_id"]

        second = self.run_classifier(
            WITH_SKILLS, args=["--max-signals", "1"],
            gap="完全不同的措辭，但講的是同一個缺口",
            duplicate_of=existing,
        )
        self.assertEqual(second["captured"], [])
        self.assertEqual({item["signal_id"] for item in second["deduped"]}, {existing})
        # 重複是帶著 id 的 **reject**；先讀 verdict 再讀 id 的話這筆會被丟掉。
        self.assertEqual(len(self.queue_entries()), 1)
        self.assertEqual(self.raw_records()[0]["evidence_count"], 1 + len(second["deduped"]))

    def test_a_duplicate_still_costs_a_call_and_so_spends_the_budget(self) -> None:
        # 預算算的是**呼叫**不是捕獲：重複也花了一次 claude -p，$0.04 一樣要付。
        # 只算捕獲的話，一個十個 skill 的 session 可以燒到 $0.40 才碰到上限。
        first = self.run_classifier(WITH_SKILLS, args=["--max-signals", "1"])
        existing = first["captured"][0]["signal_id"]
        self.log.write_text("")
        report = self.run_classifier(
            WITH_SKILLS, args=["--max-signals", "2"], gap="另一種說法", duplicate_of=existing,
        )
        self.assertEqual(report["calls"], 2)
        self.assertEqual(len(self.validator_calls()), 2)
        self.assertEqual(len(report["deduped"]), 2)
        self.assertEqual(report["captured"], [])

    def test_the_verdicts_risk_class_is_stored_as_itself_not_as_a_queue_type(self) -> None:
        self.run_classifier(WITH_SKILLS, args=["--max-signals", "1"])
        queue_text = self.queue.read_text()
        # risk_class 是「為什麼這樣判」的分類，queue 的 type 是 S1/S2/S3 嚴重度 ——
        # 兩個不同的問題，不要把其中一個折進另一個。
        self.assertIn("- **type**: S2", queue_text)
        self.assertIn("- **risk_class**: valid_gap", queue_text)
        self.assertEqual(self.raw_records()[0]["risk_class"], "valid_gap")

    def test_the_expected_and_actual_from_the_verdict_survive_into_memory(self) -> None:
        self.run_classifier(WITH_SKILLS, args=["--max-signals", "1"])
        record = self.raw_records()[0]
        self.assertEqual(record["expected_behavior"], "索引要帶出未結案狀態")
        self.assertEqual(record["actual_behavior"], "索引只列標題")

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

    def transition(self, signal_id: str, to: str, *, candidate: str | None = None) -> None:
        extra = []
        if to == "resolved":
            candidate = candidate or "candidate_fixture"
            subprocess.run(
                [
                    sys.executable, str(STATE), "prepare",
                    "--queue", str(self.queue), "--memory-dir", str(self.memory),
                    "--signal-id", signal_id, "--candidate-id", candidate,
                ],
                text=True, capture_output=True, check=True,
            )
            extra = ["--candidate-id", candidate]
        subprocess.run(
            [
                sys.executable, str(STATE), "transition",
                "--queue", str(self.queue), "--memory-dir", str(self.memory),
                "--signal-id", signal_id, "--to", to, "--decision-by", "unit-test", *extra,
            ],
            text=True, capture_output=True, check=True,
        )

    def test_a_deduped_capture_leaves_the_existing_status_alone(self) -> None:
        # 去重不該是「復活」：已經被判掉的 signal 不能靠再出現一次爬回 pending。
        for index, status in enumerate(("deferred", "rejected")):
            with self.subTest(status=status):
                gap = f"會再出現一次的 gap {index}"
                signal_id = self.capture(gap)
                self.transition(signal_id, status)
                self.capture(gap, timestamp=f"2026-09-1{index + 7}T10:00:00+08:00")
                self.assertIn(f"- **status**: {status}", self.queue.read_text())
                self.assertNotIn("- **status**: pending", self.queue.read_text())
                record = [r for r in self.raw() if r["signal_id"] == signal_id][0]
                self.assertEqual(record["evidence_count"], 2)

    def test_a_gap_that_comes_back_after_being_fixed_is_a_new_signal(self) -> None:
        # 裁示：resolved 是唯一的例外。把回歸折進已修好的那筆，就等於把「修了但沒修好」
        # 這件事唯一的證據埋掉 —— evidence_count 從 1 變 2，而 queue 上沒有任何東西變。
        gap = "索引沒有帶出未結案狀態"
        original = self.capture(gap)
        self.transition(original, "resolved")

        regression = self.capture(gap, timestamp="2026-09-20T10:00:00+08:00")
        self.assertNotEqual(regression, original)
        self.assertEqual(self.queue.read_text().count("- **signal_id**:"), 2)
        self.assertIn("- **status**: pending", self.queue.read_text())

        new_record = [r for r in self.raw() if r["signal_id"] == regression][0]
        old_record = [r for r in self.raw() if r["signal_id"] == original][0]
        self.assertEqual(new_record["links"]["regression_of"], original)
        self.assertEqual(new_record["evidence_count"], 1)
        self.assertEqual(old_record["evidence_count"], 1, "舊的那筆不該同時又被加一次")

    def test_a_third_sighting_joins_the_live_regression_not_the_resolved_ancestor(self) -> None:
        # 同一個鍵現在有兩筆 raw record。第三次出現屬於還活著的那筆，
        # 比對「第一筆」的話會開出第三個 signal，回歸就變成每次都開新的。
        gap = "索引沒有帶出未結案狀態"
        original = self.capture(gap)
        self.transition(original, "resolved")
        regression = self.capture(gap, timestamp="2026-09-20T10:00:00+08:00")

        again = self.capture(gap, timestamp="2026-09-21T10:00:00+08:00")
        self.assertEqual(again, regression)
        self.assertEqual(self.queue.read_text().count("- **signal_id**:"), 2)
        self.assertEqual([r for r in self.raw() if r["signal_id"] == regression][0]["evidence_count"], 2)

    def capture_duplicate_of(self, signal_id: str, gap: str, timestamp: str, *, check: bool = True):
        return subprocess.run(
            [
                sys.executable, str(STATE), "capture",
                "--queue", str(self.queue), "--memory-dir", str(self.memory),
                "--timestamp", timestamp, "--target-skill", "demo-skill",
                "--type", "S2", "--source", "session classifier", "--gap", gap,
                "--duplicate-of", signal_id,
            ],
            text=True, capture_output=True, check=check,
        )

    def test_a_validator_named_duplicate_counts_against_the_signal_it_names(self) -> None:
        # 文字比對接不起來的兩句話：驗證器指名的那條路走這裡。
        original = self.capture("原本的描述")
        echoed = self.capture_duplicate_of(original, "字面上毫無交集的另一種說法", "2026-09-20T10:00:00+08:00")
        self.assertEqual(echoed.stdout.strip(), original)
        self.assertEqual(self.queue.read_text().count("- **signal_id**:"), 1)
        self.assertEqual(self.raw()[0]["evidence_count"], 2)

    def test_a_validator_named_duplicate_of_a_resolved_signal_is_still_a_regression(self) -> None:
        # 裁示：duplicate_of 指到 resolved 時套用跟 exact-match 同一條回歸規則。
        original = self.capture("索引沒有帶出未結案狀態")
        self.transition(original, "resolved")
        echoed = self.capture_duplicate_of(original, "換句話說的同一個缺口", "2026-09-20T10:00:00+08:00")

        regression = echoed.stdout.strip()
        self.assertNotEqual(regression, original)
        self.assertEqual(self.queue.read_text().count("- **signal_id**:"), 2)
        self.assertEqual([r for r in self.raw() if r["signal_id"] == regression][0]["links"]["regression_of"], original)

    def test_a_regression_found_by_meaning_inherits_the_evidence_it_cannot_restate(self) -> None:
        # schema 規定 reject 一律清空 evidence_quote，而重複就是帶著 id 的 reject。
        # 不繼承的話，回歸會開出一筆沒有任何人追得回去的 signal。
        original = subprocess.run(
            [
                sys.executable, str(STATE), "capture",
                "--queue", str(self.queue), "--memory-dir", str(self.memory),
                "--timestamp", "2026-09-15T10:00:00+08:00", "--target-skill", "demo-skill",
                "--type", "S2", "--source", "unit test", "--gap", "索引沒有帶出未結案狀態",
                "--evidence-quote", "不對，未結案的項目沒有被帶進索引",
                "--expected", "索引要帶出未結案狀態", "--actual", "索引只列標題",
                "--risk-class", "valid_gap",
            ],
            text=True, capture_output=True, check=True,
        ).stdout.strip()
        self.transition(original, "resolved")
        regression = self.capture_duplicate_of(original, "換句話說的同一個缺口", "2026-09-20T10:00:00+08:00").stdout.strip()

        record = [r for r in self.raw() if r["signal_id"] == regression][0]
        self.assertEqual(record["evidence_quote"], "不對，未結案的項目沒有被帶進索引")
        self.assertEqual(record["expected_behavior"], "索引要帶出未結案狀態")
        self.assertEqual(record["actual_behavior"], "索引只列標題")

    def test_an_unknown_duplicate_of_is_refused_instead_of_invented(self) -> None:
        result = self.capture_duplicate_of("sig_does_not_exist", "任何 gap", "2026-09-20T10:00:00+08:00", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown duplicate_of", result.stderr)
        self.assertEqual(self.queue.read_text().count("- **signal_id**:"), 0)


if __name__ == "__main__":
    unittest.main()
