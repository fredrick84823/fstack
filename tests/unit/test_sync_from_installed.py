"""`bin/sync-from-installed.sh` 的黑箱測試 —— 只斷言退出碼、stdout/stderr、檔案系統。

腳本的目的地是從**它自己的位置**推出來的，不吃參數。所以要在不動真實工作樹的前提下
測同步路徑，唯一的辦法是把腳本複製進 `tmp_path` 底下的假 repo（`sandbox` fixture），
讓它把東西同步到那份假 repo 的 `skills/comms/generate-meeting-notes`。

guard 的測試不需要假 repo —— `--check DIR` 不寫任何檔案，直接指向 `tmp_path` 即可。

**為什麼 guard 一定要有正向案例**：BSD `grep` 不吃 `\\?`。pattern 寫錯的症狀是「掃出來
乾淨」，跟「內容真的乾淨」在退出碼上完全一樣。所以「guard 回 0」沒有鑑別力，每一類
內部指涉都必須有一條「塞進去會回 2」的測試，外加一條證明它不會誤報。

下面那六個字串是 guard 必須攔下的代表值。它們本來就存在於 `bin/sync-from-installed.sh`
的替換表裡（去識別化必須認得原字串才能替換），這裡不新增任何洩漏面。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "bin" / "sync-from-installed.sh"
DEST_REL = Path("skills/comms/generate-meeting-notes")

# guard 涵蓋的副檔名，介面明訂就這四種。
COVERED_EXTENSIONS = ["md", "py", "toml", "yaml"]

# rsync 要排除的四類。
NOISE = [".venv/junk.md", "__pycache__/junk.md", ".pytest_cache/junk.md", ".DS_Store"]

# 六類內部指涉，各一個代表值。
INTERNAL = [
    "我們在 Tagtoo 的流程",  # 公司名
    "project `tagtoo-staging`",  # GCP project
    "（`internal-cli-desktop`，Desktop app）",  # OAuth client 名
    "鮮乳坊 6 月零售報告",  # 客戶名
    "見 `~/thoughts/global/shared/decisions/foo.md`",  # 私有 thoughts 路徑
    "負責人：Fredrick",  # 真人名
]

# 長得像但不該被攔的。`Markdown` 是這裡唯一真正危險的近似字 —— 只要 guard 拿
# `Mark` 當人名 pattern，整份繁中 markdown 語料每一頁都會誤報。
LOOKALIKES = ["這是一份 Markdown 文件", "完全乾淨的內容"]


def _qid(value: str) -> str:
    """可被 pytest 再次選取的 node id。**不是** `repr(value)`。

    自己供的 `ids=` 只要含反斜線或非 ASCII，pytest 就選不回來（exit 4），mutmut 會把
    那個 exit 4 記成 `killed`，印出假的全綠。這個 skill 的語料是繁中 markdown，必踩。
    完整實測紀錄見 gdoc-mcp `tests/unit/test_text.py::_qid`。
    """
    return repr(value).encode("ascii", "backslashreplace").decode().replace("\\", "-")


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """跑腳本。cwd 固定在 `/`，順帶釘住「目的地不從 cwd 推」。"""
    return subprocess.run(
        [str(script), *args], capture_output=True, text=True, cwd="/"
    )


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """一份丟棄式的假 repo，`bin/` 裡是腳本的複本。回傳假 repo 根目錄。

    目的地由腳本自身位置推得，所以複製腳本是唯一能在不寫進真實工作樹的前提下
    跑同步路徑的方法。
    """
    (tmp_path / "bin").mkdir()
    shutil.copy2(SCRIPT, tmp_path / "bin" / SCRIPT.name)
    return tmp_path


def make_src(root: Path, **files: str) -> Path:
    """建一個看起來像安裝目錄的 SRC（有 SKILL.md），外加指定內容的檔案。"""
    src = root / "src"
    for rel, text in {"SKILL.md": "hello\n", **files}.items():
        path = src / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return src


def snapshot(root: Path) -> dict[str, tuple[str, int]]:
    return {
        str(p.relative_to(root)): (p.read_text(encoding="utf-8"), p.stat().st_mtime_ns)
        for p in root.rglob("*")
        if p.is_file()
    }


# --------------------------------------------------------------------------
# guard —— `--check DIR`，不寫檔案
# --------------------------------------------------------------------------


@pytest.mark.parametrize("line", INTERNAL, ids=[_qid(s) for s in INTERNAL])
def test_guard_rejects_each_internal_reference_category(tmp_path: Path, line: str):
    """六類內部指涉每一類都要回 2，且命中行要印在 stdout。

    刪掉這條 → pattern 寫錯（BSD grep 的 `\\?`、少一類、正規表示式打錯）會偽裝成
    「內容乾淨」，整道 guard 變成裝飾品。
    """
    (tmp_path / "probe.md").write_text(line + "\n", encoding="utf-8")

    result = run(SCRIPT, "--check", str(tmp_path))

    assert result.returncode == 2
    assert f"{tmp_path / 'probe.md'}:1:{line}" in result.stdout


@pytest.mark.parametrize("line", LOOKALIKES, ids=[_qid(s) for s in LOOKALIKES])
def test_guard_does_not_fire_on_lookalikes(tmp_path: Path, line: str):
    """乾淨內容要回 0，`Markdown` 不能被人名 pattern 配到。

    刪掉這條 → pattern 放寬到 `Mark` 之類的子字串也算過，guard 每次都紅，
    最後被人加 `|| true` 繞過。
    """
    (tmp_path / "probe.md").write_text(line + "\n", encoding="utf-8")

    result = run(SCRIPT, "--check", str(tmp_path))

    assert result.returncode == 0
    assert "（無）" in result.stdout


@pytest.mark.parametrize("ext", COVERED_EXTENSIONS)
def test_guard_scans_every_covered_extension_recursively(tmp_path: Path, ext: str):
    """`*.md` `*.py` `*.toml` `*.yaml` 四種都要掃，而且要遞迴進子目錄。

    刪掉這條 → 副檔名清單少一種、或 glob 只掃頂層，內部指涉從那個縫隙漏出去。
    """
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / f"probe.{ext}").write_text("Tagtoo\n", encoding="utf-8")

    assert run(SCRIPT, "--check", str(tmp_path)).returncode == 2


def test_guard_warning_goes_to_stderr_hits_to_stdout(tmp_path: Path):
    """警告在 stderr，命中行在 stdout —— 兩條流不能互換。

    刪掉這條 → 全部印到同一條流也會過，而只收 stdout 的 CI 就再也看不到警告。
    """
    (tmp_path / "probe.md").write_text("Tagtoo\n", encoding="utf-8")

    result = run(SCRIPT, "--check", str(tmp_path))

    assert "⚠️" in result.stderr
    assert "⚠️" not in result.stdout
    assert "probe.md:1:" in result.stdout


def test_check_is_read_only_and_quiet(tmp_path: Path):
    """`--check` 不動任何檔案，也不印 BETA 警告與 rsync 區段。

    刪掉這條 → `--check` 掉進同步分支（或順手跑去識別化改寫檔案），
    使用者以為只是掃一下，工作樹已經被改掉。
    """
    (tmp_path / "probe.md").write_text("project `tagtoo-staging`\n", encoding="utf-8")
    before = snapshot(tmp_path)

    result = run(SCRIPT, "--check", str(tmp_path))

    assert snapshot(tmp_path) == before
    assert "BETA" not in result.stdout
    assert ">f" not in result.stdout


def test_check_on_a_missing_directory_must_not_report_clean(tmp_path: Path):
    """不存在的目錄不該被判成乾淨。

    這條**目前是紅的**（實測回 0 ＋「（無）」）。它跟本票點名的 BSD grep 陷阱是同一
    個失敗類別：命中集合為空被讀成「內容乾淨」。路徑打錯或目錄搬走之後，`--check`
    會永遠綠。修法屬於棒③。
    """
    assert run(SCRIPT, "--check", str(tmp_path / "does-not-exist")).returncode != 0


# --------------------------------------------------------------------------
# 同步 —— 假 repo 沙箱
# --------------------------------------------------------------------------


def test_sync_mirrors_src_into_the_script_relative_skill_dir(sandbox: Path):
    """目的地是腳本旁邊的 `skills/comms/generate-meeting-notes`，且是鏡像（會刪）。

    刪掉這條 → 目的地改從 cwd 或第二個參數推（跑起來寫錯地方），或掉了 `--delete`
    （安裝版刪掉的檔案在 repo 裡留成殭屍，「比對無差異」這條驗收條件就假了）。
    """
    src = make_src(sandbox, **{"sub/notes.md": "content\n"})
    dest = sandbox / DEST_REL
    dest.mkdir(parents=True)
    (dest / "OLD.md").write_text("stale\n", encoding="utf-8")

    result = run(sandbox / "bin" / SCRIPT.name, str(src))

    assert result.returncode == 0
    assert (dest / "sub" / "notes.md").read_text(encoding="utf-8") == "content\n"
    assert not (dest / "OLD.md").exists()


@pytest.mark.parametrize("noise", NOISE)
def test_sync_excludes_noise(sandbox: Path, noise: str):
    """`.venv/` `__pycache__/` `.pytest_cache/` `.DS_Store` 一律不同步。

    刪掉這條 → 少一條 `--exclude`，整包 venv 或編譯殘骸被 commit 進 public repo。
    （安裝版的 `tests/` 現在就只剩 `.pyc`，正是這個縫隙。）
    """
    src = make_src(sandbox, **{noise: "x\n"})

    run(sandbox / "bin" / SCRIPT.name, str(src))

    assert not (sandbox / DEST_REL / noise).exists()


def test_sync_deidentifies_so_the_guard_passes(sandbox: Path):
    """去識別化在 guard 之前跑，把內部字串換成佔位符。

    刪掉這條 → 去識別化被拿掉也不會有人發現方向：guard 會紅，但紅的原因看起來
    像「安裝版有髒東西」而不是「替換沒跑」。這條把替換後的值直接釘死。
    """
    src = make_src(
        sandbox,
        **{"t.md": "project `tagtoo-staging` and `internal-cli-desktop`\n"},
    )

    result = run(sandbox / "bin" / SCRIPT.name, str(src))

    assert result.returncode == 0
    assert (sandbox / DEST_REL / "t.md").read_text(encoding="utf-8") == (
        "project `<your-gcp-project>` and `<your-oauth-client-name>`\n"
    )


def test_guard_hit_does_not_roll_back_the_sync(sandbox: Path):
    """guard 命中回 2，但檔案已經同步到工作樹 —— guard 只拒絕 commit，不還原。

    刪掉這條 → 改成命中就 rollback，使用者拿不到那份「差一點就好」的內容，
    得手動重跑並猜哪裡髒；或反過來，同步根本沒發生卻回 2。
    """
    src = make_src(sandbox, **{"dirty.md": "我們在 Tagtoo\n"})

    result = run(sandbox / "bin" / SCRIPT.name, str(src))

    assert result.returncode == 2
    assert (sandbox / DEST_REL / "dirty.md").read_text(encoding="utf-8") == "我們在 Tagtoo\n"


@pytest.mark.parametrize("kind", ["missing", "no-skill-md"])
def test_bad_src_exits_1_and_leaves_dest_untouched(sandbox: Path, kind: str):
    """SRC 不像安裝目錄 → exit 1 ＋ stderr 訊息，而且**不能碰目的地**。

    刪掉這條 → 前置檢查掉了，`rsync --delete` 拿一個空的或不存在的 SRC 去鏡像，
    整個 repo 版 skill 被清空。這是本腳本唯一會造成資料損失的路徑。
    """
    src = sandbox / "src"
    if kind == "no-skill-md":
        src.mkdir()
    dest = sandbox / DEST_REL
    dest.mkdir(parents=True)
    (dest / "keep.md").write_text("keep\n", encoding="utf-8")

    result = run(sandbox / "bin" / SCRIPT.name, str(src))

    assert result.returncode == 1
    assert str(src) in result.stderr
    assert (dest / "keep.md").read_text(encoding="utf-8") == "keep\n"


def test_default_src_is_home_agents_skill_dir(sandbox: Path, monkeypatch):
    """不給參數時 SRC 預設 `$HOME/.agents/skills/generate-meeting-notes`。

    刪掉這條 → 預設路徑寫錯（少一層、拼錯 skill 名）只會在「沒給參數」時才炸，
    而那正是日常唯一的用法。
    """
    home = sandbox / "home"
    installed = home / ".agents" / "skills" / "generate-meeting-notes"
    installed.mkdir(parents=True)
    (installed / "SKILL.md").write_text("from default src\n", encoding="utf-8")

    result = subprocess.run(
        [str(sandbox / "bin" / SCRIPT.name)],
        capture_output=True,
        text=True,
        cwd="/",
        env={"HOME": str(home), "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
    )

    assert result.returncode == 0
    assert (sandbox / DEST_REL / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "from default src\n"
