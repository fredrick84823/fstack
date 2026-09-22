"""`scripts/reconcile_drive.py` 的黑箱測試（issue #25）—— 只碰公開介面，不打網路。

這支是**無人看管**跑的，所以斷言的重心不在「成功那條路」，而在四種靜靜地做錯事的形狀：

- **多算一場**（窗的邊界、`is_note` 的兩個條件、上限的切法）。代價不對稱 —— 少算一場
  只是晚一小時，多算一場是重跑 NotebookLM 並覆寫既有記錄。所以 `0 <= delta <
  WINDOW_DAYS` 的**兩側**、`limit` 與 `limit + 1` 都各有 case；只測「在窗內」那一側
  等於沒測邊界。
- **該擋沒擋**（首次執行、NotebookLM 認證、憑證）。這幾條的斷言一律是「**沒有**東西被
  叫起來」：`rd.run` 一次都沒被呼叫、`rd.generate` 一次都沒被呼叫。只驗「擋下來時退出碼
  非 0」的話，「印完訊息照樣往下切音訊」照樣全綠。
- **把 Drive 上的原件動到**。音檔歸屬與發佈流程相反：Drive 是原件、本機只是暫存。所以
  這裡驗兩件外部可觀察的事 —— 暫存目錄跑完真的不見了，而 Drive client 上沒有任何
  delete／trash 呼叫被送出。
- **佈線掉了**。純函式沒掛進 mutation 範圍就是量不到它，而那不會讓任何測試變紅。

**子行程與 Drive 一律換成替身，斷言打在送出去的參數上**，不是替身的回傳值：
發佈那步不帶 `--audio-file` / `--delete-local-audio`（帶了會把暫存那份再上傳一次，在同
一個資料夾裡變成第二個音檔）—— 那是一個**參數**層的事實，斷言回傳的 URL 看不見它。

Drive client 用 `googleapiclient.discovery.build` 這個替身注入，而 `scan_drive` 的替身
會把拿到的 client 記下來對帳：注入沒生效的話那顆真的 client 會去打網路，而症狀會是逾時
不是紅燈。
"""

from __future__ import annotations

import ast
import copy
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.unit.conftest import ROOT, SCRIPTS, _qid, load_script, sent_kwargs

rd = load_script("reconcile_drive")

TODAY = "20260915"
DOC_URL = "https://docs.google.com/document/d/abc123/edit"

DATA_FOLDER = "週一週四_Data_內會"
PM_FOLDER = "週三_PM_會議"
KNOWN = {DATA_FOLDER: "data", PM_FOLDER: "pm"}

CONFIG = {
    "slack_dm_user": "U0DEADBEEF",
    "meetings": {
        "data": {
            "series_name": "Data內會",
            "folder_name": DATA_FOLDER,
            "folder_id": "series-data",
            "attendees": [],
        },
        "pm": {
            "series_name": "PM會議",
            "folder_name": PM_FOLDER,
            "folder_id": "series-pm",
            "attendees": [],
        },
    },
}


# --------------------------------------------------------------------------- helpers


def _shift(days: int, base: str = TODAY) -> str:
    """`base` 往前 `days` 天的 YYYYMMDD。"""
    d = date(int(base[:4]), int(base[4:6]), int(base[6:8])) - timedelta(days=days)
    return d.strftime("%Y%m%d")


def _audio(name: str = "錄音.m4a", fid: str = "audio-1") -> dict:
    return {"id": fid, "name": name, "mimeType": "audio/mp4"}


def _note() -> dict:
    return {"id": "note-1", "name": "會議記錄_Data內會_20260915", "mimeType": rd.DOC_MIME}


def _folder(
    series: str,
    days_ago: int = 0,
    files: tuple[dict, ...] = (),
    instance: str = "",
) -> dict:
    """一筆 `scan_drive` 的輸出。`instance` 非空 → 資料夾名是 `YYYYMMDD_<場次>`。"""
    name = _shift(days_ago)
    return {
        "series": series,
        "name": f"{name}_{instance}" if instance else name,
        "files": list(files),
    }


def _named_folder(series: str, name: str, files: tuple[dict, ...] = ()) -> dict:
    """名字自己指定的一筆 —— 認不得的資料夾名沒有「幾天前」可言。"""
    return {"series": series, "name": name, "files": list(files)}


def _pending_ids(round_) -> list[tuple[str, str]]:
    return [(s.series, s.date) for s in round_.pending]


def _skipped_reasons(round_) -> dict[tuple[str, str], str]:
    return {(s.series, s.date): s.reason for s in round_.skipped}


# --------------------------------------------------------------------- in_window 邊界


#: `(delta, 在不在窗內)`。7 天窗 = 今天起往前數 7 個日期，所以 delta 6 是最後一個 in、
#: delta 7 是第一個 out。未來日期（delta 為負）一律 out —— 打錯的資料夾名不該被當成
#: 今天的會議產一份。
WINDOW_CASES = [(0, True), (1, True), (6, True), (7, False), (8, False), (-1, False), (-30, False)]


@pytest.mark.parametrize(
    "delta,expected", WINDOW_CASES, ids=[_qid(f"d{d}") for d, _ in WINDOW_CASES]
)
def test_in_window_has_both_sides_of_the_seven_day_boundary(delta, expected):
    assert rd.in_window(_shift(delta), TODAY) is expected


BAD_DATES = ["202609xx", "", "2026-09-15", "20261332", "會議"]


@pytest.mark.parametrize("folder_date", BAD_DATES, ids=[_qid(b) for b in BAD_DATES])
def test_in_window_refuses_an_unparsable_folder_name_without_raising(folder_date):
    """資料夾名是別人打的。一個 `202609xx` 不該讓整輪 reconcile 掛掉。"""
    assert rd.in_window(folder_date, TODAY) is False


# ------------------------------------------------------------------- is_audio / is_note


AUDIO_NAMES = ["錄音.m4a", "a.MP3", "b.Wav", "c.aac", "d.flac", "e.ogg", "f.opus"]
NOT_AUDIO = ["會議記錄.md", "transcript.txt", "m4a", "錄音.m4a.md", "圖.png"]


@pytest.mark.parametrize("name", AUDIO_NAMES, ids=[_qid(n) for n in AUDIO_NAMES])
def test_is_audio_accepts_every_documented_suffix_case_insensitively(name):
    assert rd.is_audio(name) is True


@pytest.mark.parametrize("name", NOT_AUDIO, ids=[_qid(n) for n in NOT_AUDIO])
def test_is_audio_rejects_everything_else(name):
    assert rd.is_audio(name) is False


def test_is_note_needs_a_google_doc_and_the_prefix():
    """兩個條件都要 —— 少一個的代價方向相反，所以兩邊各一條 case。"""
    assert rd.is_note(_note()) is True


def test_is_note_rejects_a_markdown_file_with_the_note_prefix():
    """只看檔名的話，被人手動丟上來的 `會議記錄_….md` 會讓這場永遠不產。"""
    assert rd.is_note({"id": "x", "name": f"{rd.NOTE_PREFIX}_Data內會_20260915.md",
                       "mimeType": "text/markdown"}) is False


def test_is_note_rejects_any_other_doc_in_the_folder():
    """只看 mimeType 的話，隨手放進去的一份 Doc 會讓這場永遠不產。"""
    assert rd.is_note({"id": "x", "name": "逐字稿草稿", "mimeType": rd.DOC_MIME}) is False


# ------------------------------------------------------------------- compute_pending


def test_a_date_folder_with_audio_and_no_note_is_in_the_delta():
    """驗收條件 ①。"""
    round_ = rd.compute_pending([_folder(DATA_FOLDER, 0, (_audio(),))], KNOWN, TODAY)

    assert _pending_ids(round_) == [(DATA_FOLDER, TODAY)]
    (session,) = round_.pending
    assert session.reason == ""
    assert session.meeting_key == "data"
    assert [f["id"] for f in session.audio] == ["audio-1"]
    assert round_.skipped == []


def test_a_folder_that_already_has_a_note_is_in_neither_list():
    """驗收條件 ② —— 重跑不產生第二份。`skipped` 也不能有它：那會每小時 DM 一次。"""
    folders = [_folder(DATA_FOLDER, 0, (_audio(), _note()))]

    first = rd.compute_pending(folders, KNOWN, TODAY)
    second = rd.compute_pending(folders, KNOWN, TODAY)

    assert first.pending == [] and first.skipped == []
    assert second.pending == [] and second.skipped == []


def test_a_folder_older_than_the_window_is_in_neither_list():
    """驗收條件 ③ —— 有音檔、沒記錄，但過期了就不該再被翻出來。"""
    round_ = rd.compute_pending([_folder(DATA_FOLDER, 7, (_audio(),))], KNOWN, TODAY)

    assert round_.pending == []
    assert round_.skipped == []


def test_the_day_just_inside_the_window_is_still_in_the_delta():
    """③ 的另一側。只有 out 那一條的話，窗被改成 0 天也全綠。"""
    round_ = rd.compute_pending([_folder(DATA_FOLDER, 6, (_audio(),))], KNOWN, TODAY)

    assert _pending_ids(round_) == [(DATA_FOLDER, _shift(6))]


def test_an_unknown_series_folder_is_reported_but_never_generated():
    """驗收條件 ④ —— 缺會議類型脈絡，硬產出來的是壞的。"""
    round_ = rd.compute_pending(
        [_folder("誰的資料夾", 0, (_audio(),))], KNOWN, TODAY
    )

    assert round_.pending == []
    assert _skipped_reasons(round_) == {("誰的資料夾", TODAY): rd.UNKNOWN_SERIES}
    assert round_.skipped[0].meeting_key is None


def test_more_than_the_limit_keeps_the_rest_visible_instead_of_dropping_them():
    """驗收條件 ⑤ —— 上限之外的帶著 `OVER_LIMIT` 進 `skipped`，丟掉的話沒人知道還欠幾場。"""
    folders = [_folder(DATA_FOLDER, n, (_audio(),)) for n in (0, 1, 2)]

    round_ = rd.compute_pending(folders, KNOWN, TODAY, limit=2)

    assert len(round_.pending) == 2
    assert _skipped_reasons(round_) == {(DATA_FOLDER, _shift(0)): rd.OVER_LIMIT}


def test_exactly_the_limit_skips_nothing():
    """⑤ 的另一側：`limit` 與 `limit + 1` 成對，只測超過那側等於沒測邊界。"""
    folders = [_folder(DATA_FOLDER, n, (_audio(),)) for n in (0, 1)]

    round_ = rd.compute_pending(folders, KNOWN, TODAY, limit=2)

    assert len(round_.pending) == 2
    assert round_.skipped == []


