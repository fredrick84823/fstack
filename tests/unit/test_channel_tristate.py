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

**這個檔裡 `channel` 有兩顆模組物件，是刻意的。** 純函式那組走 `load_script("channel")`
（模組 `__name__` 是路徑推出來的點分名），發佈／CLI 接線那組經由
`import create_gdoc_from_md`，而它自己 `import channel` 拿到的是 import system 那顆
（`__name__ == "channel"`）。repo 既有作法一樣分兩種，只是分在兩個檔
（`test_drift_warning.py` 走 `load_script("parity")`、`test_publish_drift.py` 走
`import parity`）。

代價講清楚，免得下一個人重新爭論一次：mutmut 的 trampoline 是拿模組 `__name__` 去配
mutant key，所以**只有 `load_script` 那顆的呼叫**算得進 channel.py 的 mutant 覆蓋；
接線那幾條（`publish_once` 與 CLI）的 hit 配不上 key，對 mutation 分數沒有貢獻。
它們守的是別的東西 —— 「發佈流程真的接上了三態」「寫進去的是哪個檔」——
那些本來就不是 mutation 量得到的層。反過來把純函式那組也改成平常 import 的話，
`channel_state` 等五支會整批變 🫥 no-tests（實測過），所以不要統一。"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from types import ModuleType

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


# ---------------------------------------------------------------- 要送出去的那個值


def test_channel_id_strips_the_padding_off_a_real_channel():
    """設定檔是手改的，ID 前後帶空白很常見。送出去的要是清乾淨的那個值。"""
    assert channel.channel_id(meeting_with("  C0PADDED  ")) == "C0PADDED"


def test_channel_id_is_empty_for_unset():
    """`null` 同理 —— 而且它多一個坑：回 `None` 的話呼叫端一 `.strip()` 就 AttributeError。"""
    assert channel.channel_id(meeting_with(None)) == ""
    assert channel.channel_id(meeting_with(ABSENT)) == ""


@pytest.mark.parametrize("value", [None, "", "   ", "C0XXXXXXXXX", "  C0PADDED  "], ids=[
    "null", "muted", "whitespace", "plain", "padded",
])
def test_channel_id_agrees_with_channel_state(value):
    """兩支是同一條規則的兩面：`SEND` 時一定有值可送，其餘時一定沒有。

    這支存在的理由就是「呼叫端不要自己再判一次」（Feature Envy）。兩份規則一旦分岔，
    症狀是 `channel_state` 說要發、`channel_id` 給空字串 —— Slack 回
    `channel_not_found`，而記錄那邊一切正常，沒人會回頭查設定檔。
    """
    meeting = meeting_with(value)
    if channel.channel_state(meeting) == channel.SEND:
        assert channel.channel_id(meeting)
    else:
        assert channel.channel_id(meeting) == ""


# ------------------------------------------------ setup 那題的答案 → 要寫進 JSON 的值


def test_an_answer_overwrites_whatever_was_there():
    """有答案就覆蓋 —— 三種既有狀態一視同仁，包含改掉一個已經設好的 channel。"""
    assert channel.channel_from_answer("C0NEW", "C0OLD") == "C0NEW"
    assert channel.channel_from_answer("C0NEW", None) == "C0NEW"
    assert channel.channel_from_answer("C0NEW", "") == "C0NEW"


def test_enter_on_an_unset_meeting_stays_unset():
    """沒設過、按 Enter → 還是「還沒設定」，提醒繼續出現。"""
    assert channel.channel_from_answer("", None) is None
    assert channel.channel_state({"slack_channel": channel.channel_from_answer("", None)}) == (
        channel.UNSET
    )


def test_enter_on_a_muted_meeting_stays_muted():
    """**這是 Spec 軸抓到的那個 bug。**

    `""`（我已經決定這場不發通知）按 Enter 被寫成 `null` 的話，它就無聲降級成
    「還沒設定」，之後每一場會都被 DM 一次 —— 而區分這兩態是這張票的全部內容。
    兩者都 falsy，`answer or existing or None` 這種寫法剛好會踩到。
    """
    assert channel.channel_from_answer("", "") == ""
    assert channel.channel_state({"slack_channel": channel.channel_from_answer("", "")}) == (
        channel.MUTED
    )


