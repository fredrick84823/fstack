"""`slack_channel` 三態 —— 未設定 / 刻意不發 / 正常發（issue #26）。

**四個狀態各自一組斷言，不共用 parametrize。** `null` 與 `""` 的斷言長得幾乎一樣，
差別只有「有沒有 DM」那一條 —— 而那一條正是這張票的全部內容。一個 parametrize 掃四種
狀態配同一批 assert 的話，把 `""` 判成 `UNSET`（或反過來）只會讓同一條測試紅，
分不出壞的是哪一態；拆開才能各自獨立變紅。

**DM 這條路徑進不了 CI**（要真 token），所以斷言打在**呼叫層**：
該 DM 時 `send_dm` 有被呼叫、不該 DM 時**沒有**被呼叫。只驗前者的話，
「每場會都 DM」這種改法照樣全綠。

不打網路、不碰使用者的家目錄：Drive 與 config 用替身、Slack 兩支換成記錄器、
歸檔強制 `root=tmp_path`、設定檔一律落在 `tmp_path`。
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

from tests.unit.conftest import ROOT, SCRIPTS, load_script

sys.path.insert(0, str(SCRIPTS))

import create_gdoc_from_md as publish  # noqa: E402
import local_archive  # noqa: E402
import send_slack_notification as slack  # noqa: E402

#: `channel.py` 在 `source_paths` 裡，所以要走 `load_script` —— mutmut 的 trampoline
#: 是拿模組的 `__name__` 去配 mutant key，平常的 `import channel` 名字對不上，
#: 那些 mutant 會變成 🫥 no-tests（而這張票的邏輯全在那支檔案裡）。
channel = load_script("channel")

DOC_URL = "https://docs.google.com/document/d/abc123/edit"
CONTENT = "# 會議記錄\n\n- 日期：2026/07/08\n\n內容"
MEETING = {
    "series_name": "PM會議",
    "folder_name": "週三_PM_會議",
    "folder_id": "series-folder-id",
    "attendees": [],
}

#: 「key 根本不存在」與「key 存在但是 `None`」是同一態，但**不是**同一個輸入 ——
#: 只驗 `None` 的話，用 `meeting["slack_channel"]` 直接取值的實作會在缺 key 時
#: 炸 KeyError 而沒人擋。
ABSENT = object()


def meeting_with(value) -> dict:
    """`value is ABSENT` 時連 key 都不放。"""
    m = dict(MEETING)
    if value is not ABSENT:
        m["slack_channel"] = value
    return m


@pytest.fixture
def publish_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    """跑一次 `create_gdoc_from_md.main()`，回傳這次發佈的完整觀測值。

    Slack 兩支是從 `send_slack_notification` 模組**呼叫當下**取用的，所以替身掛在
    該模組的屬性上；替身收下呼叫參數而不是回罐頭值 —— 斷言要打在送出去的東西上。
    """

    def run(value, *, extra_argv: tuple[str, ...] = ()):
        content_file = tmp_path / "meeting_notes.md"
        content_file.write_text(CONTENT, encoding="utf-8")

        config = {
            "meetings": {"pm": meeting_with(value)},
            "slack_dm_user": "U0DEADBEEF",
        }
        monkeypatch.setattr(publish, "load_config", lambda: config)
        monkeypatch.setattr(
            publish, "create_gdoc_in_shared_drive", lambda *a, **kw: (DOC_URL, "date-folder-id")
        )

        real = local_archive.write_local_archive
        monkeypatch.setattr(
            publish, "write_local_archive", lambda *a, **kw: real(*a, **kw, root=tmp_path)
        )

        sent: list[tuple[tuple, dict]] = []
        dms: list[tuple[tuple, dict]] = []
        monkeypatch.setattr(
            slack, "send_notification", lambda *a, **kw: (sent.append((a, kw)), True)[1]
        )
        monkeypatch.setattr(slack, "send_dm", lambda *a, **kw: (dms.append((a, kw)), True)[1])

        monkeypatch.setattr(sys, "argv", [
            "create_gdoc_from_md.py",
            "--meeting", "pm",
            "--date", "20260708",
            "--content-file", str(content_file),
            *extra_argv,
        ])

        code = 0
        try:
            publish.main()
        except SystemExit as exc:  # 正常路徑不該走到這，但退出碼本身是驗收條件之一
            code = exc.code or 0

        out = capsys.readouterr().out
        results = {
            line.split(": ", 1)[0]: line.split(": ", 1)[1]
            for line in out.splitlines()
            if line.startswith("RESULT_") and ": " in line
        }
        return Run(code=code, out=out, results=results, sent=sent, dms=dms)

    return run


class Run:
    """一次發佈的觀測值。`channel_arg` 把位置參數與關鍵字參數兩種寫法都接住。"""

    def __init__(self, code, out, results, sent, dms):
        self.code = code
        self.out = out
        self.results = results
        self.sent = sent
        self.dms = dms

    @property
    def channel_arg(self):
        (args, kwargs), = self.sent
        return args[0] if args else kwargs["channel"]

    @property
    def dm_text(self):
        (args, kwargs), = self.dms
        return args[0] if args else kwargs["text"]


# ---------------------------------------------------------------- 三態判斷（純函式）


def test_channel_state_reads_an_absent_key_as_unset():
    """key 不存在 = 還沒設定。直接 `meeting["slack_channel"]` 會 KeyError。"""
    assert channel.channel_state(meeting_with(ABSENT)) == channel.UNSET


def test_channel_state_reads_none_as_unset():
    """`null` = 還沒設定 —— 設定檔裡實際長這樣（setup 跳過那題時寫的就是 `null`）。"""
    assert channel.channel_state(meeting_with(None)) == channel.UNSET


def test_channel_state_reads_the_empty_string_as_muted():
    """`""` = 刻意不發。與 `null` 分開是這張票的全部內容 —— 兩者都 falsy，
    用 `if not channel` 一把抓就會把「刻意不發」也拿去 DM 騷擾使用者。"""
    assert channel.channel_state(meeting_with("")) == channel.MUTED


def test_channel_state_reads_a_channel_id_as_send():
    assert channel.channel_state(meeting_with("C0XXXXXXXXX")) == channel.SEND


def test_channel_state_treats_whitespace_as_muted_not_as_a_channel():
    """空白字串不是 channel ID。送出去只會拿到 Slack 的 `channel_not_found`。"""
    assert channel.channel_state(meeting_with("   ")) != channel.SEND


def test_the_three_sentinels_are_distinct():
    """三個哨符相等的話，上面每一條都同時綠 —— 整組測試靜默失去鑑別力。"""
    assert len({channel.UNSET, channel.MUTED, channel.SEND}) == 3


# ---------------------------------------------------------------- DM 提醒的內容


def test_dm_reminder_carries_everything_needed_to_act_on_it():
    """提醒的用途是「我可以直接照做」：哪場會、Doc 在哪、拿到 ID 後跑哪行。

    少了 doc_url 這則 DM 就只是騷擾 —— 記錄已經產了，但看不到。
    """
    text = channel.dm_reminder("pm", "PM會議", DOC_URL, note_path=Path("/tmp/n.md"))

    assert text.startswith(channel.DM_HEADER) or channel.DM_HEADER in text
    assert DOC_URL in text
    assert "PM會議" in text
    assert "pm" in text
    assert "--channel" in text, "少了要跑的那行指令，收到的人還是得自己查用法"


def test_dm_reminder_mentions_the_local_path_only_when_there_is_one():
    """本機歸檔失敗（`note_path=None`）時那行要缺席 —— 印一個不存在的路徑比不印更糟。"""
    with_path = channel.dm_reminder("pm", "PM會議", DOC_URL, note_path=Path("/tmp/n.md"))
    without = channel.dm_reminder("pm", "PM會議", DOC_URL, note_path=None)

    assert "/tmp/n.md" in with_path
    assert "/tmp/n.md" not in without
    assert "None" not in without
    assert channel.DM_HEADER in without and DOC_URL in without


# ---------------------------------------------------------------- 四個狀態各自一組斷言


def test_a_null_channel_skips_the_notification_and_dms_instead(publish_once):
    """驗收條件 1、5、6：`null` → 不發 channel 通知，改印＋DM 提醒，記錄照產。"""
    run = publish_once(None)

    assert run.sent == [], "還沒設定 channel 卻送出了通知"
    assert run.dms, "還沒設定 channel 卻沒有 DM 提醒 —— 這張票的全部內容"
    assert channel.DM_HEADER in run.out
    assert channel.DM_HEADER in run.dm_text
    assert DOC_URL in run.dm_text
    assert run.results["RESULT_URL"] == DOC_URL
    assert run.code == 0


def test_a_missing_channel_key_behaves_exactly_like_null(publish_once):
    """驗收條件 2：key 不存在與 `null` 同一態 —— 舊設定檔裡這個 key 本來就不存在。"""
    run = publish_once(ABSENT)

    assert run.sent == []
    assert run.dms, "缺 key 被當成別的狀態了"
    assert channel.DM_HEADER in run.out
    assert channel.DM_HEADER in run.dm_text
    assert run.results["RESULT_URL"] == DOC_URL
    assert run.code == 0


def test_an_empty_channel_stays_silent(publish_once):
    """驗收條件 3、5：`""` = 刻意不發 → 不發通知、**也不 DM**、不印提醒。

    這條與上面兩條的差別只有 DM 那兩行。它跟著它們一起綠的話，
    三態就退化成兩態，而「我已經決定這場不發」每次開會都會被 DM 一次。
    """
    run = publish_once("")

    assert run.sent == []
    assert run.dms == [], "刻意不發通知的會議不該被 DM 騷擾"
    assert channel.DM_HEADER not in run.out
    assert run.results["RESULT_URL"] == DOC_URL
    assert run.code == 0


def test_a_real_channel_gets_the_notification(publish_once):
    """驗收條件 4、5：非空字串 → 送出去的 channel 參數就是設定檔那個值。

    斷言打在參數上，不是「有沒有呼叫」：傳錯 channel 的症狀是通知發到別的部門。
    """
    run = publish_once("C0XXXXXXXXX")

    assert len(run.sent) == 1
    assert run.channel_arg == "C0XXXXXXXXX"
    assert run.dms == [], "正常發通知的會議不該再 DM 一次"
    assert channel.DM_HEADER not in run.out
    assert run.results["RESULT_URL"] == DOC_URL
    assert run.code == 0


def test_no_slack_skips_the_dm_too(publish_once):
    """`--no-slack` 是「這次不要碰 Slack」，DM 也算碰 Slack。"""
    run = publish_once(None, extra_argv=("--no-slack",))

    assert run.sent == [] and run.dms == []
    assert run.results["RESULT_URL"] == DOC_URL
    assert run.code == 0


def test_send_dm_does_not_exit_when_there_is_no_token(monkeypatch, capsys):
    """`send_dm` 拿不到 token 時只能回 `False`。

    這支是在 Doc 已經建好之後才被呼叫的 —— 它 `sys.exit` 的話，
    `RESULT_URL` 會連同整個交棒一起消失，而那個 URL 只有發佈當下拿得到。
    """
    monkeypatch.setattr(slack, "load_config", lambda: {})
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)

    assert slack.send_dm("測試提醒") is False
    assert capsys.readouterr().out.strip(), "靜默回 False 等於沒人知道提醒沒送出去"


# ---------------------------------------------------------------- setup 寫出來的值


def test_setup_writes_null_not_empty_string_when_the_question_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """驗收條件 7：setup 跳過 channel 那題 → 寫出 `null`（還沒設定），不是 `""`（刻意不發）。

    寫成 `""` 的話，第一次設定完的每一場會議都變成「我決定不發通知」，
    提醒一次都不會出現 —— 而那正是這張票要修的症狀。

    真的驅動 `setup_config`：這條要守的就是「互動流程寫出去的值」，
    直接斷言一個自己捏的 dict 等於什麼都沒驗。stub 看 prompt 文字決定回什麼，
    不靠問題順序 —— 順序是實作內部，會變。
    """
    import setup as setup_mod

    monkeypatch.setattr(setup_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(setup_mod, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(setup_mod, "setup_glossary_entries", lambda *a, **kw: None)

    rounds = {"n": 0}

    def answer(prompt: str = "") -> str:
        if "會議類型" in prompt and "空白則完成" in prompt:
            rounds["n"] += 1
            return "pm會議" if rounds["n"] == 1 else ""  # 第二輪空白 → 結束迴圈
        return ""  # 其餘全部跳過，包含 Slack Channel ID 那題

    monkeypatch.setattr("builtins.input", answer)

    setup_mod.setup_config(with_audio=False)

    written = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    entry = written["meetings"]["pm會議"]

    assert entry["slack_channel"] is None
    assert channel.channel_state(entry) == channel.UNSET


# ---------------------------------------------------------------- 回寫與備份


def config_fixture(path: Path) -> dict:
    data = {
        "slack_bot_token": "xoxb-not-a-real-token",
        "slack_dm_user": "U0DEADBEEF",
        "meetings": {
            "pm": {**MEETING, "slack_channel": None, "custom_prompt": "保留我"},
            "team": {**MEETING, "series_name": "Team週會", "slack_channel": "C0OTHER"},
        },
        "prompt_path": "/somewhere/prompt.md",
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def test_set_channel_leaves_a_backup_and_changes_exactly_one_field(tmp_path: Path):
    """驗收條件 8：回寫後設定檔旁有備份，且**其他欄位逐欄相同**。

    逐欄比而不是「檔案有變」：這支腳本改的是使用者唯一一份設定檔，
    重寫時掉一個欄位（或把另一場會的 channel 一起覆蓋掉）沒有任何東西擋得住。
    """
    config_path = tmp_path / "config.json"
    before = config_fixture(config_path)

    backup = channel.set_channel("pm", "C0NEWNEW", config_path=config_path)

    assert Path(backup).name == config_path.name + channel.BACKUP_SUFFIX
    assert Path(backup).parent == config_path.parent
    assert json.loads(Path(backup).read_text(encoding="utf-8")) == before

    after = json.loads(config_path.read_text(encoding="utf-8"))
    assert after["meetings"]["pm"]["slack_channel"] == "C0NEWNEW"

    # 逐欄對帳：把改掉的那一欄補回原值之後，兩份設定必須一模一樣
    after["meetings"]["pm"]["slack_channel"] = before["meetings"]["pm"]["slack_channel"]
    assert after == before


def test_set_channel_keeps_the_config_hand_editable(tmp_path: Path):
    """回寫後的設定檔仍然是人可以手改的那種：繁中不轉義、有縮排。

    這份檔案的說明文件就是「請自行編輯 config.json」（setup 最後印的那兩行）。
    重寫成 `\\u9031\\u4e09` 的一整行 JSON 讀得回來、每條行為測試照樣綠 ——
    壞掉的只有下一個人打開它的時候。
    """
    config_path = tmp_path / "config.json"
    config_fixture(config_path)

    channel.set_channel("pm", "C0NEWNEW", config_path=config_path)

    raw = config_path.read_text(encoding="utf-8")
    assert "週三_PM_會議" in raw, "繁中被轉義成 \\uXXXX 了"
    assert len(raw.splitlines()) > 1, "整份塞成一行，手改不了"


def test_the_backup_is_the_state_from_just_before_this_write(tmp_path: Path):
    """備份救的是「上一版」，所以第二次回寫要蓋掉第一次的備份。

    備份只在第一次建立（或反過來，在寫入**之後**才備份）的話，
    它存下來的就不是我要回滾的那份 —— 而回滾這件事只有出事那天才會被發現。
    """
    config_path = tmp_path / "config.json"
    config_fixture(config_path)

    backup = channel.set_channel("pm", "C0FIRST", config_path=config_path)
    assert json.loads(Path(backup).read_text(encoding="utf-8"))["meetings"]["pm"][
        "slack_channel"
    ] is None

    again = channel.set_channel("pm", "C0SECOND", config_path=config_path)

    assert Path(again) == Path(backup)
    assert (
        json.loads(Path(again).read_text(encoding="utf-8"))["meetings"]["pm"]["slack_channel"]
        == "C0FIRST"
    )


def test_set_channel_refuses_an_unknown_meeting_key(tmp_path: Path):
    """key 打錯時要炸，不是默默長出一場不存在的會議 —— 那會安靜到下次開會才發現。"""
    config_path = tmp_path / "config.json"
    before = config_fixture(config_path)

    with pytest.raises(KeyError):
        channel.set_channel("typo", "C0NEWNEW", config_path=config_path)

    assert json.loads(config_path.read_text(encoding="utf-8")) == before


def test_cli_writes_the_channel_back_and_keeps_a_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    """驗收條件 8 的主語是 CLI —— DM 提醒裡印的就是這行指令，它得真的能跑。

    寫進去的是**哪個檔**只有走真檔案才驗得到：stub 掉 `set_channel` 的接線測試
    對「取錯設定檔路徑」是全綠的，而那個症狀是回寫進一份沒人在讀的檔。
    """
    config_path = tmp_path / "config.json"
    before = config_fixture(config_path)
    monkeypatch.setattr(channel, "CONFIG_PATH", config_path)
    monkeypatch.setattr(sys, "argv", ["channel.py", "--meeting", "pm", "--channel", "C0NEWNEW"])

    code = 0
    try:
        channel.main()
    except SystemExit as exc:
        code = exc.code or 0
    assert capsys.readouterr().out.strip(), "寫完什麼都不說，使用者不知道成功了沒"

    assert code == 0
    after = json.loads(config_path.read_text(encoding="utf-8"))
    assert after["meetings"]["pm"]["slack_channel"] == "C0NEWNEW"

    backup = config_path.with_name(config_path.name + channel.BACKUP_SUFFIX)
    assert backup.is_file(), "回寫使用者唯一一份設定檔卻沒留備份"
    assert json.loads(backup.read_text(encoding="utf-8")) == before

    # 逐欄對帳：把改掉的那一欄補回原值之後，兩份設定必須一模一樣
    after["meetings"]["pm"]["slack_channel"] = before["meetings"]["pm"]["slack_channel"]
    assert after == before


def test_cli_writing_one_meeting_leaves_the_others_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    """另一場會議的 channel 不准被波及 —— 症狀是通知從此發到錯的部門，而且沒人會查設定檔。"""
    config_path = tmp_path / "config.json"
    before = config_fixture(config_path)
    monkeypatch.setattr(channel, "CONFIG_PATH", config_path)
    monkeypatch.setattr(sys, "argv", ["channel.py", "--meeting", "pm", "--channel", "C0NEWNEW"])

    channel.main()
    capsys.readouterr()

    after = json.loads(config_path.read_text(encoding="utf-8"))
    assert after["meetings"]["team"] == before["meetings"]["team"]
    assert sorted(after["meetings"]) == sorted(before["meetings"]), "會議數量變了"


def test_cli_hands_the_parsed_arguments_to_set_channel(monkeypatch: pytest.MonkeyPatch, capsys):
    """驗收條件 8 的 CLI 接線 —— DM 提醒裡印的就是這行指令，它得真的接到回寫那支。

    兩個參數都對調不了：`--meeting` 與 `--channel` 接反的症狀是把 channel ID
    當成會議 key，一路 KeyError 到使用者臉上。
    """
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(
        channel, "set_channel", lambda *a, **kw: (calls.append((a, kw)), Path("/tmp/bak"))[1]
    )
    monkeypatch.setattr(sys, "argv", ["channel.py", "--meeting", "pm", "--channel", "C0NEWNEW"])

    code = 0
    try:
        channel.main()
    except SystemExit as exc:
        code = exc.code or 0
    capsys.readouterr()

    assert code == 0
    (args, kwargs), = calls
    assert (args + (kwargs.get("meeting_key"), kwargs.get("channel")))[:2] == ("pm", "C0NEWNEW")


def test_cli_exits_nonzero_on_an_unknown_meeting_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    """key 不存在時印訊息並以 1 收場，且設定檔原封不動。

    DM 裡的指令被貼錯 key 時要看得出來 —— `KeyError` 的 traceback 對操作者
    等於沒說明理由，而默默長出一場不存在的會議會安靜到下次開會才發現。
    """
    config_path = tmp_path / "config.json"
    before = config_fixture(config_path)
    monkeypatch.setattr(channel, "CONFIG_PATH", config_path)
    monkeypatch.setattr(sys, "argv", ["channel.py", "--meeting", "typo", "--channel", "C0NEWNEW"])

    with pytest.raises(SystemExit) as exc:
        channel.main()

    assert exc.value.code == 1
    assert capsys.readouterr().out.strip(), "靜默失敗 —— 使用者會以為寫進去了"
    assert json.loads(config_path.read_text(encoding="utf-8")) == before


@pytest.mark.parametrize("argv", [
    ["channel.py", "--meeting", "pm"],
    ["channel.py", "--channel", "C0NEWNEW"],
    ["channel.py"],
], ids=["no-channel", "no-meeting", "neither"])
def test_cli_requires_both_arguments(argv, monkeypatch: pytest.MonkeyPatch, capsys):
    """兩個都 required：少一個而還去動設定檔的話，會寫出半套的值。"""
    monkeypatch.setattr(channel, "set_channel", lambda *a, **kw: pytest.fail("不該走到回寫"))
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as exc:
        channel.main()

    assert exc.value.code != 0
    capsys.readouterr()


# ---------------------------------------------------------------- mutation 佈線


def channel_defs() -> set[str]:
    return {
        n.name
        for n in ast.parse((SCRIPTS / "channel.py").read_text(encoding="utf-8")).body
        if isinstance(n, ast.FunctionDef)
    }


def makefile_pure_names() -> set[str]:
    """Makefile 裡 `PURE := \\` 那塊列出的函式名。"""
    block = (ROOT / "Makefile").read_text(encoding="utf-8").split("PURE := \\", 1)[1]
    return {line.strip(" \t\\") for line in block.split("\n\n", 1)[0].splitlines()} - {""}


#: `main` 是 CLI 進入點（argparse ＋ sys.exit），不掛 mutation。其餘都該掛。
CLI_ONLY = {"main"}

#: 見 `test_push_shared_glossary.py`：mutmut 的 `mutants/` 複本裡 top-level def 已被
#: 改寫成 `x_<名>__mutmut_<N>`，拿去跟 Makefile 對帳必紅，而兩道事後守衛都看不見。
MUTATED_COPY = any("__mutmut_" in name for name in channel_defs())


def test_channel_is_in_the_mutation_scope():
    """三態判斷沒掛進 `source_paths` 就是量不到它 —— 而它正是這張票唯一的邏輯。"""
    assert "channel.py" in (ROOT / "setup.cfg").read_text(encoding="utf-8")


@pytest.mark.skipif(
    MUTATED_COPY,
    reason="mutmut 的 mutants/ 複本：這條量的是 repo 佈線，不是模組行為",
)
def test_every_pure_function_in_channel_is_in_the_mutation_scope():
    """純函式加了卻沒掛進 `PURE` 就是量不到它。兩側各自算出來再比，不手抄要守的那份。"""
    defined = channel_defs()
    assert defined, "AST 解不出 def，這條測試量的是空集合"

    assert makefile_pure_names() & defined == defined - CLI_ONLY
