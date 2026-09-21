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


def _folder(series: str, days_ago: int = 0, files: tuple[dict, ...] = ()) -> dict:
    return {
        "series": series,
        "date": _shift(days_ago),
        "files": list(files),
    }


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


def _session(series: str, reason: str, date_: str = TODAY):
    return rd.Session(
        series=series, date=date_, meeting_key=None, audio=(), reason=reason
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
    monkeypatch.setattr(rd, "send_dm", lambda *a, **k: rec.dms.append((a, k)))

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
        return copy.deepcopy(rec.folders)

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
        date=TODAY,
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
    # 三句話各一行。拆開來對而不是整段 `in`：黏在一起的那幾種寫法（少一個換行、
    # 每行前後多黏一段）整段 `in` 一條都看不出來。
    head, why, reassurance = rd.failure_notice("Data內會", TODAY, rd.FAILED_CAUSE).splitlines()

    assert "Data內會" in head
    assert "2026/09/15" in head, "日期要給人看的格式，不是資料夾名那串"
    assert why == f"原因：{rd.FAILED_CAUSE}"
    assert reassurance.startswith("已經有人收到通知")
    assert "不需要做任何事" in reassurance


def test_the_two_tracks_are_not_the_same_message():
    """驗收條件③ —— 同一個事件兩則訊息。開會的人不會去 debug，例外類別名只會讓他們
    回頭來問維運者，而那正是這張票要省掉的那一趟。"""
    dm = rd.dm_blocked(f"❌ {DATA_FOLDER}/{TODAY}　RuntimeError: 流程 B 失敗（退出碼 1）", 1)
    channel = rd.failure_notice("Data內會", TODAY, rd.FAILED_CAUSE)

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

    assert len(lines) == 4, lines          # 抬頭 ＋ 兩場 ＋ 設定檔路徑
    assert lines[0].startswith(rd.DM_HEADER)
    # 行首必須真的是行首：只斷言「這一行含 AAA未知」的話，把整段黏成一行再靠換行符
    # 湊出行數的寫法照樣過，而那正是這條要擋的形狀。
    assert lines[1].startswith("• ") and "AAA未知" in lines[1], lines[1]
    assert lines[2].startswith("• ") and "ZZZ未知" in lines[2], lines[2]


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
