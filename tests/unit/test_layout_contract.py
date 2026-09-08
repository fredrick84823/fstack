"""`layout_contract.check_layout` 的測試 —— 一條斷言對一種版型退化。

每條測試的命名就是「這條刪掉會溜過去的退化」。合格樣本 `GOOD` 只有一份，
每個案例從它身上**改一個地方**，所以判紅的原因不會互相汙染。
"""

from __future__ import annotations

import pytest

from layout_contract import STATUS_VALUES, check_layout


def _qid(value: str) -> str:
    """繁中字串當 parametrize id 會變 unicode escape，改用 ASCII 序號。"""
    return "".join(c if c.isascii() and (c.isalnum() or c in "-_") else "." for c in value)


GOOD = """# **會議記錄：測試**

## 核心要點

* **甲事已成 [已確認]**：純文字狀態，不套 inline code。

## 討論過程

### 議題一：甲

**TL;DR** — 一句話。

#### 議題因果鏈 · 承 8/20 → 8/24

| 時間 | 事件 |
| :---- | :---- |
| 8/20 | 起因 |

#### 討論

* 甲說了話。

#### 決策理由

* 因為條款這樣寫。

#### 狀態

* `執行中` 甲事進行中
* `待啟動` 乙事待啟動

#### 風險

* 可能拖到交期

### 議題二：乙

**TL;DR** — 另一句話。

#### 討論

* 乙說了話。

#### 狀態

* `已確認` 乙事定案

## 行動項目

| 負責人 | 待辦 |
| :---- | :---- |
| 甲 | 做事 |
"""


def test_good_sample_passes():
    """基準線。這條紅了代表檢查器本身壞掉，下面所有紅燈都不可信。"""
    r = check_layout(GOOD)
    assert r["ok"], r["violations"]
    assert r["counts"] == {"issues": 2, "h4": 7, "tldr": 2, "inline_status": 3, "tables": 2}


def _fails(md: str, needle: str):
    r = check_layout(md)
    assert not r["ok"], "應該判紅卻判綠"
    assert any(needle in v for v in r["violations"]), r["violations"]
    return r


def test_no_issue_heading_is_red():
    """防：整份退回舊版型（`### 1. 主題` 或只有 H2），議題不再分層。"""
    _fails(GOOD.replace("### 議題", "### "), "沒有任何 `### 議題`")


def test_missing_tldr_is_red():
    """防：TL;DR 消失，議題又變成一大段沒有頭條的敘述。"""
    _fails(GOOD.replace("**TL;DR** — 一句話。\n\n", ""), "TL;DR 未緊接 H3")


def test_tldr_pushed_below_討論_is_red():
    """防：TL;DR 還在，但被塞到討論後面 —— 三分鐘讀不到結論。"""
    md = GOOD.replace("**TL;DR** — 一句話。\n\n#### 議題因果鏈", "#### 議題因果鏈")
    md = md.replace("* 甲說了話。", "* 甲說了話。\n\n**TL;DR** — 一句話。")
    _fails(md, "TL;DR 未緊接 H3")


@pytest.mark.parametrize("layer", ["討論", "狀態"], ids=_qid)
def test_missing_required_layer_is_red(layer):
    """防：必出現層被省略 —— 尤其是狀態，少了它就沒有機械可判定的收斂點。"""
    md = GOOD.replace(f"#### {layer}\n", "#### 補充\n")
    _fails(md, f"缺 `#### {layer}`")


def test_invented_layer_name_is_red():
    """防：模型自創「結論」「補充」等層，版型逐次漂移直到沒人認得。"""
    _fails(GOOD.replace("#### 決策理由", "#### 結論與補充"), "自創層名")


def test_layer_order_swapped_is_red():
    """防：決策理由／狀態／風險被重排，讀者每個議題都要重新找狀態在哪。"""
    md = GOOD.replace(
        "#### 狀態\n\n* `執行中` 甲事進行中\n* `待啟動` 乙事待啟動\n\n#### 風險\n\n* 可能拖到交期",
        "#### 風險\n\n* 可能拖到交期\n\n#### 狀態\n\n* `執行中` 甲事進行中\n* `待啟動` 乙事待啟動",
    )
    _fails(md, "層順序錯亂")


