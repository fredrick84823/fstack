"""`bin/sync-from-installed.sh` 的黑箱測試 —— 只斷言退出碼、stdout/stderr、檔案系統。

腳本的目的地是從**它自己的位置**推出來的，不吃參數。所以要在不動真實工作樹的前提下
測同步路徑，唯一的辦法是把腳本複製進 `tmp_path` 底下的假 repo（`sandbox` fixture），
讓它把東西同步到那份假 repo 的 `skills/comms/generate-meeting-notes`。

guard 的測試不需要假 repo —— `--check DIR` 不寫任何檔案，直接指向 `tmp_path` 即可。

**為什麼 guard 一定要有正向案例**：BSD `grep` 不吃 `\\?`。pattern 寫錯的症狀是「掃出來
乾淨」，跟「內容真的乾淨」在退出碼上完全一樣。所以「guard 回 0」沒有鑑別力，每一類
內部指涉都必須有一條「塞進去會回 2」的測試，外加一條證明它不會誤報。

**pattern 與替換表都是使用者資料，不在 repo 裡。** 腳本讀
`$HOME/.config/generate-meeting-notes/{guard-patterns.txt,sanitize.sed}`。測試自己造一份
假的（`home` fixture）並改寫 `HOME`，所以下面每個字串都是虛構的 —— 測的是三類 pattern
的**機制**（大小寫、word boundary、副檔名涵蓋），不是任何一份真清單的內容。
"""

from __future__ import annotations

import os
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

# 假的 pattern 清單。三類前綴各兩筆，外加註解、空行、與一行空 pattern（都必須被忽略）。
GUARD_PATTERNS = """\
# 這行是註解，不是 pattern

w:
w:Zorblax
w:客戶甲
iw:acmecorp
iw:widget-desktop
i:private-notes/
i:Open Sesame
"""

# 假的去識別化替換表。
SANITIZE_RULES = """\
# 這行是註解
s/`widget-desktop`/`<your-oauth-client-name>`/g
s/example-gcp-project/<your-gcp-project>/g
"""

# 六類內部指涉，各一個代表值 —— 對應上面六條 pattern。
INTERNAL = [
    "負責人：Zorblax",  # w：人名，大小寫敏感 ＋ word boundary
    "客戶甲 6 月零售報告",  # w：客戶名
    "我們在 AcmeCorp 的流程",  # iw：公司名，大小寫不敏感
    "（`widget-desktop`，Desktop app）",  # iw：OAuth client 名
    "見 `~/private-notes/global/foo.md`",  # i：路徑，加了 boundary 就配不到
    "這題在 open sesame 提過",  # i：含空白的片語，大小寫不敏感
]

# 長得像但不該被攔的。`Markdown` 是這裡唯一真正危險的近似字 —— 只要 guard 拿
# `Mark` 當人名 pattern，整份繁中 markdown 語料每一頁都會誤報。
LOOKALIKES = [
    "這是一份 Markdown 文件",
    "Zorblaxian 不是人名",  # w 掉了 word boundary 就會誤報（真實對應：Mark ⊂ Markdown）
    "acmecorporation 的年報",  # iw 掉了 word boundary 就會誤報
    "zorblax 全小寫不是人名",  # w 改成大小寫不敏感就會誤報
    "完全乾淨的內容",
]


def _qid(value: str) -> str:
    """可被 pytest 再次選取的 node id。**不是** `repr(value)`。

    自己供的 `ids=` 只要含反斜線或非 ASCII，pytest 就選不回來（exit 4），mutmut 會把
    那個 exit 4 記成 `killed`，印出假的全綠。這個 skill 的語料是繁中 markdown，必踩。
    完整實測紀錄見 gdoc-mcp `tests/unit/test_text.py::_qid`。
    """
    return repr(value).encode("ascii", "backslashreplace").decode().replace("\\", "-")


def write_conf(
    root: Path, *, patterns: str | None = GUARD_PATTERNS, sanitize: str | None = SANITIZE_RULES
) -> Path:
    """在 `root` 底下鋪一份假的使用者設定，回傳可以當 `HOME` 用的路徑。

    傳 `None` 表示「這個設定檔不存在」。
    """
    conf = root / ".config" / "generate-meeting-notes"
    conf.mkdir(parents=True, exist_ok=True)
    if patterns is not None:
        (conf / "guard-patterns.txt").write_text(patterns, encoding="utf-8")
    if sanitize is not None:
        (conf / "sanitize.sed").write_text(sanitize, encoding="utf-8")
    return root


