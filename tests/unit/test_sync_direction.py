"""方向判斷 —— `parity.sync_direction`（純函式）、`direction_against_installed`（碰檔案）
與 `--direction` CLI，外加 repo-first 這件事在 SKILL.md 與 Makefile 上的落點。

**為什麼方向要是純函式**：它是本票唯一會「拒絕同步」的判斷，猜錯的代價不對稱 ——
猜成 `安裝版較新` 而實際上 repo 較新，`rsync --delete` 會把已經合併進 repo 的改動刪掉；
反過來只是多跑一次掉齊。所以 mtime 平手時回 `repo 較新`，而平手正是最該被 mutant
問一次的邊界（`>` 與 `>=` 在其他每條測試裡都等價）。

**輸入是「差異」檔案，不是全部檔案。** sanitize 造成的差異已經被呼叫端消掉了，所以
「兩邊都沒改」與「兩邊都改成一樣」在這支看到的都是兩份空 dict —— 下面每條 case 的
dict 都只放真的有差異的路徑。

正反兩面要成對：只有「repo 較新」的 case 時，一個永遠回 `repo 較新` 的實作照樣全綠，
而那個實作會讓正向同步從此不可用。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import child_env, load_script
from .test_sync_diff import pair, write_tree  # noqa: F401  `pair` 是 fixture，靠名字解析
from .test_sync_from_installed import DEST_REL

parity = load_script("parity")

REPO = Path(__file__).resolve().parents[2]
PARITY_PY = Path(parity.__file__)
SKILL_MD = REPO / "skills/comms/generate-meeting-notes/SKILL.md"
MAKEFILE = REPO / "Makefile"

# 兩個差得夠開的 mtime，避免檔案系統的時間解析度介入。
OLDER = 1_000_000_000
NEWER = 2_000_000_000


# --------------------------------------------------------------------------
# 純函式 —— 六條規則各一條 case
# --------------------------------------------------------------------------


def test_the_three_directions_are_distinct_strings():
    """三個方向常數必須互不相同。

    刪掉這條 → 兩個常數指到同一個字串時，下面每條斷言都還是綠的，而呼叫端
    再也分不出該擋還是該跑。
    """
    assert len({parity.INSTALLED_NEWER, parity.REPO_NEWER, parity.IN_SYNC}) == 3


def test_no_differences_at_all_is_in_sync():
    """兩邊都沒有差異 → `一致`。

    刪掉這條 → 判斷可以永遠回 `repo 較新`，正向同步從此每次都被自己的閘門擋下來。
    """
    assert parity.sync_direction({}, {}) == parity.IN_SYNC


def test_a_path_only_in_the_repo_means_repo_newer():
    """repo 端新增的檔案 → `repo 較新`。

    這是本票的主症狀：少了它，`rsync --delete` 會把 repo 端新增的檔案刪掉。
    刪掉這條 → 新增檔案被判成一致，同步照跑，改動無聲消失。
    """
    assert parity.sync_direction({}, {"NEW.md": 1.0}) == parity.REPO_NEWER


def test_a_path_only_in_the_installed_copy_means_installed_newer():
    """安裝版有、repo 沒有 → `安裝版較新`。

    刪掉這條 → 判斷只認得 repo 那一側，安裝版新增的檔案永遠同步不過來
    （或更糟：被判成 `repo 較新` 而擋下唯一能拿到它的方向）。
    """
    assert parity.sync_direction({"NEW.md": 1.0}, {}) == parity.INSTALLED_NEWER


def test_a_shared_path_with_the_newer_mtime_in_the_repo_is_repo_newer():
    """同一個路徑兩邊內容不同，repo 那份比較新 → `repo 較新`。"""
    assert parity.sync_direction({"a.md": OLDER}, {"a.md": NEWER}) == parity.REPO_NEWER


def test_a_shared_path_with_the_newer_mtime_in_the_installed_copy_is_installed_newer():
    """同一個路徑兩邊內容不同，安裝版那份比較新 → `安裝版較新`。

    與上一條成對：少了任何一條，一個不看 mtime、只回固定值的實作都全綠。
    """
    assert parity.sync_direction({"a.md": NEWER}, {"a.md": OLDER}) == parity.INSTALLED_NEWER


def test_an_mtime_tie_falls_back_to_repo_newer():
    """mtime 平手 → `repo 較新`（刻意的：猜錯的代價不對稱）。

    刪掉這條 → `>` 與 `>=` 再也分不出來，而平手不是假想情況：
    同一次操作寫出來的兩份檔案 mtime 很容易落在同一個刻度上。
    """
    assert parity.sync_direction({"a.md": NEWER}, {"a.md": NEWER}) == parity.REPO_NEWER


# --------------------------------------------------------------------------
# 碰檔案的那一層 —— 真的跑同步腳本，來源與目的地全在 tmp_path 底下
# --------------------------------------------------------------------------


def test_identical_trees_have_no_direction(pair: tuple[Path, Path]):
    """兩邊一致 → `一致`。

    刪掉這條 → 方向可以永遠回 `repo 較新`，正向同步在乾淨的情況下也被擋。
    """
    assert parity.direction_against_installed(*pair) == parity.IN_SYNC


def test_a_file_only_in_the_repo_tree_makes_the_direction_repo_newer(pair: tuple[Path, Path]):
    """repo 端多一個檔案 → `repo 較新`。"""
    installed, repo = pair
    (repo / DEST_REL / "NEW.md").write_text("repo 端新增\n", encoding="utf-8")

    assert parity.direction_against_installed(installed, repo) == parity.REPO_NEWER


def test_a_file_only_in_the_installed_tree_makes_the_direction_installed_newer(
    pair: tuple[Path, Path],
):
    """安裝版多一個檔案 → `安裝版較新`。與上一條成對。"""
    installed, repo = pair
    (installed / "NOTES.md").write_text("只有安裝版有\n", encoding="utf-8")

    assert parity.direction_against_installed(installed, repo) == parity.INSTALLED_NEWER


def test_a_placeholder_difference_does_not_create_a_direction(pair: tuple[Path, Path]):
    """佔位符不是差異 —— 就算 mtime 差很多，方向仍是 `一致`。

    刪掉這條 → 方向改成直接比兩個目錄，每個佔位符都讓方向倒向其中一邊，
    而那是永遠修不掉的：修好就把內部字串推回 public repo。
    """
    installed, repo = pair
    (installed / "SKILL.md").write_text("project example-gcp-project\n", encoding="utf-8")
    (repo / DEST_REL / "SKILL.md").write_text("project <your-gcp-project>\n", encoding="utf-8")
    os.utime(repo / DEST_REL / "SKILL.md", (NEWER, NEWER))
    os.utime(installed / "SKILL.md", (OLDER, OLDER))

    assert parity.direction_against_installed(installed, repo) == parity.IN_SYNC


def test_a_shared_file_edited_later_in_the_repo_is_repo_newer(pair: tuple[Path, Path]):
    """同名檔案兩邊都改過，repo 那份 mtime 較新 → `repo 較新`。"""
    installed, repo = pair
    (installed / "SKILL.md").write_text("安裝版的內容\n", encoding="utf-8")
    (repo / DEST_REL / "SKILL.md").write_text("repo 的內容\n", encoding="utf-8")
    os.utime(installed / "SKILL.md", (OLDER, OLDER))
    os.utime(repo / DEST_REL / "SKILL.md", (NEWER, NEWER))

    assert parity.direction_against_installed(installed, repo) == parity.REPO_NEWER


def test_a_shared_file_edited_later_in_the_installed_copy_is_installed_newer(
    pair: tuple[Path, Path],
):
    """同上，mtime 反過來 → `安裝版較新`。

    刪掉這條 → 這一層可以忽略 mtime、看到差異就回 `repo 較新`，
    日常那條「安裝版改了、掉回 repo」的路徑從此被自己擋死。
    """
    installed, repo = pair
    (installed / "SKILL.md").write_text("安裝版的內容\n", encoding="utf-8")
    (repo / DEST_REL / "SKILL.md").write_text("repo 的內容\n", encoding="utf-8")
    os.utime(installed / "SKILL.md", (NEWER, NEWER))
    os.utime(repo / DEST_REL / "SKILL.md", (OLDER, OLDER))

    assert parity.direction_against_installed(installed, repo) == parity.INSTALLED_NEWER


# --------------------------------------------------------------------------
# CLI —— shell 腳本問方向的唯一入口
# --------------------------------------------------------------------------


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """跑 `python3 parity.py ...`。cwd 固定在 `/`，順帶釘住「路徑不從 cwd 推」。

    環境走 `child_env`（理由見 `conftest.child_env`）。`cwd="/"` 留著 ——
    那個釘子在測「路徑不從 cwd 推」，不要為了繞過 mutmut 拿掉。
    """
    return subprocess.run(
        [sys.executable, str(PARITY_PY), *args],
        capture_output=True,
        text=True,
        cwd="/",
        env=child_env(),
    )


def test_the_cli_prints_in_sync_for_identical_trees(pair: tuple[Path, Path]):
    """`--direction` 把方向印到 stdout，退出碼 0。

    刪掉這條 → CLI 退化成永遠印 `repo 較新`（或印到 stderr），
    而 shell 腳本只讀 stdout：閘門從此永遠命中。
    """
    installed, repo = pair

    result = run_cli("--direction", str(installed), str(repo))

    assert result.returncode == 0
    assert result.stdout.strip() == parity.IN_SYNC


def test_the_cli_prints_repo_newer_when_the_repo_has_an_extra_file(pair: tuple[Path, Path]):
    """與上一條成對：狀況變了，印出來的字串也要跟著變。"""
    installed, repo = pair
    (repo / DEST_REL / "NEW.md").write_text("repo 端新增\n", encoding="utf-8")

    result = run_cli("--direction", str(installed), str(repo))

    assert result.returncode == 0
    assert result.stdout.strip() == parity.REPO_NEWER


BAD_USAGE = ["too-few", "too-many", "unknown-flag"]


@pytest.mark.parametrize("kind", BAD_USAGE)
def test_bad_usage_exits_non_zero_without_printing_a_direction(pair: tuple[Path, Path], kind: str):
    """旗標不對或參數個數不對 → 非零退出碼，而且不能印出任何方向字串。

    刪掉這條 → 用法打錯時 CLI 印一行空字串回 0，呼叫端把它當成「一致」，
    閘門靜悄悄地不存在。
    """
    installed, repo = pair
    args = {
        "too-few": ["--direction", str(installed)],
        "too-many": ["--direction", str(installed), str(repo), str(repo)],
        "unknown-flag": ["--nonsense", str(installed), str(repo)],
    }[kind]

    result = run_cli(*args)

    assert result.returncode != 0
    assert not any(
        d in result.stdout for d in (parity.IN_SYNC, parity.REPO_NEWER, parity.INSTALLED_NEWER)
    )


# --------------------------------------------------------------------------
# repo-first 落在文件與 mutation 範圍上的那兩個點
# --------------------------------------------------------------------------


SECTION_HEADING = "## 版本來源檢查"

# 「安裝版才是被編輯的那份」的幾種寫法。repo-first 之後這一節不該再出現任何一種。
INSTALLED_AS_SOURCE = [
    "安裝版才是實際被編輯的那份",
    "安裝版是實際被編輯的那份",
    "安裝版才是被編輯的那份",
    "以安裝版為準",
]


def version_source_section() -> str:
    """SKILL.md 的「版本來源檢查」一節（到下一個 `## ` 為止）。"""
    text = SKILL_MD.read_text(encoding="utf-8")
    start = text.find(SECTION_HEADING)
    assert start != -1, f"SKILL.md 找不到「{SECTION_HEADING}」一節"
    end = text.find("\n## ", start + len(SECTION_HEADING))
    return text[start:] if end == -1 else text[start:end]


def test_the_version_source_section_sends_drift_to_the_reverse_script():
    """repo-first：這一節要告訴讀者掉齊走 `bin/sync-to-installed.sh`。

    刪掉這條 → 文件還在教人用正向腳本掉齊，而正向現在會被閘門擋下來（exit 3）；
    讀者拿著一個永遠失敗的指令，只好手動覆蓋，回到本票要修的那個病。
    """
    assert "bin/sync-to-installed.sh" in version_source_section()


@pytest.mark.parametrize("phrase", INSTALLED_AS_SOURCE)
def test_the_version_source_section_does_not_call_the_installed_copy_the_edited_one(phrase: str):
    """這一節不可以再說「安裝版才是被編輯的那份」。

    刪掉這條 → 程式碼改成 repo-first、文件停在舊敘述，下一個人照文件去編輯安裝版，
    改動在下一次掉齊被三方合併判成衝突或直接留在本機。
    """
    assert phrase not in version_source_section()


def test_sync_direction_is_inside_the_mutation_scope():
    """`sync_direction` 要在 Makefile 的 `PURE` 白名單裡。

    刪掉這條 → 這支函式不在 mutation 範圍內，上面那七條 case 一條都不會被 mutant 問，
    「方向判斷有測試」變成只有覆蓋率意義。
    """
    pure = MAKEFILE.read_text(encoding="utf-8").split("PURE :=", 1)[-1].split("\n\n", 1)[0]

    assert "sync_direction" in pure.split()


@pytest.mark.parametrize("missing", ["installed-skill-md", "sync-script"])
def test_an_incomparable_pair_raises_instead_of_reporting_in_sync(
    pair: tuple[Path, Path], missing: str
):
    """比不了就 raise —— 不可以回 `一致`。

    `sync_diff` 在比不了的時候回空清單（「沒東西要講」對漂移警告是對的），但方向判斷
    把空清單讀成 `一致`，而 `一致` 是**放行** `rsync --delete` 的那個答案。所以同一份
    「比不了」在這一層必須翻成例外：fail closed。
    刪掉這條 → 安裝版不存在、或 repo 指到一個不是 fstack 的目錄時，閘門靜靜地放行。
    反面是 `test_identical_trees_have_no_direction`：比得了的時候照樣回 `一致`。
    """
    installed, repo = pair
    if missing == "installed-skill-md":
        (installed / "SKILL.md").unlink()
    else:
        (repo / parity.SYNC_SCRIPT).unlink()

    with pytest.raises(RuntimeError):
        parity.direction_against_installed(installed, repo)