def test_enter_on_a_configured_meeting_keeps_the_channel():
    """沒答案就原樣 —— 第三種既有狀態。

    這格與上面兩格是同一條規則（空答案＝不改變這個欄位），不是三個各自的特例。
    只對 `""` 特別處理的寫法在這裡會回 `None`，把設好的 channel 洗掉，
    而症狀跟 `""` 被降級成 `null` 一樣安靜：使用者只是重跑了一次 setup、什麼都沒改。
    """
    assert channel.channel_from_answer("", "C0OLD") == "C0OLD"
    assert channel.channel_state({"slack_channel": channel.channel_from_answer("", "C0OLD")}) == (
        channel.SEND
    )


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


def test_the_published_channel_is_the_stripped_one(publish_once):
    """設定檔手改留下的前後空白不准跟著送出去 —— Slack 只會回 `channel_not_found`，
    而那則通知沒發出去這件事，在發佈流程這邊看起來一切正常。"""
    run = publish_once("  C0PADDED  ")

    assert len(run.sent) == 1
    assert run.channel_arg == "C0PADDED"
    assert run.dms == []
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
    monkeypatch.setattr(slack, "_post", lambda *a, **kw: pytest.fail("沒 token 還是送了"))

    assert slack.send_dm("測試提醒") is False
    assert capsys.readouterr().out.strip(), "靜默回 False 等於沒人知道提醒沒送出去"


def test_send_dm_does_not_post_when_there_is_no_recipient(monkeypatch, capsys):
    """有 token 但沒設 `slack_dm_user` → 不該走到 `_post`（沒有對象可送）。"""
    monkeypatch.setattr(slack, "load_config", lambda: {"slack_bot_token": "xoxb-t"})
    monkeypatch.setattr(slack, "_post", lambda *a, **kw: pytest.fail("沒有收件對象還是送了"))

    assert slack.send_dm("測試提醒") is False
    assert capsys.readouterr().out.strip()


def test_send_dm_posts_the_text_to_the_configured_user(monkeypatch, capsys):
    """設定齊全時，送出去的對象是 `slack_dm_user`、內容是原封不動的那段字。

    斷言打在 `_post` 收到的參數上：`send_dm` 把 text 弄丟或送給別人，
    回傳值照樣是 `True`。
    """
    calls: list[tuple] = []
    monkeypatch.setattr(
        slack, "load_config", lambda: {"slack_bot_token": "xoxb-t", "slack_dm_user": "U0ME"}
    )
    monkeypatch.setattr(slack, "_post", lambda *a: (calls.append(a), True)[1])

    assert slack.send_dm("測試提醒") is True
    capsys.readouterr()

    (token, target, text, _what), = calls
    assert (token, target, text) == ("xoxb-t", "U0ME", "測試提醒")


def fake_slack_sdk() -> tuple[ModuleType, list]:
    """一顆假的 `slack_sdk`：`WebClient(token).chat_postMessage(**kw)` 記下來就好。"""
    sent: list = []

    class WebClient:
        def __init__(self, token=None, **kw):
            sent.append(("init", token))

        def chat_postMessage(self, **kw):
            sent.append(("post", kw))
            return {"ok": True}

    sdk = ModuleType("slack_sdk")
    sdk.WebClient = WebClient
    errors = ModuleType("slack_sdk.errors")

    class SlackApiError(Exception):
        def __init__(self, message="", response=None):
            super().__init__(message)
            self.response = response

    errors.SlackApiError = SlackApiError
    sdk.errors = errors
    return sdk, sent


def test_post_sends_the_text_to_the_target(monkeypatch, capsys):
    """`_post` 是兩支（channel 通知與 DM）唯一的出口，所以 target 與 text 要原樣帶到。"""
    sdk, sent = fake_slack_sdk()
    monkeypatch.setitem(sys.modules, "slack_sdk", sdk)
    monkeypatch.setitem(sys.modules, "slack_sdk.errors", sdk.errors)

    assert slack._post("xoxb-t", "C0ABC", "內容", "通知") is True
    capsys.readouterr()

    assert ("init", "xoxb-t") in sent
    (post,) = [kw for tag, kw in sent if tag == "post"]
    assert post["channel"] == "C0ABC"
    assert post["text"] == "內容"


def test_post_survives_a_machine_without_slack_sdk(monkeypatch, capsys):
    """`slack_sdk` 沒裝時印一行回 `False`，不拋 ImportError。

    `slack_sdk` 移進函式裡 import 之後，有 token 但沒裝套件的機器會**在 Doc 建好之後**
    才炸 —— 那時炸掉等於把 `RESULT_URL` 連同整個交棒一起吞掉，與「通知失敗不擋流程」
    完全相反。`mutants/` 那道 env 與 CI 都沒裝它，所以這條在那裡是真的走這條路。
    """
    monkeypatch.setitem(sys.modules, "slack_sdk", None)  # import 時 ImportError

    assert slack._post("xoxb-t", "C0ABC", "內容", "通知") is False
    assert capsys.readouterr().out.strip(), "靜默回 False 等於沒人知道為什麼沒收到"


