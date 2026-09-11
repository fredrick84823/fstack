"""把檢查器對著 73 份真實正式稿跑一次 —— 證明它有鑑別力。

一個永遠判綠的檢查器跟沒有檢查器一樣。這個檔案的全部意義是證明：
**8/31 目標樣本判綠，其餘 72 份（四種會議、2 月到 9 月）全部判紅。**

**已知的資料限制**：紅側四種會議都證明過（PM／RD／Data 內會／Data 教授各 ≥3 份），
綠側只有 Data 內會 —— 全機只有 8/31 與 9/07 兩份新版型真實產出。PM／RD／教授三種
會議在新 prompt 下的真實產出還不存在，等它們出現才補得上。低議題密度那一側由
`test_layout_contract.py::test_good_sample_passes` 的議題二在密封樣本上守著。

語料在 `~/thoughts`，是真實資料、不進版控，所以整檔在沒有它的機器上 skip。
版型規則本身的測試在 `test_layout_contract.py`，那份是密封的、CI 一定跑得動。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.layout_contract import check_layout

CORPUS = Path.home() / "thoughts/global/shared/meeting-notes"
SERIES = {
    "週三_PM_會議": "pm",
    "週四_RD_會議": "rd",
    "週一週四_Data_內會": "data",
    "週三_Data_教授會議": "prof",
}
TARGET = CORPUS / "週一週四_Data_內會/20260831/會議記錄_Data內會_20260831.md"
NEW_FORMAT = {"20260831", "20260907"}

pytestmark = pytest.mark.skipif(not CORPUS.is_dir(), reason=f"無語料：{CORPUS}")


def _notes(series: str) -> list[Path]:
    return sorted((CORPUS / series).rglob("會議記錄_*.md"))


def _old(series: str) -> list[Path]:
    return [p for p in _notes(series) if not any(d in str(p) for d in NEW_FORMAT)]


def test_target_sample_is_green():
    """8/31 是新版型的權威。它判紅代表契約或檢查器有一邊寫錯了。"""
    r = check_layout(TARGET.read_text(encoding="utf-8"))
    assert r["ok"], r["violations"]


def test_target_sample_counts_match_ticket():
    """票上點名的三個數字。防：目標樣本被改動而沒人發現，後續比對就失去基準。"""
    c = check_layout(TARGET.read_text(encoding="utf-8"))["counts"]
    assert (c["issues"], c["h4"], c["inline_status"], c["tables"]) == (7, 25, 11, 4)


@pytest.mark.parametrize("series", SERIES, ids=SERIES.get)
def test_every_series_has_old_format_samples(series):
    """四種會議各抽驗一次的機械化版本：每個系列都得真的有樣本被跑到，
    否則下面那條 parametrize 可能整個系列空轉還是綠的。"""
    assert len(_old(series)) >= 3, series


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(p, id=f"{tag}-{p.parent.name}")
        for series, tag in SERIES.items()
        for p in _old(series)
    ],
)
def test_old_format_is_red(path: Path):
    """鑑別力的主體。舊版型沒有 TL;DR、沒有 H4 分層、狀態不是 inline code —— 一份都不准漏。"""
    r = check_layout(path.read_text(encoding="utf-8"))
    assert not r["ok"], f"{path} 判綠了，檢查器對舊版型沒有鑑別力"


def test_second_new_format_output_has_only_the_known_suffix_violation():
    """9/07 是新版型的第二份真實產出。棒③ 裁決後它剩下**恰好一條**不合：
    `#### 討論 —— 評測指標與更新機制` 給必出現層加了後綴（收緊 prompt，不放寬契約）。
    另外兩處 `腦力激盪` 已收進值域。

    斷言「恰好這一條」而不是 xfail：xfail 只記得住「有東西不合」，
    多冒出一條新的不合它照樣綠。這條會紅。
    """
    path = CORPUS / "週一週四_Data_內會/20260907/會議記錄_Data內會_20260907.md"
    r = check_layout(path.read_text(encoding="utf-8"))
    # 只比對違規的「種類」，不比對議題標題 —— 標題含公司名與同事名，fstack 是 public repo；
    # 而且硬編標題會讓「該場記錄被編輯」變成版型測試紅，紅的原因與版型無關。
    (violation,) = r["violations"]
    assert "自創層名 `討論 —— 評測指標與更新機制`" in violation
