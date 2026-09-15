"""GAP validator 的契約與判讀層 —— `evals/run_validator_eval.py` 進不了 CI 的那一半。

eval 本身要起 `claude -p`、要花錢，所以 `make test` 跑不到它。跑不到的東西壞了不會有人
知道，於是這支把三種**不需要模型也能錯**的東西釘住：

1. **契約的兩份副本**。JSON 欄位同時寫在 `validate-gap.sh` 的檔頭註解（給人看）與
   `validate-gap-schema.json`（給 `claude -p --json-schema` 看）。#44 照著註解寫消費端，
   schema 卻是實際強制的那份 —— 兩邊分岔的症狀是 #44 讀一個永遠不存在的欄位。
2. **判讀層**。`grade()` 決定 eval 綠不綠。它自己壞掉的話，整輪 eval 會安靜地全綠。
3. **「判準只有一份」**。這張票的驗收條件之一是 SKILL.md 不再留一份 abstain 規則副本。
   那是一句人話承諾，不釘住的話下一次有人覺得「SKILL.md 應該自我完備」就加回來了。
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
IMPROVE = ROOT / "skills/skill-evolution/improve"
SCHEMA = IMPROVE / "references/validate-gap-schema.json"
PROMPT = IMPROVE / "references/validate-gap-prompt.md"
VALIDATOR_SH = IMPROVE / "scripts/validate-gap.sh"
FIXTURES = IMPROVE / "evals/validator-fixtures.json"
RUNNER = IMPROVE / "evals/run_validator_eval.py"
SKILL_MD = IMPROVE / "SKILL.md"
README = ROOT / "README.md"


def _load(path: Path) -> ModuleType:
    """把 `evals/run_validator_eval.py` 當模組載進來。

    目錄名有連字號，不是可 import 的套件路徑（同 conftest.load_script 的理由）。
    模組名從**路徑**推，不自己取一個好看的。
    """
    modname = str(path.relative_to(ROOT).with_suffix("")).replace("/", ".")
    spec = importlib.util.spec_from_file_location(modname, path)
    assert spec and spec.loader, f"載不進來：{path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load(RUNNER)
schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]


# --------------------------------------------------------------- 契約的兩份副本


def _fields_in_header() -> set[str]:
    """`validate-gap.sh` 檔頭 `── JSON contract ──` 那一段裡，每一行的第一個字。

    欄位名寫在行首、說明跟在後面。抓法刻意保守：只認 `#   <name>  <兩個以上空白>`，
    所以散文行（`# Invariants: ...`）配不到。
    """
    text = VALIDATOR_SH.read_text(encoding="utf-8")
    block = text[text.index("── JSON contract"):text.index("── Model")]
    return set(re.findall(r"^#   ([a-z_]+) {2,}", block, re.MULTILINE))


def test_header_comment_and_schema_list_the_same_fields() -> None:
    assert _fields_in_header() == set(schema["required"])


def test_every_contract_field_is_required_and_nothing_extra_is_allowed() -> None:
    # 可選欄位會讓 #44 必須對每個欄位寫 `.get(...)` 的防禦，而 schema 沒有理由留白。
    assert set(schema["properties"]) == set(schema["required"])
    assert schema["additionalProperties"] is False


def test_verdict_has_no_uncertain_value() -> None:
    # precision-first 的整個重點：不確定要落到 reject，不是自成一類讓呼叫端自己決定。
    assert schema["properties"]["verdict"]["enum"] == ["accept", "reject"]
    assert "uncertain" in schema["properties"]["risk_class"]["enum"]


def test_duplicate_of_is_nullable_string() -> None:
    assert schema["properties"]["duplicate_of"]["type"] == ["string", "null"]


# ------------------------------------------------------------------ 判讀層 grade()


def _verdict(**over) -> dict:
    base = {
        "verdict": "accept", "target_skill": "demo", "gap": "g",
        "duplicate_of": None, "evidence_quote": "你每次都漏掉這步",
        "expected": "e", "actual": "a", "risk_class": "valid_gap", "reason": "r",
    }
    base.update(over)
    return base


RECALL = {"class": "recall", "excerpt": "使用者：你每次都漏掉這步。", "expect_duplicate_of": None}
TRAP = {"class": "trap", "excerpt": "x", "expect_duplicate_of": None}


def test_missing_verdict_is_a_failure_not_a_reject() -> None:
    # validator 非零退出／逾時回 None。把它讀成 reject 會讓 clean/trap 在腳本壞掉時全綠。
    assert runner.grade(TRAP, None) == (False, "no verdict")


def test_recall_needs_accept() -> None:
    assert runner.grade(RECALL, _verdict())[0]
    assert not runner.grade(RECALL, _verdict(verdict="reject"))[0]


def test_trap_needs_reject() -> None:
    assert runner.grade(TRAP, _verdict(verdict="reject"))[0]
    assert not runner.grade(TRAP, _verdict())[0]


@pytest.mark.parametrize("field", ["evidence_quote", "expected", "actual"])
def test_accept_without_evidence_fails(field: str) -> None:
    ok, note = runner.grade(RECALL, _verdict(**{field: ""}))
    assert not ok and field in note


def test_accept_with_a_quote_that_is_not_in_the_excerpt_fails() -> None:
    # 這條擋的是編造引用 —— verdict 對、欄位非空，只是那句話沒人說過。
    ok, note = runner.grade(RECALL, _verdict(evidence_quote="使用者：這個功能很棒"))
    assert not ok and "verbatim" in note


def test_quote_matching_ignores_whitespace_only() -> None:
    # 模型常多吐／吃掉一個換行，那不是要抓的錯；標點與字元本體照樣要對得上。
    assert runner.grade(RECALL, _verdict(evidence_quote="你每次都漏掉這步"))[0]
    assert runner.grade(RECALL, _verdict(evidence_quote="你每次都 漏掉\n這步"))[0]
    assert not runner.grade(RECALL, _verdict(evidence_quote="你每次都漏掉這步驟"))[0]


def test_duplicate_of_must_point_at_the_expected_signal() -> None:
    case = {**TRAP, "expect_duplicate_of": "sig_a"}
    assert runner.grade(case, _verdict(verdict="reject", duplicate_of="sig_a"))[0]
    assert not runner.grade(case, _verdict(verdict="reject", duplicate_of="sig_b"))[0]
    assert not runner.grade(case, _verdict(verdict="reject", duplicate_of=None))[0]


def test_duplicate_of_must_be_null_when_the_gap_is_new() -> None:
    # 只驗「該指的有指到」的話，一個對每筆都填最近一個 id 的模型會拿滿分 ——
    # 而那正是去重壞掉的樣子。
    assert not runner.grade(TRAP, _verdict(verdict="reject", duplicate_of="sig_x"))[0]
    assert not runner.grade(RECALL, _verdict(duplicate_of="sig_x"))[0]


# --------------------------------------------------------------------- fixtures


def test_each_class_has_at_least_three_fixtures() -> None:
    counts = {k: sum(c["class"] == k for c in fixtures) for k in runner.PASS_BY_CLASS}
    assert all(n >= 3 for n in counts.values()), counts


def test_expect_agrees_with_class() -> None:
    for case in fixtures:
        assert case["expect"] == runner.PASS_BY_CLASS[case["class"]], case["id"]


def test_at_least_two_paraphrased_duplicate_traps() -> None:
    dupes = [c for c in fixtures if c["expect_duplicate_of"]]
    assert len(dupes) >= 2, [c["id"] for c in fixtures]
    for case in dupes:
        # 措辭不同才是這幾筆的重點：逐字相同的話量到的是字串比對，不是語意去重。
        known = dict(
            line.split("\t", 1)
            for line in case["known_signals"].splitlines() if "\t" in line
        )
        assert case["expect_duplicate_of"] in known, case["id"]
        assert known[case["expect_duplicate_of"]] != case["gap"], case["id"]


def test_accept_fixtures_carry_a_quotable_sentence() -> None:
    # recall 的通過條件是「引用出現在 excerpt 裡」。fixture 本身沒有可引用的使用者原句
    # 的話，那條測的是模型會不會編造，不是它會不會漏判。
    for case in fixtures:
        if case["expect"] == "accept":
            assert "使用者：" in case["excerpt"], case["id"]


def test_every_fixture_names_its_source_entry() -> None:
    for case in fixtures:
        assert case["source"].strip(), case["id"]


# ------------------------------------------------------- 判準只有一份 / README


def test_prompt_is_precision_first() -> None:
    text = PROMPT.read_text(encoding="utf-8")
    assert "When uncertain, reject." in text
    # 回填進來的那版明講「不確定時 accept」。這條是這張票的整個由來。
    assert "recall is more important than precision" not in text


def test_prompt_carries_the_abstain_rules_itself() -> None:
    text = PROMPT.read_text(encoding="utf-8")
    for risk_class in schema["properties"]["risk_class"]["enum"]:
        assert f"`{risk_class}`" in text, risk_class


def test_skill_md_points_at_the_prompt_instead_of_repeating_it() -> None:
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "references/validate-gap-prompt.md" in text
    # 舊副本的標題與表頭。任何一個回來就是兩份判準又活了。
    for copy in ("Do not emit GAP / Abstain 條件", "**Abstain examples**", "辨識關鍵字範例"):
        assert copy not in text, copy


def test_readme_no_longer_asks_for_a_global_claude_md_rule() -> None:
    text = README.read_text(encoding="utf-8")
    section = text[text.index("## Post-install"):text.index("## License")]
    assert "~/.claude/CLAUDE.md" in section  # 講了「不要加」，所以字串還在
    assert "Add the following to your" not in section
    assert "IMPROVE_VALIDATOR_MODEL" in section


def test_default_model_is_named_in_both_script_and_readme() -> None:
    # 預設模型改了只改一邊的話，README 會教人設一個跟實際預設不同的值。
    default = "claude-haiku-4-5-20251001"
    assert f"IMPROVE_VALIDATOR_MODEL:-{default}" in VALIDATOR_SH.read_text(encoding="utf-8")
    assert default in README.read_text(encoding="utf-8")


# ------------------------------------------------- validate-gap.sh 的接線與降級守衛


def _run_validator(tmp_path: Path, structured_output, *args: str,
                   claude_exit: int = 0) -> subprocess.CompletedProcess[str]:
    """把一個假的 `claude` 放到 PATH 最前面，再跑真的 `validate-gap.sh`。

    量的是整條接線：prompt 組裝、`--json-schema` 那次呼叫、jq 把 `structured_output`
    撈出來、以及兩道降級守衛。只測 jq filter 的話，filter 被改壞以外的每一種接線錯誤
    都量不到 —— 而這支腳本是 fail-closed 的，接線壞掉的症狀是「永遠沒有 verdict」，
    不是紅測試。

    `structured_output` 為 None 代表模型回了沒有 structured output 的東西。
    """
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    envelope = [{"type": "system"}]
    if structured_output is not None:
        envelope.append({"type": "result", "structured_output": structured_output})
    else:
        envelope.append({"type": "result", "result": "sorry, I cannot do that"})
    payload = json.dumps(envelope, ensure_ascii=False)
    stub = stub_dir / "claude"
    stub.write_text(
        "#!/usr/bin/env bash\ncat >/dev/null\n"
        f"exit_code={claude_exit}\n"
        f"[ $exit_code -ne 0 ] && exit $exit_code\n"
        f"cat <<'JSON'\n{payload}\nJSON\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    env = {**os.environ, "PATH": f"{stub_dir}:{os.environ['PATH']}"}
    return subprocess.run([str(VALIDATOR_SH), *args], env=env,
                          capture_output=True, text=True)


ACCEPT = {
    "verdict": "accept", "target_skill": "demo", "gap": "g", "duplicate_of": None,
    "evidence_quote": "q", "expected": "e", "actual": "a",
    "risk_class": "valid_gap", "reason": "r",
}


def test_a_well_formed_accept_passes_through(tmp_path: Path) -> None:
    proc = _run_validator(tmp_path, ACCEPT, "demo", "g", "ctx", "")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == ACCEPT


def test_accept_without_evidence_is_downgraded_to_reject(tmp_path: Path) -> None:
    proc = _run_validator(tmp_path, {**ACCEPT, "evidence_quote": ""}, "demo", "g")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["verdict"] == "reject"
    assert out["risk_class"] == "uncertain"
    assert "downgraded" in out["reason"]


def test_accept_pointing_at_a_known_signal_is_downgraded_to_duplicate(tmp_path: Path) -> None:
    proc = _run_validator(tmp_path, {**ACCEPT, "duplicate_of": "sig_a"}, "demo", "g")
    out = json.loads(proc.stdout)
    assert out["verdict"] == "reject"
    assert out["risk_class"] == "duplicate"
    assert out["duplicate_of"] == "sig_a"


def test_a_plain_reject_is_left_alone(tmp_path: Path) -> None:
    reject = {**ACCEPT, "verdict": "reject", "risk_class": "data_issue",
              "evidence_quote": "", "expected": "", "actual": ""}
    assert json.loads(_run_validator(tmp_path, reject, "demo", "g").stdout) == reject


def test_no_structured_output_fails_closed(tmp_path: Path) -> None:
    # 拿不到判決要吵，不能安靜地回空字串 —— 呼叫端分不出 reject 與「驗證器沒跑」的話，
    # 它會把所有東西都當成通過。
    proc = _run_validator(tmp_path, None, "demo", "g")
    assert proc.returncode != 0
    assert proc.stdout.strip() == ""


def test_claude_failing_fails_closed(tmp_path: Path) -> None:
    proc = _run_validator(tmp_path, ACCEPT, "demo", "g", claude_exit=1)
    assert proc.returncode != 0
    assert proc.stdout.strip() == ""
    assert "claude -p failed" in proc.stderr


def test_known_signals_reach_the_prompt(tmp_path: Path) -> None:
    """第四個參數必須真的出現在送給模型的 prompt 裡。

    忘了把它接進去的症狀是「duplicate 從來不觸發」—— 一個安靜地少一半輸入的驗證器，
    每一筆都會判成新缺口，而那正好長得像它運作良好。
    """
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    seen = tmp_path / "prompt.txt"
    stub = stub_dir / "claude"
    stub.write_text(
        f"#!/usr/bin/env bash\ncat > {seen}\n"
        f"echo '[{{\"type\":\"result\",\"structured_output\":{json.dumps(ACCEPT)}}}]'\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    env = {**os.environ, "PATH": f"{stub_dir}:{os.environ['PATH']}"}
    subprocess.run([str(VALIDATOR_SH), "demo", "the gap", "the excerpt",
                    "sig_a\tan earlier gap"], env=env, capture_output=True, text=True)
    prompt = seen.read_text(encoding="utf-8")
    assert "===KNOWN_SIGNALS===\nsig_a\tan earlier gap" in prompt
    assert "===CONTEXT===\nthe excerpt" in prompt
    assert "target_skill: demo" in prompt


@pytest.mark.parametrize("args", [(), ("only-skill",), ("", "gap"), ("skill", "")])
def test_missing_required_args_is_a_usage_error(args: tuple[str, ...]) -> None:
    proc = subprocess.run([str(VALIDATOR_SH), *args], capture_output=True, text=True)
    assert proc.returncode == 2
    assert "usage:" in proc.stderr
