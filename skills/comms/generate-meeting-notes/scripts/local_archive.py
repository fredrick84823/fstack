#!/usr/bin/env python3
"""
local_archive.py - 發佈時在本機留一份正式稿，並把 Doc URL 記在同名側檔。

Doc URL 只有發佈當下拿得到，事後要靠檔名回頭去 Drive 找。側檔就是為了記住它。

本機路徑與 Drive 路徑同形：
    {local_archive_root}/{folder_name}/{YYYYMMDD}/
        會議記錄_{series_name}_{YYYYMMDD}[_{suffix}].md          正式稿
        會議記錄_{series_name}_{YYYYMMDD}[_{suffix}].meta.json   側檔

folder_name 沿用發佈流程算 Drive 資料夾時已經用的那個值，不另外設定。
"""

import json
import re
from pathlib import Path

DEFAULT_ARCHIVE_DIRNAME = "meeting-notes"

# 日期資料夾的形狀。歸檔版面的 owner 是這支模組，所以放這裡 —— 補齊腳本與歷史索引
# 都在掃同一批資料夾，各自編一份的話版面改了只會改到其中一份。
DATE_DIR = re.compile(r"\d{8}")

# Drive 的日期資料夾可以帶場次後綴（`20260916_am`）—— 一天多場各開一個資料夾，
# 見 `references/multi-session.md`。**本機歸檔的日期資料夾永遠是 8 位數**，場次在
# 檔名裡（見 `note_title`）：兩邊都帶後綴的話同一場會散在兩個路徑形狀上。
_DATE_DIR_INSTANCE = re.compile(r"(\d{8})(?:_(.+))?")
# 正式稿檔名尾端的 `_YYYYMMDD[_場次]`。**右錨定** —— 系列名裡剛好有 8 位數字時，
# 沒錨定的話會搶到前面那串，抽出來的場次是半個系列名。
_NOTE_TAIL = re.compile(r"_(\d{8})(?:_(.+))?$")

# 掃描層認得的日期資料夾形狀，**寫給人看的那一版**。每一則「請把它放進日期資料夾」
# 的訊息都引這兩個常數，不自己寫一次字面值 —— `_DATE_DIR_INSTANCE` 擴充了而某一則
# 文案沒跟上的話，人會照著一份過期的說明去建資料夾，而那個資料夾照樣掃不到。
# （#57 的「請移進 YYYYMMDD 資料夾」就是在 #56 落地那天變得不完整的。）
DATE_DIR_SHAPES = "YYYYMMDD 或 YYYYMMDD_<場次>"
DATE_DIR_EXAMPLE = "例：20260921、20260921_am"

# 場次後綴（`meeting_instance`）在一天之中的先後。`""` 排最前：那是「當天只有一場」
# 的形狀。這張表**故意小** —— `references/multi-session.md` 允許任意短名稱
# （`project-x`、`part1-combined`），收錄它們是不可能的，所以定不出序時的退化行為
# 才是契約本身，不是這張表的長度（見 `instance_rank`）。
INSTANCE_ORDER = ("", "morning", "am", "noon", "afternoon", "pm", "evening")

# 正式稿檔名／Doc 名的前綴。同上，owner 是這支模組 —— reconcile 靠它認出「這場已經有
# 記錄」，歷史索引靠它 glob 出歷史場次，而 `note_title` 是寫檔名的那一端。三處各抄一份
# 的話，版型改了只會改到其中一處，而症狀是「這場永遠不產」或「每小時重產一次」。
NOTE_PREFIX = "會議記錄"


def _configured_root() -> Path:
    """歸檔根目錄，由 config.json 的 local_archive_root 決定。

    不寫死個人筆記路徑：這支 skill 是公開的，別人的筆記不會長在你的筆記樹底下。
    設定檔讀不到或沒這個 key 就退回 ~/<DEFAULT_ARCHIVE_DIRNAME>。

    home 在呼叫時才解析，不在 import 時 —— 綁成模組常數的話這支函式就不可測。
    """
    home = Path.home()
    config = home / ".config" / "generate-meeting-notes" / "config.json"
    try:
        root = json.loads(config.read_text(encoding="utf-8")).get("local_archive_root")
    except (OSError, ValueError):
        root = None
    return Path(root).expanduser() if root else home / DEFAULT_ARCHIVE_DIRNAME


LOCAL_ARCHIVE_ROOT = _configured_root()
SIDECAR_SUFFIX = ".meta.json"


def clean_for_filename(text: str | None) -> str:
    """把一段文字清成可安全放進檔名／Doc 名的形式。

    ponytail: 這個對應不是單射的——`a/b`、`a:b`、`a//b` 全部收斂到 `a-b`，同日兩場
    真的用這種識別碼就會撞成同一個檔名，而 `write_local_archive` 是覆寫語意，後寫的
    蓋掉前寫的。實務上的識別碼是 `am`/`pm`/`pc`/`phone`，不會撞，所以先接受。
    要升級的話是把對應改成單射（逐字元跳脫，例如 `%2F`），**不是**在寫入前偵測既有
    檔——那個檢查分不出「撞名」與「重跑同一場發佈」，而後者必須照常覆寫。
    """
    if not text:
        return ""
    return re.sub(r"[\\/:*?\"<>|]+", "-", text).strip(" -_")


