"""樣式範圍的斷言打在**送給 Docs 的 request** 上，不是解析函式的中間產物。

`_parse_inline` 回的 offset 是 Python 字元位置，Docs 的 `range` 要的是 UTF-16 code
unit、1-based、而且要加上前面所有行累積的長度。這段換算全部發生在解析函式之外，
所以只斷 `_parse_inline` 的中間產物等於沒驗到它 —— 換算整段刪掉那些測試照樣綠。

驗法是把 request 當外部觀察：拿 `insertText` 真的送出去的那串文字，用 `utf-16-le`
編碼，再用樣式 request 的 `startIndex` / `endIndex` 去切那串 bytes，解回來必須逐字
等於 Markdown 裡那段 code / bold 的內容。這是 Docs 收到 request 之後會做的同一件事。

語料刻意放 emoji（UTF-16 上是 2 個 code unit，Python 上是 1 個字元）：
`🎉` 在**前一行**、`🚀` 在**同一行的樣式範圍之前**，兩種累積偏移都涵蓋。沒有 emoji
的語料上，「用 Python 字元算」與「用 UTF-16 code unit 算」的答案一模一樣，整份測試
會變成裝飾品 —— 所以 `test_corpus_can_tell_the_two_unit_systems_apart` 直接把
「這份語料分得出兩種算法」釘成一條斷言。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.unit.conftest import _qid, load_script, sent_body, sent_kwargs

mod = load_script("extract_audio_sources")

# `create_gdoc_in_shared_drive` 內部 `from local_archive import note_title`，
# 而 scripts/ 目錄名有連字號、不是可 import 的套件路徑。
SCRIPTS = Path(__file__).resolve().parents[2] / "skills/comms/generate-meeting-notes/scripts"
sys.path.insert(0, str(SCRIPTS))

CONTENT = "\n".join([
    "# 會議記錄 🎉",
    "",
    "- 狀態：`進行中` 已確認",
    "",
    "🚀 前面有 emoji 的 **粗體**",
    "",
    "- `deploy.sh` 與 **上線時間**",
    "",
])
MEETING = {"series_name": "PM會議", "folder_id": "series-folder-id"}

CODE_SPANS = ["進行中", "deploy.sh"]
BOLD_SPANS = ["粗體", "上線時間"]


@pytest.fixture
def docs_service(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """跑一次 `create_gdoc_in_shared_drive`，回傳假的 Docs client。

    **不打網路**：憑證與 `build` 都換成替身，Drive 那兩個呼叫回罐頭 id。
    被驗的那條路徑（Markdown → requests）全部是真的。
    """
    import googleapiclient.discovery as discovery

    docs, drive = MagicMock(name="docs"), MagicMock(name="drive")
    drive.files.return_value.list.return_value.execute.return_value = {"files": []}
    drive.files.return_value.create.return_value.execute.return_value = {"id": "fake-doc-id"}
    docs.documents.return_value.batchUpdate.return_value.execute.return_value = {}
    docs.documents.return_value.get.return_value.execute.return_value = {
        "body": {"content": [{"endIndex": 1}]}
    }

    monkeypatch.setattr(mod, "get_google_credentials", lambda: object())
    monkeypatch.setattr(
        discovery, "build", lambda service, version, **kw: {"docs": docs, "drive": drive}[service]
    )

    mod.create_gdoc_in_shared_drive("20260914", CONTENT, MEETING)
    return docs


@pytest.fixture
def inserted(docs_service: MagicMock) -> tuple[str, int]:
    """送出去的 `insertText`：(文字, location.index)。後面每條斷言的基準。"""
    requests = sent_body(docs_service, "documents", "batchUpdate")["requests"]
    inserts = [r["insertText"] for r in requests if "insertText" in r]
    assert len(inserts) == 1, inserts
    return inserts[0]["text"], inserts[0]["location"]["index"]


def text_styles(docs_service: MagicMock) -> list[dict]:
    return [
        r["updateTextStyle"]
        for r in sent_body(docs_service, "documents", "batchUpdate")["requests"]
        if "updateTextStyle" in r
    ]


def sliced(text: str, index: int, rng: dict) -> str:
    """Docs 收到 request 之後做的那件事：在 UTF-16 code unit 上切。

    切 bytes 而不是切 Python 字串 —— 切 Python 字串等於把「單位是什麼」這個
    唯一要驗的東西先假設掉了。
    """
    units = text.encode("utf-16-le")
    start = (rng["startIndex"] - index) * 2
    end = (rng["endIndex"] - index) * 2
    return units[start:end].decode("utf-16-le")


def styled(docs_service: MagicMock, text: str, index: int, style: dict) -> list[str]:
    return [
        sliced(text, index, r["range"]) for r in text_styles(docs_service) if r["textStyle"] == style
    ]


# --------------------------------------------------------------------------
# 驗收 ⑤⑥ 範圍切回來必須等於原本那段 code / bold
# --------------------------------------------------------------------------


def test_inserted_text_is_the_converters_plain_text_at_index_one(inserted):
    """後面每條斷言都建立在「送出去的文字就是轉出來的 plain_text」上。

    這條先釘住它：index 0 是文件開頭的 section break、寫不進去，Docs 的規格是從 1 開始。
    起點錯了下面所有 range 會整體偏 1，而且偏得很一致 —— 看起來像「樣式差一個字」。
    """
    text, index = inserted
    plain_text, _, _ = mod._markdown_to_gdocs(CONTENT)

    assert text == plain_text
    assert index == 1


@pytest.mark.parametrize("code", CODE_SPANS, ids=[_qid(c) for c in CODE_SPANS])
def test_code_range_slices_back_to_the_code_text(inserted, docs_service, code):
    """emoji 那題的答案：用 request 的範圍去切 UTF-16 編碼後的文字，要逐字等於原文。

    擋的是「range 用 Python 字元位置算」：前面每多一個 emoji（或任何 BMP 外的字元）
    就往左偏 1 個 code unit，灰底整塊錯位，而純中英文的記錄完全正常。
    """
    text, index = inserted

    assert code in styled(docs_service, text, index, mod.INLINE_CODE_STYLE)


def test_all_code_spans_and_only_them_get_the_code_style(inserted, docs_service):
    """逐一比對還不夠：少送一條、或把整段話都標成 code，上面那條也可能是綠的。"""
    text, index = inserted

    assert styled(docs_service, text, index, mod.INLINE_CODE_STYLE) == CODE_SPANS


@pytest.mark.parametrize("bold", BOLD_SPANS, ids=[_qid(b) for b in BOLD_SPANS])
def test_bold_range_slices_back_to_the_bold_text(inserted, docs_service, bold):
    """同一件事對 bold 再驗一次。

    只挑「切回來剛好等於那段字」的 request 比對，不比對 bold request 的**總數** ——
    標題本身也是粗體，把它算進來會讓這條測試綁死「H1 要不要加粗」這個無關的決定。
    """
    text, index = inserted

    assert bold in styled(docs_service, text, index, {"bold": True})


@pytest.mark.parametrize(
    "span,astral_before",
    [("進行中", 1), ("deploy.sh", 2), ("粗體", 2), ("上線時間", 2)],
    ids=[_qid(s) for s in ("進行中", "deploy.sh", "粗體", "上線時間")],
)
def test_corpus_can_tell_the_two_unit_systems_apart(inserted, span, astral_before):
    """語料的鑑別力本身 —— 沒有這條，上面那些測試可能只是因為語料裡沒有 emoji 而綠。

    `astral_before` 是該段之前的 emoji 顆數，也就是兩種算法的差距（emoji 在 UTF-16 是
    2 個 code unit、在 Python 是 1 個字元）。差距歸零代表有人把 emoji 從語料裡刪掉了，
    這時整份檔案就再也擋不住「用 Python 字元算」那種寫法。
    """
    text, _ = inserted
    prefix = text[: text.index(span)]

    assert mod._u16len(prefix) - len(prefix) == astral_before


def test_no_style_request_points_outside_the_inserted_text(inserted, docs_service):
    """越界的 range 在本機測試裡是靜靜地切出空字串，到 Docs 才會是 400。

    真正的邊界是最後一段 —— 結尾那個 `**上線時間**` 貼著文字末端，
    endIndex 多算一格不會踩到任何別的字，只有跟總長度比才看得出來。
    """
    text, index = inserted
    end = index + mod._u16len(text)
    requests = sent_body(docs_service, "documents", "batchUpdate")["requests"]
    ranges = [r[k]["range"] for r in requests for k in r if "range" in r[k]]

    assert ranges, "一條樣式 request 都沒送出去"
    for rng in ranges:
        assert index <= rng["startIndex"] <= rng["endIndex"] <= end, rng


# --------------------------------------------------------------------------
# 驗收 ⑧ 的 unit 版：三個屬性都要出現在 fields 裡
# --------------------------------------------------------------------------


def test_code_style_request_declares_all_three_properties_in_fields(inserted, docs_service):
    """Docs 只會套用 `fields` 點名的屬性；textStyle 裡多帶的會被默默忽略。

    漏掉一個的症狀是「灰底有了但字不是紅的」這種沒有人會回報的半殘樣式，
    而 request 送得出去、回應也是 200。
    """
    text, index = inserted
    requests = sent_body(docs_service, "documents", "batchUpdate")["requests"]
    code_requests = [
        r["updateTextStyle"]
        for r in requests
        if "updateTextStyle" in r and sliced(text, index, r["updateTextStyle"]["range"]) in CODE_SPANS
    ]

    assert len(code_requests) == len(CODE_SPANS)
    for req in code_requests:
        assert req["textStyle"] == mod.INLINE_CODE_STYLE
        assert set(req["fields"].split(",")) == set(mod.INLINE_CODE_STYLE)


def test_inline_code_style_simulates_code_with_three_properties():
    """Docs 沒有原生 code 樣式，這三個屬性就是模擬它的全部。

    少一個就不像 code；這條釘住「不准為了省事只留等寬字體」。
    """
    assert set(mod.INLINE_CODE_STYLE) == {
        "weightedFontFamily",
        "backgroundColor",
        "foregroundColor",
    }


def test_batch_update_targets_the_document_it_just_created(docs_service):
    """順手釘住 request 的收件人 —— documentId 拿錯的話樣式會套到別份文件上。"""
    assert sent_kwargs(docs_service, "documents", "batchUpdate")["documentId"] == "fake-doc-id"
