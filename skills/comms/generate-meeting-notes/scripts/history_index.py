#!/usr/bin/env python3
"""
history_index.py - 同系列近 N 場的歷史索引。

**這是索引不是語料。** 每場只給三樣東西：

1. heading 大綱（層級上限 `MAX_DEPTH`，預設到 Heading 3）—— 不含任何內容行
2. **未結案項目**：`#### 狀態` 底下非 `已確認` 的條目，與 `## 行動項目` 表裡
   部署狀態非 `已上線` 的列（見 `open_items`）
3. 指標：本機正式稿路徑，以及側檔裡記著的 Doc URL

設計意圖是「只有本次議題延伸自過去議題時才需要歷史」。agent 掃大綱判斷「這個以前
談過」，再決定要不要沿指標去讀那一場的全文 —— 而不是把三場正式稿整包塞進 context。

第 2 項是 #298 加的，而且是**刻意的鬆綁**：#11 的 eval 量到「上一場留下、本次沒人提
的待辦」兩版都 0/3。根因是 heading 不帶狀態 —— 大綱裡只有議題標題，看不出它還懸著；
而「不帶狀態」又讓 agent 沒有任何理由沿指標去讀全文，於是那條待辦在兩層都隱形。
鬆綁的邊界是**只多抽未結案的那幾行**，不是把內容行整批放進來：已結案的項目一行都不進
索引（`RESOLVED_STATUS` / `SHIPPED_DEPLOY`），長度由 `MAX_OPEN_ITEMS` 封頂。

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

# 「這一項已經結案了」在正式稿裡的兩種寫法。**其餘每個值都算未結案** —— 白名單而不是
# 黑名單：版型的狀態值域將來多一個（`已驗收` 之類），黑名單會靜靜地把它當成已結案而
# 漏掉，白名單只會多帶一條進索引。多帶看得見，漏掉看不見。
RESOLVED_STATUS = "已確認"   # `#### 狀態` 底下的 inline code 標記
SHIPPED_DEPLOY = "已上線"    # `## 行動項目` 表最後一欄（部署狀態）

STATUS_LAYER = "狀態"        # 要抽的那個 Heading 4 層名
ACTION_HEADING = "行動項目"  # 要抽的那個 Heading 2 節名（用 `in` 比對，容得下編號前綴）
ACTION_MIN_CELLS = 3         # 少於這個欄數的表不是行動項目表的形狀，不抽

# 一場最多列幾條未結案。**索引長度的上限是驗收條件**（一場 40 行內），而未結案的條數
# 是這裡唯一沒有天花板的東西：大綱的條數由 heading 決定、指標固定兩行。這個值是從那條
# 上限回推的，不是隨手挑的：
#
#     40 − 19（語料裡最長的一場大綱）− 3（`## 標籤`／`本機:`／`Doc:`）
#        − 1（未結案的標籤行）− 1（超出時的「還有幾條」）− 6（檔頭與空行）= 10
#
# 超出的不靜靜丟掉 —— `render` 會多寫一行說還有幾條，並指回全文。
MAX_OPEN_ITEMS = 10

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
# 索引只要讀得懂的標題文字，不要行內標記。粗體與 inline code 的標記字元原樣留著會讓
# 大綱多一堆 `**`，對「掃過去判斷以前談過沒有」沒有幫助。
_INLINE_MARK = re.compile(r"\*\*|__|`")
# `* `執行中` 排程重複觸發的修復（Speaker2，本週）` → (`執行中`, 說明)。
# 版型規定狀態條目一律 inline code 標記開頭，所以認標記而不是認行首形狀。
_STATUS_BULLET = re.compile(r"^\s*[*-]\s+`([^`]+)`\s+(\S.*?)\s*$")
# Markdown 表格的分隔列（`| :--- | :--- |`）。它是「上面那列是表頭」的唯一訊號 ——
# 認表頭的文字（`部署狀態`）會在欄名換句話時靜靜地把表頭當成一條未結案項目。
_TABLE_SEP = re.compile(r"[\s:|-]+")

# 索引檔開頭那幾句是**資料不是邏輯**，所以放在模組層而不是 render() 裡面。
# 擺在函式裡的話 mutation 會把每一句都變異一次，而「這句話少了一個字」殺不掉也不該
# 殺得掉 —— 要殺就得寫逐字釘死版面的測試，那正是棒④會刪掉的裝飾性測試。
INDEX_HEADER = (
    "**這是索引不是語料**：各場只有 heading 大綱、未結案項目與指標，沒有其餘內容行。\n"
    "`未結案` 那幾條還懸著。**逐條確認本次有沒有再提到**；完全沒人提的寫進正式稿的\n"
    "「前次未結案項目」並標明本次未提。接地優先序低於 `transcript.md`。"
)
EMPTY_NOTICE = "（本機歸檔沒有早於 {before_date} 的同系列場次。）"


class Session(NamedTuple):
    """索引裡的一場。`doc_url` 是 None 表示側檔缺席或沒記 URL。

    `open_items` 給預設值不是為了方便 —— 是為了讓「這一場沒有任何未結案」與「呼叫端
    忘了傳」在型別上就分不出來的那種 bug 不可能發生：兩者都是空的，而空的就是不 render。
    """

    label: str
    note_path: Path
    doc_url: str | None
    outline: list[tuple[int, str]]
    open_items: tuple[str, ...] = ()


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


def open_items(markdown: str) -> list[str]:
    """一場裡**還沒結案**的項目，由上而下、原文順序。

    兩個來源，因為兩種版型都真的存在於歸檔裡：

    | 來源 | 判為未結案的條件 |
    |---|---|
    | `#### 狀態` 底下的條目 | inline code 標記**不是** `已確認` |
    | `## 行動項目` 表的資料列 | 最後一欄（部署狀態）**不是** `已上線` |

    只做第一個來源的話，2026-09-10 版型落地之前的每一份正式稿都抽不出東西 —— 那是歸檔
    裡的多數。只做第二個來源的話，沒有行動項目表的短會議抽不出東西。

    表格的資料列只認**分隔列之後**的：表頭那一列的最後一欄是欄名（`部署狀態`），不是
    狀態值，照收會讓每張表都長出一條假的未結案項目。

    回傳的是**全部**未結案項目，不截斷 —— 要列幾條是版面的事，由 `render` 決定
    （`MAX_OPEN_ITEMS`）。抽取函式自己截斷的話，「這場只有三條」與「這場被切到剩三條」
    在回傳值上一模一樣。

    圍欄程式區塊照 `outline` 的規矩跳過：裡面的 `|` 表格與 `* ` 條目都不是正式稿的結構。

    **已知邊界：正式稿的 `## 前次未結案項目` 那一節不是來源。** 一條待辦連續好幾場沒人提
    的話，第二場之後它只出現在那一節裡，所以它撈得出來的期限就是索引的視窗
    （`DEFAULT_SESSIONS`，預設 3 場）—— 視窗外就跟著滑掉。這是**刻意**的：把那一節也當
    來源會讓「沒人提」自我延續下去，而索引本來只承諾近 N 場。要更長的記憶，要的是議題
    關係圖（#14 已列 Out of Scope），不是在這裡多接一個來源。
    """
    items: list[str] = []
    fence: str | None = None
    layer: str | None = None
    in_actions = False
    after_table_header = False

    for line in markdown.splitlines():
        opener = _FENCE.match(line)
        if fence is not None:
            if opener and opener.group(1) == fence:
                fence = None
            continue
        if opener:
            fence = opener.group(1)
            continue

        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            title = _INLINE_MARK.sub("", heading.group(2)).strip()
            # 任何 heading 都會蓋掉 `layer`，所以「豁免漏到下一個議題」本來就不會發生。
            # `level == 4` 真正擋的是**別的層級上叫「狀態」的標題**（`### 狀態` 之類）——
            # 版型規定狀態層是 Heading 4，非 H4 的同名標題不當成它。代價是歸檔裡真有
            # `### 狀態` 的話會一條都抽不到而且不出聲；版型固定，接受這個代價。
            # `· 承 8/20 → 8/24` 這類後綴切掉（`議題因果鏈` 的形狀）。
            layer = title.split(" · ")[0].strip() if level == 4 else None
            if level <= 2:
                in_actions = ACTION_HEADING in title
            # ponytail: 值翻成 `True` 由 `test_open_items_never_turns_the_table_header_into_an_item`
            # 的第二個 assert 守著（heading 與表格之間沒有空行時，只剩這一行在擋表頭）。
            # **整行刪掉**才測不到，而且是結構性的：下面 `if not in_actions: continue`
            # 擋在表格解析之前，所以要湊出差別得「行動項目節以表格列結尾 → 緊接 heading
            # 無空行 → 下一節又是行動項目節」。成本一行，留著。
            after_table_header = False
            continue

        if layer == STATUS_LAYER:
            bullet = _STATUS_BULLET.match(line)
            if bullet and bullet.group(1) != RESOLVED_STATUS:
                text = _INLINE_MARK.sub("", bullet.group(2)).strip()
                items.append(f"{bullet.group(1)} · {text}")
            continue

        if not in_actions:
            continue

        row = line.strip()
        if not row.startswith("|"):
            after_table_header = False
            continue
        if _TABLE_SEP.fullmatch(row):
            after_table_header = True
            continue
        if not after_table_header:
            continue

        cells = [_INLINE_MARK.sub("", c).strip() for c in row.strip("|").split("|")]
        state = cells[-1]
        if len(cells) < ACTION_MIN_CELLS or not state or state == SHIPPED_DEPLOY:
            continue
        owner, description = cells[0], cells[1]
        if description:
            items.append(f"{state} · {description}（{owner}）" if owner else f"{state} · {description}")

    # 同一件事常常同時寫在 `#### 狀態` 與行動項目表裡，但**措辭不同**，所以只去逐字重複的。
    # 模糊比對會把兩條講不同面向的項目合成一條，而合掉哪一條沒有任何斷言看得見。
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


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
    # 讀一次就好 —— 兩支抽取函式吃同一份文字。分兩次讀的話，兩次之間檔案被改寫會讓
    # 大綱與未結案來自不同版本的同一場，而那種不一致沒有任何斷言看得見。
    text = note_path.read_text(encoding="utf-8")
    return Session(
        label=label,
        note_path=note_path,
        doc_url=doc_url(note_path.with_name(note_path.stem + SIDECAR_SUFFIX)),
        outline=outline(text),
        open_items=tuple(open_items(text)),
    )


OPEN_ITEMS_LABEL = "未結案（上一場留下的，逐條確認本次有沒有再提到）"
MORE_ITEMS = "…另有 {count} 條未結案沒列出，需要完整清單就沿 `本機:` 讀全文"


def _open_items_block(items: tuple[str, ...]) -> list[str]:
    """未結案那一小塊的行。一條都沒有時回空 list —— **不留標籤**。

    留一個空標籤的話，「這場全部結案了」與「抽取壞了」在索引上長得一模一樣，而這正是
    這一塊要解決的那種隱形。超過 `MAX_OPEN_ITEMS` 時多寫一行說還有幾條並指回全文：
    靜靜截斷會讓 agent 以為它看到的是全部。
    """
    if not items:
        return []
    shown = list(items[:MAX_OPEN_ITEMS])
    lines = [f"- {OPEN_ITEMS_LABEL}"] + [f"  - {item}" for item in shown]
    rest = len(items) - len(shown)
    if rest:
        lines.append(f"  - {MORE_ITEMS.format(count=rest)}")
    return lines


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
        lines += _open_items_block(session.open_items)
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