@pytest.fixture
def home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """設定齊全的假 `HOME`。刻意不放在 `tmp_path` 底下 —— 被掃描的目錄就是 `tmp_path`。"""
    return write_conf(tmp_path_factory.mktemp("home"))


def run(script: Path, *args: str, home: Path) -> subprocess.CompletedProcess[str]:
    """跑腳本。cwd 固定在 `/`，順帶釘住「目的地不從 cwd 推」。"""
    return subprocess.run(
        [str(script), *args],
        capture_output=True,
        text=True,
        cwd="/",
        env={**os.environ, "HOME": str(home)},
    )


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """一份丟棄式的假 repo，`bin/` 裡是腳本的複本。回傳假 repo 根目錄。

    目的地由腳本自身位置推得，所以複製腳本是唯一能在不寫進真實工作樹的前提下
    跑同步路徑的方法。範例設定檔也一起複製 —— 「未設定」的錯誤訊息會指向它們。
    """
    (tmp_path / "bin").mkdir()
    for name in (SCRIPT.name, "guard-patterns.example.txt", "sanitize.example.sed"):
        shutil.copy2(REPO / "bin" / name, tmp_path / "bin" / name)
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
def test_guard_rejects_each_internal_reference_category(tmp_path: Path, home: Path, line: str):
    """六類內部指涉每一類都要回 2，且命中行要印在 stdout。

    刪掉這條 → pattern 寫錯（BSD grep 的 `\\?`、少一類、正規表示式打錯）會偽裝成
    「內容乾淨」，整道 guard 變成裝飾品。
    """
    (tmp_path / "probe.md").write_text(line + "\n", encoding="utf-8")

    result = run(SCRIPT, "--check", str(tmp_path), home=home)

    assert result.returncode == 2
    assert f"{tmp_path / 'probe.md'}:1:{line}" in result.stdout


@pytest.mark.parametrize("line", LOOKALIKES, ids=[_qid(s) for s in LOOKALIKES])
def test_guard_does_not_fire_on_lookalikes(tmp_path: Path, home: Path, line: str):
    """乾淨內容要回 0，`Markdown` 不能被人名 pattern 配到。

    刪掉這條 → pattern 放寬到 `Mark` 之類的子字串也算過，guard 每次都紅，
    最後被人加 `|| true` 繞過。
    """
    (tmp_path / "probe.md").write_text(line + "\n", encoding="utf-8")

    result = run(SCRIPT, "--check", str(tmp_path), home=home)

    assert result.returncode == 0
    assert "（無）" in result.stdout


@pytest.mark.parametrize("ext", COVERED_EXTENSIONS)
def test_guard_scans_every_covered_extension_recursively(tmp_path: Path, home: Path, ext: str):
    """`*.md` `*.py` `*.toml` `*.yaml` 四種都要掃，而且要遞迴進子目錄。

    刪掉這條 → 副檔名清單少一種、或 glob 只掃頂層，內部指涉從那個縫隙漏出去。
    """
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / f"probe.{ext}").write_text("AcmeCorp\n", encoding="utf-8")

    assert run(SCRIPT, "--check", str(tmp_path), home=home).returncode == 2


def test_guard_warning_goes_to_stderr_hits_to_stdout(tmp_path: Path, home: Path):
    """警告在 stderr，命中行在 stdout —— 兩條流不能互換。

    刪掉這條 → 全部印到同一條流也會過，而只收 stdout 的 CI 就再也看不到警告。
    """
    (tmp_path / "probe.md").write_text("AcmeCorp\n", encoding="utf-8")

    result = run(SCRIPT, "--check", str(tmp_path), home=home)

    assert "⚠️" in result.stderr
    assert "⚠️" not in result.stdout
    assert "probe.md:1:" in result.stdout