def test_the_backlog_is_consumed_oldest_first():
    """新的排前面的話，一場久久沒人處理的會議會永遠排在後面，每輪都被上限擋掉。"""
    folders = [_folder(DATA_FOLDER, n, (_audio(),)) for n in (0, 4, 2)]

    round_ = rd.compute_pending(folders, KNOWN, TODAY, limit=3)

    assert [s.date for s in round_.pending] == [_shift(4), _shift(2), _shift(0)]


def test_a_folder_without_audio_is_in_neither_list():
    """沒有音檔就沒有這場 —— 空的日期資料夾不該每小時 DM 一次。"""
    round_ = rd.compute_pending([_folder(DATA_FOLDER, 0, ())], KNOWN, TODAY)

    assert round_.pending == [] and round_.skipped == []


def test_two_audio_files_in_one_folder_are_reported_instead_of_guessed():
    """挑一個產會讓另一半永遠沒有機會。"""
    folder = _folder(DATA_FOLDER, 0, (_audio(fid="a1"), _audio("錄音2.m4a", fid="a2")))

    round_ = rd.compute_pending([folder], KNOWN, TODAY)

    assert round_.pending == []
    assert _skipped_reasons(round_) == {(DATA_FOLDER, TODAY): rd.MULTI_AUDIO}


def test_compute_pending_does_not_mutate_its_input():
    """純函式 —— 呼叫端（`scan_drive` 的輸出）不該在回來之後長得不一樣。"""
    folders = [_folder(DATA_FOLDER, 0, (_audio(),))]
    before = copy.deepcopy(folders)

    rd.compute_pending(folders, KNOWN, TODAY)

    assert folders == before


# ------------------------------------------------------------------------ series_map


def test_series_map_reads_the_drive_folder_name():
    assert rd.series_map(CONFIG["meetings"]) == {DATA_FOLDER: "data", PM_FOLDER: "pm"}


def test_series_map_falls_back_to_series_name_when_folder_name_is_absent():
    """與 `backfill_local_archive.scan_meeting` 同一條規則 —— 兩支在掃同一批資料夾。"""
    assert rd.series_map({"x": {"series_name": "臨時會"}}) == {"臨時會": "x"}


# ------------------------------------------------------------------- DM 的文字內容


def _session(series: str, reason: str, date_: str = TODAY, instance: str = ""):
    return rd.Session(
        series=series,
        name=f"{date_}_{instance}" if instance else date_,
        date=date_,
        instance=instance,
        meeting_key=None,
        audio=(),
        reason=reason,
    )


def test_over_limit_alone_produces_no_dm():
    """它們下一輪就會被處理。每小時提醒一次只會讓人學會忽略這個 DM。"""
    assert rd.dm_skipped([_session(DATA_FOLDER, rd.OVER_LIMIT)]) == ""


def test_an_unknown_series_produces_a_dm_naming_the_folder():
    text = rd.dm_skipped([_session("誰的資料夾", rd.UNKNOWN_SERIES)])

    assert "誰的資料夾" in text
    assert rd.UNKNOWN_SERIES in text


def test_the_dm_drops_the_over_limit_rows_but_keeps_the_rest():
    """混在一起時「需要人介入的那些」不能被每輪都有的雜訊蓋掉。"""
    text = rd.dm_skipped(
        [_session("誰的資料夾", rd.UNKNOWN_SERIES), _session(DATA_FOLDER, rd.OVER_LIMIT)]
    )

    assert "誰的資料夾" in text
    assert rd.OVER_LIMIT not in text


def test_dm_blocked_stays_quiet_about_a_zero_count():
    """「0 場一場都沒產」讀起來像沒事，而這通 DM 的存在就是因為有事。"""
    text = rd.dm_blocked("NotebookLM 認證過不了", 0)

    assert "NotebookLM 認證過不了" in text
    assert "0" not in text


def test_dm_blocked_says_how_many_were_dropped():
    assert "2" in rd.dm_blocked("Drive API 掛了", 2)


def test_dm_blocked_keeps_the_exception_in_its_own_block():
    """抬頭、摘要、例外三段分開，例外那段包在 code block 裡。

    整段對而不是逐項 `in`：黏成一行、少一個換行、圍欄掉一邊，這幾種都會讓 traceback
    跟上面兩行人話混在一起，而 `in` 一條都看不出來。
    """
    assert rd.dm_blocked("RuntimeError: 流程 B 失敗", 2).splitlines() == [
        rd.DM_HEADER,
        "有一段沒跑完，2 場一場都沒產",
        "",
        "```",
        "RuntimeError: 流程 B 失敗",
        "```",
    ]


# ------------------------------------------------------------------- parse_handoff


def test_parse_handoff_reads_the_result_lines_and_ignores_the_noise():
    stdout = (
        "切成 20 段\n"
        f"RESULT_TRANSCRIPT: /tmp/s/transcript.md\n"
        "這行不是契約\n"
        "RESULT_SERIES_NAME: Data內會\n"
    )

    assert rd.parse_handoff(stdout) == {
        "RESULT_TRANSCRIPT": "/tmp/s/transcript.md",
        "RESULT_SERIES_NAME": "Data內會",
    }


def test_parse_handoff_of_an_empty_stdout_is_empty():
    assert rd.parse_handoff("") == {}


# --------------------------------------------------------------------- prompt_file


def test_prompt_file_prefers_the_configured_one(tmp_path: Path):
    custom = tmp_path / "my-prompt.md"
    custom.write_text("# 版型", encoding="utf-8")

    assert rd.prompt_file({"prompt_path": str(custom)}) == custom


def test_prompt_file_falls_back_when_the_configured_one_is_gone(tmp_path: Path):
    """版型退化是下一份記錄看起來不一樣；沒有版型是這輪一份都產不出來。"""
    result = rd.prompt_file({"prompt_path": str(tmp_path / "不存在.md")})

    assert result.is_file()
    assert result == rd.DEFAULT_PROMPT_PATH


def test_prompt_file_falls_back_when_nothing_is_configured():
    assert rd.prompt_file({}) == rd.DEFAULT_PROMPT_PATH


# ------------------------------------------------------------------ synthesis_prompt


def test_synthesis_prompt_points_at_the_files_instead_of_inlining_them(tmp_path: Path):
    """規格**指路徑不內嵌** —— 內嵌會在 prompt 裡養出一份會漂移的複本。"""
    prompt_path = tmp_path / "default-prompt.md"
    prompt_path.write_text("版型規範的內文不該出現在 prompt 裡", encoding="utf-8")
    notes_path = tmp_path / "notes.md"
    handoff = {
        "RESULT_TRANSCRIPT": str(tmp_path / "transcript.md"),
        "RESULT_EXTRACT": str(tmp_path / "extract.md"),
        "RESULT_CONTEXT": str(tmp_path / "meeting-context.md"),
        "RESULT_HISTORY_INDEX": str(tmp_path / "history-index.md"),
    }

    text = rd.synthesis_prompt(handoff, prompt_path, notes_path)

    for value in handoff.values():
        assert value in text
    assert str(prompt_path) in text
    assert str(notes_path) in text
    assert "版型規範的內文不該出現在 prompt 裡" not in text


# ------------------------------------------------------------------- credential_gap


def test_credential_gap_is_silent_without_a_credentials_file(tmp_path: Path):
    """那條路走 `google.auth.default()`，要嘛成功要嘛拋 —— 不會開瀏覽器。

    順手報告「ADC 沒登入」正是 8/31 的誤判本身。
    """
    assert rd.credential_gap(tmp_path) == ""


def test_credential_gap_is_silent_for_a_service_account(tmp_path: Path):
    (tmp_path / "credentials.json").write_text(
        json.dumps({"type": "service_account", "client_email": "x@y.iam"}), encoding="utf-8"
    )

    assert rd.credential_gap(tmp_path) == ""


def test_credential_gap_blocks_an_oauth_client_with_no_token(tmp_path: Path):
    """排程底下 `flow.run_local_server()` 會**卡住**而不是變紅。"""
    (tmp_path / "credentials.json").write_text(
        json.dumps({"installed": {"client_id": "x", "client_secret": "y"}}), encoding="utf-8"
    )

    assert rd.credential_gap(tmp_path) != ""


# ------------------------------------------------------------------------ main 的閘門


