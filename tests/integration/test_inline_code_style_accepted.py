"""驗收條件「Google Docs 真的接受 inline code 的那三個 textStyle 屬性」。

`INLINE_CODE_STYLE` 是拿三個泛用屬性模擬「Docs 沒有的 code 樣式」，所以它會不會被
接受是**外部服務的事實**，不是這個 repo 的決定：Docs 對 `fields` 沒點名的屬性靜靜
忽略，對形狀不對的 colour 直接 400。兩種都只有真的送出去才看得到，故歸 integration。

unit 版在 `tests/unit/test_inline_style_requests.py::
test_code_style_request_declares_all_three_properties_in_fields` —— 那支驗「送出去的
request 帶對的 fields」，這支驗「Docs 收下之後真的套上了」。少了 unit 版，這條規則
在沒憑證的機器上等於沒有；少了這支，`fields` 可以整串寫錯而測試全綠。

不碰 Shared Drive：文件建在個人雲端硬碟根目錄，跑完 `files().delete()` 刪掉。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/comms/generate-meeting-notes/scripts"
sys.path.insert(0, str(SCRIPTS))

# 憑證檔的兩個來源見 references/setup.md。檔案不在就 skip —— 直接呼叫
# `get_google_credentials()` 探測會在沒有 token 的機器上開瀏覽器要授權，
# 那是把「跑測試」變成「要人來按同意」。
TOKEN = Path.home() / ".config/generate-meeting-notes/google_token.json"
ADC = Path.home() / ".config/gcloud/application_default_credentials.json"

pytestmark = pytest.mark.skipif(
    not (TOKEN.exists() or ADC.exists()), reason=f"沒有本機憑證：{TOKEN} 或 {ADC}"
)

CODE_TEXT = "cloud run deploy"


def survived(sent, got) -> bool:
    """送出去的每個葉節點都還在回讀的樣式裡嗎？

    不能直接比對整個屬性相等，Docs 讀回來的值跟送出去的不會逐字一樣，兩處實測：
      - 沒送的欄位會補上預設值（`weightedFontFamily` 多一個 `weight: 400`）
      - rgbColor 會量化成 8 bit（0.95 存回來是 242/255 = 0.9490196）
    兩種都是 Docs 的行為，不是這個 skill 的 bug；斷整體相等只會讓這支變成
    「Google 有沒有改預設值」的探針。
    """
    for key, want in sent.items():
        have = got.get(key) if isinstance(got, dict) else None
        if isinstance(want, dict):
            if not survived(want, have):
                return False
        elif isinstance(want, float):
            if have is None or abs(have - want) > 1 / 255:
                return False
        elif have != want:
            return False
    return True


@pytest.fixture
def services():
    from googleapiclient.discovery import build

    from extract_audio_sources import get_google_credentials

    creds = get_google_credentials()
    return build("docs", "v1", credentials=creds), build("drive", "v3", credentials=creds)


def test_docs_applies_all_three_inline_code_properties(services):
    """把真的 request 送出去，再讀回來比對三個屬性。

    擋的是「`fields` 的字串拼錯」與「colour 的巢狀形狀寫錯」這兩種在本機
    完全看不出來的壞法：前者 Docs 回 200 但什麼都沒套上，後者 400。
    """
    from extract_audio_sources import INLINE_CODE_STYLE

    docs, drive = services
    doc_id = drive.files().create(
        body={"name": "gmn-inline-code-style-probe", "mimeType": "application/vnd.google-apps.document"},
        fields="id",
    ).execute()["id"]

    try:
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {"insertText": {"location": {"index": 1}, "text": CODE_TEXT}},
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": 1, "endIndex": 1 + len(CODE_TEXT)},
                            "textStyle": INLINE_CODE_STYLE,
                            "fields": ",".join(INLINE_CODE_STYLE),
                        }
                    },
                ]
            },
        ).execute()

        doc = docs.documents().get(documentId=doc_id).execute()
        runs = [
            el["textRun"]
            for block in doc["body"]["content"]
            if "paragraph" in block
            for el in block["paragraph"]["elements"]
            if "textRun" in el and el["textRun"]["content"].strip()
        ]
        (run,) = runs

        assert run["content"].strip() == CODE_TEXT
        for prop, expected in INLINE_CODE_STYLE.items():
            assert survived(expected, run["textStyle"].get(prop)), (prop, run["textStyle"])
    finally:
        drive.files().delete(fileId=doc_id).execute()