@pytest.mark.parametrize("filler", ["", "無", "N/A"], ids=lambda s: _qid(s) or "empty")
def test_empty_or_filler_layer_is_red(filler):
    """防：選填層沒內容還硬輸出，用「無」湊層 —— 分層變裝飾，不再帶資訊。"""
    _fails(GOOD.replace("* 可能拖到交期", filler), "空層或填充層")


def test_status_bullet_without_inline_code_is_red():
    """防：狀態退回 `[已確認]` 方括號或純文字 —— 這張票要改的就是這個。"""
    _fails(GOOD.replace("* `執行中` 甲事進行中", "* [執行中] 甲事進行中"), "未用 inline code")


def test_status_value_outside_domain_is_red():
    """防：狀態值域擴散（`腦力激盪`、`已完成`…），下游沒辦法照固定值分流。"""
    _fails(GOOD.replace("`執行中` 甲事", "`腦力激盪` 甲事"), "不在值域內")


def test_inline_code_leaking_into_核心要點_is_red():
    """防：inline code 標記外溢到核心要點／行動項目 —— 契約明說那兩區維持純文字。"""
    md = GOOD.replace(
        "* **甲事已成 [已確認]**：純文字狀態，不套 inline code。",
        "* `已確認` 甲事已成",
    )
    _fails(md, "外溢到議題區塊之外")


@pytest.mark.parametrize("layer", ["狀態", "風險"], ids=_qid)
def test_table_under_狀態_or_風險_is_red(layer):
    """防：內容表格漂到狀態／風險底下 —— 契約限定表格只在 TL;DR 之後、狀態之前。"""
    md = GOOD.replace(f"#### {layer}\n\n", f"#### {layer}\n\n| a | b |\n| :-- | :-- |\n| 1 | 2 |\n\n")
    _fails(md, "底下出現表格")


def test_table_between_tldr_and_狀態_is_green():
    """R8 的反向案例：契約**保留**內容表格的用法，檢查器不得把它一律判紅。"""
    assert check_layout(GOOD)["ok"]
    assert check_layout(GOOD)["counts"]["tables"] == 2


def test_optional_layers_may_be_absent():
    """反向案例：選填層缺席是合格的。少了這條，檢查器會退化成「每議題五層」。"""
    minimal = "## 討論過程\n\n### 議題一：甲\n\n**TL;DR** — 一句話。\n\n#### 討論\n\n* 話。\n\n#### 狀態\n\n* `已確認` 定案\n"
    r = check_layout(minimal)
    assert r["ok"], r["violations"]


def test_status_values_are_exactly_five():
    """防：值域被悄悄加值。值域是契約的一部分，改它要改這條。"""
    assert STATUS_VALUES == ("已確認", "執行中", "待驗證", "待確認", "待啟動")


@pytest.mark.xfail(
    strict=True,
    reason="契約寫死「議題因果鏈 在 討論 之前，順序不可調換」，但 8/31 目標樣本的議題六、"
    "9/07 的議題六與議題十都把因果鏈排在討論之後。契約與實際輸出對不上，"
    "由棒③ 裁定是改 prompt 還是改契約；在那之前 check_layout 只把它記進 advisories。",
)
def test_因果鏈_must_precede_討論():
    md = GOOD.replace(
        "#### 議題因果鏈 · 承 8/20 → 8/24\n\n| 時間 | 事件 |\n| :---- | :---- |\n| 8/20 | 起因 |\n\n",
        "",
    ).replace(
        "#### 決策理由",
        "#### 議題因果鏈\n\n* 起因 → 結果\n\n#### 決策理由",
    )
    assert not check_layout(md)["ok"], "因果鏈排在討論之後應判紅"
