"""棒② 從公開介面獨立推導的 harness 契約測試。

每一條釘住的都是一種「helper 看起來成功、其實什麼都沒測到」的路徑。
"""
import pytest
from unittest.mock import MagicMock

from tests.unit import conftest
from tests.unit.conftest import _qid, load_script, sent_body, sent_kwargs

# 實際會餵進 mutation 測試的繁中語料，_qid 至少要在它上面是單射的
CORPUS = ["會議記錄_20260309.m4a", "會議記錄_20260316.m4a", "週三_PM_會議", "週四_RD_會議"]


def test_an_unexercised_leaf_raises_even_when_the_outer_layer_was_called():
    """外層被呼叫過、葉節點沒有，仍必須 raise。

    回空 dict 會讓下游所有 `not in` / 長度斷言 vacuously true。
    """
    service = MagicMock()
    service.documents()

    with pytest.raises(AssertionError, match="no call recorded"):
        sent_kwargs(service, "documents", "batchUpdate")


def test_positional_only_call_cannot_pass_as_a_body_assertion():
    """body 用位置參數送出時，sent_body 必須 raise 而不是回 MagicMock。

    產品碼把 `body=` 改成位置參數是真實會發生的回歸；若這裡回 mock，
    所有 body 斷言會全部假通過。
    """
    service = MagicMock()
    service.documents().batchUpdate({"requests": []})

    assert sent_kwargs(service, "documents", "batchUpdate") == {}
    with pytest.raises(AssertionError, match="body"):
        sent_body(service, "documents", "batchUpdate")


def test_an_empty_body_is_not_the_same_as_no_body():
    """raise 的判準是 `body=` 在不在，不是它真不真。

    用真假值判斷會把「送了空 body」誤報成「沒送 body」，
    於是「產品碼算出空 requests」這個 bug 被當成 helper 的問題吃掉。
    """
    service = MagicMock()
    service.documents().batchUpdate(body={})

    assert sent_body(service, "documents", "batchUpdate") == {}


def test_reads_the_last_call_of_that_leaf_not_a_later_sibling():
    """同一層之後呼叫了別的 endpoint，不能污染這個 endpoint 的斷言。

    從父節點的 mock_calls 尾端取值會回到 get() 的 kwargs，
    於是「batchUpdate 根本沒送對東西」照樣綠。
    """
    service = MagicMock()
    service.documents().batchUpdate(body={"requests": ["first"]})
    service.documents().batchUpdate(body={"requests": ["last"]})
    service.documents().get(documentId="other")

    assert sent_body(service, "documents", "batchUpdate") == {"requests": ["last"]}


def test_qid_keeps_the_real_corpus_distinguishable():
    """繁中語料經 _qid 之後仍互不相同，否則 mutmut 會選錯測試。"""
    ids = [_qid(v) for v in CORPUS]

    assert len(set(ids)) == len(CORPUS)
    assert all(i.isascii() and "\\" not in i for i in ids)


def test_load_script_propagates_the_error_from_a_module_that_fails_to_import(
    tmp_path, monkeypatch
):
    """import 期間爆掉的模組必須每次都 raise，不能第二次交出半個模組。

    交出半個模組會讓下游 `getattr` 拿到空殼，整套純函式測試無聲全綠。
    """
    monkeypatch.setattr(conftest, "ROOT", tmp_path)
    monkeypatch.setattr(conftest, "SCRIPTS", tmp_path)
    (tmp_path / "zz_import_failure_probe.py").write_text("raise RuntimeError('boom')\n")

    for _ in range(2):
        with pytest.raises(RuntimeError, match="boom"):
            load_script("zz_import_failure_probe")
