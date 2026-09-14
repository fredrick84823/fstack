"""`parity.drift_warning` —— 差異清單 → 要印出來的那段警告。

純函式，不碰檔案系統，所以整支是直接呼叫。載入一律走 `conftest.load_script`：
模組名要是**路徑推出來的那個**，mutmut 的 mutant key 才對得上 trampoline 記的
`__module__`；用 `sys.path` + `import parity` 載到的模組叫 `parity`，對不上 key，
那幾顆 mutant 會靜靜地記成「沒有測試覆蓋」。

**為什麼不寫一條 golden 斷言**：整串比對只能回答「有沒有壞」，不能回答「壞在哪」——
一顆把 `sorted` 拿掉的 mutant 與一顆把「掉齊」那行刪掉的 mutant 會讓同一條測試變紅，
讀的人還是得自己去 diff。下面一條測一件事：行的結構、項目數、排序、尾行，各自獨立。
"""

from __future__ import annotations

import pytest

from .conftest import _qid, load_script

parity = load_script("parity")

# 沒排序的輸入。排序後的順序跟輸入順序不同 —— 相同的話「有沒有排序」測不出來。
PATHS = ["scripts/parity.py", "SKILL.md", "README.md"]
SORTED = ["README.md", "SKILL.md", "scripts/parity.py"]


@pytest.fixture
def warning() -> str:
    return parity.drift_warning(PATHS)


def items(text: str) -> list[str]:
    """縮排那幾行（去掉縮排），結尾「掉齊」那行不算。"""
    return [
        line[3:]
        for line in text.split("\n")
        if line.startswith("   ") and not line.startswith("   掉齊")
    ]


def test_the_public_strings_are_what_the_interface_promises():
    """`DRIFT_HEADER` / `SYNC_SCRIPT` / `SKILL_REL` 是被斷言的介面。

    下面每條測試都拿 `DRIFT_HEADER` 當期望值，所以常數本身要有一條把值釘死的測試 ——
    少了這條，把 header 整個改掉（或改成空字串）不會有任何一條變紅。
    """
    assert parity.DRIFT_HEADER == "⚠️  安裝版與 fstack 已經漂移"
    assert str(parity.SYNC_SCRIPT) == "bin/sync-from-installed.sh"
    assert str(parity.SKILL_REL) == "skills/comms/generate-meeting-notes"


def test_no_difference_means_an_empty_string_not_none():
    """驗收條件 1 的純函式側：沒有差異就沒有話要講。

    回 `None` 也「不含警告字串」，但呼叫端一律 `print(..., end="")`，`None` 會印出
    `None` 三個字。空字串是介面明訂的回傳值。
    """
    assert parity.drift_warning([]) == ""


def test_the_warning_opens_with_a_blank_line():
    """警告接在發佈輸出後面，前面要空一行才看得出是另一段。

    刪掉這條 → 開頭的 `\\n` 掉了，警告黏在 Slack／歸檔那幾行的尾巴上。
    """
    assert parity.drift_warning(PATHS).split("\n")[0] == ""


def test_the_header_line_says_it_has_drifted(warning: str):
    """第二行是 `DRIFT_HEADER` 開頭 —— 那是使用者唯一會掃到的字串。"""
    assert warning.split("\n")[1].startswith(parity.DRIFT_HEADER)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_the_header_counts_the_items(n: int):
    """`（N 項）` 的 N 是項目數。

    刪掉這條 → N 寫成常數或差一，使用者以為只漂了一個檔案，實際上是整包。
    """
    assert f"（{n} 項）" in parity.drift_warning(PATHS[:n])


@pytest.mark.parametrize("path", PATHS, ids=[_qid(s) for s in PATHS])
def test_every_path_gets_its_own_line(warning: str, path: str):
    """每個路徑各佔一行，不是擠成一行的逗號清單。

    刪掉這條 → 分隔符改成空字串，三個路徑黏成一坨沒人讀得出來的字串；
    或某幾個路徑根本沒印出來（清單被切過）。
    """
    assert path in items(warning)


def test_the_paths_are_sorted(warning: str):
    """順序是排序過的，不是 `sync_diff` 回來的走訪順序。

    刪掉這條 → `sorted` 被拿掉，同一份漂移每次跑印出來的順序不一樣，
    使用者沒辦法用眼睛比對兩次輸出。
    """
    assert items(warning) == SORTED


def test_the_last_line_names_the_script_that_fixes_it(warning: str):
    """驗收條件 2 的後半：警告要講「怎麼掉齊」，不是只講「有漂移」。

    刪掉這條 → 尾行不見了，使用者看到警告但不知道下一步要跑什麼。
    """
    assert warning.endswith(f"   掉齊：{parity.SYNC_SCRIPT}\n")
