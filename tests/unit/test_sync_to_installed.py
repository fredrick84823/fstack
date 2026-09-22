"""`bin/sync-to-installed.sh` 的黑箱測試 —— repo 版掉齊回安裝版的那個方向。

作法照抄 `test_sync_from_installed.py`：來源由腳本自身位置推得，所以把兩支腳本都複製
進 `tmp_path` 底下的假 repo；`HOME` 與 DST 也全在 `tmp_path` 底下。
**真實安裝版（`~/.agents/skills/generate-meeting-notes`）在這支裡一個字都不會被寫到** ——
DST 每條測試都明示傳進去。

這個方向最危險的事是**把佔位符推回安裝版**：repo 版是去識別化之後的樣子，直接覆蓋
就等於把使用者的 GCP project、OAuth client 名換成 `<your-...>`，而那是靜默的
——skill 下一次跑起來才炸，而且看起來像設定壞了。所以合併是三方的：
base = sanitize(安裝版)、ours = 安裝版、theirs = repo 版；佔位符那幾行在 base 與
theirs 之間沒變化，安裝版的真值因此留著。

「內部事實」下面全是虛構值，對應 `test_sync_from_installed.py` 那份假的 sanitize 表。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import load_script
from .test_sync_diff import write_tree
from .test_sync_from_installed import (  # noqa: F401  `home` 是 fixture，靠名字解析
    DEST_REL,
    PARITY,
    SCRIPT,
    home,
    run,
    snapshot,
    write_conf,
)

parity = load_script("parity")

REPO = Path(__file__).resolve().parents[2]
TO_SCRIPT = REPO / "bin" / "sync-to-installed.sh"

HEAD = "# 會議記錄 skill\n"
REAL = "GCP project: example-gcp-project\n"  # 安裝版留著的內部事實
MASKED = "GCP project: <your-gcp-project>\n"  # repo 版看到的樣子
TAIL = "尾巴\n"

# 一組「已經掉齊」的內容：repo 版正好是安裝版去識別化之後的樣子。
INSTALLED_BASE = {"SKILL.md": HEAD + REAL + TAIL, "references/glossary.md": "詞彙\n"}
REPO_BASE = {"SKILL.md": HEAD + MASKED + TAIL, "references/glossary.md": "詞彙\n"}


@pytest.fixture
def trees(tmp_path: Path) -> tuple[Path, Path]:
    """回傳 (repo 根目錄, DST)。repo 的 `bin/` 裡兩支腳本都有 —— 反向腳本要靠正向
    腳本產出 base，而正向腳本要問 `parity_skills.py` 這支 skill 要不要去識別化。"""
    repo = tmp_path / "repo"
    (repo / "bin").mkdir(parents=True)
    for script in (TO_SCRIPT, SCRIPT, PARITY):
        (repo / "bin" / script.name).write_bytes(script.read_bytes())
        (repo / "bin" / script.name).chmod(0o755)
    write_tree(repo / DEST_REL, REPO_BASE)

    dst = write_tree(tmp_path / "installed", INSTALLED_BASE)
    return repo, dst


def sync_to(repo: Path, dst: Path, home: Path):
    return run(repo / "bin" / TO_SCRIPT.name, str(dst), home=home)


# --------------------------------------------------------------------------
# 掉齊 —— 新增、刪除、不碰、合併
# --------------------------------------------------------------------------


def test_a_file_only_in_the_repo_is_copied_over(trees: tuple[Path, Path], home: Path):
    """repo 有、安裝版沒有的檔案 → 複製過去。

    刪掉這條 → 掉齊可以什麼都不做而全綠；repo 端新增的檔案永遠到不了安裝版，
    正向的方向閘門從此每次都命中，兩個方向一起卡死。
    """
    repo, dst = trees
    (repo / DEST_REL / "scripts").mkdir(parents=True)
    (repo / DEST_REL / "scripts" / "new_tool.py").write_text("# 新工具\n", encoding="utf-8")

    sync_to(repo, dst, home)

    assert (dst / "scripts" / "new_tool.py").read_text(encoding="utf-8") == "# 新工具\n"


def test_a_file_the_repo_deleted_is_deleted_in_the_installed_copy(
    trees: tuple[Path, Path], home: Path
):
    """repo 端刪掉的檔案 → 安裝版也刪掉。

    刪掉這條 → 刪除不會傳播，那個檔案在下一次比對永遠算差異，
    方向判斷從此固定倒向安裝版。
    """
    repo, dst = trees
    (dst / "ZOMBIE.md").write_text("repo 已經刪掉了\n", encoding="utf-8")

    sync_to(repo, dst, home)

    assert not (dst / "ZOMBIE.md").exists()


def test_an_identical_file_is_not_rewritten(trees: tuple[Path, Path], home: Path):
    """內容已經一致的檔案完全不碰 —— 連 mtime 都不能動。

    刪掉這條 → 掉齊變成無條件覆寫，每個檔案的 mtime 都刷新；
    而 mtime 正是方向判斷的依據，掉齊一次就把下一次的方向判斷洗成「安裝版較新」。
    """
    repo, dst = trees
    before = snapshot(dst)["references/glossary.md"]

    sync_to(repo, dst, home)

    assert snapshot(dst)["references/glossary.md"] == before


def test_a_repo_edit_lands_in_the_installed_copy(trees: tuple[Path, Path], home: Path):
    """repo 端合併進來的改動要帶到安裝版。

    刪掉這條 → 合併可以永遠選 ours（安裝版原樣），掉齊變成裝飾品，
    而「掉齊完成」的退出碼照樣是 0。
    """
    repo, dst = trees
    (repo / DEST_REL / "SKILL.md").write_text(HEAD + MASKED + TAIL + "新增一行\n", encoding="utf-8")

    sync_to(repo, dst, home)

    assert "新增一行" in (dst / "SKILL.md").read_text(encoding="utf-8")


def test_the_installed_internal_value_survives_the_merge(trees: tuple[Path, Path], home: Path):
    """掉齊前該欄位在安裝版有值，掉齊後仍是同一個值 —— 佔位符不可以蓋過去。

    刪掉這條 → 掉齊改成直接複製，repo 的 `<your-gcp-project>` 覆蓋掉使用者的真實設定。
    症狀是靜默的：skill 下一次跑起來才炸，而且看起來像設定壞了。
    """
    repo, dst = trees
    (repo / DEST_REL / "SKILL.md").write_text(HEAD + MASKED + TAIL + "新增一行\n", encoding="utf-8")

    sync_to(repo, dst, home)

    text = (dst / "SKILL.md").read_text(encoding="utf-8")
    assert REAL in text
    assert MASKED not in text


def test_the_reverse_sync_clears_the_parity_diff(
    trees: tuple[Path, Path], home: Path, monkeypatch: pytest.MonkeyPatch
):
    """掉齊之前 parity 比對有差異，掉齊之後沒有。

    這是驗收條件 4 的整條路徑：前面每條測試都只看單一檔案，這條問的是
    「跑完之後兩邊真的一致了嗎」。刪掉這條 → 掉齊可以每個檔案各自看起來都對，
    卻留下一個誰都沒斷言到的差異，下一次正向同步又被閘門擋下來。
    """
    repo, dst = trees
    monkeypatch.setenv("HOME", str(home))
    (repo / DEST_REL / "NEW.md").write_text("repo 端新增\n", encoding="utf-8")
    assert parity.sync_diff(dst, repo) != []

    sync_to(repo, dst, home)

    assert parity.sync_diff(dst, repo) == []


# --------------------------------------------------------------------------
# 衝突 —— 該檔保持原樣，其餘照樣掉齊
# --------------------------------------------------------------------------


CONFLICT_REPO = HEAD + "GCP project: 完全換掉了\n" + TAIL


def test_a_clean_merge_exits_0(trees: tuple[Path, Path], home: Path):
    """合得起來就回 0。

    與下面的 `exit 3` 成對：少了這條，一個永遠回 3 的實作照樣全綠，
    而呼叫端會把每一次正常掉齊都讀成「有衝突」。
    """
    repo, dst = trees
    (repo / DEST_REL / "SKILL.md").write_text(HEAD + MASKED + TAIL + "新增一行\n", encoding="utf-8")

    assert sync_to(repo, dst, home).returncode == 0


def test_a_conflict_exits_3(trees: tuple[Path, Path], home: Path):
    """同一行 ours 與 theirs 各改各的 → 回 3。

    刪掉這條 → 衝突靜悄悄地被跳過，使用者以為掉齊完成了。
    """
    repo, dst = trees
    (repo / DEST_REL / "SKILL.md").write_text(CONFLICT_REPO, encoding="utf-8")

    assert sync_to(repo, dst, home).returncode == 3


def test_a_conflicting_file_keeps_the_installed_copy(trees: tuple[Path, Path], home: Path):
    """合不起來的檔案，安裝版保持原樣。

    刪掉這條 → 衝突時直接取 theirs，使用者的內部事實被 repo 版蓋掉 ——
    跟沒有三方合併是同一個結果，只是多回了一個 3。
    """
    repo, dst = trees
    (repo / DEST_REL / "SKILL.md").write_text(CONFLICT_REPO, encoding="utf-8")

    sync_to(repo, dst, home)

    assert (dst / "SKILL.md").read_text(encoding="utf-8") == HEAD + REAL + TAIL


def test_a_conflict_writes_no_merge_markers_anywhere(trees: tuple[Path, Path], home: Path):
    """衝突不可以把 `<<<<<<<` 寫進安裝版的任何一個檔案。

    刪掉這條 → 合併結果照寫，安裝版變成一份語法壞掉的 skill，
    而「保持原樣」那條測試只看得到它指名的那一個檔案。
    """
    repo, dst = trees
    (repo / DEST_REL / "SKILL.md").write_text(CONFLICT_REPO, encoding="utf-8")

    sync_to(repo, dst, home)

    assert not any("<<<<<<<" in text for text, _ in snapshot(dst).values())


def test_a_conflict_does_not_hold_back_the_other_files(trees: tuple[Path, Path], home: Path):
    """有衝突時，其餘檔案照樣掉齊。

    刪掉這條 → 一個衝突就整批中止，而衝突是常態；掉齊變成全有全無。
    """
    repo, dst = trees
    (repo / DEST_REL / "SKILL.md").write_text(CONFLICT_REPO, encoding="utf-8")
    (repo / DEST_REL / "NEW.md").write_text("repo 端新增\n", encoding="utf-8")

    sync_to(repo, dst, home)

    assert (dst / "NEW.md").read_text(encoding="utf-8") == "repo 端新增\n"


# --------------------------------------------------------------------------
# 用法與環境
# --------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["missing", "no-skill-md"])
def test_a_dst_that_is_not_a_skill_dir_exits_1(trees: tuple[Path, Path], home: Path, kind: str):
    """DST 不像 skill 目錄 → exit 1。

    刪掉這條 → 路徑打錯時腳本照樣把整份 skill 倒進去（或倒進 `/`），
    而那個目錄裡本來有什麼沒人知道。
    """
    repo, dst = trees
    bad = dst.parent / "nope"
    if kind == "no-skill-md":
        bad.mkdir()

    assert sync_to(repo, bad, home).returncode == 1


def test_a_repo_without_the_skill_dir_exits_1(trees: tuple[Path, Path], home: Path):
    """來源那側不像 skill 目錄 → exit 1，而且不能動 DST。

    刪掉這條 → 腳本從一個空來源出發，把 DST 的檔案一個一個「刪掉」
    （repo 沒有的就刪），安裝版被清空。
    """
    repo, dst = trees
    (repo / DEST_REL / "SKILL.md").unlink()
    before = snapshot(dst)

    result = sync_to(repo, dst, home)

    assert result.returncode == 1
    assert snapshot(dst) == before


def test_a_base_that_cannot_be_produced_exits_2(
    trees: tuple[Path, Path], tmp_path_factory: pytest.TempPathFactory
):
    """正向腳本沒有乾淨收尾（這裡：guard pattern 未設定）→ exit 2。

    base 產不出來就沒有三方合併，只剩「直接覆蓋」與「什麼都不做」兩條路，
    兩條都是資料損失。刪掉這條 → 腳本在這種情況下退回其中一條而不出聲。
    """
    repo, dst = trees
    bare = write_conf(tmp_path_factory.mktemp("bare-home"), patterns=None)

    assert sync_to(repo, dst, bare).returncode == 2