def test_check_is_read_only_and_quiet(tmp_path: Path, home: Path):
    """`--check` 不動任何檔案，也不印 BETA 警告與 rsync 區段。

    刪掉這條 → `--check` 掉進同步分支（或順手跑去識別化改寫檔案），
    使用者以為只是掃一下，工作樹已經被改掉。
    """
    (tmp_path / "probe.md").write_text("project example-gcp-project\n", encoding="utf-8")
    before = snapshot(tmp_path)

    result = run(SCRIPT, "--check", str(tmp_path), home=home)

    assert snapshot(tmp_path) == before
    assert "BETA" not in result.stdout
    assert ">f" not in result.stdout


def test_check_on_a_missing_directory_must_not_report_clean(tmp_path: Path, home: Path):
    """不存在的目錄不該被判成乾淨 —— 回 1（環境錯誤），訊息走 stderr。

    這跟本票點名的 BSD grep 陷阱是同一個失敗類別：命中集合為空被讀成「內容乾淨」。
    刪掉這條 → 路徑打錯或目錄搬走之後，`--check` 會永遠綠。
    """
    missing = tmp_path / "does-not-exist"

    result = run(SCRIPT, "--check", str(missing), home=home)

    assert result.returncode == 1
    assert str(missing) in result.stderr
    assert "（無）" not in result.stdout


# --------------------------------------------------------------------------
# guard 的設定檔 —— 沒設定不等於乾淨
# --------------------------------------------------------------------------


def test_guard_refuses_when_the_pattern_file_is_missing(tmp_path: Path, tmp_path_factory):
    """pattern 檔不存在 → 回 1 並說「未設定」，**不可以**靜默回 0 放行。

    刪掉這條 → 同事 clone 下來沒建設定檔，guard 每次都印「（無）」回 0，
    整道防線在沒人知道的情況下不存在。
    """
    bare = write_conf(tmp_path_factory.mktemp("home"), patterns=None)
    (tmp_path / "probe.md").write_text("AcmeCorp\n", encoding="utf-8")

    result = run(SCRIPT, "--check", str(tmp_path), home=bare)

    assert result.returncode == 1
    assert "未設定" in result.stderr
    assert "guard-patterns.example.txt" in result.stderr
    assert "（無）" not in result.stdout


def test_guard_refuses_when_the_pattern_file_has_no_patterns(tmp_path: Path, tmp_path_factory):
    """只有註解與空行的 pattern 檔 → 一樣回 1。

    刪掉這條 → 空清單掃出零命中，回 0；「沒設定」與「內容乾淨」再次分不出來。
    順帶釘住註解與空行不會被當成 pattern。
    """
    empty = write_conf(tmp_path_factory.mktemp("home"), patterns="# 只有註解\n\n")
    (tmp_path / "probe.md").write_text("AcmeCorp\n", encoding="utf-8")

    result = run(SCRIPT, "--check", str(tmp_path), home=empty)

    assert result.returncode == 1
    assert "未設定" in result.stderr
    assert "（無）" not in result.stdout


def test_sync_refuses_before_touching_anything_when_sanitize_is_missing(
    sandbox: Path, tmp_path_factory
):
    """替換表不存在 → 回 1，而且**在 rsync 之前**擋下來。

    刪掉這條 → 沒有替換表也照跑，內部字串原封不動被 rsync 進 public repo，
    只剩 guard 擋；guard 的 pattern 與替換表是兩份清單，涵蓋範圍不保證相同。
    """
    no_sed = write_conf(tmp_path_factory.mktemp("home"), sanitize=None)
    src = make_src(sandbox, **{"t.md": "project example-gcp-project\n"})
    dest = sandbox / DEST_REL
    dest.mkdir(parents=True)
    (dest / "keep.md").write_text("keep\n", encoding="utf-8")

    result = run(sandbox / "bin" / SCRIPT.name, str(src), home=no_sed)

    assert result.returncode == 1
    assert "未設定" in result.stderr
    assert not (dest / "t.md").exists()
    assert (dest / "keep.md").read_text(encoding="utf-8") == "keep\n"


# --------------------------------------------------------------------------
# 同步 —— 假 repo 沙箱
# --------------------------------------------------------------------------


