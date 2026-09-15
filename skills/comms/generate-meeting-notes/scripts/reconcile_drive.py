#!/usr/bin/env python3
"""
reconcile_drive.py - 每小時掃 Shared Drive：日期資料夾有音檔、沒有會議記錄，就自己產。

**reconcile，不是事件觸發。** 事件觸發靠「發生了什麼」—— Mac 關機、Drive 同步延遲、
腳本當掉，錯過就永遠錯過。這支靠「現在長怎樣」：漏掉一輪下一輪自己補回來，沒有差集
就不動。兩個都做是多一條程式路徑換低延遲，而會議記錄不需要秒級。

    {Shared Drive}/{系列資料夾}/{YYYYMMDD}/
                        │            └─ 日期來自資料夾名，不從檔名解析
                        └─ 反查設定檔的 folder_name → 這是哪種會議

    該日期資料夾有音檔 && 沒有會議記錄  ──▶ 產

**這支是無人看管的**，所以每一條「失敗時的行為」都比「成功時的行為」重要：

| 情況 | 行為 |
|---|---|
| 首次執行（沒有狀態檔） | 強制 dry-run，只印差集 |
| 每輪處理上限 | `MAX_PER_ROUND` 場。判準寫錯時不會一次燒 20 次 NotebookLM |
| 系列資料夾在設定檔裡找不到 | 不產，只 DM。缺會議類型脈絡，硬產出來的是壞的 |
| 同一個日期資料夾有多個音檔 | 不產，只 DM。挑一個產會讓另一半永遠沒有機會 |
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
    另有 --limit N、--window-days N，以及 --today / --state（測試用）。

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
from datetime import date, datetime
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
from local_archive import DATE_DIR
from send_slack_notification import send_dm

STATE_PATH = CONFIG_DIR / "reconcile-state.json"
SKILL_MD = SKILL_DIR / "SKILL.md"

WINDOW_DAYS = 7
MAX_PER_ROUND = 2

FOLDER_MIME = "application/vnd.google-apps.folder"
DOC_MIME = "application/vnd.google-apps.document"

# 與 SKILL.md 的「輸入類型與路由」同一份清單。
AUDIO_SUFFIXES = (".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".opus")

# 會議記錄的 Doc 名前綴，與 `local_archive.note_title` 同一個字面。
NOTE_PREFIX = "會議記錄"

# 掃到了但沒有產的三個理由。字串而非 enum：它們會被印進 stdout 與 DM，也會被測試
# 逐字斷言（同 `channel.DM_HEADER`）。
UNKNOWN_SERIES = "系列資料夾不在設定檔的任何會議類型"
MULTI_AUDIO = "同一個日期資料夾有多個音檔"
OVER_LIMIT = "超過本輪上限，下一輪會再看到"

DM_HEADER = "📮 每小時 reconcile 有東西需要你看一眼"

# 子行程的硬上限。NotebookLM 那段要上傳幾十段再等 AI 處理，所以給得寬；但一定要有，
# 卡住的排程是「每小時卡一次而沒人知道」，不是「變紅」。
EXTRACT_TIMEOUT = 3600
SYNTHESIS_TIMEOUT = 1800
PUBLISH_TIMEOUT = 900
AUTH_TIMEOUT = 120


class Session(NamedTuple):
    """一個日期資料夾。`reason` 是空字串表示這場要產。"""

    series: str
    date: str
    meeting_key: str | None
    folder_id: str
    audio: tuple[dict, ...]
    reason: str


class Round(NamedTuple):
    """這一輪的差集。`pending` 要產，`skipped` 每一筆都帶著沒產的理由。"""

    pending: list[Session]
    skipped: list[Session]


# ─── 純函式 ────────────────────────────────────────────────────────────────────

def in_window(folder_date: str, today: str, window_days: int = WINDOW_DAYS) -> bool:
    """`folder_date` 是否落在以 `today` 結尾的 `window_days` 天窗內。兩個都是 YYYYMMDD。

    窗是**固定**的，不是「上次跑到哪」：每小時跑一次，落差不會累積；7 天足以涵蓋 Mac
    關機幾天，而且第一次跑不會把幾個月的舊資料夾全部翻出來。

    未來日期回 `False`（`delta < 0`）：打錯的日期資料夾不該被當成今天的會議產一份。
    解不出日期的也回 `False` 而不是拋 —— 資料夾名是別人打的，一個 `202609xx` 不該讓
    整輪 reconcile 掛掉。
    """
    try:
        delta = (_as_date(today) - _as_date(folder_date)).days
    except ValueError:
        return False
    return 0 <= delta < window_days


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
    """
    return file.get("mimeType") == DOC_MIME and file.get("name", "").startswith(NOTE_PREFIX)


