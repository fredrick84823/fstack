"""integration 那支的**斷言層**自己要有 unit 守著。

#14 的陷阱表指給本票的就是這條：

> 驗收腳本進不了 CI（要真憑證或 subagent），它自己的靜默失敗沒人守
> → 在 unit test 測**斷言層**，每壞一件事必須且**只有**對應那條變紅

`tests/integration/test_inline_code_style_accepted.py` 在 CI 與沒憑證的機器上整支
skip，所以它的 `survived()` 壞掉不會有任何顏色。而它正好是最容易靜默壞掉的那種
helper：遞迴比對 ＋ 浮點容差，寫成 `return True` 或把容差開到無限大之後，
那支 integration 在有憑證的機器上照樣全綠，只是什麼都沒驗。

這裡不打網路、不吃憑證 —— 只餵 dict 給 `survived()`，驗它該說 True 的說 True、
該說 False 的說 False。
"""

from __future__ import annotations

import pytest

from tests.integration.test_inline_code_style_accepted import survived

# 送出去的形狀（`INLINE_CODE_STYLE` 的一個屬性）與 Docs 讀回來的形狀。
SENT_COLOR = {"color": {"rgbColor": {"red": 0.95, "green": 0.95, "blue": 0.95}}}
SENT_FONT = {"fontFamily": "Roboto Mono"}


def test_docs_own_round_trip_noise_still_counts_as_survived():
    """Docs 回讀的值跟送出去的不逐字相同，那不是 bug —— 兩處實測過的雜訊都要放行。

    這條是 `survived()` 存在的唯一理由。它紅了代表有人把它收緊成整體相等，
    那支 integration 會變成「Google 有沒有改預設值」的探針，每次 Google 動一次
    就紅一次，而且紅的位置跟這個 skill 無關。
    """
    # ① 沒送的欄位被補上預設值
    assert survived(SENT_FONT, {"fontFamily": "Roboto Mono", "weight": 400})
    # ② rgbColor 量化成 8 bit：0.95 → 242/255
    assert survived(SENT_COLOR, {"color": {"rgbColor": {c: 242 / 255 for c in ("red", "green", "blue")}}})


def test_a_property_that_never_arrived_is_not_survived():
    """Docs 回 200 但沒套上任何東西（`fields` 拼錯就是這個症狀）。

    `survived()` 拿到 `None` 時必須說 False。這是它最重要的一條 ——
    說 True 的話「fields 整串寫錯」這件事就再也沒有人守。
    """
    assert not survived(SENT_FONT, None)
    assert not survived(SENT_COLOR, {"color": {}})


def test_a_wrong_value_is_not_survived():
    """值真的不一樣時要說 False，否則容差等於把整條斷言關掉。"""
    assert not survived(SENT_FONT, {"fontFamily": "Arial"})
    assert not survived({"bold": True}, {"bold": False})


@pytest.mark.parametrize("delta,expect", [(0.5 / 255, True), (4 / 255, False)])
def test_the_float_tolerance_is_one_8bit_step_not_unbounded(delta, expect):
    """容差只夠吸收 8 bit 量化（1/255），不能寬到「什麼顏色都算過」。

    容差開太大的症狀：深紅字換成淺灰字照樣綠。所以兩個方向都要釘 ——
    只驗「小誤差放行」的話，`return True` 也會過。
    """
    got = {"color": {"rgbColor": {"red": 0.95 + delta, "green": 0.95, "blue": 0.95}}}

    assert survived(SENT_COLOR, got) is expect