@pytest.fixture
def rig(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """一整輪 main() 的替身：Drive、憑證、設定、子行程、DM 全部換掉。

    `folders` 是要餵給差集的日期資料夾清單，測試自己填。
    """
    rec = SimpleNamespace(
        drive=MagicMock(name="drive"),
        folders=[],
        roots=[],
        scanned=[],
        generated=[],
        workdirs=[],
        dms=[],
        posts=[],
        slack_up=True,
        runs=[],
        config=copy.deepcopy(CONFIG),
        state=tmp_path / "reconcile-state.json",
    )

    monkeypatch.setattr(rd, "credential_gap", lambda *a, **k: "")
    monkeypatch.setattr(rd, "load_config", lambda *a, **k: copy.deepcopy(rec.config))
    monkeypatch.setattr(rd, "get_google_credentials", lambda *a, **k: MagicMock())
    monkeypatch.setattr("googleapiclient.discovery.build", lambda *a, **k: rec.drive)
    monkeypatch.setattr(rd, "notebooklm_gap", lambda *a, **k: "")
    def fake_dm(*a, **k):
        """`send_dm` 回的是「真的送出去了沒有」，替身也要回 —— 少了回傳值，
        `send_once` 會判定沒送成功而不記進狀態檔，於是去重在測試裡看起來永遠是壞的。"""
        rec.dms.append((a, k))
        return rec.slack_up

    monkeypatch.setattr(rd, "send_dm", fake_dm)

    def fake_channel(channel, text):
        """Slack 兩支都是替身。`slack_up=False` 演「送不出去」—— 那時候不能記成發過。"""
        rec.posts.append((channel, text))
        return rec.slack_up

    monkeypatch.setattr(rd, "send_channel", fake_channel)

    def fake_run(cmd, timeout, stdin=None):
        rec.runs.append([str(c) for c in cmd])
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(rd, "run_step", fake_run)

    def fake_scan(drive, meetings, today):
        rec.scanned.append(drive)
        return rd.Scan(copy.deepcopy(rec.folders), copy.deepcopy(rec.roots))

    monkeypatch.setattr(rd, "scan_drive", fake_scan)

    def fake_generate(drive, session, config, workdir):
        workdir = Path(workdir)
        assert workdir.is_dir(), "產製時暫存目錄就該已經在了"
        (workdir / f"{session.date}.m4a").write_bytes(b"AUDIO")
        rec.generated.append(session)
        rec.workdirs.append(workdir)
        return DOC_URL

    monkeypatch.setattr(rd, "generate", fake_generate)
    return rec


def _main(monkeypatch: pytest.MonkeyPatch, rec, *extra: str) -> int:
    monkeypatch.setattr(
        sys,
        "argv",
        ["reconcile_drive.py", "--today", TODAY, "--state", str(rec.state), *extra],
    )
    return rd.main()


def test_the_first_run_prints_the_delta_and_generates_nothing(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """驗收條件 ⑥ —— 沒有狀態檔時強制 dry-run。

    「退出碼 0」不算擋住了：判準寫錯的那一輪照樣會產。所以斷言是**沒有**任何產製流程
    與子行程被叫起來。
    """
    rig.folders = [_folder(DATA_FOLDER, 0, (_audio(),))]

    code = _main(monkeypatch, rig)
    out = capsys.readouterr().out

    assert code == 0
    assert rig.generated == []
    assert rig.runs == []
    assert DATA_FOLDER in out and TODAY in out
    assert rig.state.exists(), "第一輪沒寫狀態檔的話，永遠都是第一輪"


def test_the_second_run_actually_generates(rig, monkeypatch: pytest.MonkeyPatch, capsys):
    rig.folders = [_folder(DATA_FOLDER, 0, (_audio(),))]

    assert _main(monkeypatch, rig) == 0
    code = _main(monkeypatch, rig)
    capsys.readouterr()

    assert code == 0
    assert [(s.series, s.date) for s in rig.generated] == [(DATA_FOLDER, TODAY)]


def test_dry_run_generates_nothing_even_with_a_state_file(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    rig.folders = [_folder(DATA_FOLDER, 0, (_audio(),))]
    _main(monkeypatch, rig)

    code = _main(monkeypatch, rig, "--dry-run")
    capsys.readouterr()

    assert code == 0
    assert rig.generated == []
    assert rig.runs == []


def test_a_round_over_the_limit_handles_two_and_exits_zero(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """驗收條件 ⑤ 的退出碼那一半 —— 剩下的不是錯誤，下一輪會再看到。"""
    rig.folders = [_folder(DATA_FOLDER, n, (_audio(),)) for n in (0, 1, 2, 3)]
    _main(monkeypatch, rig)

    code = _main(monkeypatch, rig)
    capsys.readouterr()

    assert code == 0
    assert len(rig.generated) == rd.MAX_PER_ROUND == 2


def test_an_unknown_series_is_printed_and_dm_ed(rig, monkeypatch: pytest.MonkeyPatch, capsys):
    """驗收條件 ④ 的輸出那一半。"""
    rig.folders = [_folder("誰的資料夾", 0, (_audio(),))]
    _main(monkeypatch, rig)
    capsys.readouterr()

    code = _main(monkeypatch, rig)
    out = capsys.readouterr().out

    assert code == 0
    assert rig.generated == []
    assert "誰的資料夾" in out
    assert rd.DM_HEADER in out
    assert rig.dms, "只印在 stdout 的話，無人看管底下等於沒通知"


def test_a_notebooklm_auth_failure_stops_before_any_audio_work(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """驗收條件 ⑧ —— 一場兩小時的錄音切完 20 段才發現登不進去，等於白燒一輪。"""
    monkeypatch.setattr(rd, "notebooklm_gap", lambda *a, **k: "notebooklm 登入過期了")
    monkeypatch.setattr(
        rd, "generate", lambda *a, **k: pytest.fail("認證都過不了還去產")
    )
    rig.folders = [_folder(DATA_FOLDER, 0, (_audio(),))]
    _main(monkeypatch, rig)
    capsys.readouterr()

    code = _main(monkeypatch, rig)
    out = capsys.readouterr().out

    assert code != 0
    assert not any("extract_audio_sources.py" in " ".join(cmd) for cmd in rig.runs)
    assert rd.DM_HEADER in out
    assert "notebooklm 登入過期了" in out


def test_a_credential_gap_stops_before_touching_drive(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """憑證那條會開瀏覽器，排程底下是**卡住**不是變紅 —— 所以一開始就擋。"""
    monkeypatch.setattr(rd, "credential_gap", lambda *a, **k: "要先跑一次 uv run scripts/setup.py")
    rig.folders = [_folder(DATA_FOLDER, 0, (_audio(),))]

    code = _main(monkeypatch, rig)
    out = capsys.readouterr().out

    assert code != 0
    assert rig.scanned == [], "憑證不齊還去掃 Drive，就是卡在沒有人的提示上"
    assert rig.generated == []
    assert rd.DM_HEADER in out


def test_the_local_scratch_is_removed_and_drive_is_never_asked_to_delete(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """驗收條件 ⑦ —— Drive 是原件、本機只是暫存，音檔歸屬與發佈流程相反。"""
    rig.folders = [_folder(DATA_FOLDER, 0, (_audio(),))]
    _main(monkeypatch, rig)

    assert _main(monkeypatch, rig) == 0
    capsys.readouterr()

    (workdir,) = rig.workdirs
    assert not workdir.exists(), f"暫存目錄跑完還在：{workdir}"

    assert rig.scanned and all(
        d is rig.drive for d in rig.scanned
    ), "注入的 Drive client 沒被用上，這條測到的是別人"


def test_nothing_happens_when_there_is_no_delta(rig, monkeypatch: pytest.MonkeyPatch, capsys):
    """沒有差集就不動 —— 每小時跑一次，空轉必須真的是空轉。"""
    rig.folders = [_folder(DATA_FOLDER, 0, (_audio(), _note()))]
    _main(monkeypatch, rig)
    capsys.readouterr()

    code = _main(monkeypatch, rig)
    capsys.readouterr()

    assert code == 0
    assert rig.generated == []
    assert rig.dms == []


# -------------------------------------------------------------- generate 送出的參數


def test_generate_publishes_without_the_audio_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """帶了 `--audio-file` 會把暫存那份再上傳一次，在同一個資料夾裡變成第二個音檔。

    斷言打在**送出去的指令**上：回傳的 URL 看不見多帶了哪個旗標。
    """
    workdir = tmp_path / "work"
    workdir.mkdir()

    calls: list[tuple[list[str], str | None]] = []

    def fake_download(drive, file, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"AUDIO")
        return dest

    def fake_run(cmd, timeout, stdin=None):
        cmd = [str(c) for c in cmd]
        calls.append((cmd, stdin))
        # 子 agent 是替身，不會真的寫檔 —— 但 `generate` 有權要求正式稿存在。
        for hit in re.findall(rf"{re.escape(str(tmp_path))}\S*\.md", stdin or ""):
            Path(hit).write_text("# 會議記錄\n", encoding="utf-8")
        stdout = "\n".join(
            [
                f"RESULT_TRANSCRIPT: {workdir / 'transcript.md'}",
                f"RESULT_EXTRACT: {workdir / 'extract.md'}",
                f"RESULT_CONTEXT: {workdir / 'meeting-context.md'}",
                f"RESULT_HISTORY_INDEX: {workdir / 'history-index.md'}",
                "RESULT_SERIES_NAME: Data內會",
                f"RESULT_URL: {DOC_URL}",
            ]
        )
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(rd, "download_audio", fake_download)
    monkeypatch.setattr(rd, "run_step", fake_run)

    session = rd.Session(
        series=DATA_FOLDER,
        name=TODAY,
        date=TODAY,
        instance="",
        meeting_key="data",
        audio=(_audio(),),
        reason="",
    )

    url = rd.generate(MagicMock(name="drive"), session, copy.deepcopy(CONFIG), workdir)

    assert url == DOC_URL
    publish = [cmd for cmd, _ in calls if any("create_gdoc_from_md.py" in c for c in cmd)]
    assert publish, f"沒有發佈那一步；送出去的是 {[c for c, _ in calls]}"
    flat = " ".join(publish[-1])
    assert "--audio-file" not in flat
    assert "--delete-local-audio" not in flat


# ------------------------------------------------- 雙軌通知：維運者 DM ／ 會議 channel


def test_the_channel_notice_names_the_meeting_the_cause_and_that_nobody_needs_to_act():
    """三件事缺一不可。少了「有人在處理」那句，channel 裡的人會開始猜自己該補做什麼。"""
    # 三段各自一行，中間隔空行。拆開來對而不是整段 `in`：黏在一起的那幾種寫法（少一個
    # 換行、每行前後多黏一段）整段 `in` 一條都看不出來。空行也一起釘 —— 它就是這則
    # 訊息「一眼看得出在講什麼」的那個東西。
    when = rd.when_label(_session(DATA_FOLDER, "", TODAY))
    head, gap1, ident, why, gap2, reassurance = (
        rd.failure_notice("Data內會", when, rd.FAILED_CAUSE).splitlines()
    )

    assert head == rd.CHANNEL_HEADER
    assert (gap1, gap2) == ("", ""), "抬頭、內容、結語之間各留一行"
    assert "Data內會" in ident
    assert "2026/09/15" in ident, "日期要給人看的格式，不是資料夾名那串"
    assert why == f"原因：{rd.FAILED_CAUSE}"
    assert reassurance.startswith("已經有人收到通知")
    assert "不需要做任何事" in reassurance


def test_the_two_tracks_are_not_the_same_message():
    """驗收條件③ —— 同一個事件兩則訊息。開會的人不會去 debug，例外類別名只會讓他們
    回頭來問維運者，而那正是這張票要省掉的那一趟。"""
    dm = rd.dm_blocked(f"❌ {DATA_FOLDER}/{TODAY}　RuntimeError: 流程 B 失敗（退出碼 1）", 1)
    channel = rd.failure_notice(
        "Data內會", rd.when_label(_session(DATA_FOLDER, "", TODAY)), rd.FAILED_CAUSE
    )

    assert "RuntimeError" in dm
    assert "RuntimeError" not in channel
    assert channel != dm


def test_notice_key_separates_the_meeting_the_day_and_the_cause():
    """「同一場、同一個原因」是去重的身份。三個維度任何一個不同就是另一則。"""
    base = rd.notice_key(DATA_FOLDER, TODAY, rd.FAILED_CAUSE)

    assert base == rd.notice_key(DATA_FOLDER, TODAY, rd.FAILED_CAUSE)
    assert base != rd.notice_key(PM_FOLDER, TODAY, rd.FAILED_CAUSE)
    assert base != rd.notice_key(DATA_FOLDER, _shift(1), rd.FAILED_CAUSE)
    assert base != rd.notice_key(DATA_FOLDER, TODAY, rd.MULTI_AUDIO_CAUSE)


def test_notice_due_is_false_for_today_and_true_for_a_new_day():
    """`!=` 寫成 `==` 的症狀是「該提醒的那天不提醒、不該提醒的每輪都提醒」。"""
    sent = {"k": TODAY}

    assert rd.notice_due(sent, "k", TODAY) is False
    assert rd.notice_due(sent, "k", _shift(-1)) is True
    assert rd.notice_due(sent, "沒發過的", TODAY) is True
    assert rd.notice_due({}, "k", TODAY) is True


def test_prune_sent_keeps_today_and_drops_the_older_rows():
    """狀態檔是長命的，昨天的記錄對「一天一次」已經沒有作用。"""
    assert rd.prune_sent({"a": TODAY, "b": _shift(1), "c": _shift(30)}, TODAY) == {"a": TODAY}


def _boom(rig, monkeypatch: pytest.MonkeyPatch, message: str = "流程 B 失敗（退出碼 1）"):
    """讓這輪的產製炸掉，並把一場有音檔的資料夾擺好。"""
    monkeypatch.setattr(rd, "generate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError(message)))
    rig.folders = [_folder(DATA_FOLDER, 0, (_audio(),))]


def test_a_failure_dms_the_operator_and_tells_the_meeting_channel(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """驗收條件①②③ —— 一個事件、兩則訊息、兩個收件者。"""
    rig.config["meetings"]["data"]["slack_channel"] = "C0DATA"
    _boom(rig, monkeypatch)
    _main(monkeypatch, rig)          # 首次執行：強制 dry-run
    capsys.readouterr()

    code = _main(monkeypatch, rig)
    out = capsys.readouterr().out

    assert code != 0
    (channel, text), = rig.posts
    assert channel == "C0DATA"
    assert "RuntimeError" not in text
    assert "已經有人收到通知" in text
    assert text in out, "channel 那則也要留在 stdout 上"

    (dm_args, _), = rig.dms
    assert "RuntimeError" in dm_args[0], "維運者那則沒有技術細節就等於沒有除錯線索"


def test_a_muted_meeting_stays_silent_even_when_it_fails(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """三態照舊 —— 刻意設成空字串的會議不會因為這張票開始出聲。維運者照樣收得到。"""
    rig.config["meetings"]["data"]["slack_channel"] = ""
    _boom(rig, monkeypatch)
    _main(monkeypatch, rig)
    capsys.readouterr()

    _main(monkeypatch, rig)
    capsys.readouterr()

    assert rig.posts == []
    assert rig.dms, "安靜的是 channel，不是維運者"


def test_a_meeting_with_no_channel_set_only_dms(rig, monkeypatch: pytest.MonkeyPatch, capsys):
    """三態的第三態：還沒設定 → 沒有收件者可發，只有 DM。"""
    assert "slack_channel" not in rig.config["meetings"]["data"]
    _boom(rig, monkeypatch)
    _main(monkeypatch, rig)
    capsys.readouterr()

    _main(monkeypatch, rig)
    capsys.readouterr()

    assert rig.posts == []
    assert rig.dms


def test_the_same_failure_tells_the_channel_once_a_day_then_again_tomorrow(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """驗收條件⑤ —— 每小時一輪，同一場同一個原因會連續七天每輪都命中。

    最後一輪的 `--today` 疊在 `_main` 那個之後，argparse 取後面那個。
    """
    rig.config["meetings"]["data"]["slack_channel"] = "C0DATA"
    _boom(rig, monkeypatch)
    for _ in range(3):
        _main(monkeypatch, rig)
        capsys.readouterr()

    assert len(rig.posts) == 1, "同一天重複提醒會讓人學會忽略這個 channel"
    assert len(rig.dms) == 2, "維運者的 DM 照舊每輪都發"

    _main(monkeypatch, rig, "--today", _shift(-1))
    capsys.readouterr()

    assert len(rig.posts) == 2, "換一天之後就不是同一則提醒了"


def test_a_channel_send_that_failed_is_retried_next_round(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """送不出去不算發過。先記起來的話，Slack 掛掉那一天就再也不會提醒。"""
    rig.config["meetings"]["data"]["slack_channel"] = "C0DATA"
    rig.slack_up = False
    _boom(rig, monkeypatch)
    for _ in range(3):
        _main(monkeypatch, rig)
        out = capsys.readouterr().out

    assert len(rig.posts) == 2, "第一輪是 dry-run，後兩輪各試一次"
    assert "已經有人收到通知" in out, "Slack 送不出去時提醒不能跟著消失"


def test_multi_audio_tells_the_channel_too(rig, monkeypatch: pytest.MonkeyPatch, capsys):
    """驗收條件① 的「掃到但跳過」那一半 —— 沒產出來就是沒產出來，不分是哪一種。"""
    rig.config["meetings"]["data"]["slack_channel"] = "C0DATA"
    rig.folders = [
        _folder(DATA_FOLDER, 0, (_audio(), _audio("錄音2.m4a", "audio-2")))
    ]
    _main(monkeypatch, rig)
    capsys.readouterr()

    _main(monkeypatch, rig)
    capsys.readouterr()

    (channel, text), = rig.posts
    assert channel == "C0DATA"
    assert rd.MULTI_AUDIO_CAUSE in text
    assert rd.MULTI_AUDIO not in text, "channel 那則講人話，不是搬內部的理由字串"


def test_an_unknown_series_never_reaches_a_channel(rig, monkeypatch: pytest.MonkeyPatch, capsys):
    """不知道是哪一種會議就不知道要發哪個 channel —— 只有維運者收得到。"""
    rig.folders = [_folder("誰的資料夾", 0, (_audio(),))]
    _main(monkeypatch, rig)
    capsys.readouterr()

    _main(monkeypatch, rig)
    capsys.readouterr()

    assert rig.posts == []
    assert rig.dms


def test_the_over_limit_rows_never_reach_a_channel(rig, monkeypatch: pytest.MonkeyPatch, capsys):
    """下一輪就會處理完。每輪對整個會議 channel 喊一次等於教大家忽略它。"""
    rig.config["meetings"]["data"]["slack_channel"] = "C0DATA"
    rig.folders = [_folder(DATA_FOLDER, n, (_audio(),)) for n in (0, 1, 2, 3)]
    _main(monkeypatch, rig)
    capsys.readouterr()

    _main(monkeypatch, rig)
    capsys.readouterr()

    assert rig.posts == []


def test_a_dry_run_never_posts_to_a_channel(rig, monkeypatch: pytest.MonkeyPatch, capsys):
    """手動看一次差集不該對著整個會議 channel 喊「沒產出來」—— 那是假警報。"""
    rig.config["meetings"]["data"]["slack_channel"] = "C0DATA"
    rig.folders = [
        _folder(DATA_FOLDER, 0, (_audio(), _audio("錄音2.m4a", "audio-2")))
    ]
    _main(monkeypatch, rig)          # 首次執行也是強制 dry-run
    capsys.readouterr()
    assert rig.posts == []

    _main(monkeypatch, rig, "--dry-run")
    capsys.readouterr()

    assert rig.posts == []


# ---------------------------------------------------------------- mutation 佈線


def reconcile_defs() -> set[str]:
    source = (SCRIPTS / "reconcile_drive.py").read_text(encoding="utf-8")
    return {n.name for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}


def makefile_pure_names() -> set[str]:
    """Makefile 裡 `PURE := \\` 那塊列出的函式名。"""
    block = (ROOT / "Makefile").read_text(encoding="utf-8").split("PURE := \\", 1)[1]
    return {line.strip(" \t\\") for line in block.split("\n\n", 1)[0].splitlines()} - {""}


#: 介面文件裡吃 `drive`、起子行程、或只負責印東西的那幾支。它們要憑證、要網路、要
#: NotebookLM —— 掛進 mutation 只會噴一牆 🫥 no-tests，數字沒有意義。
IO_LAYER = {
    "series_folders",
    "scan_drive",
    "list_all",
    "download_audio",
    "run_step",
    "notebooklm_gap",
    "generate",
    "report",
    "notify",
    "notify_channel",
    "notify_once",
    "notify_misplaced",
    "notify_dm_once",
    "send_once",
    "read_state",
    "write_state",
    "main",
}

#: 見 `test_channel_tristate.py`：mutmut 的 `mutants/` 複本裡 top-level def 已被改寫成
#: `x_<名>__mutmut_<N>`，拿去跟 Makefile 對帳必紅，而兩道事後守衛都看不見。
MUTATED_COPY = any("__mutmut_" in name for name in reconcile_defs())


def test_reconcile_drive_is_in_the_mutation_scope():
    """差集的判準沒掛進 `source_paths` 就是量不到它 —— 而多算一場的代價是覆寫既有記錄。"""
    assert "reconcile_drive.py" in (ROOT / "setup.cfg").read_text(encoding="utf-8")


@pytest.mark.skipif(
    MUTATED_COPY,
    reason="mutmut 的 mutants/ 複本：這條量的是 repo 佈線，不是模組行為",
)
def test_every_pure_function_in_reconcile_drive_is_in_the_mutation_scope():
    """純函式加了卻沒掛進 `PURE` 就是量不到它。兩側各自算出來再比，不手抄要守的那份。"""
    defined = reconcile_defs()
    assert defined, "AST 解不出 def，這條測試量的是空集合"

    assert makefile_pure_names() & defined == defined - IO_LAYER


# ------------------------------------------------ 棒④ kill-set：活著的 mutant 補洞


def test_a_skipped_folder_does_not_abort_the_rest_of_the_scan():
    """跳過一筆用的是 `continue` 不是 `break`。

    `break` 的症狀是「排在被跳過那筆後面的場次全部靜靜不見」，而清單順序是 Drive 給
    的，沒有人控制得了誰排前面。三個跳過的理由各擋一次。
    """
    wanted = _folder(PM_FOLDER, 0, (_audio(),))
    for blocker in (
        _folder(DATA_FOLDER, 30, (_audio(),)),          # 窗外
        _folder(DATA_FOLDER, 1, (_audio(), _note())),   # 已經有記錄
        _folder(DATA_FOLDER, 2, ()),                    # 沒有音檔
    ):
        round_ = rd.compute_pending([blocker, wanted], KNOWN, TODAY)
        assert _pending_ids(round_) == [(PM_FOLDER, TODAY)], blocker["date"]


def test_the_dm_puts_one_skipped_session_per_line():
    """一場一行。黏成一行的話，讀 DM 的人看不出到底有幾場擱著、分別是哪幾場。"""
    sessions = [
        _session("AAA未知", rd.UNKNOWN_SERIES, _shift(3)),
        _session("ZZZ未知", rd.MULTI_AUDIO, TODAY),
    ]
    lines = rd.dm_skipped(sessions).splitlines()

    # 抬頭 ＋ 摘要 ＋ 空行 ＋ 兩場 ＋ 空行 ＋ 設定檔路徑
    assert len(lines) == 7, lines
    assert lines[0] == rd.DM_HEADER
    assert lines[1] == "2 場掃到了但沒有產"
    assert (lines[2], lines[5]) == ("", ""), "清單前後各留一行，不然又擠成一坨"
    # 行首必須真的是行首：只斷言「這一行含 AAA未知」的話，把整段黏成一行再靠換行符
    # 湊出行數的寫法照樣過，而那正是這條要擋的形狀。
    assert lines[3].startswith("• ") and "AAA未知" in lines[3], lines[3]
    assert lines[4].startswith("• ") and "ZZZ未知" in lines[4], lines[4]


def test_the_round_takes_the_oldest_sessions_not_the_first_by_series_name():
    """上限之內取哪幾場按**日期**，不是按 `Session` 欄位的自然順序（系列名在最前面）。

    照自然順序排的話，同一輪裡最舊的那場會被一個較新、但系列名排前面的場次擠掉 ——
    而被擠掉的那場下一輪再被同一條規則擠掉一次，於是它永遠排不到。
    """
    known = {"AAA系列": "a", "ZZZ系列": "z"}
    folders = [
        _folder("AAA系列", 0, (_audio(),)),
        _folder("ZZZ系列", 5, (_audio(),)),
        _folder("AAA系列", 1, (_audio(),)),
    ]
    round_ = rd.compute_pending(folders, known, TODAY, limit=2)

    assert _pending_ids(round_) == [("ZZZ系列", _shift(5)), ("AAA系列", _shift(1))]
    assert _skipped_reasons(round_) == {("AAA系列", TODAY): rd.OVER_LIMIT}


def test_the_skipped_list_is_oldest_first_too():
    """沒產的那幾場也照日期排。DM 是人在讀的，順序跳來跳去的清單看不出哪件擱最久。"""
    folders = [
        _folder("AAA未知", 0, (_audio(),)),
        _folder("ZZZ未知", 3, (_audio(),)),
    ]
    round_ = rd.compute_pending(folders, KNOWN, TODAY)

    assert [(s.series, s.date) for s in round_.skipped] == [
        ("ZZZ未知", _shift(3)),
        ("AAA未知", TODAY),
    ]


def test_parse_handoff_takes_only_result_lines_that_carry_a_value():
    """`RESULT_` 前綴與「值非空」是**且**，不是**或**。

    寫成「或」的症狀是子行程的一般輸出也被收進交棒契約 —— 於是「`RESULT_URL` 有沒有
    真的被印出來」不再可信，而發佈成功與否就是靠它判的。
    """
    out = "\n".join([
        "📄 Transcript: /tmp/x/transcript.md",   # 有值，但不是 RESULT_ 開頭
        "RESULT_EXTRACT:    ",                   # 是 RESULT_ 開頭，但沒有值
        "沒有冒號的一行",
        f"RESULT_URL: {DOC_URL}",
    ])

    assert rd.parse_handoff(out) == {"RESULT_URL": DOC_URL}


def test_credential_gap_covers_a_web_oauth_client_too(tmp_path: Path):
    """`installed` 與 `web` 是同一條會開瀏覽器的路徑，只擋其中一種等於沒擋。"""
    (tmp_path / "credentials.json").write_text(
        json.dumps({"web": {"client_id": "x"}}), encoding="utf-8"
    )

    assert rd.credential_gap(tmp_path) != ""


def test_download_audio_only_asks_drive_for_the_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """驗收條件 ⑦ 的另一半：Drive 上那份是原件，下載這條路徑上**只有讀**。

    斷言打在 Drive client 收到的呼叫上，不是替身的回傳值 —— 回傳的 Path 看不出這支
    有沒有順手呼叫 `delete`。這條跑的是真的 `download_audio`，不是替身。
    """
    import googleapiclient.http as gah

    class _FakeDownloader:
        def __init__(self, handle, request, chunksize=None):
            self._handle = handle

        def next_chunk(self):
            self._handle.write(b"AUDIO")
            return None, True

    monkeypatch.setattr(gah, "MediaIoBaseDownload", _FakeDownloader)
    drive = MagicMock()
    dest = tmp_path / "還沒建的目錄" / "reconcile_20260915.m4a"

    out = rd.download_audio(drive, _audio(), dest)

    assert out.read_bytes() == b"AUDIO"
    assert sent_kwargs(drive, "files", "get_media") == {
        "fileId": "audio-1",
        "supportsAllDrives": True,
    }
    touched = [c[0] for c in drive.mock_calls]
    assert not [
        n for n in touched
        if any(w in n for w in ("delete", "trash", "create", "update", "copy"))
    ]


# ------------------------------------------------- 放錯層的音檔（issue #57）
#
# 「我丟了，然後什麼都沒發生」是這支腳本最容易踩到的失敗：檔案掉在系列資料夾最外層
# 時，它不在 pending、不在 skipped，連維運者的 DM 都不會出現。所以這一節的斷言重心
# 是**有沒有出聲**，以及**有沒有因此產出東西** —— 沒有日期資料夾就沒有可信的日期。


def _root(series: str, *files: dict) -> dict:
    """一個系列資料夾的直接子項。日期資料夾本人也在這份清單裡。"""
    return {"series": series, "files": list(files)}


def _subfolder(name: str) -> dict:
    return {"id": f"folder-{name}", "name": name, "mimeType": rd.FOLDER_MIME}


def test_an_audio_file_in_the_series_root_is_reported():
    """驗收條件① —— 它現在在一份清單裡了。"""
    roots = [_root(DATA_FOLDER, _subfolder(TODAY), _audio("錄音.m4a", "a1"))]

    (item,) = rd.compute_misplaced(roots, KNOWN)

    assert (item.series, item.meeting_key, item.file_id, item.name) == (
        DATA_FOLDER, "data", "a1", "錄音.m4a",
    )


#: 系列資料夾最外層本來就會有這些東西。對它們出聲就是每小時假警報一次。
INNOCENT = [
    {"id": "d1", "name": "會議記錄_Data內會_20260915", "mimeType": rd.DOC_MIME},
    {"id": "t1", "name": "transcript.md", "mimeType": "text/markdown"},
    {"id": "x1", "name": "報帳.xlsx", "mimeType": "application/vnd.ms-excel"},
    {"id": "n1", "name": "錄音.m4a.txt", "mimeType": "text/plain"},
]


@pytest.mark.parametrize("file", INNOCENT, ids=[_qid(f["name"]) for f in INNOCENT])
def test_a_non_audio_file_in_the_series_root_stays_silent(file):
    """驗收條件④ —— 正式稿、source artifacts、其他雜檔躺在那裡是正常的。"""
    assert rd.compute_misplaced([_root(DATA_FOLDER, file)], KNOWN) == []


def test_a_date_folder_is_not_a_misplaced_file():
    """日期資料夾與最外層的檔案來自同一次 `files().list()`，濾網要擋得住資料夾。

    副檔名那道濾網擋不了一個叫 `錄音.m4a` 的**資料夾** —— 而那正是 mimeType 那道在的
    理由。少了它，每個系列的每個日期資料夾都會變成一則提醒。
    """
    roots = [_root(DATA_FOLDER, _subfolder(TODAY), _subfolder("錄音.m4a"))]

    assert rd.compute_misplaced(roots, KNOWN) == []


def test_a_misplaced_file_under_an_unknown_series_has_no_meeting_key():
    """設定檔裡找不到的系列 → 沒有 `meeting_key` → 三態落在 `UNSET`，只有維運者收得到。"""
    (item,) = rd.compute_misplaced([_root("誰的資料夾", _audio())], KNOWN)

    assert item.meeting_key is None


def test_misplaced_is_sorted_by_series_then_name():
    """清單順序是 Drive 給的。每輪換一次順序會讓人以為內容變了。

    三個名字刻意跟**系列順序**和 **Drive 檔案 id 的順序**都不一致：只按檔名排、或
    照 `Misplaced` 欄位的自然順序排（`series, meeting_key, file_id, name` —— id 排在
    name 前面）都會給出另一種答案，而那兩種在「名字剛好同序」的資料上看不出來。
    """
    roots = [
        _root(PM_FOLDER, _audio("a.m4a", "p1")),
        _root(DATA_FOLDER, _audio("z.wav", "d1"), _audio("b.mp3", "d2")),
    ]

    assert [(i.series, i.name) for i in rd.compute_misplaced(roots, KNOWN)] == [
        (DATA_FOLDER, "b.mp3"),
        (DATA_FOLDER, "z.wav"),
        (PM_FOLDER, "a.m4a"),
    ]


def test_the_misplaced_notice_says_what_to_do_next_instead_of_sit_tight():
    """驗收條件② —— 這則的角色與失敗那則**相反**：只有丟檔案的人移得動它。"""
    head, gap1, why, gap2, nextstep = rd.misplaced_notice("Data內會", "錄音.m4a").splitlines()

    assert head == rd.MISPLACED_HEADER
    assert (gap1, gap2) == ("", ""), "抬頭、現象、下一步之間各留一行"
    assert "錄音.m4a" in why
    assert "Data內會" in why
    assert nextstep.startswith("請把它移進") and "YYYYMMDD" in nextstep
    assert "不需要做任何事" not in nextstep, "這則要的正是對方做一件事"
    assert "_場次" not in nextstep, "帶後綴的資料夾一樣掃不到，叫人建一個等於再演一次無聲"


def test_dm_misplaced_is_empty_when_nothing_is_misplaced():
    assert rd.dm_misplaced([]) == ""


def test_dm_misplaced_puts_one_file_per_line():
    """一個檔案一行 —— 黏成一行的話看不出到底有幾個、分別是哪幾個。"""
    items = rd.compute_misplaced(
        [_root(DATA_FOLDER, _audio("a.m4a", "a"), _audio("b.m4a", "b"))], KNOWN
    )
    lines = rd.dm_misplaced(items).splitlines()

    # 抬頭 ＋ 摘要 ＋ 空行 ＋ 兩個檔 ＋ 空行 ＋ 下一步
    assert len(lines) == 7, lines
    assert lines[0] == rd.DM_HEADER
    assert lines[1] == "2 個音檔躺在系列資料夾根目錄"
    assert (lines[2], lines[5]) == ("", ""), "清單前後各留一行"
    assert lines[3].startswith("• ") and "a.m4a" in lines[3], lines[3]
    assert lines[4].startswith("• ") and "b.m4a" in lines[4], lines[4]
    assert lines[6].startswith("請"), "最後一行是下一步，不是又一個檔案"


def _misplace(rig, *files: dict, series: str = DATA_FOLDER):
    rig.config["meetings"]["data"]["slack_channel"] = "C0DATA"
    rig.roots = [_root(series, *(files or (_audio(),)))]


def test_a_misplaced_file_tells_both_tracks_and_generates_nothing(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """驗收條件①②③ —— 兩軌都出聲，而且**一份記錄都沒產**。

    「退出碼 0」不算證明沒產：硬從檔名推日期的那個版本照樣退 0。所以斷言是
    `rd.generate` 一次都沒被呼叫。
    """
    _misplace(rig, _audio("錄音.m4a", "a1"))
    _main(monkeypatch, rig)          # 首次執行：強制 dry-run
    capsys.readouterr()

    code = _main(monkeypatch, rig)
    out = capsys.readouterr().out

    assert code == 0
    assert rig.generated == [], "沒有日期資料夾就沒有可信的日期，不該產任何記錄"
    (channel, text), = rig.posts
    assert channel == "C0DATA"
    assert "錄音.m4a" in text and "YYYYMMDD" in text
    assert text in out, "channel 那則也要留在 stdout 上"
    (dm_args, _) = rig.dms[-1]
    assert "錄音.m4a" in dm_args[0] and DATA_FOLDER in dm_args[0]


def test_the_same_misplaced_file_is_mentioned_once_a_day_then_again_tomorrow(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """每小時一輪，而沒有人移動它之前每輪都會再掃到 —— 不去重就是一天 24 則。

    **DM 與 channel 同一套去重**（#64）：DM 原本每輪重發，而真實 Drive 上那是一面 102
    行的牆一天出現 24 次 —— 同一個收件匣裡真正該看的那幾則會跟著一起被學會忽略。
    """
    _misplace(rig, _audio("錄音.m4a", "a1"))
    for _ in range(3):
        _main(monkeypatch, rig)
        capsys.readouterr()

    assert len(rig.posts) == 1, "同一天重複提醒會讓人學會忽略這個 channel"
    assert len(rig.dms) == 1, "維運者的 DM 也是一天一次，首次執行那輪算過了"

    _main(monkeypatch, rig, "--today", _shift(-1))
    capsys.readouterr()

    assert len(rig.posts) == 2, "隔天還躺在那裡就再提醒一次"
    assert len(rig.dms) == 2, "隔天那則 DM 也要再發一次 —— 去重是一天一次，不是一次而已"


def test_renaming_the_file_does_not_buy_a_second_reminder_the_same_day(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """去重的身份是 Drive 檔案 id，不是檔名。

    看到提醒之後把檔名改成帶日期的是很自然的反應 —— 拿檔名當身份的話，那個有在處理
    的人會因此多收到一則。
    """
    _misplace(rig, _audio("錄音.m4a", "a1"))
    _main(monkeypatch, rig)
    _main(monkeypatch, rig)
    capsys.readouterr()
    assert len(rig.posts) == 1

    rig.roots = [_root(DATA_FOLDER, _audio("20260915_錄音.m4a", "a1"))]
    _main(monkeypatch, rig)
    capsys.readouterr()

    assert len(rig.posts) == 1, "同一個檔案改了名字還是同一個檔案"


def test_two_misplaced_files_each_get_their_own_reminder(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """一則只講一個檔案，所以身份不能是系列本身 —— 不然另一個要等到隔天才被提到。"""
    _misplace(rig, _audio("上午.m4a", "a1"), _audio("下午.m4a", "a2"))
    _main(monkeypatch, rig)
    capsys.readouterr()

    _main(monkeypatch, rig)
    capsys.readouterr()

    assert [t for _, t in rig.posts] == [
        rd.misplaced_notice("Data內會", "上午.m4a"),
        rd.misplaced_notice("Data內會", "下午.m4a"),
    ]


def test_a_muted_meeting_stays_silent_about_a_misplaced_file(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """三態照舊 —— 刻意設成空字串的會議不會因為這張票開始出聲。維運者照樣收得到。"""
    _misplace(rig)
    rig.config["meetings"]["data"]["slack_channel"] = ""
    _main(monkeypatch, rig)
    capsys.readouterr()

    _main(monkeypatch, rig)
    capsys.readouterr()

    assert rig.posts == []
    assert rig.dms, "安靜的是 channel，不是維運者"


def test_a_dry_run_never_posts_about_a_misplaced_file(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """首次執行與 `--dry-run` 都只印不發，同 `MULTI_AUDIO` 那條。"""
    _misplace(rig)
    _main(monkeypatch, rig)          # 首次執行也是強制 dry-run
    capsys.readouterr()
    assert rig.posts == []

    _main(monkeypatch, rig, "--dry-run")
    out = capsys.readouterr().out

    assert rig.posts == []
    assert "錄音.m4a" in out, "dry-run 還是要在 stdout 上看得到它"


def test_an_innocent_series_root_is_quiet_end_to_end(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """最外層只有正式稿與日期資料夾時，這條路徑一個字都不該發出去。"""
    rig.config["meetings"]["data"]["slack_channel"] = "C0DATA"
    rig.roots = [_root(DATA_FOLDER, _subfolder(TODAY), *INNOCENT)]
    _main(monkeypatch, rig)
    capsys.readouterr()

    _main(monkeypatch, rig)
    capsys.readouterr()

    assert rig.posts == [] and rig.dms == []


# --------------------------------------- 未登記的系列只報系列，不逐檔（issue #64）
#
# #57 上線第一輪在真實 Drive 上掃出 102 個根目錄音檔，**全部**來自沒有登記過的系列
#（`series_folders` 從 parent 反推，同一層其他部門的資料夾也一起掃了進來）。
# 分界不是「重不重要」，是**這個建議執行得了嗎**：已登記的系列移進日期資料夾下一輪
# 就會產（可執行 → 逐檔講），未登記的移了也產不出來（不可執行 → 只報系列）。101 行
# 102 行每小時刷一次，第二天就會被學會忽略 —— 而那會連帶弄死同一則 DM 裡真正該看的
# 那三則（要產的、多音檔的、認不得資料夾的）。
#
# 所以這一節的斷言重心是**兩種說法各自成立**，以及未登記那則的身份是**系列**：
# 同一個系列再多丟一個檔，行數不變。

STRANGER = "週一_BD Meeting"          #: 設定檔裡沒有這個系列
STRANGER2 = "週二_AM Meeting"


def test_the_per_file_dm_leaves_out_unregistered_series():
    """驗收條件① —— 逐檔那份只留可執行的。"""
    items = rd.compute_misplaced(
        [_root(DATA_FOLDER, _audio("有登記.m4a", "a1")),
         _root(STRANGER, _audio("沒登記.m4a", "s1"))],
        KNOWN,
    )

    lines = rd.dm_misplaced(items).splitlines()

    # 抬頭 ＋ 摘要 ＋ 空行 ＋ 一個檔 ＋ 空行 ＋ 下一步
    assert len(lines) == 6, lines
    assert "有登記.m4a" in lines[3]
    assert "沒登記.m4a" not in rd.dm_misplaced(items), "移了也產不出來的不該叫人去移"
    assert "1 個" in lines[1], "數的是列出來的那幾個，不是掃到的全部"


def test_the_per_file_dm_is_empty_when_every_misplaced_file_is_unregistered():
    """101 個未登記的檔案不該讓那則「請移進日期資料夾」的 DM 照樣發出去。"""
    items = rd.compute_misplaced([_root(STRANGER, _audio())], KNOWN)

    assert rd.dm_misplaced(items) == ""


def test_the_unregistered_dm_puts_one_line_per_series():
    """驗收條件② —— 一個系列一行，說出系列名與音檔數量，並點出它不在設定檔裡。"""
    items = rd.compute_misplaced(
        [_root(STRANGER, _audio("a.m4a", "s1"), _audio("b.m4a", "s2"), _audio("c.m4a", "s3")),
         _root(STRANGER2, _audio("d.m4a", "s4"))],
        KNOWN,
    )

    text = rd.dm_unregistered(items)
    lines = text.splitlines()

    # 抬頭 ＋ 摘要 ＋ 空行 ＋ 兩個系列 ＋ 空行 ＋ 下一步
    assert len(lines) == 7, lines
    assert "2 個系列" in lines[1]
    assert (lines[2], lines[5]) == ("", ""), "清單前後各留一行"
    assert lines[3].startswith("• ") and STRANGER in lines[3] and "3 個音檔" in lines[3]
    assert lines[4].startswith("• ") and STRANGER2 in lines[4] and "1 個音檔" in lines[4]
    assert "a.m4a" not in text, "未登記的不逐檔 —— 101 個檔案就是 101 行"
    assert "設定檔" in lines[6] and str(rd.CONFIG_PATH) in lines[6]


def test_the_unregistered_dm_is_silent_when_every_series_is_registered():
    assert rd.dm_unregistered([]) == ""
    assert rd.dm_unregistered(rd.compute_misplaced([_root(DATA_FOLDER, _audio())], KNOWN)) == ""


def test_one_more_file_in_an_unregistered_series_does_not_buy_another_line():
    """驗收條件④ —— 這則的身份是**系列**不是檔案。

    身份是檔案的話，同事再丟一個進去就多一則提醒，而那一則沒有任何新資訊：要做的事
    從頭到尾都是同一件（把這個系列登記進設定檔）。數量還是要跟著變 —— 那是這則唯一
    會動的東西。
    """
    one = rd.compute_misplaced([_root(STRANGER, _audio("a.m4a", "s1"))], KNOWN)
    two = rd.compute_misplaced(
        [_root(STRANGER, _audio("a.m4a", "s1"), _audio("b.m4a", "s2"))], KNOWN
    )

    assert len(rd.dm_unregistered(one).splitlines()) == len(rd.dm_unregistered(two).splitlines())
    assert rd.dm_unregistered(one) != rd.dm_unregistered(two), "數量要跟著變"


def test_an_unregistered_series_never_reaches_a_meeting_channel(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """驗收條件③ —— 沒有 `meeting_key` 就不知道要發哪裡，收件者是維運者不是開會的人。

    `rig.posts` 收的是**所有** channel 送出去的訊息，不分哪一場 —— 斷言「一則都沒有」
    才擋得住「誤發到某個剛好設好的 channel」那條路。
    """
    rig.config["meetings"]["data"]["slack_channel"] = "C0DATA"
    rig.roots = [_root(STRANGER, _audio("a.m4a", "s1"), _audio("b.m4a", "s2"))]
    _main(monkeypatch, rig)              # 首次執行：強制 dry-run
    capsys.readouterr()

    code = _main(monkeypatch, rig)
    capsys.readouterr()

    assert code == 0
    assert rig.posts == []
    assert rig.generated == [], "這條路徑只回報，不產任何記錄"
    (dm_args, _) = rig.dms[-1]
    assert STRANGER in dm_args[0] and "2 個音檔" in dm_args[0]
    assert "a.m4a" not in dm_args[0]


def test_a_registered_and_an_unregistered_series_each_get_their_own_wording(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """驗收條件①② —— 同一輪裡兩種說法各自成立，互相不污染。"""
    rig.config["meetings"]["data"]["slack_channel"] = "C0DATA"
    rig.roots = [
        _root(DATA_FOLDER, _audio("有登記.m4a", "a1")),
        _root(STRANGER, _audio("沒登記.m4a", "s1")),
    ]
    _main(monkeypatch, rig)
    capsys.readouterr()

    _main(monkeypatch, rig)
    capsys.readouterr()

    assert [t for _, t in rig.posts] == [rd.misplaced_notice("Data內會", "有登記.m4a")]
    dms = [a[0] for a, _ in rig.dms]
    assert any("有登記.m4a" in t for t in dms), "已登記的照舊逐檔"
    assert not any("沒登記.m4a" in t for t in dms), "未登記的不逐檔"
    assert any(STRANGER in t and "1 個音檔" in t for t in dms), "但那個系列本身要被點名"


# ------------------------------- 維運者的 DM 也一天一次，身份分兩種（#64）
#
# 去重原本只保護 channel：`notify_once` 管的是那一則，DM 走 `notify()` **每輪重發**。
# 每小時一輪，於是真實 Drive 上那面 102 行的牆一天出現 24 次 —— 而同一個收件匣裡真正
# 該看的三則（要產的、多音檔的、認不得資料夾的）就跟著一起被學會忽略。


def test_the_dm_key_ignores_the_order_drive_happened_to_return():
    """清單順序是 Drive 給的。順序一換就是另一個 key，等於去重當輪失效。

    形狀一起釘死：這些 key 會**留在狀態檔裡跨輪比對**，改了形狀等於當天所有的 key 都
    是新的 —— 那不是重構，是去重失效一天。
    """
    assert rd.dm_notice_key("cause", ["b", "a"]) == "cause/a,b"
    assert rd.dm_notice_key(rd.MISPLACED_DM, ["a", "b"]) == rd.dm_notice_key(
        rd.MISPLACED_DM, ["b", "a"]
    )


def test_the_dm_key_ignores_how_many_times_the_same_id_shows_up():
    """未登記那則餵進來的是**每個檔案的系列名**，所以同一個系列會出現很多次。

    數量進了 key 的話，同一個系列多丟一個音檔就等於一則新提醒 —— 而那則要說的事
    （這個系列沒登記過）從頭到尾都是同一件。
    """
    assert rd.dm_notice_key(rd.UNREGISTERED_DM, [STRANGER, STRANGER]) == rd.dm_notice_key(
        rd.UNREGISTERED_DM, [STRANGER]
    )


def test_the_dm_key_changes_when_the_set_itself_changes():
    """集合變了就是一則有新資訊的提醒，該發。兩則 DM 之間也不能互相擋。"""
    assert rd.dm_notice_key(rd.UNREGISTERED_DM, ["a"]) != rd.dm_notice_key(
        rd.UNREGISTERED_DM, ["a", "b"]
    )
    assert rd.dm_notice_key(rd.MISPLACED_DM, ["a"]) != rd.dm_notice_key(
        rd.UNREGISTERED_DM, ["a"]
    )


def test_another_file_in_an_unregistered_series_does_not_buy_another_dm(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """驗收條件④ 的端到端那一半 —— 身份是**系列**，所以同事再丟一個進去也不多一則。"""
    rig.roots = [_root(STRANGER, _audio("a.m4a", "s1"))]
    _main(monkeypatch, rig)              # 首次執行：這一則 DM 已經發過了
    capsys.readouterr()
    assert len(rig.dms) == 1

    rig.roots = [_root(STRANGER, _audio("a.m4a", "s1"), _audio("b.m4a", "s2"))]
    _main(monkeypatch, rig)
    capsys.readouterr()

    assert len(rig.dms) == 1, "同一個系列多一個音檔，要做的事還是同一件"


def test_another_misplaced_file_in_a_registered_series_does_buy_another_dm(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """逐檔那則相反：身份是那幾個 Drive 檔案 id，多一個檔就是一則有新資訊的提醒。

    這兩條一起看才是這張票的分界本身 —— 已登記的移進日期資料夾下一輪就會產（可執行，
    所以值得為新的檔案再響一次），未登記的移了也產不出來。
    """
    _misplace(rig, _audio("a.m4a", "a1"))
    _main(monkeypatch, rig)
    _main(monkeypatch, rig)
    capsys.readouterr()
    assert len(rig.dms) == 1, "同一個檔案不會在同一天講第二次"

    rig.roots = [_root(DATA_FOLDER, _audio("a.m4a", "a1"), _audio("b.m4a", "a2"))]
    _main(monkeypatch, rig)
    capsys.readouterr()

    assert len(rig.dms) == 2
    assert "b.m4a" in rig.dms[-1][0][0]


def test_a_dm_that_failed_to_send_is_retried_next_round(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """送不出去不算發過 —— 同 channel 那條。先記起來的話，Slack 掛掉那天就再也不提醒。"""
    rig.slack_up = False
    _misplace(rig, _audio("錄音.m4a", "a1"))
    for _ in range(3):
        _main(monkeypatch, rig)
        capsys.readouterr()

    assert len(rig.dms) == 3


def test_a_blocked_round_still_dms_every_time(
    rig, monkeypatch: pytest.MonkeyPatch, capsys
):
    """去重只包住「有東西躺在那裡沒動」那兩則。

    `dm_blocked` 是「這一輪停了」—— 每一輪都是一次新的失敗，壓成一天一次會讓連續
    24 小時掛掉看起來像只掛了一次。
    """
    rig.folders = [_folder(DATA_FOLDER, 0, (_audio(),))]
    monkeypatch.setattr(rd, "notebooklm_gap", lambda *a, **k: "❌ 沒有登入")
    _main(monkeypatch, rig)
    capsys.readouterr()

    assert _main(monkeypatch, rig) == 1
    assert _main(monkeypatch, rig) == 1
    capsys.readouterr()

    assert len(rig.dms) == 2, "每一輪都要講一次"


# ------------------------------------------------- 同日多場：YYYYMMDD_<場次>（#56）
#
# 這一節的形狀與上面幾節不同：要擋的不是「多算一場」，是**少算一場而且不出聲**。
# `20260916_am` 以前整個被 `continue` 掉，於是「一天多場請各開一個資料夾」這個約定
# 是空的 —— 第二個資料夾是隱形的，把檔案丟進去的人會以為丟進去了。


def _scan(monkeypatch: pytest.MonkeyPatch, folders: dict[str, list[dict]]) -> list[dict]:
    """跑一次 `scan_drive`，回它的 `listings`。`folders` 是 {日期資料夾名: 裡面的檔案}。

    替身只換 `series_folders` 與 `list_all` —— 要驗的是掃描層自己**認不認得**那個名字，
    而 Drive client 怎麼翻頁不是這一節的事。
    """
    ids = {f"folder-{i}": name for i, name in enumerate(folders)}
    monkeypatch.setattr(
        rd, "series_folders", lambda drive, meetings: [{"id": "series-data", "name": DATA_FOLDER}]
    )

    def fake_list_all(drive, query):
        if "'series-data' in parents" in query:
            return [_subfolder(name) | {"id": fid} for fid, name in ids.items()]
        for fid, name in ids.items():
            if f"'{fid}' in parents" in query:
                return list(folders[name])
        return []

    monkeypatch.setattr(rd, "list_all", fake_list_all)
    return rd.scan_drive(MagicMock(name="drive"), CONFIG["meetings"], TODAY).listings


def test_the_scan_sees_a_session_suffixed_date_folder(monkeypatch: pytest.MonkeyPatch):
    """驗收條件① —— `20260916_am` 以前在掃描層就 `continue` 掉了，一路沒有訊息。"""
    listings = _scan(monkeypatch, {f"{TODAY}_am": [_audio()], f"{TODAY}_pm": [_audio()]})

    assert sorted(l["name"] for l in listings) == [f"{TODAY}_am", f"{TODAY}_pm"]


def test_the_scan_still_drops_date_folders_outside_the_window(monkeypatch: pytest.MonkeyPatch):
    """認得出日期的照舊過窗。放寬的是**名字的形狀**，不是 7 天窗。"""
    listings = _scan(
        monkeypatch, {f"{_shift(30)}_am": [_audio()], f"{TODAY}_am": [_audio()]}
    )

    assert [l["name"] for l in listings] == [f"{TODAY}_am"]


def test_the_scan_lists_the_files_of_a_folder_it_cannot_name(monkeypatch: pytest.MonkeyPatch):
    """認不得的名字沒有日期可以過窗，所以它一定進得來 —— 而且檔案要列出來。

    不列的話差集層分不出「有人放錯地方」與「這本來就不是收件夾」，只能一律提醒，
    而一律提醒的下場是沒有人看那則提醒。
    """
    listings = _scan(monkeypatch, {"舊資料": [_audio()]})

    assert [(l["name"], [f["id"] for f in l["files"]]) for l in listings] == [
        ("舊資料", ["audio-1"])
    ]


def test_two_sessions_on_the_same_day_are_two_independent_pending_rows():
    """驗收條件① —— 各開一個資料夾就各產一份，不是二選一、也不是合成一份。"""
    folders = [
        _folder(DATA_FOLDER, 0, (_audio(fid="pm-1"),), instance="pm"),
        _folder(DATA_FOLDER, 0, (_audio(fid="am-1"),), instance="am"),
    ]

    round_ = rd.compute_pending(folders, KNOWN, TODAY, limit=2)

    assert [(s.name, s.instance, s.audio[0]["id"]) for s in round_.pending] == [
        (f"{TODAY}_am", "am", "am-1"),
        (f"{TODAY}_pm", "pm", "pm-1"),
    ], "同一天兩場：上午那場先做，不是按字母序也不是按 Drive 給的順序"
    assert round_.skipped == []


def test_the_backlog_orders_same_day_sessions_by_real_time_not_by_spelling():
    """`afternoon` < `am` 是字串比較的事實（`af` < `am`）—— 照字母序排就是先做下午那場。

    這條與 `history_index` 那邊用的是**同一支**判準（`instance_order_key`）。各寫一份的話
    兩邊會靜靜地漂開，而漂開時兩邊都不會變紅。
    """
    folders = [
        _folder(DATA_FOLDER, 0, (_audio(),), instance="afternoon"),
        _folder(DATA_FOLDER, 0, (_audio(),), instance="am"),
    ]

    round_ = rd.compute_pending(folders, KNOWN, TODAY, limit=2)

    assert [s.instance for s in round_.pending] == ["am", "afternoon"]


def test_the_session_suffix_reaches_the_publish_command(tmp_path: Path, monkeypatch):
    """驗收條件② —— 後綴要一路帶到正式稿檔名與 Doc 標題，靠的就是這個旗標。

    斷言打在**送出去的指令**上：`create_gdoc_from_md.py` 用它算 Doc 名、本機檔名與
    Drive 的日期資料夾。少了它，第二場的 Doc 會被建進 `20260916`，而音檔躺在
    `20260916_am` —— 下一輪掃描在那個資料夾裡還是找不到記錄，於是每小時重產一次。
    """
    workdir = tmp_path / "work"
    workdir.mkdir()
    calls: list[list[str]] = []

    def fake_run(cmd, timeout, stdin=None):
        cmd = [str(c) for c in cmd]
        calls.append(cmd)
        for hit in re.findall(rf"{re.escape(str(tmp_path))}\S*\.md", stdin or ""):
            Path(hit).write_text("# 會議記錄\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            cmd, 0,
            stdout=f"RESULT_TRANSCRIPT: {workdir / 'transcript.md'}\nRESULT_URL: {DOC_URL}",
            stderr="",
        )

    monkeypatch.setattr(rd, "download_audio", lambda drive, file, dest: Path(dest))
    monkeypatch.setattr(rd, "run_step", fake_run)

    session = rd.Session(
        series=DATA_FOLDER, name=f"{TODAY}_am", date=TODAY, instance="am",
        meeting_key="data", audio=(_audio(),), reason="",
    )
    rd.generate(MagicMock(name="drive"), session, copy.deepcopy(CONFIG), workdir)

    publish = [c for c in calls if any("create_gdoc_from_md.py" in part for part in c)]
    assert publish, f"沒有發佈那一步；送出去的是 {calls}"
    assert "--title-suffix" in publish[-1]
    assert publish[-1][publish[-1].index("--title-suffix") + 1] == "am"
    assert publish[-1][publish[-1].index("--date") + 1] == TODAY, "日期那格仍是 8 位數"


def test_a_single_session_day_still_publishes_without_a_title_suffix(
    tmp_path: Path, monkeypatch
):
    """另一側 —— 沒有後綴時不能硬塞一個空字串進去，那會產出 `會議記錄_X_20260915_`。"""
    workdir = tmp_path / "work"
    workdir.mkdir()
    calls: list[list[str]] = []

    def fake_run(cmd, timeout, stdin=None):
        cmd = [str(c) for c in cmd]
        calls.append(cmd)
        for hit in re.findall(rf"{re.escape(str(tmp_path))}\S*\.md", stdin or ""):
            Path(hit).write_text("# 會議記錄\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            cmd, 0,
            stdout=f"RESULT_TRANSCRIPT: {workdir / 'transcript.md'}\nRESULT_URL: {DOC_URL}",
            stderr="",
        )

    monkeypatch.setattr(rd, "download_audio", lambda drive, file, dest: Path(dest))
    monkeypatch.setattr(rd, "run_step", fake_run)

    session = rd.Session(
        series=DATA_FOLDER, name=TODAY, date=TODAY, instance="",
        meeting_key="data", audio=(_audio(),), reason="",
    )
    rd.generate(MagicMock(name="drive"), session, copy.deepcopy(CONFIG), workdir)

    publish = [c for c in calls if any("create_gdoc_from_md.py" in part for part in c)]
    assert "--title-suffix" not in publish[-1]


def test_two_audio_files_in_one_folder_are_still_refused():
    """驗收條件③ —— 刻意的守衛，不因為本票放寬。放寬的是名字，不是「一個資料夾一個音檔」。"""
    folder = _folder(DATA_FOLDER, 0, (_audio(fid="a1"), _audio("錄音2.m4a", "a2")), instance="am")

    round_ = rd.compute_pending([folder], KNOWN, TODAY)

    assert round_.pending == []
    assert [s.reason for s in round_.skipped] == [rd.MULTI_AUDIO]


def test_the_refusal_message_says_what_to_do_next():
    """驗收條件④ —— 只講現象的訊息讓人知道系統沒動，卻不知道該把檔案搬去哪。

    斷言打在**指示**上而不是整句文案：形狀那句就是那個下一步本身，而「一天多場」是它
    適用的時機。兩個都在才算說完。
    """
    assert rd.DATE_DIR_SHAPES in rd.MULTI_AUDIO
    assert rd.DATE_DIR_EXAMPLE in rd.MULTI_AUDIO
    assert "一天多場" in rd.MULTI_AUDIO


#: 每一則會叫人「把檔案放進日期資料夾」的訊息。形狀那句一律引 `DATE_DIR_SHAPES`，
#: 不各自寫一次字面值 —— #57 的放錯層提醒原本只講 `YYYYMMDD`（當時帶後綴的資料夾確實
#: 掃不到），#56 讓後綴生效之後那句話就過期了，而過期不會讓任何東西變紅。
FOLDER_ADVICE = [
    ("MULTI_AUDIO", lambda: rd.MULTI_AUDIO),
    ("UNKNOWN_FOLDER", lambda: rd.UNKNOWN_FOLDER),
    ("misplaced_notice", lambda: rd.misplaced_notice("Data內會", "錄音.m4a")),
    ("dm_misplaced", lambda: rd.dm_misplaced([rd.Misplaced(DATA_FOLDER, "data", "f1", "錄音.m4a")])),
]


@pytest.mark.parametrize("label,render", FOLDER_ADVICE, ids=[n for n, _ in FOLDER_ADVICE])
def test_every_message_about_folder_names_quotes_the_same_source(label, render):
    """下次再擴充形狀時，漏改的只會是註解，不會是叫人怎麼做的那句話。"""
    assert rd.DATE_DIR_SHAPES in render(), label


def test_an_unrecognisable_folder_name_with_audio_is_reported_not_skipped():
    """驗收條件⑤ —— 以前是 `continue`，沒有任何訊息。"""
    round_ = rd.compute_pending(
        [_named_folder(DATA_FOLDER, "20260916_", [_audio()]),
         _named_folder(DATA_FOLDER, "9月16日下午", [_audio()])],
        KNOWN, TODAY,
    )

    assert round_.pending == []
    assert {s.name: s.reason for s in round_.skipped} == {
        "20260916_": rd.UNKNOWN_FOLDER,
        "9月16日下午": rd.UNKNOWN_FOLDER,
    }
    # 拆不出來時兩半都是空的。`instance` 塞一個假值的話，`_by_date` 會拿它去查
    # `instance_order_key`，而那個順序沒有任何斷言看得見。
    assert {(s.date, s.instance) for s in round_.skipped} == {("", "")}


def test_an_unrecognisable_folder_without_audio_stays_silent():
    """`舊資料`／`備份` 這種資料夾本來就不是收件夾 —— 為它每小時提醒一次等於訓練人忽略。

    這條刪掉 → 「認不得就提醒」退化成一律提醒，而一律提醒的下場是連 `MULTI_AUDIO`
    那幾則也一起被忽略。
    """
    round_ = rd.compute_pending(
        [_named_folder(DATA_FOLDER, "備份", [{"id": "x", "name": "筆記.md", "mimeType": "text/markdown"}])],
        KNOWN, TODAY,
    )

    assert round_.pending == [] and round_.skipped == []


def test_an_unrecognisable_folder_that_already_has_a_note_is_left_alone():
    """已經有記錄的就是有記錄了 —— 名字認不得不該讓一場已經完成的會議重新變成待辦。"""
    round_ = rd.compute_pending(
        [_named_folder(DATA_FOLDER, "20260916（重錄）", [_audio(), _note()])], KNOWN, TODAY
    )

    assert round_.pending == [] and round_.skipped == []


def test_an_unrecognisable_folder_name_reaches_the_dm(rig, monkeypatch, capsys):
    """驗收條件⑤ 的維運者那一軌 —— 要修名字的人是他。"""
    rig.folders = [_named_folder(DATA_FOLDER, "9月16日下午", [_audio()])]
    _main(monkeypatch, rig)                      # 首次執行：強制 dry-run
    capsys.readouterr()
    rig.dms.clear()

    _main(monkeypatch, rig)

    (dm_args, _), = rig.dms
    assert "9月16日下午" in dm_args[0]
    assert rd.UNKNOWN_FOLDER in dm_args[0]


def test_an_unrecognisable_folder_name_reaches_the_meeting_channel(rig, monkeypatch, capsys):
    """驗收條件⑤ 的會議成員那一軌 —— 走 #55 既有的那條路，不另開一條。

    這一場**知道**自己在哪個系列底下（`UNKNOWN_SERIES` 不知道），所以三態算得出來。
    """
    rig.config["meetings"]["data"]["slack_channel"] = "C0DATA"
    rig.folders = [_named_folder(DATA_FOLDER, "9月16日下午", [_audio()])]
    _main(monkeypatch, rig)
    capsys.readouterr()

    _main(monkeypatch, rig)

    (channel, text), = rig.posts
    assert channel == "C0DATA"
    assert "9月16日下午" in text, "認不得的名字要指認得出來，不能印成 `//`"
    assert rd.UNKNOWN_FOLDER_CAUSE in text


def test_a_muted_meeting_stays_silent_about_an_unrecognisable_folder(rig, monkeypatch, capsys):
    """三態照舊 —— 刻意設成空字串的會議不會因為本票開始出聲。維運者照樣收得到。"""
    rig.config["meetings"]["data"]["slack_channel"] = ""
    rig.folders = [_named_folder(DATA_FOLDER, "9月16日下午", [_audio()])]
    _main(monkeypatch, rig)
    capsys.readouterr()
    rig.dms.clear()

    _main(monkeypatch, rig)

    assert rig.posts == []
    assert rig.dms, "維運者那一軌不受三態影響"


def test_the_same_day_two_sessions_are_deduped_separately(rig, monkeypatch, capsys):
    """一天一次的去重身份是**資料夾**不是日期 —— 用日期的話下午那場那天永遠不會提醒。"""
    rig.config["meetings"]["data"]["slack_channel"] = "C0DATA"
    two = (_audio(fid="a1"), _audio("錄音2.m4a", "a2"))
    rig.folders = [
        _folder(DATA_FOLDER, 0, two, instance="am"),
        _folder(DATA_FOLDER, 0, two, instance="pm"),
    ]
    _main(monkeypatch, rig)
    capsys.readouterr()

    _main(monkeypatch, rig)

    # 指認哪一場的是抬頭底下那行（`failure_notice` 的第三行），不是抬頭本身 ——
    # 抬頭每一則都一樣。
    idents = sorted(text.splitlines()[2] for _, text in rig.posts)

    assert len(idents) == 2, f"兩場各一則，實際是 {idents}"
    assert idents[0].endswith("2026/09/15 am")
    assert idents[1].endswith("2026/09/15 pm")


# ------------------------------------------------------------------- when_label


def test_when_label_names_the_session_not_just_the_day():
    """同日兩場的日期一模一樣 —— 只印日期的話 channel 裡的人不知道講的是哪一場。"""
    assert rd.when_label(_session(DATA_FOLDER, "", TODAY)) == "2026/09/15"
    assert rd.when_label(_session(DATA_FOLDER, "", TODAY, "am")) == "2026/09/15 am"


def test_when_label_falls_back_to_the_folder_name_it_could_not_parse():
    """`format_date_display("")` 會印成 `//` —— 把唯一的線索換成噪音。"""
    session = _session(DATA_FOLDER, rd.UNKNOWN_FOLDER)._replace(
        name="9月16日下午", date="", instance=""
    )

    assert rd.when_label(session) == "9月16日下午"
