"""純函式的最小真實測試 —— 讓 mutation 入口有東西可量。

不是回歸測試套件；inline 解析的回歸屬於 #9。
"""
import pytest

from tests.unit.conftest import _qid, load_script

mod = load_script("extract_audio_sources")

DATED = [
    ("會議記錄_20260309.m4a", "20260309"),
    ("週三_PM_會議_20260316_第2段.m4a", "20260316"),
    ("data_meeting_20260309.m4a", "20260309"),
]

HTML = [
    ("<u>季度回顧</u>", "**季度回顧**"),
    ("<u>季度回顧</u>\n<b>粗體</b>說明", "**季度回顧**\n粗體說明"),
    ("前綴 <u>不獨行</u>", "前綴 不獨行"),
    ("純文字沒有標籤", "純文字沒有標籤"),
]


@pytest.mark.parametrize("filename,expected", DATED, ids=[_qid(f) for f, _ in DATED])
def test_extract_date_picks_the_eight_digit_run(filename, expected):
    assert mod.extract_date(filename) == expected


def test_extract_date_refuses_a_filename_without_a_date():
    # 訊息一起釘住：ValueError(None) 對操作者等於沒說明拒絕的理由
    with pytest.raises(ValueError, match="無法從檔名提取日期"):
        mod.extract_date("會議記錄.m4a")


@pytest.mark.parametrize("raw,expected", HTML, ids=[_qid(r) for r, _ in HTML])
def test_preprocess_content_promotes_standalone_u_and_strips_the_rest(raw, expected):
    assert mod.preprocess_content(raw) == expected
