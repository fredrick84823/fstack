#!/usr/bin/env python3
"""
history_index.py - 同系列近 N 場的歷史索引。

**這是索引不是語料。** 每場只給兩樣東西：

1. heading 大綱（層級上限 `MAX_DEPTH`，預設到 Heading 3）—— 不含任何內容行
2. 指標：本機正式稿路徑，以及側檔裡記著的 Doc URL

設計意圖是「只有本次議題延伸自過去議題時才需要歷史」。agent 掃大綱判斷「這個以前
談過」，再決定要不要沿指標去讀那一場的全文 —— 而不是把三場正式稿整包塞進 context。

日期邊界是**嚴格小於**本次日期：索引含本次或之後的場次時，agent 會讀到自己的產出。

來源是 `local_archive.py` 寫下的本機歸檔：

    {root}/{folder_name}/{YYYYMMDD}/會議記錄_….md          正式稿
    {root}/{folder_name}/{YYYYMMDD}/會議記錄_….meta.json   側檔（doc_url）

用法（與 SKILL.md 一致，都從 skill 目錄用 uv 跑）：
    uv run scripts/history_index.py --meeting data內會 --date 20260914 \
        --output-dir /tmp/meeting_sources/data內會_20260914
    另有 --sessions N（預設 3）與 --root（換歸檔根目錄，測試用）。

stdout 印交棒契約的一行：

    RESULT_HISTORY_INDEX: <索引檔路徑>

退出碼：
    0  索引已寫出（**找不到任何歷史場次也是 0** —— 空索引是合法結果，不是錯誤）
    2  參數錯誤：--meeting 指到 config 裡沒有的會議，或 --date 不是 8 位數字
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).parent))
from local_archive import DATE_DIR, LOCAL_ARCHIVE_ROOT, SIDECAR_SUFFIX

INDEX_FILENAME = "history-index.md"
NOTE_PREFIX = "會議記錄"
DEFAULT_SESSIONS = 3
MAX_DEPTH = 3

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
# 索引只要讀得懂的標題文字，不要行內標記。粗體與 inline code 的標記字元原樣留著會讓
# 大綱多一堆 `**`，對「掃過去判斷以前談過沒有」沒有幫助。
_INLINE_MARK = re.compile(r"\*\*|__|`")

# 索引檔開頭那幾句是**資料不是邏輯**，所以放在模組層而不是 render() 裡面。
# 擺在函式裡的話 mutation 會把每一句都變異一次，而「這句話少了一個字」殺不掉也不該
# 殺得掉 —— 要殺就得寫逐字釘死版面的測試，那正是棒④會刪掉的裝飾性測試。
INDEX_HEADER = (
    "**這是索引不是語料**：只有各場的 heading 大綱與指標，沒有內容行。\n"
    "接地優先序低於 `transcript.md`：歷史不能長出本次會議沒講過的事實。"
)
EMPTY_NOTICE = "（本機歸檔沒有早於 {before_date} 的同系列場次。）"


class Session(NamedTuple):
    """索引裡的一場。`doc_url` 是 None 表示側檔缺席或沒記 URL。"""

    label: str
    note_path: Path
    doc_url: str | None
    outline: list[tuple[int, str]]


def outline(markdown: str) -> list[tuple[int, str]]:
    """抽 heading 大綱，回傳 [(層級, 標題文字)]。

    `MAX_DEPTH` 是在擋 Heading 4 那層的版型樣板（`#### 討論`／`#### 狀態`／`#### 風險`
    每個議題重複一次，資訊量是零）。議題 heading 本身是 Heading 3，不會被切掉。
    做成參數過一次又收回來了 —— 沒有任何產品呼叫端會傳別的值。

    圍欄程式區塊裡的 `# 註解`**不是** heading —— 不濾掉的話會在大綱裡長出假議題。
    """
    found: list[tuple[int, str]] = []
    fence: str | None = None
    for line in markdown.splitlines():
        opener = _FENCE.match(line)
        if fence is not None:
            if opener and opener.group(1) == fence:
                fence = None
            continue
        if opener:
            fence = opener.group(1)
            continue
        m = _HEADING.match(line)
        if not m:
            continue
        level = len(m.group(1))
        text = _INLINE_MARK.sub("", m.group(2)).strip()
        if level <= MAX_DEPTH and text:
            found.append((level, text))
    return found


def doc_url(sidecar_path: Path) -> str | None:
    """側檔裡的 Doc URL。側檔缺席、壞掉或沒記 URL 都回 None。

    回 None 的下游意義是「這欄位缺席」，不是「URL 是 None」—— 寫 `None` 進索引會讓
    agent 以為那是一個可用的值。
    """
    try:
        value = json.loads(sidecar_path.read_text(encoding="utf-8")).get("doc_url")
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) and value.strip() else None


def find_notes(
    root: Path,
    folder_name: str,
    before_date: str,
    limit: int = DEFAULT_SESSIONS,
) -> list[Path]:
    """同系列、**早於** `before_date` 的最近 `limit` 份正式稿，由舊到新。

    「場」數的是正式稿份數不是日期數：同日多場次（`_am`／`_pm`）各算一場，不然
    近三場會被同一天吃掉兩格。

    只認 `會議記錄` 開頭的 `.md` —— 日期資料夾裡同時躺著 source artifacts
    （`transcript.md`／`extract.md`／`meeting-context.md`），拿它們當正式稿會讓索引
    指到逐字稿。
    """
    if limit <= 0:
        return []
    notes: list[Path] = []
    series_dir = root / folder_name
    try:
        date_dirs = sorted(p for p in series_dir.iterdir() if p.is_dir())
    except OSError:
        return []
    for date_dir in date_dirs:
        if not DATE_DIR.fullmatch(date_dir.name) or date_dir.name >= before_date:
            continue
        notes.extend(
            sorted(p for p in date_dir.glob(f"{NOTE_PREFIX}*.md") if p.is_file())
        )
    return notes[-limit:]


def read_session(note_path: Path, series_name: str) -> Session:
    """把一份正式稿讀成 `Session`。讀不到正式稿會 raise；側檔讀不到只是沒有 URL。"""
    # 前綴對不上就退回整個檔名（`series_name` 含 `/` 之類時，寫檔那步會把它清成 `-`，
    # 前綴就對不上了）。退化後的 label 仍然唯一且看得懂，所以不當成錯誤。
    label = note_path.stem.removeprefix(f"{NOTE_PREFIX}_{series_name}_")
    return Session(
        label=label,
        note_path=note_path,
        doc_url=doc_url(note_path.with_name(note_path.stem + SIDECAR_SUFFIX)),
        outline=outline(note_path.read_text(encoding="utf-8")),
    )


def render(series_name: str, before_date: str, sessions: list[Session]) -> str:
    """索引的 Markdown。沒有任何場次時說明為什麼，不留一份空白檔讓人以為壞了。"""
    lines = [f"# 歷史會議索引：{series_name}", "", INDEX_HEADER, ""]
    if not sessions:
        lines.append(EMPTY_NOTICE.format(before_date=before_date))
        return "\n".join(lines) + "\n"

    lines.append(f"近 {len(sessions)} 場，全部早於 {before_date}（不含本次與之後的日期）。")
    for session in sessions:
        lines += ["", f"## {session.label}", f"本機: {session.note_path}"]
        if session.doc_url:
            lines.append(f"Doc: {session.doc_url}")
        lines += [f"{'  ' * (level - 1)}- {text}" for level, text in session.outline]
    return "\n".join(lines) + "\n"


def build_index(
    source_dir: Path,
    folder_name: str,
    series_name: str,
    before_date: str,
    root: Path = LOCAL_ARCHIVE_ROOT,
    limit: int = DEFAULT_SESSIONS,
) -> Path:
    """產索引檔並回傳路徑。

    單一份正式稿讀不進來時只跳過那一場並印出原因 —— 歸檔裡一個壞檔不該讓整個
    source extraction 流程掛掉，但也不能靜靜少一場。
    """
    sessions: list[Session] = []
    for note_path in find_notes(root, folder_name, before_date, limit):
        try:
            sessions.append(read_session(note_path, series_name))
        except (OSError, ValueError) as e:
            print(f"⚠️  歷史索引略過讀不到的正式稿：{note_path}（{e}）")
    index_path = Path(source_dir) / INDEX_FILENAME
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(render(series_name, before_date, sessions), encoding="utf-8")
    return index_path


def main() -> None:
    # 這裡才 import：`extract_audio_sources` 在模組層 import 本檔，頂層互 import 會繞成環。
    from extract_audio_sources import load_config

    parser = argparse.ArgumentParser(description="產同系列近 N 場的歷史會議索引")
    parser.add_argument("--meeting", "-m", required=True, help="會議類型（config.json 的 meetings key）")
    parser.add_argument("--date", required=True, help="本次日期 YYYYMMDD（8 位數字）；索引只收早於它的場次")
    parser.add_argument("--output-dir", required=True, help="source artifacts 目錄，索引寫在裡面")
    parser.add_argument("--sessions", type=int, default=DEFAULT_SESSIONS, help=f"取近 N 場（預設 {DEFAULT_SESSIONS}）")
    parser.add_argument("--root", help="歸檔根目錄（預設吃 config 的 local_archive_root）")
    args = parser.parse_args()

    # 日期比較是字串比較。`--date` 不是 8 位數字時（例如 `2026-09-14`），每一場都會被
    # 判成「本次或之後」而排掉 —— 索引靜靜寫成空檔、exit 0、契約行照印。失敗模式是資料
    # 缺失而不是報錯，人會去 debug 索引但病在參數，所以擋在這裡。
    if not DATE_DIR.fullmatch(args.date):
        print(f"❌ --date 要 8 位數字 YYYYMMDD，收到：'{args.date}'")
        sys.exit(2)

    meetings = load_config().get("meetings", {})
    if args.meeting not in meetings:
        print(f"❌ 找不到會議類型：'{args.meeting}'")
        print(f"   可用的會議類型：{', '.join(meetings)}")
        sys.exit(2)

    meeting = meetings[args.meeting]
    series_name = meeting["series_name"]
    index_path = build_index(
        Path(args.output_dir).expanduser(),
        meeting.get("folder_name", series_name),
        series_name,
        args.date,
        root=Path(args.root).expanduser() if args.root else LOCAL_ARCHIVE_ROOT,
        limit=args.sessions,
    )
    print(f"RESULT_HISTORY_INDEX: {index_path}")


if __name__ == "__main__":
    main()
