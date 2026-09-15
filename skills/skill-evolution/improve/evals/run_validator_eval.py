#!/usr/bin/env python3
"""eval：precision-first 的 GAP validator 到底擋不擋得住雜訊。

    python3 skills/skill-evolution/improve/evals/run_validator_eval.py
    python3 .../run_validator_eval.py --case trap-02 --runs 1
    IMPROVE_VALIDATOR_MODEL=sonnet python3 .../run_validator_eval.py

14 筆 fixture × 三次。**三次都對才算過** —— 判對一次可能是模型自己猜中。

## 為什麼是跑 `validate-gap.sh` 而不是自己叫 `claude -p`

量的要是**出貨的那條路**。自己在這裡刻一份 `claude -p` 呼叫，等於量一個平行實作：
prompt 檔換了、schema 換了、`validate-gap.sh` 裡那道「accept 但沒有 evidence_quote
就降級」的守衛壞了，這支都還是綠的。所以 subprocess 打進去的是真的那支腳本。

## 通過條件

| 類別 | 條件 |
|---|---|
| `recall` | verdict 必須是 `accept`，`evidence_quote` 非空且逐字出現在 excerpt 裡，`duplicate_of` 為 null |
| `clean` / `trap` | verdict 必須是 `reject` |
| 任一筆有 `expect_duplicate_of` | `duplicate_of` 必須等於那個 signal id |

`expect_duplicate_of` 是硬條件而非 advisory：#44 拿 `duplicate_of` 去做去重，
指錯或漏填就是一筆重複進 queue，而重複佔了那個月 43% 的條目。

`risk_class` **只記錄不判定**。data_issue 與 one_shot_pref 的界線本來就可爭辯，
把它綁成硬條件只會得到一支沒人相信的 eval。不一致的筆數印在摘要裡供人看。

## 三次迴圈有上限

`range(runs)`，**零重試**。每一跑再套 `--timeout` 秒的硬上限，逾時記成 `timeout`。
壞掉要變紅不要跑不完。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "validator-fixtures.json"
VALIDATOR = HERE.parent / "scripts" / "validate-gap.sh"

# 這支不進 CI（要起 claude -p、要花錢）。判讀層由 tests/unit/test_validator_eval_layer.py
# 守著 —— 那支 import 下面的 grade()，所以這裡改了判準、測試會跟著叫。
PASS_BY_CLASS = {"recall": "accept", "clean": "reject", "trap": "reject"}


def normalize(text: str) -> str:
    """比對 evidence_quote 用的寬鬆形式：去掉所有空白。

    模型引用時常吃掉或多吐一個全形空白／換行，而那不是我們要抓的錯 —— 要抓的是
    「引用了一句 excerpt 裡根本沒有的話」。標點與字元本體一律保留。
    """
    return "".join(text.split())


def grade(case: dict, verdict: dict | None) -> tuple[bool, str]:
    """回 `(過了沒, 一句話原因)`。

    `verdict is None` 代表這一跑沒拿到 JSON（validator 非零退出或逾時）——
    那是**不過**，不是 reject：把「驗證器沒跑起來」記成 reject 會讓整個 clean/trap
    類別在腳本壞掉時全綠。
    """
    if verdict is None:
        return False, "no verdict"

    want = PASS_BY_CLASS[case["class"]]
    got = verdict.get("verdict")
    if got != want:
        return False, f"verdict={got}, want {want}"

    # duplicate_of 兩個方向都要對：該指的要指對，不該指的要是 null。只驗前者的話，
    # 一個對每筆都填上最近一個 signal id 的模型會拿滿分，而那正是去重壞掉的樣子。
    want_dup = case.get("expect_duplicate_of")
    got_dup = verdict.get("duplicate_of")
    if want_dup and got_dup != want_dup:
        return False, f"duplicate_of={got_dup!r}, want {want_dup!r}"
    if not want_dup and got_dup:
        return False, f"duplicate_of={got_dup!r}, want null"

    if want == "reject":
        return True, "reject" + (f" (duplicate_of {got_dup})" if got_dup else "")

    quote = (verdict.get("evidence_quote") or "").strip()
    if not quote:
        return False, "accept without evidence_quote"
    if normalize(quote) not in normalize(case["excerpt"]):
        return False, "evidence_quote not found verbatim in excerpt"
    for field in ("expected", "actual"):
        if not (verdict.get(field) or "").strip():
            return False, f"accept without {field}"
    return True, "accept with quoted evidence"


def run_once(case: dict, timeout: int) -> tuple[dict | None, str]:
    """跑一次 validator，回 `(verdict 物件或 None, 狀態)`。

    逾時與非零退出都把 stderr 帶回來：validator 是 fail-closed 的，失敗原因寫在
    stderr（模型不存在、認證過期、jq 沒裝），丟掉它會讓「不過」變成沒有線索的狀態。
    """
    cmd = [str(VALIDATOR), case["target_skill"], case["gap"],
           case["excerpt"], case.get("known_signals", "")]
    try:
        proc = subprocess.run(cmd, timeout=timeout, capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    if proc.returncode != 0:
        return None, f"exit:{proc.returncode} {proc.stderr.strip()[:200]}"
    try:
        return json.loads(proc.stdout), "ok"
    except json.JSONDecodeError:
        return None, f"unparseable: {proc.stdout.strip()[:200]}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--case", help="只跑這一筆 fixture id")
    ap.add_argument("--class", dest="klass", choices=sorted(PASS_BY_CLASS),
                    help="只跑這個類別")
    ap.add_argument("--runs", type=int, default=3, help="每筆跑幾次（預設 3）")
    ap.add_argument("--timeout", type=int, default=180, help="每一跑的秒數上限")
    ap.add_argument("--out", type=Path, default=HERE / "validator-eval-results.json")
    args = ap.parse_args()

    if not VALIDATOR.is_file():
        print(f"找不到 validator：{VALIDATOR}", file=sys.stderr)
        return 1

    cases = json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
    if args.klass:
        cases = [c for c in cases if c["class"] == args.klass]
    if not cases:
        print("沒有符合的 fixture", file=sys.stderr)
        return 1

    started = time.time()
    results = []
    for case in cases:
        runs = []
        for i in range(args.runs):
            verdict, status = run_once(case, args.timeout)
            ok, note = grade(case, verdict)
            runs.append({
                "run": i + 1, "status": status, "pass": ok, "note": note,
                "verdict": verdict,
            })
            mark = "✅" if ok else "❌"
            print(f"  {mark} {case['id']} run {i + 1}/{args.runs}: {note}", flush=True)
        passed = sum(r["pass"] for r in runs)
        risk_seen = sorted({(r["verdict"] or {}).get("risk_class") for r in runs} - {None})
        risk_ok = all(r in case["expect_risk_class"] for r in risk_seen) if risk_seen else False
        results.append({
            "id": case["id"], "class": case["class"], "expect": case["expect"],
            "passed": passed, "runs": args.runs,
            "risk_class_seen": risk_seen,
            "risk_class_expected": case["expect_risk_class"],
            "risk_class_matches": risk_ok,
            "detail": runs,
        })
        print(f"  → {case['id']}: {passed}/{args.runs}"
              f"  risk_class={risk_seen or '—'}{'' if risk_ok else ' (advisory mismatch)'}\n",
              flush=True)

    by_class: dict[str, list[dict]] = {}
    for r in results:
        by_class.setdefault(r["class"], []).append(r)

    print("=" * 62)
    all_green = True
    for klass in sorted(by_class):
        rows = by_class[klass]
        full = sum(r["passed"] == r["runs"] for r in rows)
        all_green &= full == len(rows)
        print(f"  {klass:<7} {full}/{len(rows)} 筆三次全對"
              f"   （須 {PASS_BY_CLASS[klass]}）")
    advisory = [r["id"] for r in results if not r["risk_class_matches"]]
    print(f"  risk_class 不一致（僅記錄）：{advisory or '無'}")
    print(f"  總計 {sum(r['passed'] for r in results)}/{sum(r['runs'] for r in results)} 跑"
          f"，耗時 {time.time() - started:.0f}s")
    print("=" * 62)

    args.out.write_text(
        json.dumps({
            "model": os.environ.get("IMPROVE_VALIDATOR_MODEL",
                                    "claude-haiku-4-5-20251001"),
            "runs_per_case": args.runs,
            "results": results,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"完整結果：{args.out}")
    return 0 if all_green else 1


if __name__ == "__main__":
    raise SystemExit(main())
