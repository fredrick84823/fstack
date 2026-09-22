"""`bin/parity_skills.py` —— parity 的涵蓋清單，以及兩類 skill 的比對。

這張票在修的病是「護欄只涵蓋 1 支 skill，對其餘 59 支等於沒有護欄」。所以這裡要釘的
不是某一支 skill 的行為，是**機制**：

- 涵蓋範圍是資料（`SKILLS`），加一支 skill 不需要改任何一個函式；
- 沒被涵蓋的 skill 要 `KeyError`，不可以被讀成「沒有漂移」；
- 兩類比對（sanitize 過的走同步腳本、沒 sanitize 的直接比）都要真的抓得到漂移。

外加一條**把兩份實作釘在一起**的測試：`skills/comms/generate-meeting-notes/scripts/
parity.py` 現在還有一份同樣作法的比對（理由見 `bin/parity_skills.py` 的 module
docstring：那支住在被同步的 skill 目錄裡，這條分支上不能改）。兩份比對邏輯是整套機制
最糟的失敗方式 —— 一份漂掉了，另一份照樣綠。那條釘子在兩份合一之後才可以拆。

跟 `test_sync_diff.py` 一樣**跑真的 `bin/sync-from-installed.sh`**，`HOME` 與兩邊的目錄
全部造在 `tmp_path` 底下，所以不碰 `~/.agents` 也不碰 `~/.config`。
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from .conftest import load_script
from .test_sync_diff import BASE, pair, write_tree  # noqa: F401 —— pair 是 fixture
from .test_sync_from_installed import DEST_REL

ROOT = Path(__file__).resolve().parents[2]
GMN = str(DEST_REL)


def load_bin(name: str) -> ModuleType:
    """把 `bin/<name>.py` 當模組載進來。

    路徑從**本檔案**推（同 `conftest.load_script` 的理由）：mutmut 把原始碼與測試一起
    複製進 `mutants/` 之後，寫死 repo 路徑載到的是原檔，測試看起來有鑑別力其實沒有。
    """
    path = ROOT / "bin" / f"{name}.py"
    modname = str(path.relative_to(ROOT).with_suffix("")).replace(os.sep, ".")
    spec = importlib.util.spec_from_file_location(modname, path)
    assert spec is not None and spec.loader is not None, f"載不進來：{path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


parity_skills = load_bin("parity_skills")
parity = load_script("parity")


# --------------------------------------------------------------------------
# 涵蓋清單是資料
# --------------------------------------------------------------------------


def test_the_coverage_list_is_data_not_a_hardcoded_skill():
    """`SKILLS` 是「repo 相對路徑 → 是不是 sanitize 過的」的對照表。

    刪掉這條 → 清單被改回寫死在函式裡的字串，而「加一支 skill 要改邏輯」正是
    這套護欄當初只涵蓋 1 支的原因。
    """
    assert parity_skills.SKILLS[GMN] is True
    assert all(isinstance(v, bool) for v in parity_skills.SKILLS.values())


def test_a_skill_outside_the_coverage_list_raises(tmp_path: Path):
    """沒被涵蓋的 skill → `KeyError`，**不可以**回空清單。

    刪掉這條 → 未涵蓋的 skill 被讀成「沒有漂移」，60 幾支 skill 全部靜悄悄地綠，
    正是這張票要修的那個形狀。
    """
    with pytest.raises(KeyError):
        parity_skills.sync_diff("skills/nowhere/not-covered", tmp_path, tmp_path)


def test_the_installed_dir_is_flat(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """安裝位置是 `~/.agents/skills/<skill 目錄名>` —— repo 的分類目錄那層不帶過去。

    刪掉這條 → 安裝路徑算成 `~/.agents/skills/comms/generate-meeting-notes`，
    找不到安裝版，而「找不到安裝版」的行為是**安靜地跳過比對**。
    """
    monkeypatch.setenv("HOME", str(tmp_path))

    assert parity_skills.installed_dir(GMN) == tmp_path / ".agents/skills/generate-meeting-notes"
    assert parity_skills.installed_dir("skills/skill-evolution/improve") == (
        tmp_path / ".agents/skills/improve"
    )


# --------------------------------------------------------------------------
# sanitize 過的那類 —— 走同步腳本，而且要跟舊的那份答案一致
# --------------------------------------------------------------------------


def identical(installed: Path, repo: Path) -> None:
    pass


def installed_only(installed: Path, repo: Path) -> None:
    (installed / "NOTES.md").write_text("只有安裝版有\n", encoding="utf-8")


def repo_only(installed: Path, repo: Path) -> None:
    (repo / DEST_REL / "ZOMBIE.md").write_text("只有 repo 有\n", encoding="utf-8")


def both_edited(installed: Path, repo: Path) -> None:
    (repo / DEST_REL / "scripts/create_gdoc_from_md.py").write_text("# 改過了\n", encoding="utf-8")


def placeholder(installed: Path, repo: Path) -> None:
    (installed / "SKILL.md").write_text("project example-gcp-project\n", encoding="utf-8")
    (repo / DEST_REL / "SKILL.md").write_text("project <your-gcp-project>\n", encoding="utf-8")


DRIFTS = [identical, installed_only, repo_only, both_edited, placeholder]


@pytest.mark.parametrize("drift", DRIFTS, ids=[f.__name__ for f in DRIFTS])
def test_it_answers_exactly_what_the_skills_own_parity_answers(pair, drift):  # noqa: F811
    """泛化版與 skill 自己那份 `parity.sync_diff` 對同一棵樹給同一個答案。

    兩份比對邏輯是這整套機制最糟的失敗方式：一份漂掉了，另一份照樣綠。合併並跑過
    `bin/sync-to-installed.sh`、把 parity.py 改成 delegate 之後，這條才可以拆。

    刪掉這條 → 兩份實作可以各自演化（排除清單、遞迴、退出碼判斷），而差別只會在
    「發佈時有警告、integration 卻是綠的」那種對不起來的現場被發現。
    """
    installed, repo = pair
    drift(installed, repo)

    assert parity_skills.sync_diff(GMN, installed, repo) == parity.sync_diff(installed, repo)


def test_a_sanitized_skill_still_detects_a_planted_drift(pair):  # noqa: F811
    """正向斷言，不只是「兩份一樣」：植入一個 repo 版沒有的檔案要抓得到。

    刪掉這條 → 兩份實作可以同時退化成 `return []`，上面那條等式照樣成立。
    """
    installed, repo = pair
    installed_only(installed, repo)

    assert "NOTES.md" in parity_skills.sync_diff(GMN, installed, repo)


# --------------------------------------------------------------------------
# 沒 sanitize 的那類 —— 直接比對，排除那四類雜訊
# --------------------------------------------------------------------------

PLAIN = "skills/skill-evolution/plain-skill"


def git_init(repo: Path, ignore: str = "") -> Path:
    """把 `repo` 變成一個真的 git checkout，`.gitignore` 內容照給的來。

    直接比對那條路徑要問 repo 自己的 git「這條路徑被忽略了嗎」，所以假 repo 不能只是
    一個普通目錄。造一個真的 checkout 比把 `git check-ignore` 換成替身誠實 ——
    替身證明不了「`memory/` 這種目錄規則配得到」，而那正是假漂移的大宗。
    """
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    (repo / ".gitignore").write_text(ignore, encoding="utf-8")
    return repo


@pytest.fixture
def plain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """一組內容相同的 (installed, repo)，skill 掛在 `SKILLS` 裡是 `False`。

    `monkeypatch.setitem` 而不是真的加一支進清單：這裡測的是**機制**，不是
    哪一支 skill 已經被涵蓋。
    """
    monkeypatch.setitem(parity_skills.SKILLS, PLAIN, False)
    repo = git_init(tmp_path / "repo")
    write_tree(repo / PLAIN, BASE)
    return write_tree(tmp_path / "installed", BASE), repo


def test_a_plain_skill_compares_directly(plain: tuple[Path, Path]):
    """兩邊一致回 `[]`，改一個檔就指得出是哪個路徑。

    刪掉這條 → 直接比對那條分支可以是 `return []`（或永遠非空），
    而 improve 那類 skill 的漂移從此不會叫 —— 正是事故 1 的形狀。
    """
    installed, repo = plain

    assert parity_skills.sync_diff(PLAIN, installed, repo) == []

    (installed / "scripts/create_gdoc_from_md.py").write_text("# 改過了\n", encoding="utf-8")
    assert "scripts/create_gdoc_from_md.py" in parity_skills.sync_diff(PLAIN, installed, repo)


@pytest.mark.parametrize("noise", [".venv", "__pycache__", ".pytest_cache"])
def test_a_plain_skill_ignores_the_same_noise_rsync_excludes(plain: tuple[Path, Path], noise: str):
    """`.venv/` `__pycache__/` `.pytest_cache/` 只在其中一邊也不算漂移。

    刪掉這條 → 排除清單沒套到直接比對那條路徑，每一顆 `__pycache__` 都是一筆假漂移，
    警告變成噪音然後被忽略。
    """
    installed, repo = plain
    write_tree(installed, {f"{noise}/junk.md": "x\n"})

    assert parity_skills.sync_diff(PLAIN, installed, repo) == []


def test_a_plain_skill_does_not_need_the_sync_script(plain: tuple[Path, Path]):
    """直接比對那條路徑不碰 `bin/sync-from-installed.sh`。

    假 repo 裡本來就沒有那支腳本 —— 走到它就會回 `[]`（「比不了」），
    上面那條「改一個檔要抓得到」因此不會過。這條把「不碰」講明白。
    """
    installed, repo = plain

    assert not (repo / parity_skills.SYNC_SCRIPT).exists()
    (installed / "NEW.md").write_text("新的\n", encoding="utf-8")
    assert parity_skills.sync_diff(PLAIN, installed, repo) == ["NEW.md"]


def test_a_missing_installed_copy_is_not_a_comparison(plain: tuple[Path, Path]):
    """安裝版不像安裝目錄 → `[]`，不 raise。沒裝過這支 skill 的機器沒東西可以漂移。"""
    installed, repo = plain
    (installed / "SKILL.md").unlink()

    assert parity_skills.sync_diff(PLAIN, installed, repo) == []


# --------------------------------------------------------------------------
# .gitignore —— 執行期資料不是漂移
# --------------------------------------------------------------------------
#
# improve 那類 skill 的安裝版帶著佇列、log、lock 與 memory/：全部是執行期資料，全部被
# repo 的 .gitignore 擋在版控外面。repo 端**永遠**沒有它們，所以不排除就是每次都報一串
# 修不掉的假漂移 —— 一個每次都喊狼來了的護欄跟沒有護欄是同一件事。
# 判準問 repo 自己的 git，不在 parity_skills.py 再維護第二份清單。

# (id, .gitignore 的規則, repo 端多的檔案, 安裝版多的檔案)
IGNORED = [
    ("整條路徑", "signal-queue.md", {}, {"signal-queue.md": "佇列\n"}),
    ("glob", "*.lock", {}, {".signal-lifecycle.lock": ""}),
    # 整個目錄只存在於安裝版：repo 端沒有那個目錄可以 stat，判定必須自己告訴 git
    # 「這是目錄」，否則 `memory/` 這條規則配不到，而它是假漂移的大宗。
    ("整個目錄", "memory/", {}, {"memory/transitions.jsonl": "執行期\n"}),
    # 兩邊都有的目錄，底下多一個被忽略的檔案 —— 這條走的是遞迴那一半。
    (
        "共用目錄底下",
        "memory/",
        {"memory/README.md": "說明\n"},
        {"memory/README.md": "說明\n", "memory/classifier.log": "執行期\n"},
    ),
]


@pytest.mark.parametrize(
    "rule, repo_extra, installed_extra", [c[1:] for c in IGNORED], ids=[c[0] for c in IGNORED]
)
def test_a_gitignored_path_is_not_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rule: str,
    repo_extra: dict[str, str],
    installed_extra: dict[str, str],
):
    """repo 端 gitignore 掉的路徑，安裝版有也不算漂移。

    刪掉這條 → improve 那類 skill 每次比對都報一串 `memory`／`*.lock`／佇列檔，
    而且永遠修不掉（repo 端刻意沒有它們）。每次都喊狼來了的護欄跟沒有護欄是同一件事。
    """
    monkeypatch.setitem(parity_skills.SKILLS, PLAIN, False)
    repo = git_init(tmp_path / "repo", f"{PLAIN}/{rule}\n")
    write_tree(repo / PLAIN, {**BASE, **repo_extra})
    installed = write_tree(tmp_path / "installed", {**BASE, **installed_extra})

    assert parity_skills.sync_diff(PLAIN, installed, repo) == []


def test_a_path_the_gitignore_does_not_cover_is_still_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """同一棵樹上，**沒有**被 gitignore 的差異照樣要報出來。

    只測「被忽略的不算」等於沒測：一個把整份清單都丟掉的實作也會全綠，而那是把真漂移
    吞掉 —— 比假漂移糟得多（improve 的三個 hotfix 就是這樣在安裝版活了五天）。
    """
    monkeypatch.setitem(parity_skills.SKILLS, PLAIN, False)
    repo = git_init(tmp_path / "repo", f"{PLAIN}/memory/\n{PLAIN}/*.lock\n")
    write_tree(repo / PLAIN, BASE)
    installed = write_tree(
        tmp_path / "installed",
        {
            **BASE,
            "memory/transitions.jsonl": "執行期\n",
            ".signal-lifecycle.lock": "",
            "scripts/session_classifier.py": "# 只活在安裝版的 hotfix\n",
        },
    )

    assert parity_skills.sync_diff(PLAIN, installed, repo) == ["scripts/session_classifier.py"]


def test_a_repo_that_is_not_a_git_checkout_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """問不到 .gitignore → raise，**不可以**靜默當成「沒有漂移」。

    回空集合（什麼都沒被忽略）會讓假漂移照報，回全集會靜默吞掉真漂移。兩個都不行，
    所以讓呼叫端知道這次沒比成 —— 同 `_sanitized()` 立過的原則。
    刪掉這條 → 判定壞掉時整套護欄退化成永遠綠，而症狀是安靜的。
    """
    monkeypatch.setitem(parity_skills.SKILLS, PLAIN, False)
    repo = tmp_path / "repo"          # 沒有 git init
    write_tree(repo / PLAIN, BASE)
    installed = write_tree(tmp_path / "installed", {**BASE, "NEW.md": "新的\n"})

    with pytest.raises(RuntimeError, match="check-ignore"):
        parity_skills.sync_diff(PLAIN, installed, repo)