def test_sync_mirrors_src_into_the_script_relative_skill_dir(sandbox: Path, home: Path):
    """目的地是腳本旁邊的 `skills/comms/generate-meeting-notes`，且是鏡像（會刪）。

    刪掉這條 → 目的地改從 cwd 或第二個參數推（跑起來寫錯地方），或掉了 `--delete`
    （安裝版刪掉的檔案在 repo 裡留成殭屍，「比對無差異」這條驗收條件就假了）。
    """
    src = make_src(sandbox, **{"sub/notes.md": "content\n"})
    dest = sandbox / DEST_REL
    dest.mkdir(parents=True)
    (dest / "OLD.md").write_text("stale\n", encoding="utf-8")

    result = run(sandbox / "bin" / SCRIPT.name, str(src), home=home)

    assert result.returncode == 0
    assert (dest / "sub" / "notes.md").read_text(encoding="utf-8") == "content\n"
    assert not (dest / "OLD.md").exists()


@pytest.mark.parametrize("noise", NOISE)
def test_sync_excludes_noise(sandbox: Path, home: Path, noise: str):
    """`.venv/` `__pycache__/` `.pytest_cache/` `.DS_Store` 一律不同步。

    刪掉這條 → 少一條 `--exclude`，整包 venv 或編譯殘骸被 commit 進 public repo。
    （安裝版的 `tests/` 現在就只剩 `.pyc`，正是這個縫隙。）
    """
    src = make_src(sandbox, **{noise: "x\n"})

    run(sandbox / "bin" / SCRIPT.name, str(src), home=home)

    assert not (sandbox / DEST_REL / noise).exists()


def test_sync_deidentifies_so_the_guard_passes(sandbox: Path, home: Path):
    """去識別化在 guard 之前跑，把內部字串換成佔位符。

    刪掉這條 → 去識別化被拿掉也不會有人發現方向：guard 會紅，但紅的原因看起來
    像「安裝版有髒東西」而不是「替換沒跑」。這條把替換後的值直接釘死。
    """
    src = make_src(
        sandbox,
        **{"t.md": "project example-gcp-project and `widget-desktop`\n"},
    )

    result = run(sandbox / "bin" / SCRIPT.name, str(src), home=home)

    assert result.returncode == 0
    assert (sandbox / DEST_REL / "t.md").read_text(encoding="utf-8") == (
        "project <your-gcp-project> and `<your-oauth-client-name>`\n"
    )


def test_guard_hit_does_not_roll_back_the_sync(sandbox: Path, home: Path):
    """guard 命中回 2，但檔案已經同步到工作樹 —— guard 只拒絕 commit，不還原。

    刪掉這條 → 改成命中就 rollback，使用者拿不到那份「差一點就好」的內容，
    得手動重跑並猜哪裡髒；或反過來，同步根本沒發生卻回 2。
    """
    src = make_src(sandbox, **{"dirty.md": "我們在 AcmeCorp\n"})

    result = run(sandbox / "bin" / SCRIPT.name, str(src), home=home)

    assert result.returncode == 2
    assert (sandbox / DEST_REL / "dirty.md").read_text(encoding="utf-8") == "我們在 AcmeCorp\n"


@pytest.mark.parametrize("kind", ["missing", "no-skill-md"])
def test_bad_src_exits_1_and_leaves_dest_untouched(sandbox: Path, home: Path, kind: str):
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

    result = run(sandbox / "bin" / SCRIPT.name, str(src), home=home)

    assert result.returncode == 1
    assert str(src) in result.stderr
    assert (dest / "keep.md").read_text(encoding="utf-8") == "keep\n"


def test_default_src_is_home_agents_skill_dir(sandbox: Path, home: Path):
    """不給參數時 SRC 預設 `$HOME/.agents/skills/generate-meeting-notes`。

    刪掉這條 → 預設路徑寫錯（少一層、拼錯 skill 名）只會在「沒給參數」時才炸，
    而那正是日常唯一的用法。
    """
    installed = home / ".agents" / "skills" / "generate-meeting-notes"
    installed.mkdir(parents=True)
    (installed / "SKILL.md").write_text("from default src\n", encoding="utf-8")

    result = run(sandbox / "bin" / SCRIPT.name, home=home)

    assert result.returncode == 0
    assert (sandbox / DEST_REL / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "from default src\n"
