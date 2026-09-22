"""`bin/parity_skills.py` —— parity 的涵蓋清單，以及兩類 skill 的比對。

這張票在修的病是「護欄只涵蓋 1 支 skill，對其餘 59 支等於沒有護欄」。所以這裡要釘的
不是某一支 skill 的行為，是**機制**：

- 涵蓋範圍是資料（`SKILLS`），沒被涵蓋的 skill 要 raise，不可以被讀成「沒有漂移」；
- 兩類比對（sanitize 過的走同步腳本、沒 sanitize 的直接比）都要真的抓得到漂移；
- 而「抓得到」包含 `dircmp` 的 funny 那兩類 —— 懸空 symlink 對著一般檔，三個正常清單
  全是空的，漏收就是靜默的資料遺失。

外加一條**把兩份實作釘在一起**的測試：`skills/comms/generate-meeting-notes/scripts/
parity.py` 現在還有一份同樣作法的比對（理由見 `bin/parity_skills.py` 的 module
docstring：那支住在被同步的 skill 目錄裡，這條分支上不能改）。兩份比對邏輯是整套機制
最糟的失敗方式 —— 一份漂掉了，另一份照樣綠。那條釘子在兩份合一之後才可以拆。

跟 `test_sync_diff.py` 一樣**跑真的 `bin/sync-from-installed.sh`**，`HOME` 與兩邊的目錄
全部造在 `tmp_path` 底下，所以不碰 `~/.agents` 也不碰 `~/.config`。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from .conftest import ROOT, load_script
from .test_sync_diff import BASE, pair, write_tree  # noqa: F401 —— pair 是 fixture
from .test_sync_from_installed import DEST_REL

parity_skills = load_script("parity_skills", ROOT / "bin")
parity = load_script("parity")

GMN = str(DEST_REL)


# --------------------------------------------------------------------------
# 涵蓋清單是資料
# --------------------------------------------------------------------------


def test_a_skill_outside_the_coverage_list_raises(tmp_path: Path):
    """沒被涵蓋的 skill → `KeyError`，**不可以**回空清單，而且訊息要指出下一步。

    刪掉這條 → 未涵蓋的 skill 被讀成「沒有漂移」，60 幾支 skill 全部靜悄悄地綠，
    正是這張票要修的那個形狀。
    """
    with pytest.raises(KeyError, match="SKILLS"):
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


# crap.py 只有黑箱子行程測試（`test_crap.py` 餵兩份 json 給它跑），而 mutmut 的
# trampoline 記的是**行程內**的呼叫 —— 子行程碰不到。掛進 source_paths 是一牆
# 🫥 no-tests，不是覆蓋。
NOT_MUTATED = {"crap.py"}


def test_every_bin_module_is_inside_the_mutation_scope():
    """`bin/` 底下的模組要掛進 `setup.cfg` 的 `source_paths`。

    `bin` 在 setup.cfg 裡本來只以 `also_copy` 出現 —— 那是「複製過去讓測試跑得起來」，
    不是「產 mutant」。所以**任何搬進 `bin/` 的純邏輯都會自動掉出變異覆蓋，而且沒有
    任何測試會紅**：既有那四條守門測試都是 per-module 寫的，誰也不會發現。
    實際發生過：`sync_direction` 本來就在 `PURE` 裡，搬進 `bin/parity_skills.py` 之後
    整支檔案不在 `source_paths`，那七條 case 一顆 mutant 都不會被問。

    例外列在 `NOT_MUTATED` 並寫理由 —— 明著豁免，不是靜靜漏掉。
    """
    cfg = (ROOT / "setup.cfg").read_text(encoding="utf-8")
    mutated = cfg.split("source_paths=", 1)[1].split("\n\n", 1)[0].split()

    for path in sorted((ROOT / "bin").glob("*.py")):
        if path.name in NOT_MUTATED:
            continue
        assert f"bin/{path.name}" in mutated, f"bin/{path.name} 沒掛進 source_paths"


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

    釘的是上面這五種**一般**形狀。泛化版另外收 `dircmp` 的 funny 兩類（parity.py 沒有，
    而它這條分支上不能改），所以那個形狀不在這條的比對範圍裡 —— 它有自己的測試。

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
# 沒 sanitize 的那類 —— 直接比對
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


def test_a_missing_installed_copy_is_not_a_comparison(plain: tuple[Path, Path]):
    """安裝版不像安裝目錄 → `[]`，不 raise。沒裝過這支 skill 的機器沒東西可以漂移。"""
    installed, repo = plain
    (installed / "SKILL.md").unlink()

    assert parity_skills.sync_diff(PLAIN, installed, repo) == []


# --------------------------------------------------------------------------
# dircmp 的 funny 兩類 —— 漏收就是靜默的資料遺失
# --------------------------------------------------------------------------


# 挑一支 `scripts/` 底下的檔案，不是 SKILL.md：SKILL.md 是「這裡像不像安裝目錄」的
# 判準，換成懸空連結會走「沒有安裝版」那條早退，測不到比對本身。
DANGLING = "scripts/create_gdoc_from_md.py"


def dangle(installed: Path) -> None:
    """把安裝版的那個檔案換成一個懸空 symlink（improve 的執行期資料現在就是這個形狀）。"""
    (installed / DANGLING).unlink()
    (installed / DANGLING).symlink_to(installed / "指不到的東西")


def test_a_dangling_symlink_facing_a_real_file_is_drift(plain: tuple[Path, Path]):
    """左邊懸空 symlink、右邊一般檔 → `common_funny`，三個正常清單全空。

    漏收的整條路徑：`sync_diff` 回 `[]` → 方向判斷讀成「一致」→ 正向同步的閘門放行 →
    `rsync -a --delete` 把 repo 的真實檔案換成一個懸空連結，全程無聲。
    安裝版的 improve 現在就有 5 個指向 private repo 的 symlink，第二台機器沒 clone
    那個 repo 時全部懸空 —— 今天可達。
    """
    installed, repo = plain
    dangle(installed)

    assert parity_skills.sync_diff(PLAIN, installed, repo) == [DANGLING]


def test_a_dangling_symlink_does_not_read_as_in_sync(plain: tuple[Path, Path]):
    """同一個形狀在方向判斷上也不可以是「一致」——「一致」是**放行** `--delete` 的答案。

    刪掉這條 → `_mtimes` 改回只看 `exists()`（對懸空連結是 False），兩邊都收不到那條
    路徑，`sync_direction({}, {})` 回「一致」，閘門照樣放行。
    """
    installed, repo = plain
    dangle(installed)

    assert parity_skills.direction_against_installed(PLAIN, installed, repo) != (
        parity_skills.IN_SYNC
    )


def test_a_file_that_cannot_be_read_is_drift(plain: tuple[Path, Path]):
    """兩邊都是一般檔、但讀不到 → `funny_files`，一樣要報。

    刪掉這條 → 只收 `common_funny` 也會全綠，而「比不下去」被讀成「一致」是同一種病：
    權限壞掉的那一刻護欄靜靜熄火。
    """
    installed, repo = plain
    blocked = installed / "SKILL.md"
    blocked.write_text("不一樣的內容\n", encoding="utf-8")
    blocked.chmod(0o000)
    try:
        assert parity_skills.sync_diff(PLAIN, installed, repo) == ["SKILL.md"]
    finally:
        blocked.chmod(0o644)


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
    # 整個目錄只存在於安裝版：repo 端沒有那個目錄可以 stat，判定必須自己告訴 git
    # 「這是目錄」（尾斜線探針），否則 `memory/` 這條規則配不到。假漂移的大宗。
    ("整個目錄", "memory/", {}, {"memory/transitions.jsonl": "執行期\n"}),
    # 兩邊都有的目錄，底下多一個被忽略的檔案 —— 這條走的是遞迴那一半。
    (
        "共用目錄底下",
        "memory/",
        {"memory/README.md": "說明\n"},
        {"memory/README.md": "說明\n", "memory/classifier.log": "執行期\n"},
    ),
    # 非 ASCII 路徑：`core.quotePath` 預設把輸出包成 C-quoted 字串，包了就對不上前綴，
    # 那條路徑永遠排不掉 —— 每次都報一筆清不掉的假漂移。`-z` 同時解決 quoting 與換行歧義。
    ("非 ASCII", "會議記錄/", {}, {"會議記錄/2026-09-22.md": "執行期\n"}),
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

    刪掉這條 → improve 那類 skill 每次比對都報一串 `memory`／佇列檔，而且永遠修不掉
    （repo 端刻意沒有它們）。
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


def test_a_repo_that_is_not_a_git_checkout_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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


# --------------------------------------------------------------------------
# 探針 —— git 拒絕回答穿過 symlink 的路徑，而一個壞探針殺掉整批
# --------------------------------------------------------------------------


def test_probes_ask_both_forms_for_an_ordinary_path(tmp_path: Path):
    """一般路徑送兩個探針：不帶斜線的（檔案規則）與帶斜線的（目錄規則）。

    刪掉這條 → 尾斜線那半沒了，`memory/` 這種整個目錄的忽略規則全部配不到，
    假漂移原封不動回來。
    """
    assert parity_skills._probes(tmp_path, "memory") == ["memory", "memory/"]


def test_probes_drop_the_slash_form_when_the_path_itself_is_a_symlink(tmp_path: Path):
    """路徑自己是 symlink → 只送不帶斜線那個。

    帶斜線等於叫 git 走進那個連結，它會以 `beyond a symbolic link`（退出碼 128）拒答，
    而那會殺掉**整批**探針 —— 整支 skill 的比對跟著炸掉。
    """
    (tmp_path / "queue.md").symlink_to(tmp_path / "別處")

    assert parity_skills._probes(tmp_path, "queue.md") == ["queue.md"]


def test_probes_skip_a_path_whose_ancestor_is_a_symlink(tmp_path: Path):
    """祖先是 symlink → 整條都不送（git 兩種形式都拒答）。

    送不出去的路徑不會被排除，也就是照樣報成漂移 —— 這個方向是安全的。
    刪掉這條 → 跑過一次正向同步（`rsync -a` 會把安裝版的 symlink 原樣複製進 repo
    工作樹）之後，整支 skill 的比對就以 RuntimeError 收場。
    """
    (tmp_path / "real").mkdir()
    (tmp_path / "linkdir").symlink_to(tmp_path / "real")

    assert parity_skills._probes(tmp_path, "linkdir/a.md") == []


def test_a_symlinked_directory_in_the_repo_does_not_abort_the_whole_comparison(
    plain: tuple[Path, Path],
):
    """repo 工作樹裡有 symlink 目錄時，比對照樣給得出答案。

    刪掉這條 → 一個壞探針把 `git check-ignore` 打成退出碼 128，`_gitignored` raise，
    整支 skill 的比對炸掉。fail closed 不是安全缺陷，但壞掉的護欄就是沒有護欄。
    """
    installed, repo = plain
    write_tree(repo / PLAIN, {"real/a.md": "同一份\n"})
    (repo / PLAIN / "linkdir").symlink_to(repo / PLAIN / "real")
    write_tree(installed, {"real/a.md": "同一份\n", "linkdir/a.md": "安裝版改過\n"})

    assert parity_skills.sync_diff(PLAIN, installed, repo) == ["linkdir/a.md"]