def compute_pending(
    folders: list[dict],
    known_series: dict[str, str],
    today: str,
    *,
    window_days: int = WINDOW_DAYS,
    limit: int = MAX_PER_ROUND,
) -> Round:
    """吃日期資料夾清單，吐這一輪的差集。**純函式** —— 不碰 Drive、不碰時鐘、不碰檔案。

    `folders` 每筆是 `{"series": 系列資料夾名, "date": "YYYYMMDD", "folder_id": …,
    "files": [{"id":…, "name":…, "mimeType":…}]}`；`known_series` 是系列資料夾名 →
    會議 key。

    排序是 `(date, series)`，**舊的先**：積壓要從最舊的開始消化，不然一場久久沒人處理
    的會議會永遠排在新的後面。上限之外的不是丟掉，是帶著 `OVER_LIMIT` 進 `skipped`
    —— 丟掉的話沒有人知道這輪還欠幾場。
    """
    candidates: list[Session] = []
    skipped: list[Session] = []

    for folder in folders:
        if not in_window(folder["date"], today, window_days):
            continue
        files = folder.get("files", [])
        if any(is_note(f) for f in files):
            continue
        audio = tuple(f for f in files if is_audio(f.get("name", "")))
        if not audio:
            continue

        key = known_series.get(folder["series"])
        if not key:
            reason = UNKNOWN_SERIES
        elif len(audio) > 1:
            reason = MULTI_AUDIO
        else:
            reason = ""
        session = Session(
            series=folder["series"],
            date=folder["date"],
            meeting_key=key,
            folder_id=folder.get("folder_id", ""),
            audio=audio,
            reason=reason,
        )
        (skipped if reason else candidates).append(session)

    candidates.sort(key=_by_date)
    skipped += [s._replace(reason=OVER_LIMIT) for s in candidates[limit:]]
    skipped.sort(key=_by_date)
    return Round(candidates[:limit], skipped)


def _by_date(session: Session) -> tuple[str, str]:
    """排序鍵：**舊的先**。積壓要從最舊的開始消化，不然一場久久沒人處理的會議會永遠
    排在新的後面。同一天有多場時用系列名定序 —— 只要是固定的就好。"""
    return (session.date, session.series)