# ---------------------------------------------------------------- setup 寫出來的值


def run_setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing: dict | None = None,
    channel_answer: str = "",
) -> dict:
    """真的跑一次 `setup_config`，全程只碰 `tmp_path`，回傳寫出來的 `pm會議` entry。

    `existing` 給的話先當成已存在的設定檔放好（模擬「重跑 setup」）。
    stub 看 prompt 文字決定回什麼，不靠問題順序 —— 順序是實作內部，會變。
    channel 那題一律按 Enter（回空字串）。
    """
    import setup as setup_mod

    config_path = tmp_path / "config.json"
    if existing is not None:
        config_path.write_text(
            json.dumps({"meetings": {"pm會議": existing}}, ensure_ascii=False), encoding="utf-8"
        )

    monkeypatch.setattr(setup_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(setup_mod, "CONFIG_PATH", config_path)
    monkeypatch.setattr(setup_mod, "setup_glossary_entries", lambda *a, **kw: None)

    rounds = {"n": 0}

    def answer(prompt: str = "") -> str:
        if "會議類型" in prompt and "空白則完成" in prompt:
            rounds["n"] += 1
            return "pm會議" if rounds["n"] == 1 else ""  # 第二輪空白 → 結束迴圈
        if "Slack Channel ID" in prompt:
            return channel_answer
        return ""  # 其餘全部跳過

    monkeypatch.setattr("builtins.input", answer)

    setup_mod.setup_config(with_audio=False)

    return json.loads(config_path.read_text(encoding="utf-8"))["meetings"]["pm會議"]


def test_setup_writes_null_not_empty_string_when_the_question_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """驗收條件 7：setup 跳過 channel 那題 → 寫出 `null`（還沒設定），不是 `""`（刻意不發）。

    寫成 `""` 的話，第一次設定完的每一場會議都變成「我決定不發通知」，
    提醒一次都不會出現 —— 而那正是這張票要修的症狀。

    真的驅動 `setup_config`：這條要守的就是「互動流程寫出去的值」，
    直接斷言一個自己捏的 dict 等於什麼都沒驗。
    """
    entry = run_setup(tmp_path, monkeypatch)

    assert entry["slack_channel"] is None
    assert channel.channel_state(entry) == channel.UNSET


def test_rerunning_setup_does_not_downgrade_a_muted_meeting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """**Spec 軸抓到的 bug 走完整流程的那一條。**

    一個 `""`（我已經決定這場不發通知）的會議，重跑 setup 按 Enter 就被寫成 `null`，
    於是無聲降級成「還沒設定」—— 之後每場會都被 DM 一次。使用者做的唯一動作是
    「重跑一次 setup、什麼都沒改」，所以這個退化不會有人聯想到原因。

    上面 `channel_from_answer` 那層的 case 只驗函式；這條驗 `setup.py` 真的接上了它。
    """
    entry = run_setup(tmp_path, monkeypatch, existing={"slack_channel": ""})

    assert entry["slack_channel"] == ""
    assert channel.channel_state(entry) == channel.MUTED


def test_rerunning_setup_keeps_a_configured_channel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """已經設好 channel 的會議，重跑 setup 按 Enter 不該把它洗掉。"""
    entry = run_setup(tmp_path, monkeypatch, existing={"slack_channel": "C0KEEPME"})

    assert entry["slack_channel"] == "C0KEEPME"
    assert channel.channel_id(entry) == "C0KEEPME"


def test_setup_never_writes_a_fourth_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """那題打了空白就走 —— 寫進 JSON 的必須是三態之一，不是 `"   "`。

    `"   "` 既不是 `null` 也不是 `""`：`channel_state` 判它不是 `SEND`，但沒有任何
    路徑處理它，而它長得跟「刻意不發」一模一樣（都不發、都不提醒？看實作怎麼落）。
    現在靠 `ask()` 會 strip 擋住，這條釘的就是那個保證。
    """
    entry = run_setup(tmp_path, monkeypatch, channel_answer="   ")

    assert entry["slack_channel"] in (None, "")
    assert channel.channel_state(entry) in (channel.UNSET, channel.MUTED)


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
