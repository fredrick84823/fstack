"""發佈流程結束後的漂移偵測 —— `report_drift` 掛在 `main()` 尾巴上的那一刀（#17）。

裁決是「發佈結束才比對」：那時編輯已經停了，此刻的漂移是真漂移。所以驗收條件講的是
**發佈流程的 stdout 與退出碼**，這支就從 `main()` 跑，不是直接呼叫 `report_drift`。

**不打網路、不碰安裝版。** Drive 與 config 用替身、Slack 用 `--no-slack`、歸檔換成
不寫檔的替身；比對那一步把 `parity.sync_diff` 換掉 —— 這支問的是「發佈流程拿比對結果
做了什麼」，比對自己怎麼做的在 `test_sync_diff.py`（那裡跑真的腳本，來源與目的地全在
`tmp_path` 底下）。

替身要掛在 `sys.modules["parity"]` 那顆模組物件上：`create_gdoc_from_md` 是
`from parity import report_drift` 拿到函式的，函式的 globals 就是那顆模組的 dict，
換掉 dict 裡的 `sync_diff` 才換得掉 `report_drift` 實際會呼叫的那一個。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/comms/generate-meeting-notes/scripts"
sys.path.insert(0, str(SCRIPTS))

import create_gdoc_from_md as publish  # noqa: E402
import parity  # noqa: E402  與 publish 綁的是同一顆模組物件

DOC_URL = "https://docs.google.com/document/d/abc123/edit"
DONE = "✅ 完成"
SKIPPED = "ℹ️  漂移比對跳過："
DRIFTED = ["SKILL.md", "scripts/parity.py"]
MEETING = {"series_name": "PM會議", "folder_name": "週三_PM_會議", "folder_id": "fid", "attendees": []}


@pytest.fixture
def publish_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    """跑一次 `main()`，回傳 (退出碼, stdout)。

    `diff=` 是 `sync_diff` 的替身，簽章與真貨相同 `(installed, repo) -> list[str]`；
    丟例外的替身用來驗「比對自己壞掉」那條路徑。
    """
    repo = tmp_path / "fstack"
    (repo / "bin").mkdir(parents=True)
    (repo / parity.SYNC_SCRIPT).write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    def run(diff):
        content_file = tmp_path / "meeting_notes.md"
        content_file.write_text("# 會議記錄\n\n內容\n", encoding="utf-8")

        monkeypatch.setattr(
            publish,
            "load_config",
            lambda: {"meetings": {"pm": MEETING}, "fstack_repo": str(repo)},
        )
        monkeypatch.setattr(
            publish, "create_gdoc_in_shared_drive", lambda *a, **kw: (DOC_URL, "date-folder-id")
        )
        monkeypatch.setattr(
            publish,
            "write_local_archive",
            lambda *a, **kw: (tmp_path / "note.md", tmp_path / "note.meta.json"),
        )
        monkeypatch.setattr(parity, "sync_diff", diff)
        monkeypatch.setattr(sys, "argv", [
            "create_gdoc_from_md.py",
            "--meeting", "pm",
            "--date", "20260708",
            "--content-file", str(content_file),
            "--no-slack",
        ])

        code = 0
        try:
            publish.main()
        except SystemExit as exc:  # 正常路徑不會走到這裡，走到了就是退出碼不是 0
            code = exc.code or 0
        return code, capsys.readouterr().out

    return run


# --------------------------------------------------------------------------
# 驗收條件 1／3 —— 一致就閉嘴
# --------------------------------------------------------------------------


def test_no_drift_prints_no_warning_and_exits_zero(publish_once):
    """驗收條件 1 ＋ 3：兩邊一致時，發佈輸出裡不該出現警告，退出碼 0。

    刪掉這條 → 警告變成每次發佈都印（例如「沒有差異」被寫成印一個空清單的警告），
    使用者學會忽略它，真的漂移時也不會看。

    「比對跳過」那行同理：比對成功就不該出現，否則它會變成每次發佈都有的噪音，
    真的跳過時沒人分得出來。
    """
    code, out = publish_once(lambda installed, repo: [])

    assert parity.DRIFT_HEADER not in out
    assert SKIPPED not in out
    assert (code, DONE in out) == (0, True)


# --------------------------------------------------------------------------
# 驗收條件 2／3 —— 漂了就講，並且講怎麼掉齊
# --------------------------------------------------------------------------


def test_drift_prints_the_warning_and_still_exits_zero(publish_once):
    """驗收條件 2 ＋ 3：有差異時印警告 ＋ `bin/sync-to-installed.sh`，退出碼仍是 0。

    刪掉這條 → 整個偵測被拿掉也不會有人發現（沒有輸出的功能跟不存在一樣）；
    或者反過來，漂移被當成錯誤回非零，把一個已經成功的發佈弄成看起來失敗。
    """
    code, out = publish_once(lambda installed, repo: DRIFTED)

    assert parity.DRIFT_HEADER in out
    assert str(parity.FIX_SCRIPT) in out
    assert (code, DONE in out) == (0, True)


def test_the_drifted_paths_are_the_ones_that_get_printed(publish_once):
    """印出來的是比對回來的那幾個路徑，不是一句籠統的「有漂移」。

    刪掉這條 → 警告印得出來但內容是空的／固定的，使用者得自己重跑一次同步腳本
    才知道漂在哪。
    """
    _, out = publish_once(lambda installed, repo: DRIFTED)

    assert [p for p in DRIFTED if p in out] == DRIFTED


def test_the_warning_comes_after_the_publish_output(publish_once):
    """裁決是「掛在發佈流程**結束後**」—— 警告要在交棒的 `RESULT_*` 之後、`✅ 完成` 之前。

    刪掉這條 → 比對挪到發佈之前（那時編輯還沒結束，漂移不是真漂移），或挪到
    `RESULT_*` 中間，把靠 stdout 解析交棒的下游弄壞。
    """
    _, out = publish_once(lambda installed, repo: DRIFTED)

    assert out.index("RESULT_URL") < out.index(parity.DRIFT_HEADER) < out.index(DONE)


# --------------------------------------------------------------------------
# 比對本身失敗 —— 附屬品不該弄髒主流程，但也不能靜靜消失
# --------------------------------------------------------------------------

BROKEN = [RuntimeError("rsync 跑不完"), OSError(13, "Permission denied")]


def _raiser(exc: BaseException):
    """簽章與 `sync_diff` 相同、只會丟例外的替身。"""

    def boom(installed, repo):
        raise exc

    return boom


@pytest.mark.parametrize("exc", BROKEN, ids=[type(e).__name__ for e in BROKEN])
def test_a_broken_comparison_does_not_make_a_successful_publish_look_failed(publish_once, exc):
    """比對炸了時退出碼還是 0、`RESULT_URL` 照樣交出去，也不會冒出漂移警告。

    Doc 已經發出去了，URL 只有此刻拿得到。這支是發佈的附屬品，它自己壞掉不該讓
    `main()` 拋例外 —— 刪掉這條 → 一支壞掉的同步腳本會讓每次發佈都以 traceback 收場。
    `OSError` 那一組是真實情境：`~/.config` 讀不到時例外從子行程那層冒上來。
    """
    code, out = publish_once(_raiser(exc))

    assert parity.DRIFT_HEADER not in out
    assert f"RESULT_URL: {DOC_URL}" in out
    assert (code, DONE in out) == (0, True)


@pytest.mark.parametrize("exc", BROKEN, ids=[type(e).__name__ for e in BROKEN])
def test_a_skipped_comparison_says_so_and_names_the_reason(publish_once, exc):
    """比對跳過時要印一行，而且帶著例外型別與訊息。

    #14 點名的陷阱：一台沒建 `~/.config/generate-meeting-notes/` 的機器，同步腳本以 1
    收場，漂移偵測**永遠不叫**。靜默的 except 讓那件事沒有任何症狀 —— 刪掉這條 →
    偵測在整個團隊的機器上死掉半年都不會有人發現。
    """
    _, out = publish_once(_raiser(exc))
    lines = out.splitlines()

    assert f"{SKIPPED}{type(exc).__name__}: {exc}" in lines
    assert lines[lines.index(f"{SKIPPED}{type(exc).__name__}: {exc}") - 1] == ""


# --------------------------------------------------------------------------
# 驗收條件 4 —— 本機沒有安裝版
# --------------------------------------------------------------------------
#
# 這幾條直接呼叫 `report_drift`：`installed` 的預設值是 import 時就綁死的 `SKILL_DIR`
# （= 這支 skill 自己的目錄），從 `main()` 跑改不掉它，而改得掉的唯一辦法是去碰
# `~/.agents` —— 那是 integration 的領域。`sync_diff` 這裡用真貨：兩邊都指向
# tmp_path，它在「不像安裝目錄」就回空清單，不會跑到子行程那一步。


def test_a_missing_installed_copy_is_silent_not_an_error(tmp_path: Path, capsys):
    """驗收條件 4：本機沒有安裝版目錄時不炸、不印警告。

    「沒有安裝版」與「安裝版一致」在呼叫端是同一件事：沒東西要講。
    刪掉這條 → 同事 clone 下來沒裝過這個 skill，每次發佈都吃一個例外或一段
    看不懂的警告。
    """
    report = parity.report_drift(
        {"fstack_repo": str(tmp_path / "fstack")}, installed=tmp_path / "not-installed"
    )

    assert report is None
    assert capsys.readouterr().out == ""


def test_the_fstack_location_comes_only_from_the_config_key(tmp_path: Path, monkeypatch, capsys):
    """fstack 的位置只認 config 的 `fstack_repo`，沒設定就不比對 —— 不會自己往上找。

    刪掉這條 → 改成從 cwd 往上爬找 `.git`，發佈流程在任何一個不相干的 repo 底下
    跑都會拿那個 repo 當 fstack，印出一整串假漂移。
    """
    called: list[tuple] = []
    monkeypatch.setattr(parity, "sync_diff", lambda installed, repo: called.append((installed, repo)) or [])

    for config in ({}, {"meetings": {}}):
        parity.report_drift(config, installed=tmp_path)

    assert called == []
    assert capsys.readouterr().out == ""


def test_the_configured_repo_is_the_one_compared_against(tmp_path: Path, monkeypatch, capsys):
    """設定了就要真的用它 —— 傳進 `sync_diff` 的 repo 就是 config 裡那個值。

    刪掉這條 → key 讀錯或值被忽略（永遠比對一個寫死的路徑），比對永遠回空清單，
    整道偵測靜靜地變成裝飾品。
    """
    seen: list[tuple] = []
    monkeypatch.setattr(parity, "sync_diff", lambda installed, repo: seen.append((installed, repo)) or [])

    parity.report_drift({"fstack_repo": str(tmp_path / "fstack")}, installed=tmp_path / "installed")

    assert seen == [(tmp_path / "installed", tmp_path / "fstack")]
    assert capsys.readouterr().out == ""
