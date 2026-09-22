#!/usr/bin/env python3
"""
reconcile_drive.py - 每小時掃 Shared Drive：日期資料夾有音檔、沒有會議記錄，就自己產。

**reconcile，不是事件觸發。** 事件觸發靠「發生了什麼」—— Mac 關機、Drive 同步延遲、
腳本當掉，錯過就永遠錯過。這支靠「現在長怎樣」：漏掉一輪下一輪自己補回來，沒有差集
就不動。兩個都做是多一條程式路徑換低延遲，而會議記錄不需要秒級。

    {Shared Drive}/{系列資料夾}/{YYYYMMDD}[_{場次}]/
                        │      │            │      └─ 一天多場：各開一個資料夾，
                        │      │            │         後綴成為該場的 meeting_instance
                        │      │            └─ 日期來自資料夾名，不從檔名解析
                        │      └─ 音檔掉在這一層 ──▶ 不產，只提醒（沒有日期可信）
                        └─ 反查設定檔的 folder_name → 這是哪種會議

    該日期資料夾有音檔 && 沒有會議記錄  ──▶ 產

**這支是無人看管的**，所以每一條「失敗時的行為」都比「成功時的行為」重要：

| 情況 | 行為 |
|---|---|
| 首次執行（沒有狀態檔） | 強制 dry-run，只印差集 |
| 每輪處理上限 | `MAX_PER_ROUND` 場。判準寫錯時不會一次燒 20 次 NotebookLM |
| 系列資料夾在設定檔裡找不到 | 不產，只 DM。缺會議類型脈絡，硬產出來的是壞的 |
| 同一個日期資料夾有多個音檔 | 不產。挑一個產會讓另一半永遠沒有機會。訊息帶著下一步：一天多場請各開一個 `YYYYMMDD_<場次>` |
| 日期資料夾名兩種形狀都不是 | 不產，但**不靜靜跳過**（裡面有音檔時）。跳過等於那個資料夾是隱形的 |
| 音檔躺在系列資料夾根目錄 | 不產，兩軌提醒「請移進日期資料夾」。沒有日期資料夾就沒有可信的日期 |
| 任何一場沒產出（跳過或失敗） | **兩軌**：維運者 DM 拿技術細節，會議 channel 拿「有人在處理」的提醒 |
| 同一場、同一個原因連續命中 | channel 那則一天只發一次（狀態檔記到 `notified`）。DM 照舊每輪 |
| 該會議類型沒設 `slack_channel` | 記錄照產，通知走 DM fallback（`channel.py` 的三態） |
| Google 憑證會開瀏覽器 | 一開始就擋（`credential_gap`），不要卡在沒有人的提示上 |
| NotebookLM 認證失效 | **切音訊前**就驗，失敗就 DM 並停，退出碼非 `0` |
| Drive 翻頁超過上限 | 報錯收工（`list_all`）。無上限的翻頁是「跑不完」不是「變紅」 |

判準錯的代價**不對稱**：少算一場只是晚一小時，多算一場是重跑 NotebookLM 並覆寫既有
記錄。每輪上限與首次強制 dry-run 都是為這個不對稱設的，不是可選項。

**音檔歸屬與發佈流程相反。** 發佈流程的「跑完刪本機音檔」是為「本機是原件、Drive 是
副本」寫的，所以上傳後要另外向 Drive 查實際位元數才敢刪。這裡反過來：Drive 是原件、
本機只是暫存下載。Drive 上的音檔一律不動，本機暫存整個目錄跑完就刪，那三道保險沒有
對象。因此發佈那步**不帶** `--audio-file` / `--delete-local-audio` —— 帶了會把暫存
那份再上傳一次，用我們自己取的檔名，在同一個資料夾裡變成第二個音檔。

用法（與 SKILL.md 一致，都從 skill 目錄用 uv 跑）：
    uv run scripts/reconcile_drive.py              # 正常一輪（cron 每小時）
    uv run scripts/reconcile_drive.py --dry-run    # 只印差集，不產
    另有 --today / --state（測試用）。**每輪上限與 7 天窗沒有旗標** —— 票上它們是
    為判準錯的代價不對稱設的，做成旗標等於留一個一行就能關掉的洞。

**預設是真的會產，不是 dry-run** —— 與 `backfill_local_archive.py` 相反。那支是人手動
跑的一次性補齊，dry-run 當預設才安全；這支是排程跑的，預設不做事等於永遠不做事。
首次執行的那一次例外由狀態檔管，不由旗標管。

退出碼：
    0  這輪走完（沒有差集、dry-run、或該產的都產了）
    1  出錯：憑證、Drive API、翻頁超上限、NotebookLM 認證、或某一場產製失敗
    2  參數錯誤
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date, datetime
from operator import attrgetter
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).parent))
from backfill_local_archive import list_all
from extract_audio_sources import (
    CONFIG_DIR,
    CONFIG_PATH,
    DEFAULT_PROMPT_PATH,
    SKILL_DIR,
    get_google_credentials,
    load_config,
)
from channel import SEND, channel_id, channel_state
from local_archive import (
    DATE_DIR_EXAMPLE,
    DATE_DIR_SHAPES,
    NOTE_PREFIX,
    instance_order_key,
    parse_date_dir,
)
from send_slack_notification import format_date_display, send_channel, send_dm

STATE_PATH = CONFIG_DIR / "reconcile-state.json"
SKILL_MD = SKILL_DIR / "SKILL.md"

WINDOW_DAYS = 7
MAX_PER_ROUND = 2

FOLDER_MIME = "application/vnd.google-apps.folder"
DOC_MIME = "application/vnd.google-apps.document"

# 與 SKILL.md 的「輸入類型與路由」同一份清單。
AUDIO_SUFFIXES = (".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".opus")

# 掃到了但沒有產的四個理由。字串而非 enum：它們會被印進 stdout 與 DM，也會被測試
# 逐字斷言（同 `channel.DM_HEADER`）。
UNKNOWN_SERIES = "系列資料夾不在設定檔的任何會議類型"
UNKNOWN_FOLDER = f"資料夾名不是 {DATE_DIR_SHAPES}，所以掃不到"
# 「不產」的理由要**帶著下一步**。只講現象的話，看到 DM 的人知道系統沒動，卻不知道
# 該把檔案搬去哪 —— 而「一天多場請各開一個資料夾」這個約定就是這樣一直是空的（#56）。
MULTI_AUDIO = (
    "同一個日期資料夾有多個音檔，一天多場請各開一個資料夾"
    f"（{DATE_DIR_SHAPES}，{DATE_DIR_EXAMPLE}）"
)
OVER_LIMIT = "超過本輪上限，下一輪會再看到"

# 掃到了但**不在任何日期資料夾裡**的音檔。這不是「沒產」的第四個理由（它沒有場次、
# 沒有日期，進不了 `Session`），是另一條清單 —— 見 `compute_misplaced`。
MISPLACED = "音檔躺在系列資料夾根目錄，沒有日期資料夾"

# 抬頭自成一行、粗體，下一行才是「這次是哪一件事」。粗體只包抬頭本身，因為那是
# 每一則 DM 都一樣的那一格 —— 會變的那句留原體，兩行就有了層次。
DM_HEADER = "📮 *每小時 reconcile 有東西需要你看一眼*"

# 同一個事件，兩則不同的訊息、兩個收件者：維運者的 DM 帶例外型別與訊息（修復的人要
# 的），會議 channel 那則只講「哪一場、為什麼、已經有人在處理」。**不是轉發** ——
# 收到 channel 那則的人不會去 debug，例外類別名只會讓他們回頭來問維運者，而那正是
# 這張票要省掉的那一趟。
CHANNEL_HEADER = "📋 *這場的會議記錄還沒產出來*"
MULTI_AUDIO_CAUSE = "這天的資料夾裡有不只一個錄音檔，系統不確定該用哪一個"
UNKNOWN_FOLDER_CAUSE = "錄音放在一個系統認不得名字的資料夾裡，所以沒有被掃到"
FAILED_CAUSE = "產製途中出了狀況"

# 掃到了沒產、而且該讓會議成員知道的那幾個理由 → 給人看的那句。
# `UNKNOWN_SERIES` 不在裡面：那些場次連 `meeting_key` 都沒有，不知道要發哪個 channel
# （三態自然落在 `UNSET`），所以本來就只有維運者的 DM 會提到它們。`OVER_LIMIT` 也不在：
# 下一輪就處理完了 —— 同 `dm_skipped`，每輪喊一次只會讓人學會忽略這則提醒。
CHANNEL_CAUSES = {
    MULTI_AUDIO: MULTI_AUDIO_CAUSE,
    UNKNOWN_FOLDER: UNKNOWN_FOLDER_CAUSE,
}

# 放錯層那則的角色與上面兩則**相反**：那兩則是「有人在處理、你不用做什麼」，這一則
# 是「只有你做得了、請去移動它」。所以另起一個抬頭，不共用 `CHANNEL_HEADER`。
MISPLACED_HEADER = "📥 *有一個錄音檔還沒進到日期資料夾*"
MISPLACED_CAUSE = "錄音檔放在系列資料夾最外層"

# 維運者那兩則 DM 的去重身份（`dm_notice_key` 的第一格）。跟 channel 那幾則共用同一個
# 狀態檔與同一支 `notice_due`，所以名字要跟 `notice_key` 的第三格分得開。
MISPLACED_DM = "維運者DM：放錯層的音檔"
UNREGISTERED_DM = "維運者DM：不在設定檔裡的系列"

# 子行程的硬上限。NotebookLM 那段要上傳幾十段再等 AI 處理，所以給得寬；但一定要有，
# 卡住的排程是「每小時卡一次而沒人知道」，不是「變紅」。
EXTRACT_TIMEOUT = 3600
SYNTHESIS_TIMEOUT = 1800
PUBLISH_TIMEOUT = 900
AUTH_TIMEOUT = 120


class Session(NamedTuple):
    """一個日期資料夾。`reason` 是空字串表示這場要產。

    `name` 是 Drive 上那個資料夾名本身（`20260916` 或 `20260916_am`），`date` 與
    `instance` 是它拆出來的兩半；名字認不得時 `date` 與 `instance` 都是 `""`。

    訊息一律指認 `name` 而不是 `date`：同日兩場的 `date` 一模一樣，只印日期的話讀 DM
    的人分不出是哪一場 —— 而分不出是哪一場，跟這張票要修的「第二個資料夾是隱形的」
    是同一種失明。
    """

    series: str
    name: str
    date: str
    instance: str
    meeting_key: str | None
    audio: tuple[dict, ...]
    reason: str


class Round(NamedTuple):
    """這一輪的差集。`pending` 要產，`skipped` 每一筆都帶著沒產的理由。"""

    pending: list[Session]
    skipped: list[Session]


class Misplaced(NamedTuple):
    """一個躺在系列資料夾根目錄的音檔。**沒有 `date`** —— 這正是它的問題本身。"""

    series: str
    meeting_key: str | None
    file_id: str
    name: str


class Scan(NamedTuple):
    """掃一輪 Drive 看到的兩層東西。

    分成兩個欄位而不是兩支函式：兩層是**同一次** `files().list()` 的回傳（見
    `scan_drive`），拆成兩支就等於每個系列多打一次 Drive 換一個不會更清楚的介面。
    """

    listings: list[dict]
    roots: list[dict]


# ─── Seam ① 純函式層 ──────────────────────────────────────────────────────────
#
# str/dict in → str/dict out，不碰網路。`credential_gap` 與 `prompt_file` 是例外：它們
# 碰檔案系統，但碰的是測試自己建的 tmp 目錄（同 `channel.set_channel`、`history_index`
# 的那幾支），所以照樣掛進 mutation 範圍。Drive 掃描、下載與三個子行程在下面兩節。

def in_window(folder_date: str, today: str) -> bool:
    """`folder_date` 是否落在以 `today` 結尾的 `WINDOW_DAYS` 天窗內。兩個都是 YYYYMMDD。

    窗是**固定**的，不是「上次跑到哪」：每小時跑一次，落差不會累積；7 天足以涵蓋 Mac
    關機幾天，而且第一次跑不會把幾個月的舊資料夾全部翻出來。

    ponytail: 天花板是「關機超過 7 天的那幾場永遠補不回來」。要升級的話是記下上次
    成功掃到哪一天、窗取 `max(7, 距上次)` —— **不是**把窗調大，調大等於每小時多掃
    幾十個資料夾來換一年用不到一次的情況。

    未來日期回 `False`（`delta < 0`）：打錯的日期資料夾不該被當成今天的會議產一份。
    解不出日期的也回 `False` 而不是拋 —— 資料夾名是別人打的，一個 `202609xx` 不該讓
    整輪 reconcile 掛掉。
    """
    try:
        delta = (_as_date(today) - _as_date(folder_date)).days
    except ValueError:
        return False
    return 0 <= delta < WINDOW_DAYS


def _as_date(text: str) -> date:
    return datetime.strptime(text, "%Y%m%d").date()


def is_audio(name: str) -> bool:
    """檔名看起來是不是音檔。副檔名比對，大小寫不敏感。"""
    return name.lower().endswith(AUDIO_SUFFIXES)


def is_note(file: dict) -> bool:
    """這個 Drive 檔是不是這場的會議記錄。

    **兩個條件都要**：Google Doc，而且檔名以 `會議記錄` 開頭。只看檔名的話，同一個
    資料夾裡的 `會議記錄_….md`（源自本機歸檔被人手動丟上來）會被當成已經有記錄；
    只看 mimeType 的話，任何一份放進資料夾的 Doc 都會讓這場永遠不產。

    ponytail: 判準是**檔名前綴**，所以有人把 Doc 改掉名字，下一輪就會重產一份並蓋掉
    那場的既有記錄。要升級的話是在 Doc 上寫一個 `appProperties` 標記、改認那個標記
    —— 但那要先讓 `create_gdoc_from_md.py` 開始寫它，而既有的 Doc 一份都沒有。
    """
    return file.get("mimeType") == DOC_MIME and file["name"].startswith(NOTE_PREFIX)


def compute_pending(
    folders: list[dict],
    known_series: dict[str, str],
    today: str,
    *,
    limit: int = MAX_PER_ROUND,
) -> Round:
    """吃日期資料夾清單，吐這一輪的差集。**純函式** —— 不碰 Drive、不碰時鐘、不碰檔案。

    `folders` 每筆是 `{"series": 系列資料夾名, "name": 日期資料夾名,
    "files": [{"id":…, "name":…, "mimeType":…}]}`；`known_series` 是系列資料夾名 →
    會議 key。

    日期資料夾名有兩種合法形狀：`YYYYMMDD`，以及一天多場時各開一個的
    `YYYYMMDD_<場次>`（`references/multi-session.md` 的 `meeting_instance`）。
    兩種都不是的**不靜靜跳過** —— 帶著 `UNKNOWN_FOLDER` 進 `skipped`，讓它走通知那條
    路。跳過的話那個資料夾是隱形的，而把檔案丟進去的人會以為已經丟進去了（#56）。

    排序見 `_by_date`，**舊的先**：積壓要從最舊的開始消化，不然一場久久沒人處理的會議
    會永遠排在新的後面。上限之外的不是丟掉，是帶著 `OVER_LIMIT` 進 `skipped` ——
    丟掉的話沒有人知道這輪還欠幾場。
    """
    candidates: list[Session] = []
    skipped: list[Session] = []

    for folder in folders:
        parsed = parse_date_dir(folder["name"])
        folder_date, instance = parsed or ("", "")
        # 認不得的名字沒有日期，所以過不了窗 —— 窗的判斷只對認得出日期的那些做。
        if parsed and not in_window(folder_date, today):
            continue
        files = folder["files"]
        if any(is_note(f) for f in files):
            continue
        audio = tuple(f for f in files if is_audio(f["name"]))
        # 沒有音檔就沒有這場。認不得的資料夾也走這一關：`舊資料`、`備份` 這種本來就
        # 不是要丟錄音的資料夾不該每小時提醒一次，而「裡面躺著錄音」正是「有人放錯地方」
        # 唯一可靠的證據。
        if not audio:
            continue

        key = known_series.get(folder["series"])
        if not parsed:
            reason = UNKNOWN_FOLDER
        elif not key:
            reason = UNKNOWN_SERIES
        elif len(audio) > 1:
            reason = MULTI_AUDIO
        else:
            reason = ""
        session = Session(
            series=folder["series"],
            name=folder["name"],
            date=folder_date,
            instance=instance,
            meeting_key=key,
            audio=audio,
            reason=reason,
        )
        (skipped if reason else candidates).append(session)

    candidates.sort(key=_by_date)
    skipped += [s._replace(reason=OVER_LIMIT) for s in candidates[limit:]]
    skipped.sort(key=_by_date)
    return Round(candidates[:limit], skipped)


def _by_date(session: Session) -> tuple:
    """排序鍵：**舊的先**，同一天照場次的真實時序，再用系列名定死。

    同日兩場照字母序排的話 `_afternoon` 會排到 `_am` 前面（`af` < `am`），而積壓是從
    最前面開始消化的 —— 用的是 `instance_order_key` 本人，與 `history_index.find_notes`
    同一支判準，不在這裡另寫一次（兩份會靜靜地漂開，而漂開時兩邊都不會變紅）。

    認不得名字的那些 `date` 是 `""`，排在所有日期之前 —— 它們是最需要有人動手的那幾筆。
    """
    return (session.date, instance_order_key(session.instance), session.series)


def compute_misplaced(roots: list[dict], known_series: dict[str, str]) -> list[Misplaced]:
    """系列資料夾**根目錄**的音檔清單。**純函式** —— 不碰 Drive、不碰時鐘。

    `roots` 每筆是 `{"series": 系列資料夾名, "files": [{"id":…, "name":…,
    "mimeType":…}]}`，也就是那個系列資料夾的直接子項（含日期資料夾本身）。

    兩道濾網缺一不可：**不是資料夾**（日期資料夾也在這份清單裡）、而且**是音檔**
    （既有的正式稿、source artifacts、其他雜檔躺在這一層是正常的，對它們出聲就是
    每小時假警報一次）。

    這裡**不產任何記錄**，只回報。沒有日期資料夾就沒有可信的日期 —— 從檔名推會撞上
    「檔名必須含八位連續數字」那條既有規則的例外，而推錯的代價是一份日期錯的記錄
    永久留在 Drive 上（`is_note` 下一輪就認定這場有記錄了）。

    排序是 `(series, name)`：清單順序是 Drive 給的，固定一份好讓 DM 每輪長一樣。
    """
    return sorted(
        (
            Misplaced(
                series=root["series"],
                meeting_key=known_series.get(root["series"]),
                file_id=file["id"],
                name=file["name"],
            )
            for root in roots
            for file in root["files"]
            if file.get("mimeType") != FOLDER_MIME and is_audio(file["name"])
        ),
        key=attrgetter("series", "name"),
    )


def series_map(meetings: dict) -> dict[str, str]:
    """設定檔 → {系列資料夾名: 會議 key}。

    `folder_name` 缺席時退回 `series_name`，與 `backfill_local_archive.scan_meeting`
    同一條規則 —— 那兩支在掃同一批資料夾。
    """
    return {
        meeting.get("folder_name", meeting["series_name"]): key
        for key, meeting in meetings.items()
    }


def credential_gap(config_dir: Path = CONFIG_DIR) -> str:
    """回 `""` 表示這台機器能在**沒有人**的情況下拿到 Google 憑證；否則回一句該修什麼。

    `get_google_credentials()` 走 OAuth client 那條時，拿不到可用 token 就會
    `flow.run_local_server()` —— 開瀏覽器等人按同意。互動式跑的時候那是正確行為；
    排程跑的時候它會**卡住**而不是變紅，而「跑不完」正是這張票點名要避的那一類失敗。

    **ADC 與這支 skill 自己的登入是兩份憑證**（8/31 踩過一次，誤判成「這台沒有憑證」）。
    這裡只檢查會開瀏覽器的那一條路徑：service account 不會、`google.auth.default()`
    那條（`credentials.json` 不存在或不是 OAuth client）也不會 —— 它要嘛成功要嘛拋。
    所以那兩種都回 `""`，不要順手報告「ADC 沒登入」，那正是 8/31 的誤判本身。
    """
    creds_path = config_dir / "credentials.json"
    try:
        creds_data = json.loads(creds_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(creds_data, dict) or not ({"installed", "web"} & set(creds_data)):
        return ""

    # 「讀不到」與「讀得到但沒有 refresh_token」不分兩條訊息：補救動作一樣（把它刪掉、
    # 手動跑一次 setup 重建授權），分開寫只是把同一句話寫兩遍再各自漂移。
    token_path = config_dir / "google_token.json"
    try:
        token = json.loads(token_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        token = None
    if not isinstance(token, dict) or not token.get("refresh_token"):
        return (
            f"{token_path} 讀不到、或沒有 refresh_token，下次取憑證會開瀏覽器等人按"
            f"同意 —— 排程沒有人。\n"
            f"   把它刪掉再手動跑一次 `uv run scripts/setup.py` 把授權重建起來。\n"
            f"   （這是 {creds_path} 那份授權，不是 ADC；兩者是不同的兩份。）"
        )
    return ""


def parse_handoff(stdout: str) -> dict[str, str]:
    """stdout 裡的 `RESULT_*` 行 → dict。交棒契約是流程之間唯一的介面，不重新推導路徑。"""
    handoff = {}
    for line in stdout.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip().startswith("RESULT_") and value.strip():
            handoff[key.strip()] = value.strip()
    return handoff


def prompt_file(config: dict) -> Path:
    """流程 C 的版型規範：config 指定的那份優先，不存在就退回 skill 內建的那份。

    指定了卻讀不到時**退回**而不是報錯：版型退化是下一份記錄看起來不一樣，沒有版型
    是這輪一份都產不出來。
    """
    configured = config.get("prompt_path")
    if configured:
        path = Path(configured).expanduser()
        if path.exists():
            return path
    return DEFAULT_PROMPT_PATH


def synthesis_prompt(handoff: dict[str, str], prompt_path: Path, notes_path: Path) -> str:
    """交給子 agent 跑流程 C 的那份 prompt。

    規格**指路徑不內嵌**：SKILL.md 與版型規範是這支 skill 出貨的那兩份，現讀才不會在
    prompt 裡養出一份會漂移的複本。四份 source artifacts 同理 —— 路徑都在交棒契約裡。

    這裡只做到 Markdown，不發佈：發佈要決定帶不帶 `--audio-file`，而這輪的答案是
    **不帶**（Drive 上那份是原件）。把那個決定交給 agent 等於每小時重擲一次骰子。
    """
    lines = "\n".join(f"{k}: {v}" for k, v in sorted(handoff.items()))
    return "\n".join([
        "你是 `generate-meeting-notes` skill 的 main agent，現在在流程 C（Main Synthesis）。",
        "",
        "先讀這兩份規格：",
        f"- {SKILL_MD}　只看「## 流程 C：Main Synthesis」一節，到 `### Step 1` 為止"
        "（Step 1 之後是發佈，這輪不歸你做）",
        f"- {prompt_path}　版型規範",
        "",
        "上一段流程印出的交棒契約（路徑都是真的，直接 Read）：",
        "```",
        lines,
        "```",
        "",
        f"依流程 C 產出正式稿 Markdown，**寫進這個檔**：{notes_path}",
        "",
        "只寫正式稿本身：不要前言、不要結語、不要說明你做了什麼。",
        "不要發佈 —— 不要建 Google Doc、不要發 Slack、不要跑任何腳本。發佈由呼叫端做。",
        f"寫完在回覆最後一行印 `WROTE: {notes_path}`。",
    ])


def dm_skipped(skipped: list[Session]) -> str:
    """掃到了卻沒產的那幾場要 DM 的字。沒有要講的就回 `""`，呼叫端據此決定發不發。

    `OVER_LIMIT` 那幾場**不進 DM**：它們下一輪就會被處理，每小時提醒一次只會讓人
    學會忽略這個 DM，而真正需要人介入的那兩個理由就跟著一起被忽略。
    """
    needs_human = [s for s in skipped if s.reason != OVER_LIMIT]
    if not needs_human:
        return ""
    lines = [DM_HEADER, f"{len(needs_human)} 場掃到了但沒有產", ""]
    lines += [f"• `{s.series}/{s.name}`　{s.reason}" for s in needs_human]
    lines += ["", f"設定檔：`{CONFIG_PATH}`"]
    return "\n".join(lines)


def dm_blocked(detail: str, count: int) -> str:
    """整輪（或某一場）停下來時要 DM 的字。

    `count` 是這輪本來要產幾場；`0` 表示還沒數到那一步（憑證、掃 Drive）。零的時候
    不印那句話 —— 「0 場一場都沒產」讀起來像沒事，而這通 DM 的存在就是因為有事。
    """
    summary = "有一段沒跑完"
    if count:
        summary += f"，{count} 場一場都沒產"
    # `detail` 帶的是例外型別與訊息，包進 code block：等寬字型讓 traceback 自己成一塊，
    # 也把「這段是機器講的」跟上面兩行人話分開。
    return "\n".join([DM_HEADER, summary, "", "```", detail, "```"])


def when_label(session: Session) -> str:
    """訊息裡指認「是哪一場」的那一段。

    認得出日期就印 `YYYY/MM/DD`，同日多場再帶上場次 —— 兩場的日期一模一樣，只印日期
    的話 channel 裡的人不知道講的是上午還是下午那場。

    認不得的資料夾名就印**名字本身**：那正是要請人改的那個東西，而
    `format_date_display("")` 會印成 `//`，等於把唯一的線索換成噪音。
    """
    if not session.date:
        return session.name
    display = format_date_display(session.date)
    return f"{display} {session.instance}" if session.instance else display


def failure_notice(series_name: str, when: str, cause: str) -> str:
    """會議 channel 那一則的字。`cause` 是給人看的那句，不是例外訊息。

    三句話：哪一場、為什麼、以及「已經有人在處理、你不用做什麼」。最後那句是這則訊息
    的**角色本身** —— 少了它，channel 裡看到的人會開始猜自己該不該補做點什麼，而修復
    負責人始終是維運者。所以 `cause` 只講現象不講下一步：下一步是維運者的事，寫進這
    則會跟最後那句自相矛盾（要請人動手的那句在 `dm_skipped` 的 `reason` 裡）。

    `when` 是已經給人看過的那串（`when_label`），不是 `YYYYMMDD` —— 同日多場與認不得
    的資料夾名都要指認得出來，而那個判斷不屬於「怎麼排版這幾行」。

    抬頭、內容、結語三段之間各留一行空白：每則訊息都一樣的那格（抬頭）與只有這一則
    才有的那格（哪一場、為什麼）分開，掃過去才知道自己要不要讀下去。
    """
    return "\n".join([
        CHANNEL_HEADER,
        "",
        f"*{series_name}*　{when}",
        f"原因：{cause}",
        "",
        "已經有人收到通知會去處理，這則只是讓大家知道記錄會晚一點到，不需要做任何事。",
    ])


def misplaced_notice(series_name: str, file_name: str) -> str:
    """放錯層那則給會議 channel 的字。**與失敗那則的角色相反。**

    失敗那則的最後一句是「已經有人在處理、不需要做任何事」；這則不能那樣寫 ——
    沒有人能代替丟檔案的人把它移進日期資料夾，維運者也不行（他不知道那是哪一天的
    會議）。所以這則講的是**下一步**：移到哪裡、移完會發生什麼。

    形狀那句引 `DATE_DIR_SHAPES` / `DATE_DIR_EXAMPLE`，**不在這裡寫一次字面值**：
    這則訊息原本只講 `YYYYMMDD`，因為帶後綴的資料夾當時掃不到；#56 讓
    `YYYYMMDD_<場次>` 生效之後那句話就不完整了，而它不會讓任何測試變紅。共用來源之後，
    下次再擴充形狀時漏改的只會是註解，不會是叫人怎麼做的那句話。
    """
    return "\n".join([
        MISPLACED_HEADER,
        "",
        f"`{file_name}` 放在「{series_name}」的最外層，沒有日期就不知道是哪一天的會議，"
        "所以不會產記錄。",
        "",
        f"請把它移進該場會議的日期資料夾（{DATE_DIR_SHAPES}，{DATE_DIR_EXAMPLE}），下一輪就會自己產。",
    ])


def dm_misplaced(items: list[Misplaced]) -> str:
    """**已登記**系列的根目錄音檔要 DM 給維運者的字。沒有要講的就回 `""`。

    與 `dm_skipped` 分開：那支列的是**場次**（系列/日期/理由），這裡一筆是一個**檔案**，
    沒有日期可列 —— 硬塞進同一份清單會讓讀 DM 的人以為那個空白的日期是資料壞了。

    沒有 `meeting_key` 的**不在這裡**（見 `dm_unregistered`）。分界不是「重不重要」，
    是**這個建議執行得了嗎**：已登記的系列移進日期資料夾，下一輪就會產；未登記的移了
    也產不出來。#57 上線第一輪掃出的 102 個全是後者（`series_folders` 從 parent 反推，
    把同一層其他部門的資料夾也掃了進來），而 102 行每小時刷一次會連帶弄死同一則 DM 裡
    真正可執行的那幾行。
    """
    known = [i for i in items if i.meeting_key]
    if not known:
        return ""
    lines = [DM_HEADER, f"{len(known)} 個音檔躺在系列資料夾根目錄", ""]
    lines += [f"• `{i.series}/{i.name}`" for i in known]
    lines += [
        "",
        f"請它們的主人移進日期資料夾（{DATE_DIR_SHAPES}），在那之前這幾個不會有記錄。",
    ]
    return "\n".join(lines)


def dm_unregistered(items: list[Misplaced]) -> str:
    """設定檔裡沒有的系列，根目錄有音檔的那則。**一個系列一行，不逐檔。**

    這則要說的是「有幾個部門還沒 onboard」，不是「哪幾個檔案要搬」 —— 那些系列沒有
    `meeting_key`，搬到日期資料夾照樣產不出來，逐檔喊等於發一個**執行不了**的建議。

    **這則的身份是系列，不是檔案**：同一個系列再多丟一個音檔，這則不會多一行。逐檔
    那份（`dm_misplaced` 與 `notify_misplaced`）身份才是 Drive 檔案 id —— 那裡要人動的
    正是那個檔案本人。

    也只有這一則、只給維運者：未登記的系列連 `meeting_key` 都沒有，不知道要發哪個會議
    channel（三態自然落在 `UNSET`），而且要動手的是把系列登記進設定檔的那個人。

    行的順序跟著 `compute_misplaced` 的排序走（`Counter` 保插入序），所以 DM 每輪長一樣。
    """
    counts = Counter(i.series for i in items if not i.meeting_key)
    if not counts:
        return ""
    lines = [DM_HEADER, f"{len(counts)} 個系列資料夾不在設定檔裡", ""]
    lines += [f"• `{series}`　根目錄有 {n} 個音檔" for series, n in counts.items()]
    lines += [
        "",
        f"這幾個系列沒有登記過，搬進日期資料夾也產不出來。要產就先加進設定檔：`{CONFIG_PATH}`",
    ]
    return "\n".join(lines)


def notice_key(series: str, folder: str, cause: str) -> str:
    """去重的身份：**同一場、同一個原因**。

    `folder` 是日期資料夾名而不是日期：同日兩場（`20260916_am`／`20260916_pm`）是兩場
    不同的會議，用日期當身份的話第二場那天永遠不會被提醒。

    原因用的是給人看的那句（`MULTI_AUDIO_CAUSE` / `FAILED_CAUSE`），不是例外訊息 ——
    例外訊息每輪都可能差一個暫存路徑，拿它當 key 等於每一輪都是全新的一則。

    中間那格是「這一則在講哪一個東西」，場次那條路徑放**日期資料夾名**；放錯層那條
    連資料夾都沒有，放的是 Drive 檔案 id（理由見 `notify_misplaced`）。
    """
    return f"{series}/{folder}/{cause}"


def dm_notice_key(cause: str, ids: list[str]) -> str:
    """維運者 DM 的去重身份：`cause` ＋ 一份排序過的 id 清單。

    DM 與 channel 那幾則的形狀不同 —— 一則訊息講 N 件事，所以身份是**那 N 件事的集合
    本身**：集合沒變 → 今天已經講過 → 不重發；集合變了（多一個檔、多一個系列）→ 那是
    一則有新資訊的提醒，該發。

    放進來的是「要被當成身份的那一格」，由呼叫端決定：逐檔那則放 Drive 檔案 id（同
    `notify_misplaced` —— 改名不算新的），未登記那則放**系列名**（同一個系列再多丟一個
    音檔，身份不變）。**數量不進 key** —— 進了的話多丟一個檔就等於一則新提醒，而那則
    要說的事從頭到尾都是同一件。

    排序過再接：清單順序是 Drive 給的，順序一換就變成另一個 key，等於去重失效一次。
    """
    return f"{cause}/{','.join(sorted(set(ids)))}"


def notice_due(sent: dict[str, str], key: str, today: str) -> bool:
    """這則今天還沒發過。

    每小時一輪，而同一場的同一個原因會在 7 天的掃描窗裡每輪都命中 —— 不去重就是 168
    則，而第二則之後沒有任何新資訊。一天一次是「還沒好」這件事的合理頻率。
    """
    return sent.get(key) != today


def prune_sent(sent: dict[str, str], today: str) -> dict[str, str]:
    """只留今天的記錄。昨天以前的對「一天一次」已經沒有作用，留著只會讓狀態檔一路長。"""
    return {key: day for key, day in sent.items() if day == today}


# ─── Drive ────────────────────────────────────────────────────────────────────

def series_folders(drive, meetings: dict) -> list[dict]:
    """Drive 上與設定檔平行的系列資料夾（含設定檔裡沒有的那些）。

    容器從設定檔既有的 `folder_id` 反推 —— 設定檔沒有 drive id 這個欄位，硬加一個
    等於要每個人重跑 setup。而「設定檔裡沒有的系列資料夾」正是要報告的東西之一，
    所以不能只走 config 裡那幾個 id。

    ponytail: 每個會議類型各打一次 `files().get()` 拿 parent（N+1）。四種會議是四次，
    每小時一輪，不值得快取。真的變幾十種再改成在 config 存一個 `drive_id`，那時候
    重跑 setup 的代價才比每輪 N 次 round-trip 小。
    """
    parents: set[str] = set()
    for meeting in meetings.values():
        folder_id = meeting.get("folder_id")
        if not folder_id:
            continue
        info = drive.files().get(
            fileId=folder_id, fields="parents", supportsAllDrives=True
        ).execute()
        parents.update(info.get("parents", []))

    folders: list[dict] = []
    seen: set[str] = set()
    for parent in parents:
        for folder in list_all(
            drive,
            f"'{parent}' in parents and mimeType='{FOLDER_MIME}' and trashed=false",
        ):
            if folder["id"] not in seen:
                seen.add(folder["id"])
                folders.append(folder)
    return folders


def scan_drive(drive, meetings: dict, today: str) -> Scan:
    """掃出窗內每個日期資料夾的檔案清單（餵 `compute_pending`），以及每個系列資料夾
    根目錄的直接子項（餵 `compute_misplaced`）。

    **兩層來自同一次 `files().list()`**：系列資料夾的子項裡，是資料夾的那些才是日期
    資料夾候選，剩下的就是掉在最外層的檔案。改成兩個查詢（一個 `mimeType=資料夾`、
    一個不是）是每個系列每小時多一次 round-trip，換來的只是把 `if` 從這裡搬到 Drive。

    窗的判斷用的是 `in_window` 本人，不是在這裡另寫一次 —— 兩份會靜靜地漂開，而漂開
    的症狀是「掃描層說不在窗內、差集層說在」，兩邊都不會變紅。名字的拆法同理，用
    `parse_date_dir` 本人。

    根目錄那份**不套窗**：Drive 的 `files().list()` 給不出「這個檔案是哪一天的會議」，
    而修改時間不是會議日期（同事可能上週錄、今天才丟）。一個系列的最外層本來就該是
    空的，所以全部回報，由 `compute_misplaced` 濾出音檔。

    **名字認不得的資料夾照樣列檔案。** 窗過不了的不列（省一次 API），但認不得的不能省
    —— 差集層要靠「裡面有沒有音檔」分辨「有人放錯地方」與「這本來就不是收件夾」，
    不列就等於把那個判斷換成「一律提醒」。

    ponytail: 天花板是每個認不得的資料夾每輪多一次 `files().list()`。它們是誤打的名字，
    不該有幾十個；真的堆起來了，要升級的是請人改名或搬走，不是在這裡加一份忽略清單
    —— 忽略清單會把「掃不到」重新變成隱形的。
    """
    listings: list[dict] = []
    roots: list[dict] = []
    for series in series_folders(drive, meetings):
        children = list_all(drive, f"'{series['id']}' in parents and trashed=false")
        roots.append({"series": series["name"], "files": children})
        for folder in children:
            if folder.get("mimeType") != FOLDER_MIME:
                continue
            parsed = parse_date_dir(folder["name"])
            if parsed and not in_window(parsed[0], today):
                continue
            listings.append({
                "series": series["name"],
                "name": folder["name"],
                "files": list_all(drive, f"'{folder['id']}' in parents and trashed=false"),
            })
    return Scan(listings, roots)


def download_audio(drive, file: dict, dest: Path) -> Path:
    """把 Drive 上的音檔抓到本機暫存。**Drive 上那份一個位元都不動。**"""
    from googleapiclient.http import MediaIoBaseDownload

    dest.parent.mkdir(parents=True, exist_ok=True)
    request = drive.files().get_media(fileId=file["id"], supportsAllDrives=True)
    with dest.open("wb") as handle:
        downloader = MediaIoBaseDownload(handle, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"\r   下載 {status.progress() * 100:5.1f}%", end="", flush=True)
    print(f"\r   下載 100.0% ✓  {dest.name}")
    return dest


# ─── 產製 ──────────────────────────────────────────────────────────────────────

def run_step(cmd: list[str], timeout: int, stdin: str | None = None) -> subprocess.CompletedProcess:
    """跑一個子行程，一律帶硬上限。逾時是 `TimeoutExpired`，由呼叫端翻成 DM ＋ 非零。"""
    return subprocess.run(
        cmd, cwd=SKILL_DIR, input=stdin, capture_output=True, text=True, timeout=timeout
    )


def notebooklm_gap() -> str:
    """NotebookLM 認證過不了就回一句該修什麼，過得了回 `""`。

    **這個檢查一定要在切音訊之前**：一場兩小時的錄音切完 20 段才發現登不進去，等於
    白燒一輪，而排程沒有人在旁邊看著那 20 段白切。
    """
    try:
        proc = run_step(["uv", "run", "notebooklm", "auth", "check", "--test"], AUTH_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"NotebookLM 認證檢查跑不起來：{type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr).strip()[-500:]
        return (
            f"NotebookLM 認證檢查失敗（退出碼 {proc.returncode}）：\n{tail}\n"
            f"   去跑：cd {SKILL_DIR} && uv run notebooklm login"
        )
    return ""


def generate(drive, session: Session, config: dict, workdir: Path) -> str:
    """把一場從 Drive 音檔做到發佈完。回傳 `RESULT_URL`；任何一步不成就 raise。

    三步都是子行程，而且都吃／吐**交棒契約**：流程 B 印路徑、子 agent 寫 Markdown、
    發佈印 URL。中間沒有一步重新推導路徑。
    """
    audio = session.audio[0]
    suffix = Path(audio["name"]).suffix
    # 本機暫存檔名由我們自己取，日期來自**資料夾名** —— 那條「檔名必須含 8 位連續
    # 數字」的規則是同事最容易踩的，而資料夾已經給了更可靠的答案。
    local_audio = workdir / f"reconcile_{session.date}{suffix}"
    download_audio(drive, audio, local_audio)

    sources = workdir / "sources"
    extract = run_step([
        "uv", "run", "scripts/extract_audio_sources.py", str(local_audio),
        "--meeting", session.meeting_key,
        "--delete-segments", "--segment-count", "20",
        "--output-dir", str(sources),
    ], EXTRACT_TIMEOUT)
    if extract.returncode != 0:
        raise RuntimeError(f"流程 B 失敗（退出碼 {extract.returncode}）：\n{extract.stderr[-1000:]}")
    handoff = parse_handoff(extract.stdout)
    if "RESULT_TRANSCRIPT" not in handoff:
        raise RuntimeError(f"流程 B 沒有印出交棒契約：\n{extract.stdout[-1000:]}")

    notes = workdir / "meeting_notes.md"
    synth = run_step([
        "claude", "-p",
        "--safe-mode",                   # 不吃使用者的 CLAUDE.md／hooks／plugins／MCP
        "--output-format", "text",
        "--no-session-persistence",
        "--allowed-tools", "Read Write",  # 其餘一律自動拒絕 —— 發佈那幾步過不了這一關
        "--permission-prompts", "none",
    ], SYNTHESIS_TIMEOUT, stdin=synthesis_prompt(handoff, prompt_file(config), notes))
    # 退出碼與檔案**兩個都要**。子 agent 非零退出但已經寫了半份稿時，只看檔案會照樣
    # 往下發佈 —— 而 Doc 一旦建起來，下一輪 `is_note` 就認定這場有記錄，半份稿永久生效。
    # 那正是「多算一場是重跑 NotebookLM 並覆寫既有記錄」這個不對稱的另一面。
    if synth.returncode != 0 or not notes.exists() or not notes.read_text(encoding="utf-8").strip():
        raise RuntimeError(
            f"流程 C 沒有交出正式稿（退出碼 {synth.returncode}）：\n"
            f"{(synth.stdout + synth.stderr)[-1000:]}"
        )

    # 不帶 --audio-file／--delete-local-audio：Drive 上那份是原件，本機這份是暫存。
    publish_cmd = [
        "uv", "run", "scripts/create_gdoc_from_md.py",
        "--meeting", session.meeting_key,
        "--date", session.date,
        "--content-file", str(notes),
        "--source-dir", str(sources),
    ]
    # 場次後綴一路帶到 Doc 名、本機檔名與 **Drive 的日期資料夾**（`date_dir_name`）。
    # 不帶的話兩場撞成同一個 Doc 名，而且 Doc 會被建進 `20260916`，音檔卻躺在
    # `20260916_am` —— 下一輪 `is_note` 在那個資料夾裡還是找不到記錄，於是每小時重產
    # 一次並覆寫前一次的成果。那正是「多算一場」那一側的代價。
    if session.instance:
        publish_cmd += ["--title-suffix", session.instance]
    publish = run_step(publish_cmd, PUBLISH_TIMEOUT)
    url = parse_handoff(publish.stdout).get("RESULT_URL")
    if publish.returncode != 0 or not url:
        raise RuntimeError(
            f"發佈失敗（退出碼 {publish.returncode}）：\n{(publish.stdout + publish.stderr)[-1000:]}"
        )
    return url


# ─── 主流程 ────────────────────────────────────────────────────────────────────

def report(round_: Round, misplaced: list[Misplaced] = ()) -> None:
    print(f"\n📋 差集：{len(round_.pending)} 場要產、{len(round_.skipped)} 場沒產")
    for session in round_.pending:
        print(f"   產　 {session.series}/{session.name}　{session.audio[0]['name']}")
    for session in round_.skipped:
        print(f"   不產 {session.series}/{session.name}　{session.reason}")
    for item in misplaced:
        print(f"   不產 {item.series}/{item.name}　{MISPLACED}")


def notify(text: str) -> None:
    """DM ＋ stdout。**兩個都要** —— DM 送不出去時（沒 token、沒設 `slack_dm_user`）
    提醒不能跟著消失，而 stdout 在排程底下只有事後翻 log 才看得到。"""
    if text:
        print(f"\n{text}")
        send_dm(text)


def notify_once(
    meeting: dict,
    key: str,
    text: str,
    state_path: Path,
    today: str,
    *,
    send: bool = True,
) -> None:
    """發一則 channel 通知，一天最多一次。**channel 的每一則都走這裡**，不分原因。

    三件事在這裡只寫一次：三態、`key` 的一天一次、以及「送出去了才記進狀態檔」。
    收件者與內文由呼叫端決定 —— 原因不同，該對那場會的人說的話就不同。

    **三態照舊**（`channel.py`）：只有 `SEND` 才發，沒設定與刻意安靜都不出聲 —— 新的
    原因加的是一則新訊息，不是一條繞過三態的新路徑。設定檔裡找不到的系列資料夾連
    `meeting_key` 都沒有，落在 `UNSET`，所以本來就只有維運者的 DM 會提到它們。

    **送出去了才記進狀態檔**：Slack 當下送不出去（沒 token、API 掛了）不算發過，下一輪
    會再試 —— 先記的話那一天就再也不會提醒，而提醒消失正是這條路徑要防的事。

    `send=False`（dry-run 與首次執行）只印不發：那兩輪本來就不產記錄，對著整個會議
    channel 喊一次是假警報。
    """
    if channel_state(meeting) != SEND:
        return
    send_once(
        key, text, state_path, today,
        lambda t: send and send_channel(channel_id(meeting), t),
    )


def read_state(state_path: Path) -> dict:
    """狀態檔 → dict。壞掉、不見、不是 dict 一律當空的。

    壞掉時不拋：這支是無人看管跑的，為了一個去重記錄讓整輪停下來，代價是那一輪的記錄
    整批不產 —— 而重發一則提醒的代價只是重發一則提醒。
    """
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def write_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def send_once(
    key: str, text: str, state_path: Path, today: str, deliver
) -> None:
    """一天最多一次地送一則。`deliver(text)` 回「真的送出去了沒有」。

    **channel 與 DM 共用這一支**：「一天一次」與「送出去了才記進狀態檔」這兩條規則只能
    有一份。DM 原本走的是 `notify()`，每輪重發 —— 每小時一輪，於是同一面 102 行的牆一天
    出現 24 次，而同一則 DM 裡真正該看的那幾行（要產的、多音檔的、認不得資料夾的）就跟
    著一起被學會忽略。

    **送出去了才記**：Slack 當下送不出去（沒 token、API 掛了）不算發過，下一輪會再試。
    """
    state = read_state(state_path)
    sent = state.get("notified", {})
    if not notice_due(sent, key, today):
        return

    print(f"\n{text}")
    if not deliver(text):
        return

    state["notified"] = {**prune_sent(sent, today), key: today}
    write_state(state_path, state)


def notify_dm_once(text: str, key: str, state_path: Path, today: str) -> None:
    """維運者的 DM，一天最多一次。空字串就不發（呼叫端據此決定發不發）。

    與 `notify()` 的差別只有去重。`dm_blocked` 那幾則**不走這裡** —— 那是「這輪停了」，
    每一輪都該講一次；這裡兩則講的是「有東西躺在那裡沒動」，而那件事一天講一次就夠。
    """
    if text:
        send_once(key, text, state_path, today, send_dm)


def notify_channel(
    session: Session,
    cause: str,
    meetings: dict,
    state_path: Path,
    today: str,
    *,
    send: bool = True,
) -> None:
    """掃到了沒產的那一則：告知那場會的人，不是求救。維運者的 DM 另外送，內容不同。

    去重的身份是**同一場、同一個原因**（`notice_key`），而「哪一場」是**日期資料夾名**
    不是日期：同日兩場（`20260916_am`／`20260916_pm`）用日期當身份的話，第二場那天
    永遠不會被提醒。認不得名字的資料夾也走這裡 —— 它知道自己在哪個系列底下，所以
    三態算得出來（見 `CHANNEL_CAUSES`）。
    """
    meeting = meetings.get(session.meeting_key or "", {})
    notify_once(
        meeting,
        notice_key(session.series, session.name, cause),
        failure_notice(
            meeting.get("series_name", session.series), when_label(session), cause
        ),
        state_path,
        today,
        send=send,
    )


def notify_misplaced(
    item: Misplaced,
    meetings: dict,
    state_path: Path,
    today: str,
    *,
    send: bool = True,
) -> None:
    """放錯層的那一則。走的是 `notify_once` 同一條路徑，只有身份與內文不同。

    **去重的身份是「系列 ＋ Drive 檔案 id」**，不是檔名，也不是系列本身：

    - 檔名不是身份 —— Drive 允許同一個資料夾裡兩個同名檔，撞名時第二個會被第一個的
      記錄擋掉一整天；而同事看到提醒後把檔名改成帶日期的（一個很自然的反應）會讓它
      在同一天被當成新檔案再提醒一次，等於懲罰有在處理的人。
    - 系列本身也不是 —— 一次丟三個檔進最外層時只有一個會被提到，另外兩個要等到隔天。
    - 檔案 id 在檔案被移進日期資料夾之後不變，但那時候它已經不在這份清單裡了，所以
      「移完當天不會再收到提醒」是自然的結果，不需要另外記一筆「已解決」。

    所以中間那格放 `file_id` 而不是日期（`notice_key` 的第二個參數）。
    """
    meeting = meetings.get(item.meeting_key or "", {})
    notify_once(
        meeting,
        notice_key(item.series, item.file_id, MISPLACED_CAUSE),
        misplaced_notice(meeting.get("series_name", item.series), item.name),
        state_path,
        today,
        send=send,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="每小時 reconcile Shared Drive：有音檔沒記錄就產")
    parser.add_argument("--dry-run", action="store_true", help="只印差集，不產任何記錄")
    parser.add_argument("--today", help="把今天當成哪一天 YYYYMMDD（測試用）")
    parser.add_argument("--state", default=str(STATE_PATH),
                        help=f"狀態檔路徑（預設 {STATE_PATH}）；不存在＝首次執行，強制 dry-run")
    args = parser.parse_args()

    today = args.today or date.today().strftime("%Y%m%d")
    try:
        _as_date(today)
    except ValueError:
        print(f"❌ --today 要是 YYYYMMDD：{today!r}")
        return 2

    config = load_config()
    meetings = config.get("meetings", {})
    if not meetings:
        print(f"❌ 設定檔裡沒有任何會議類型：{CONFIG_PATH}")
        return 2

    gap = credential_gap(CONFIG_DIR)
    if gap:
        notify(dm_blocked(f"❌ {gap}", 0))
        return 1

    state_path = Path(args.state).expanduser()
    first_run = not state_path.exists()

    from googleapiclient.discovery import build
    try:
        # 走 skill 自己的憑證，不要走 ADC —— 兩者是不同的兩份，ADC 過期會誤判成沒憑證
        drive = build("drive", "v3", credentials=get_google_credentials())
    except Exception as exc:
        notify(dm_blocked(f"❌ 取不到 Google 憑證：{type(exc).__name__}: {exc}", 0))
        return 1

    try:
        scan = scan_drive(drive, meetings, today)
    except Exception as exc:
        notify(dm_blocked(f"❌ 掃 Drive 失敗：{type(exc).__name__}: {exc}", 0))
        return 1

    known = series_map(meetings)
    round_ = compute_pending(scan.listings, known, today)
    misplaced = compute_misplaced(scan.roots, known)
    report(round_, misplaced)
    notify(dm_skipped(round_.skipped))

    # 放錯層的兩則 DM **一天一次**，走 channel 那條同一支 `send_once`：每小時重發一次
    # 的話，102 行的牆一天出現 24 次，而同一個收件匣裡真正該看的東西會跟著被忽略。
    # 身份分別是「有哪幾個檔案」與「有哪幾個系列」（見 `dm_notice_key`）。
    notify_dm_once(
        dm_misplaced(misplaced),
        dm_notice_key(MISPLACED_DM, [i.file_id for i in misplaced if i.meeting_key]),
        state_path,
        today,
    )
    notify_dm_once(
        dm_unregistered(misplaced),
        dm_notice_key(UNREGISTERED_DM, [i.series for i in misplaced if not i.meeting_key]),
        state_path,
        today,
    )

    # 掃到了沒產的那些，會議成員也該知道。哪幾個理由走到這裡見 `CHANNEL_CAUSES`
    # —— 新的理由要不要對外發聲是那張表的事，不是在這裡多一條 `or`。
    # dry-run 與首次執行不對外發聲。
    quiet = args.dry_run or first_run
    for session in round_.skipped:
        cause = CHANNEL_CAUSES.get(session.reason)
        if cause:
            notify_channel(session, cause, meetings, state_path, today, send=not quiet)

    # 掉在系列資料夾最外層的音檔。**不產任何記錄** —— 沒有日期資料夾就沒有可信的日期。
    # 一個檔案一則（身份是 Drive 檔案 id，見 `notify_misplaced`），因為要移動的是那個
    # 檔案本人；走的是上面同一條通知路徑，三態與一天一次都照舊。
    #
    # 未登記系列的那些在這裡**自然安靜**：沒有 `meeting_key` → `meetings.get` 拿到空
    # dict → 三態是 `UNSET` → `notify_once` 第一行就回。它們只出現在維運者的
    # `dm_unregistered`，一個系列一行。
    for item in misplaced:
        notify_misplaced(item, meetings, state_path, today, send=not quiet)

    # `--dry-run` 先判，而且**不寫狀態檔**：寫了的話手動看一次差集就把「首次強制
    # dry-run」那道閘門用掉了，而 SKILL.md 承諾的「確認差集無誤之後下一輪才真的產」
    # 靠的就是那道閘門還在。
    if args.dry_run:
        print("\n這是 dry-run，沒有產任何記錄。")
        return 0
    if first_run:
        # 併進去而不是覆蓋：這一輪的 DM 已經發過、也已經記進 `notified` 了，整個蓋掉
        # 等於下一輪再發一次同一則。
        write_state(state_path, {**read_state(state_path), "first_run": today})
        print(f"\n這是首次執行，強制 dry-run，沒有產任何記錄。狀態檔已建立：{state_path}")
        print("確認上面的差集無誤之後，下一輪就會真的產。")
        return 0
    if not round_.pending:
        print("\n沒有差集，這輪不動。")
        return 0

    gap = notebooklm_gap()
    if gap:
        notify(dm_blocked(f"❌ {gap}", len(round_.pending)))
        return 1

    failures = 0
    for session in round_.pending:
        workdir = Path(tempfile.mkdtemp(prefix=f"gmn-reconcile-{session.date}-"))
        print(f"\n▶️  {session.series}/{session.name}（{session.meeting_key}）→ {workdir}")
        try:
            url = generate(drive, session, config, workdir)
            print(f"✅ {session.series}/{session.name}　{url}")
        except Exception as exc:
            failures += 1
            # 兩軌：維運者拿到例外型別與訊息，會議成員拿到「這場還沒好、有人在處理」。
            notify(dm_blocked(
                f"❌ {session.series}/{session.name}　{type(exc).__name__}: {exc}", 1
            ))
            notify_channel(session, FAILED_CAUSE, meetings, state_path, today)
        finally:
            # 本機暫存整個目錄移除。Drive 上的音檔是原件，一個位元都沒動過。
            shutil.rmtree(workdir, ignore_errors=True)

    print(f"\n✅ 這輪產了 {len(round_.pending) - failures} 場，失敗 {failures} 場。")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