def parse_date_dir(name: str) -> tuple[str, str] | None:
    """日期資料夾名 → `(YYYYMMDD, 場次後綴)`。認不得的名字回 `None`。

    回 `None` 而不是 `("", "")`：掃描層要據此發提醒（#56），而「認不得」與「沒有後綴」
    是兩件完全不同的事 —— 壓成同一個值的話，掃描層就只剩靜靜跳過這一個選擇，而靜靜
    跳過正是那張票的病本身（第二個資料夾是隱形的，丟檔的人以為已經丟進去了）。
    """
    m = _DATE_DIR_INSTANCE.fullmatch(name)
    return (m.group(1), m.group(2) or "") if m else None


def note_instance(stem: str) -> str:
    """正式稿檔名（不含 `.md`）尾端的場次後綴。沒有後綴、或認不出日期都回 `""`。

    `""` 對兩者是同一個答案，因為下游只有一個問題要問：「這份在同一天裡排第幾」——
    而沒有後綴與認不出日期的答案都是「就當它是當天唯一那場」。
    """
    m = _NOTE_TAIL.search(stem)
    return (m.group(2) or "") if m else ""


def instance_rank(instance: str) -> int | None:
    """場次後綴 → 一天之中的先後。表外的後綴回 `None`：**不知道排哪**，不是排最後。

    回 `None` 而不是一個很大的數字：呼叫端要分得出「排最後」與「定不出序」，後者要
    出聲。靜靜地照檔名字母序正是 #53 的病本身 —— `會議記錄_…_20260911_afternoon.md`
    < `…_20260911_am.md`（`af` < `am`），於是索引把下午那場排到上午那場前面，而
    `notes[-limit:]` 截斷時砍掉的是**較晚**那場，最新的未結案狀態就這樣不見了。
    """
    key = instance.lower()
    return INSTANCE_ORDER.index(key) if key in INSTANCE_ORDER else None


def instance_order_key(instance: str) -> int:
    """`instance_rank` 的排序鍵版本：定不出序的排在同日已知場次**之後**。

    排後面而不是前面，是為了截斷那一端：`notes[-limit:]` 留下的是排最後的那幾份，而
    「可能是最新的那一場」比「已知的上午場」更該留 —— 索引存在的理由就是把最新的
    未結案狀態交給下一場。呼叫端另外要出聲說有哪幾份定不出序。

    退化值是 `len(INSTANCE_ORDER)`（＝最後一個已知 rank 再加一），不是隨手挑的大數字：
    挑數字的話那個常數是什麼值都一樣對，於是「排在最後」這件事沒有任何斷言看得見。
    """
    rank = instance_rank(instance)
    return len(INSTANCE_ORDER) if rank is None else rank


def date_dir_name(date: str, title_suffix: str | None = None) -> str:
    """Drive 上的日期資料夾名。多場次帶場次後綴 —— 一天多場各一個資料夾。

    與 `note_title` 共用同一份清洗，兩邊才不會漂開：Doc 叫 `會議記錄_X_20260916_am`，
    資料夾就是 `20260916_am`。reconcile 的掃描層正是靠資料夾名認出「這是哪一場」，
    Doc 建進 `20260916` 而音檔躺在 `20260916_am` 的話，那個資料夾永遠掃不到記錄 ——
    症狀是每小時重產一次，不是報錯。
    """
    cleaned = clean_for_filename(title_suffix)
    return f"{date}_{cleaned}" if cleaned else date


def note_title(series_name: str, date: str, title_suffix: str | None = None) -> str:
    """正式稿標題。Doc 名稱與本機檔名共用這個值，兩邊才不會漂開。"""
    title = f"{NOTE_PREFIX}_{series_name}_{date}"
    cleaned = clean_for_filename(title_suffix)
    return f"{title}_{cleaned}" if cleaned else title


def archive_paths(
    folder_name: str,
    date: str,
    title: str,
    root: Path = LOCAL_ARCHIVE_ROOT,
) -> tuple[Path, Path]:
    """回傳 (正式稿路徑, 側檔路徑)。純路徑組裝，不碰檔案系統。

    `title` 過一次檔名清洗：補齊腳本餵進來的是 Drive 上的 Doc 名，而 Drive 允許
    `/`，原樣當檔名會把檔案寫進另一個目錄。`folder_name` 與 `date` **不清洗** ——
    前者來自本機 config（不是外部輸入），後者傳什麼就是什麼。
    """
    directory = root / folder_name / date
    safe = clean_for_filename(title)
    return directory / f"{safe}.md", directory / f"{safe}{SIDECAR_SUFFIX}"


def sidecar_content(doc_url: str | None) -> str:
    """側檔內容。沒有 URL 時該欄位缺席——寫 None 會被下游當成可用的值。"""
    data = {"doc_url": doc_url} if doc_url else {}
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def write_local_archive(
    folder_name: str,
    date: str,
    title: str,
    content: str,
    doc_url: str | None = None,
    root: Path = LOCAL_ARCHIVE_ROOT,
) -> tuple[Path, Path]:
    """寫入正式稿與側檔，回傳兩者的路徑。"""
    note_path, sidecar_path = archive_paths(folder_name, date, title, root)
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(content, encoding="utf-8")
    sidecar_path.write_text(sidecar_content(doc_url), encoding="utf-8")
    return note_path, sidecar_path
