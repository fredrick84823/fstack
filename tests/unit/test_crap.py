"""`bin/crap.py` 的公式。

CRAP 是這張票要留下的基線數字，而算錯的成本剛好是「基線看起來很漂亮」——
少了三次方，半覆蓋的函式從 22.5 掉到 60 或反過來，紅線位置整個位移；不跳過 class，
class 的 CC 是底下 method 的總和，會把同一段複雜度數兩次。兩種都不會有人看見紅燈。

黑箱跑：`crap.py` 是 `sys.argv` 直取的腳本，開子行程餵兩份最小 json 最省事。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.conftest import ROOT

CRAP = ROOT / "bin" / "crap.py"

FILE = "pkg/mod.py"


def _run(tmp_path: Path, blocks: list[dict], executed: list[int], missing: list[int]) -> str:
    cc = tmp_path / "cc.json"
    cov = tmp_path / "cov.json"
    cc.write_text(json.dumps({FILE: blocks}))
    cov.write_text(
        json.dumps({"files": {FILE: {"executed_lines": executed, "missing_lines": missing}}})
    )
    done = subprocess.run(
        [sys.executable, str(CRAP), str(cc), str(cov)],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


def _block(name: str, lineno: int, endline: int, complexity: int, type_: str = "function") -> dict:
    return {
        "name": name,
        "lineno": lineno,
        "endline": endline,
        "complexity": complexity,
        "type": type_,
    }


@pytest.mark.parametrize(
    "executed,missing,expected",
    [
        ([], [1, 2, 3, 4], "110.0"),  # cov 0%   → 10^2 * 1     + 10
        ([1, 2], [3, 4], "22.5"),  # cov 50%  → 10^2 * .125  + 10
        ([1, 2, 3, 4], [], "10.0"),  # cov 100% → 10^2 * 0     + 10
    ],
    ids=["cov-0", "cov-50", "cov-100"],
)
def test_uncovered_share_is_cubed(tmp_path: Path, executed, missing, expected):
    """(1-cov) 是三次方。線性的話 50% 覆蓋會算成 60，紅線位置整個位移。"""
    out = _run(tmp_path, [_block("only_one", 1, 4, 10)], executed, missing)

    (row,) = [line for line in out.splitlines() if "only_one" in line]
    assert row.split()[0] == expected


def test_a_function_with_no_measured_lines_counts_as_covered(tmp_path: Path):
    """coverage 沒量到的函式當作 100% —— 當 0% 會讓沒被 coverage 收錄的檔案衝上榜首。"""
    out = _run(tmp_path, [_block("f", 90, 95, 10)], [1], [2])

    assert "100.0%" in out


def test_class_blocks_are_left_out_of_the_ranking(tmp_path: Path):
    """class 的 CC 是底下 method 的總和；一起算會把同一段複雜度數兩次。"""
    blocks = [_block("C", 1, 8, 12, type_="class"), _block("C.m", 2, 4, 6)]

    out = _run(tmp_path, blocks, [], [1, 2, 3, 4, 5, 6, 7, 8])

    assert "C.m" in out
    assert "functions: 1" in out
    assert " C\n" not in out


def test_the_red_count_is_the_number_over_the_threshold(tmp_path: Path):
    """尾行的計數是這支腳本唯一的匯總輸出，錯了就沒有基線可比。"""
    blocks = [_block("bad", 1, 4, 10), _block("fine", 10, 12, 1)]

    out = _run(tmp_path, blocks, [10, 11, 12], [1, 2, 3, 4])

    assert "functions: 2, CRAP>30: 1" in out
    assert "<-- RED (>30)" in out
