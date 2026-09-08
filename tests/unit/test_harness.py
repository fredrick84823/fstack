"""harness 自己的契約（`conftest` 的 `sent_kwargs` / `sent_body` / `_qid` / `load_script`）。

之後每一支 unit test 都靠 harness 從假的 Google client 挖東西出來斷言。harness 在沒東西
可挖時若默默回一顆 MagicMock，那些斷言會全部 vacuously true —— 整套測試變成裝飾品，而且
看起來是綠的。所以「raise」是這裡釘住的契約，不是實作細節。

`_qid` 與 `load_script` 同理：前者壞掉會讓 mutmut 把選不到測試的 exit 4 記成 killed，
後者壞掉會讓每顆 mutant 都活下來 —— 兩種都不會有人看見紅燈。
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from . import conftest
from .conftest import _qid, load_script, sent_body, sent_kwargs

# --------------------------------------------------------------------------
# sent_kwargs / sent_body —— 打在 request 上，沒有 call 就 raise
# --------------------------------------------------------------------------


def test_sent_kwargs_returns_the_values_actually_sent():
    svc = MagicMock()
    svc.documents().get(documentId="doc_id", includeTabsContent=True)

    kwargs = sent_kwargs(svc, "documents", "get")

    assert kwargs == {"documentId": "doc_id", "includeTabsContent": True}
    # 順手釘住「happy path 也不能回 MagicMock」—— MagicMock 對上面那個 == 會是 False，
    # 但錯得像是「送出的值不對」。這一行讓失敗訊息直接指出真正的病。
    assert type(kwargs) is dict


def test_sent_body_returns_the_body():
    svc = MagicMock()
    svc.documents().batchUpdate(
        documentId="doc_id",
        body={"requests": [{"insertText": {"text": "會議記錄_資料內會"}}]},
    )

    assert sent_body(svc, "documents", "batchUpdate") == {
        "requests": [{"insertText": {"text": "會議記錄_資料內會"}}]
    }


def test_walks_a_chain_deeper_than_two_segments():
    svc = MagicMock()
    svc.files().permissions().create(fileId="f_id", body={"role": "reader"})

    assert sent_kwargs(svc, "files", "permissions", "create")["fileId"] == "f_id"
    assert sent_body(svc, "files", "permissions", "create") == {"role": "reader"}


def test_reads_the_last_call_not_the_first():
    svc = MagicMock()
    svc.documents().batchUpdate(documentId="first", body={"requests": [1]})
    svc.documents().batchUpdate(documentId="last", body={"requests": [2]})

    assert sent_kwargs(svc, "documents", "batchUpdate")["documentId"] == "last"
    assert sent_body(svc, "documents", "batchUpdate") == {"requests": [2]}


@pytest.mark.parametrize("helper", [sent_kwargs, sent_body], ids=["kwargs", "body"])
def test_raises_when_nothing_was_sent(helper):
    svc = MagicMock()

    with pytest.raises(AssertionError, match="no call recorded"):
        helper(svc, "documents", "batchUpdate")


@pytest.mark.parametrize("helper", [sent_kwargs, sent_body], ids=["kwargs", "body"])
def test_never_hands_back_a_magicmock(helper):
    """本檔存在的理由：回一顆 mock 會讓下游每條斷言都通過。"""
    svc = MagicMock()
    returned = []

    try:
        returned.append(helper(svc, "documents", "batchUpdate"))
    except AssertionError:
        pass

    assert not returned, f"expected a raise, got {returned[0]!r}"


def test_sent_body_raises_when_the_call_carried_no_body():
    svc = MagicMock()
    svc.documents().get(documentId="doc_id")

    with pytest.raises(AssertionError, match="body"):
        sent_body(svc, "documents", "get")


@pytest.mark.parametrize("helper", [sent_kwargs, sent_body], ids=["kwargs", "body"])
def test_raises_on_an_empty_path(helper):
    with pytest.raises(AssertionError):
        helper(MagicMock())


# --------------------------------------------------------------------------
# _qid —— 產出的 id 必須是 pytest 選得回來的
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["負責人：Zorblax", "a\tb", "`inline code`", "行1\n行2", "🎉 emoji"],
    ids=["cjk", "tab", "backtick", "newline", "emoji"],
)
def test_qid_is_ascii_and_backslash_free(value):
    """非 ASCII 與反斜線是 pytest 選不回來的兩種字元，兩種都要被換掉。"""
    qid = _qid(value)

    assert qid.isascii(), qid
    assert "\\" not in qid, qid


def test_qid_still_tells_two_values_apart():
    """全部壓成同一個 id 也會「沒有反斜線也沒有非 ASCII」—— 那樣 parametrize 會撞名。"""
    assert _qid("客戶甲") != _qid("客戶乙")


# --------------------------------------------------------------------------
# load_script —— 載到的必須是「跟本檔案同一棵樹」的那份
# --------------------------------------------------------------------------


def test_load_script_returns_the_module():
    module = load_script("extract_audio_sources")

    assert callable(module.extract_date)


def test_load_script_names_the_module_after_its_path():
    """`__name__` 必須等於 mutmut 從檔案路徑推出來的那個 key 前綴。

    取一個好看的名字（`gmn_extract_audio_sources`）會讓 mutmut 整輪停在
    「tests recorded trampoline hits but none match any mutant key」—— 實測過，
    而且那個訊息不會出現在測試裡，只會出現在 `make mutation` 的輸出。
    """
    module = load_script("extract_audio_sources")

    assert module.__name__ == (
        "skills.comms.generate-meeting-notes.scripts.extract_audio_sources"
    )


def test_load_script_raises_on_a_missing_script():
    with pytest.raises((AssertionError, FileNotFoundError, ImportError)):
        load_script("no_such_script")


def test_load_script_follows_the_conftest_into_a_copied_tree(tmp_path):
    """把 harness 複製到另一棵樹，載到的必須是**那棵樹**的腳本。

    斷「SCRIPTS 與本檔同根」不算數 —— 那在 repo 裡恆真，`ROOT` 改寫死一個絕對路徑
    也照樣綠。真正會壞的場景是 mutmut：它把整棵樹複製進 `mutants/` 再跑，寫死路徑那一輪載到的是 repo 原檔，
    每顆 mutant 都活下來，症狀長得像「測試沒鑑別力」而不是「載錯檔」。所以這裡
    真的複製一棵樹出來，用它的 conftest 載，斷在只有複製品才有的 MARKER 上。
    """
    scripts = tmp_path / "skills/comms/generate-meeting-notes/scripts"
    scripts.mkdir(parents=True)
    (scripts / "extract_audio_sources.py").write_text("MARKER = 'copy'\n")
    unit = tmp_path / "tests/unit"
    unit.mkdir(parents=True)
    shutil.copy2(conftest.__file__, unit / "conftest.py")

    spec = importlib.util.spec_from_file_location("copied_conftest", unit / "conftest.py")
    copied = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copied)

    module = copied.load_script("extract_audio_sources")

    assert module.MARKER == "copy"
    assert Path(module.__file__).is_relative_to(tmp_path)
