#!/usr/bin/env python3
"""eval：agent 到底有沒有讀歷史 —— 改前／改後各跑三次。

    python3 tests/eval/run_eval.py                      # 3 題 × 2 版 × 3 次 = 18 跑
    python3 tests/eval/run_eval.py --case glossary --arm after --runs 1

**這支進不了 CI**（要起 subagent、要花錢），所以它的判讀層由
`tests/unit/test_eval_assertion_layer.py` 守著。這裡只負責「把料擺好、跑、記帳」。

## 兩版是什麼

| arm | 流程 C 的來源表 | source artifacts |
|---|---|---|
| `before` | `fixtures/flow-c-before.md` —— #10 之前那版，歷史是一句沒有路徑的散文 | 不含 `history-index.md` |
| `after` | 現行 `SKILL.md` 的流程 C 導言（**跑的時候才讀**） | 含 `history-index.md` |

`before` 是從 git 取出來的真實舊版，不是拿現行版做文字手術 —— 手術版會隨現行版的
措辭漂移，而對照組本來就該是凍結的。`after` 反過來要跟著現行版走：eval 量的是**現在
出貨的那份**，不是某次快照。

## 停在 Markdown 是結構性的，不是靠叮嚀

`--allowed-tools Read` 加上 `--permission-prompts none`：Bash 這些工具**存在但一律被
自動拒絕**（`--print` 模式下任何會跳權限提示的呼叫直接視為拒絕）。跑不了
`create_gdoc_from_md.py`，也發不了 Slack —— 重複跑不會產生真的 Doc 與訊息。
（prompt 裡那句「不要發佈」是給人看的，不是這條保證的來源。）

## 已知的量測邊界：索引是**內嵌**進 prompt 的

`build_prompt()` 把四份 source artifacts 的內容直接放進 prompt。自變數因此是「歷史在
不在 agent 手上」—— 那正是 #14 說這個修法要改變的東西（「讀歷史從紀律問題變成資料可
得性問題」）。**沒有**被量到的是設計的另一半：「agent 掃大綱之後會不會沿 `本機:` 指標
去讀那一場全文」。索引已經在 context 裡，所以答對可以零次 `Read`。指標路徑是真的、
`Read` 也開著，agent 要跟得動，只是這條 eval 不強迫它跟。

## 三次迴圈有上限

`range(runs)`，**零重試**。每一跑再套 `--timeout` 秒的硬上限，逾時記成 `timeout` 並
把當下拿到的輸出印出來。壞掉要變紅不要跑不完 —— 無上限的重試迴圈不會讓任何東西變色，
只會讓整輪卡住而沒人知道。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# 兩支都從 conftest 拿，不自己刻：`skill_md_section` 是切節那幾行的唯一 owner
# （自刻一份的話 SKILL.md 標題形狀改了只會改到其中一份，另一份靜靜地量到別的範圍），
# `load_script` 是「腳本目錄有連字號、不是可 import 的套件路徑」的唯一解法，而且它把
# 路徑從**自己的檔案位置**推出來 —— mutmut 把東西複製進 `mutants/` 之後載到的才是
# 那一份。自己 `sys.path.insert` 一個寫死的 repo 路徑會載到原檔。
from tests.eval.grade import CASES, grade, passed  # noqa: E402
from tests.unit.conftest import load_script, skill_md_section  # noqa: E402

history_index = load_script("history_index")

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROMPT_FILE = ROOT / "skills/comms/generate-meeting-notes/references/default-prompt.md"
BEFORE_FILE = FIXTURES / "flow-c-before.md"

FLOW_C = "## 流程 C：Main Synthesis"
ARMS = ("before", "after")
MEETING_DATE = "20260831"

# 語料的系列名＝歸檔資料夾名（`local_archive.py` 的形狀）。一題一個系列，索引才不會
# 撈到別題的歷史 —— 一組斷言配多份語料是這張票要避的陷阱，一份歷史配多份語料同理。
SERIES = {
    "glossary": "評測_術語校正",
    "dropped-todo": "評測_消失的待辦",
    "overridden-decision": "評測_被推翻的決策",
}

EXCERPT_CHARS = 1200
DEFAULT_MODEL = "sonnet"
DEFAULT_TIMEOUT = 600
DEFAULT_RUNS = 3


# --------------------------------------------------------------------------- prompt


def flow_c(arm: str) -> str:
    """該版流程 C 的**導言** —— 來源表、證據優先序、輸出規則，到第一個 `### ` 為止。

    `after` 現讀 SKILL.md，`before` 讀凍結的舊版快照。Step 1 之後是發佈（建 Doc、
    發 Slack、歸檔），一個字都不能進 eval 的 prompt。

    ponytail: 切點是「第一個 `### `」這個字面。SKILL.md 把 Step 1 改成別的層級時，
    這裡會靜靜地把發佈那段也送進 prompt（或把導言整個切光）。兩個方向都由
    `tests/unit/test_eval_assertion_layer.py` 的兩版 prompt 比對擋著；真的常改了再
    換成解析 heading 層級。
    """
    section = (
        skill_md_section(FLOW_C) if arm == "after"
        else BEFORE_FILE.read_text(encoding="utf-8")
    )
    end = section.find("\n### ")
    return (section if end == -1 else section[:end]).strip()


def handoff(source_dir: Path, index_path: Path | None) -> str:
    """交棒契約那幾行。`before` 沒有 `RESULT_HISTORY_INDEX` —— 那正是對照的那一行。"""
    lines = [
        f"RESULT_SOURCE_DIR: {source_dir}",
        f"RESULT_TRANSCRIPT: {source_dir / 'transcript.md'}",
        f"RESULT_EXTRACT: {source_dir / 'extract.md'}",
        f"RESULT_CONTEXT: {source_dir / 'meeting-context.md'}",
        f"RESULT_DATE: {MEETING_DATE}",
    ]
    if index_path is not None:
        lines.append(f"RESULT_HISTORY_INDEX: {index_path}")
    return "\n".join(lines)


def _fenced(path: Path) -> str:
    return f"### `{path.name}`\n\n````markdown\n{path.read_text(encoding='utf-8')}\n````"


def build_prompt(arm: str, source_dir: Path, index_path: Path | None) -> str:
    """整份 prompt。四份 source artifacts 直接內嵌 —— 流程 C 的 agent 本來就會把它們
    讀進 context，內嵌只是省掉四次 Read，不改變它拿得到什麼。

    唯一的自變數是 `arm`：流程 C 那一節的措辭，以及交棒契約有沒有歷史那一行。
    """
    files = [source_dir / n for n in ("transcript.md", "extract.md", "meeting-context.md")]
    if index_path is not None:
        files.append(index_path)
    return "\n\n".join(
        [
            "你是 `generate-meeting-notes` skill 的 main agent，現在在流程 C。",
            "以下是 SKILL.md 的流程 C 一節：",
            flow_c(arm),
            "---\n\n以下是 `references/default-prompt.md`（版型規範）：",
            PROMPT_FILE.read_text(encoding="utf-8"),
            "---\n\n上一段流程印出的交棒契約：",
            f"```\n{handoff(source_dir, index_path)}\n```",
            "---\n\n各檔內容如下（路徑都是真的，需要時可以再 Read）：",
            *[_fenced(p) for p in files],
            "---\n\n產出正式稿 Markdown，**直接印在回覆裡，不要寫檔**。"
            "不要發佈：不要建 Google Doc、不要發 Slack、不要跑任何腳本。"
            "回覆裡只放正式稿本身，不要前言、不要結語、不要說明你做了什麼。",
        ]
    )


# --------------------------------------------------------------------------- 跑一次


def run_once(prompt: str, cwd: Path, model: str, timeout: int) -> tuple[str, str]:
    """起一個子 agent 跑這份 prompt，回 `(狀態, 輸出)`。

    狀態是 `ok` / `timeout` / `exit:<code>`。**不重試** —— 重試迴圈是這張票點名要避的
    陷阱：它不會讓任何東西變紅，只會讓整輪跑不完。

    逾時也要把當下拿到的 stdout 與 stderr 交出來：逾時最常見的原因寫在 stderr 裡
    （認證過期、模型不存在），丟掉它會讓「跑不完」變成一個沒有線索的狀態。
    """
    cmd = [
        "claude", "-p",
        "--safe-mode",                 # 不吃使用者的 CLAUDE.md／hooks／plugins／MCP
        "--model", model,
        "--output-format", "text",
        "--no-session-persistence",
        "--allowed-tools", "Read",       # 只預先核准 Read
        "--permission-prompts", "none",  # 其餘一律自動拒絕 —— 發佈那幾步過不了這一關
    ]
    try:
        proc = subprocess.run(
            cmd, input=prompt, cwd=cwd, timeout=timeout,
            capture_output=True, text=True,
        )
    except subprocess.TimeoutExpired as e:
        return "timeout", "\n".join(x for x in (e.stdout, e.stderr) if x)
    if proc.returncode != 0:
        return f"exit:{proc.returncode}", proc.stdout + proc.stderr
    return "ok", proc.stdout


# --------------------------------------------------------------------------- 主流程


def prepare(case: str, arm: str, work: Path) -> tuple[Path, Path | None]:
    """把該題該版的 source artifacts 擺進 `work`，回 `(source_dir, index_path)`。

    索引是**當場用 `history_index.build_index` 產的**，不是手寫一份塞進語料 ——
    手寫的索引一旦與腳本的實際輸出漂開，eval 量到的就是一份不存在的產物。
    """
    fixture = FIXTURES / case
    # 複製到 work/ 而不是直接指回語料目錄：`build_index` 會把 `history-index.md`
    # 寫進 source dir，指回去就是每跑一次在版控的語料裡長一個產物。
    source_dir = work / "sources"
    shutil.copytree(fixture / "sources", source_dir, dirs_exist_ok=True)
    if arm == "before":
        return source_dir, None
    series = SERIES[case]
    index = history_index.build_index(
        source_dir, series, series, MEETING_DATE, root=fixture / "archive"
    )
    return source_dir, index


def main() -> int:
    ap = argparse.ArgumentParser(description="eval：agent 有沒有真的讀歷史")
    ap.add_argument("--case", choices=CASES, action="append", help="只跑這幾題（預設全部）")
    ap.add_argument("--arm", choices=ARMS, action="append", help="只跑這幾版（預設兩版）")
    ap.add_argument("--runs", type=int, default=DEFAULT_RUNS, help=f"每題每版跑幾次（預設 {DEFAULT_RUNS}）")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"子 agent 的模型（預設 {DEFAULT_MODEL}）")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"單次上限秒數（預設 {DEFAULT_TIMEOUT}）")
    ap.add_argument("--out-dir", help="輸出目錄（預設 /tmp/gmn-eval-<timestamp>）")
    args = ap.parse_args()

    if args.runs < 1:
        print("❌ --runs 至少是 1")
        return 2

    cases = args.case or list(CASES)
    arms = args.arm or list(ARMS)
    out = Path(args.out_dir).expanduser() if args.out_dir else Path(f"/tmp/gmn-eval-{int(time.time())}")
    out.mkdir(parents=True, exist_ok=True)
    print(f"輸出目錄：{out}\n模型：{args.model}｜每題每版 {args.runs} 次｜單次上限 {args.timeout}s\n")

    results: list[dict] = []
    for case in cases:
        for arm in arms:
            work = out / case / arm
            source_dir, index_path = prepare(case, arm, work)
            prompt = build_prompt(arm, source_dir, index_path)
            (work / "prompt.txt").write_text(prompt, encoding="utf-8")
            for i in range(args.runs):
                started = time.time()
                status, note = run_once(prompt, FIXTURES / case, args.model, args.timeout)
                (work / f"run{i + 1}.md").write_text(note, encoding="utf-8")
                marks = grade(case, note) if status == "ok" else dict.fromkeys(grade(case, ""), False)
                ok = status == "ok" and passed(marks)
                results.append(
                    {"case": case, "arm": arm, "run": i + 1, "status": status,
                     "checks": marks, "passed": ok, "seconds": round(time.time() - started, 1)}
                )
                failed = [k for k, v in marks.items() if not v]
                print(
                    f"{'✅' if ok else '❌'} {case:22} {arm:6} run{i + 1} "
                    f"{status:8} {round(time.time() - started):>4}s"
                    + (f"  紅：{', '.join(failed)}" if failed else "")
                )
                if not ok:
                    # 失敗時把實際輸出印出來，不是只印路徑 —— 管線化的 log 裡只有路徑
                    # 等於沒有線索，而「改後仍失敗」要靠這段才分得出是 agent 沒讀歷史
                    # 還是判準的說法集合不夠。全文留在檔案裡，這裡印開頭夠判斷的量。
                    print(f"   ↳ 全文：{work / f'run{i + 1}.md'}（{len(note)} 字元）")
                    excerpt = note[:EXCERPT_CHARS]
                    print("\n".join(f"   │ {ln}" for ln in excerpt.splitlines()))
                    if len(note) > EXCERPT_CHARS:
                        print(f"   │ …（還有 {len(note) - EXCERPT_CHARS} 字元）")

    (out / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n── 三次都對才算過 ──")
    for case in cases:
        row = []
        for arm in arms:
            runs = [r for r in results if r["case"] == case and r["arm"] == arm]
            row.append(f"{arm} {sum(r['passed'] for r in runs)}/{len(runs)}")
        print(f"{case:22} " + "｜".join(row))
    print(f"\n完整結果：{out / 'results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