def series_map(meetings: dict) -> dict[str, str]:
    """設定檔 → {系列資料夾名: 會議 key}。

    `folder_name` 缺席時退回 `series_name`，與 `backfill_local_archive.scan_meeting`
    同一條規則 —— 那兩支在掃同一批資料夾。
    """
    return {
        meeting.get("folder_name", meeting.get("series_name", key)): key
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

    token_path = config_dir / "google_token.json"
    try:
        token = json.loads(token_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return (
            f"讀不到 {token_path}，下次取憑證會開瀏覽器等人按同意 —— 排程沒有人。\n"
            f"   先手動跑一次 `uv run scripts/setup.py` 把授權建起來。\n"
            f"   （這是 {creds_path} 那份授權，不是 ADC；兩者是不同的兩份。）"
        )
    if not isinstance(token, dict) or not token.get("refresh_token"):
        return (
            f"{token_path} 沒有 refresh_token，下次取憑證會開瀏覽器等人按同意。\n"
            f"   刪掉它再手動跑一次 `uv run scripts/setup.py`。\n"
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
    lines = [f"{DM_HEADER}：{len(needs_human)} 場掃到了但沒有產"]
    lines += [f"• {s.series}/{s.date}　{s.reason}" for s in needs_human]
    lines.append(f"設定檔：{CONFIG_PATH}")
    return "\n".join(lines)


def dm_blocked(detail: str, count: int = 0) -> str:
    """整輪（或某一場）停下來時要 DM 的字。

    `count` 是這輪本來要產幾場；`0` 表示還沒數到那一步（憑證、掃 Drive）。零的時候
    不印那句話 —— 「0 場一場都沒產」讀起來像沒事，而這通 DM 的存在就是因為有事。
    """
    head = f"{DM_HEADER}：有一段沒跑完"
    if count:
        head += f"，{count} 場一場都沒產"
    return f"{head}\n{detail}"


# ─── Drive ────────────────────────────────────────────────────────────────────

def series_folders(drive, meetings: dict) -> list[dict]:
    """Drive 上與設定檔平行的系列資料夾（含設定檔裡沒有的那些）。

    容器從設定檔既有的 `folder_id` 反推 —— 設定檔沒有 drive id 這個欄位，硬加一個
    等於要每個人重跑 setup。而「設定檔裡沒有的系列資料夾」正是要報告的東西之一，
    所以不能只走 config 裡那幾個 id。
    """
    parents: list[str] = []
    for meeting in meetings.values():
        folder_id = meeting.get("folder_id")
        if not folder_id:
            continue
        info = drive.files().get(
            fileId=folder_id, fields="parents", supportsAllDrives=True
        ).execute()
        parents.extend(p for p in info.get("parents", []) if p not in parents)

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


def scan_drive(drive, meetings: dict, today: str, window_days: int = WINDOW_DAYS) -> list[dict]:
    """掃出窗內每個日期資料夾的檔案清單，餵給 `compute_pending`。

    窗的判斷用的是 `in_window` 本人，不是在這裡另寫一次 —— 兩份會靜靜地漂開，而漂開
    的症狀是「掃描層說不在窗內、差集層說在」，兩邊都不會變紅。
    """
    listings: list[dict] = []
    for series in series_folders(drive, meetings):
        date_folders = list_all(
            drive,
            f"'{series['id']}' in parents and mimeType='{FOLDER_MIME}' and trashed=false",
        )
        for folder in date_folders:
            if not DATE_DIR.fullmatch(folder["name"]):
                continue
            if not in_window(folder["name"], today, window_days):
                continue
            listings.append({
                "series": series["name"],
                "date": folder["name"],
                "folder_id": folder["id"],
                "files": list_all(drive, f"'{folder['id']}' in parents and trashed=false"),
            })
    return listings


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

def run(cmd: list[str], timeout: int, stdin: str | None = None) -> subprocess.CompletedProcess:
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
        proc = run(["uv", "run", "notebooklm", "auth", "check", "--test"], AUTH_TIMEOUT)
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
    extract = run([
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
    synth = run([
        "claude", "-p",
        "--safe-mode",                   # 不吃使用者的 CLAUDE.md／hooks／plugins／MCP
        "--output-format", "text",
        "--no-session-persistence",
        "--allowed-tools", "Read Write",  # 其餘一律自動拒絕 —— 發佈那幾步過不了這一關
        "--permission-prompts", "none",
    ], SYNTHESIS_TIMEOUT, stdin=synthesis_prompt(handoff, prompt_file(config), notes))
    if not notes.exists() or not notes.read_text(encoding="utf-8").strip():
        raise RuntimeError(
            f"流程 C 沒有寫出正式稿（退出碼 {synth.returncode}）：\n"
            f"{(synth.stdout + synth.stderr)[-1000:]}"
        )

    # 不帶 --audio-file／--delete-local-audio：Drive 上那份是原件，本機這份是暫存。
    publish = run([
        "uv", "run", "scripts/create_gdoc_from_md.py",
        "--meeting", session.meeting_key,
        "--date", session.date,
        "--content-file", str(notes),
        "--source-dir", str(sources),
    ], PUBLISH_TIMEOUT)
    url = parse_handoff(publish.stdout).get("RESULT_URL")
    if publish.returncode != 0 or not url:
        raise RuntimeError(
            f"發佈失敗（退出碼 {publish.returncode}）：\n{(publish.stdout + publish.stderr)[-1000:]}"
        )
    return url


# ─── 主流程 ────────────────────────────────────────────────────────────────────

def report(round_: Round) -> None:
    print(f"\n📋 差集：{len(round_.pending)} 場要產、{len(round_.skipped)} 場沒產")
    for session in round_.pending:
        print(f"   產　 {session.series}/{session.date}　{session.audio[0]['name']}")
    for session in round_.skipped:
        print(f"   不產 {session.series}/{session.date}　{session.reason}")


def notify(text: str) -> None:
    """DM ＋ stdout。**兩個都要** —— DM 送不出去時（沒 token、沒設 `slack_dm_user`）
    提醒不能跟著消失，而 stdout 在排程底下只有事後翻 log 才看得到。"""
    if text:
        print(f"\n{text}")
        send_dm(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="每小時 reconcile Shared Drive：有音檔沒記錄就產")
    parser.add_argument("--dry-run", action="store_true", help="只印差集，不產任何記錄")
    parser.add_argument("--limit", type=int, default=MAX_PER_ROUND,
                        help=f"每輪處理上限（預設 {MAX_PER_ROUND}）")
    parser.add_argument("--window-days", type=int, default=WINDOW_DAYS,
                        help=f"掃描窗幾天（預設 {WINDOW_DAYS}）")
    parser.add_argument("--today", help="把今天當成哪一天 YYYYMMDD（測試用）")
    parser.add_argument("--state", default=str(STATE_PATH),
                        help=f"狀態檔路徑（預設 {STATE_PATH}）；不存在＝首次執行，強制 dry-run")
    args = parser.parse_args()

    if args.limit < 1 or args.window_days < 1:
        print("❌ --limit 與 --window-days 至少是 1")
        return 2
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
    dry_run = args.dry_run or first_run

    from googleapiclient.discovery import build
    try:
        # 走 skill 自己的憑證，不要走 ADC —— 兩者是不同的兩份，ADC 過期會誤判成沒憑證
        drive = build("drive", "v3", credentials=get_google_credentials())
    except Exception as exc:
        notify(dm_blocked(f"❌ 取不到 Google 憑證：{type(exc).__name__}: {exc}", 0))
        return 1

    try:
        listings = scan_drive(drive, meetings, today, args.window_days)
    except Exception as exc:
        notify(dm_blocked(f"❌ 掃 Drive 失敗：{type(exc).__name__}: {exc}", 0))
        return 1

    round_ = compute_pending(
        listings, series_map(meetings), today,
        window_days=args.window_days, limit=args.limit,
    )
    report(round_)
    notify(dm_skipped(round_.skipped))

    if first_run:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"first_run": today}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\n這是首次執行，強制 dry-run，沒有產任何記錄。狀態檔已建立：{state_path}")
        print("確認上面的差集無誤之後，下一輪就會真的產。")
        return 0
    if dry_run:
        print("\n這是 dry-run，沒有產任何記錄。")
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
        print(f"\n▶️  {session.series}/{session.date}（{session.meeting_key}）→ {workdir}")
        try:
            url = generate(drive, session, config, workdir)
            print(f"✅ {session.series}/{session.date}　{url}")
        except Exception as exc:
            failures += 1
            notify(dm_blocked(
                f"❌ {session.series}/{session.date}　{type(exc).__name__}: {exc}", 1
            ))
        finally:
            # 本機暫存整個目錄移除。Drive 上的音檔是原件，一個位元都沒動過。
            shutil.rmtree(workdir, ignore_errors=True)

    print(f"\n✅ 這輪產了 {len(round_.pending) - failures} 場，失敗 {failures} 場。")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
