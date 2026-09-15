"""流程 C 的歷史交棒契約 —— **文件叫 agent 去找的東西，腳本必須真的產得出來。**

`test_history_index.py` 守的是「索引這支腳本自己對不對」（抽取、邊界、stdout 的值）。
這一支守的是**跨檔的那條縫**：SKILL.md 流程 C 的來源表寫著一個字串，agent 拿那個字串
去 stdout 找路徑。兩邊各自綠、字串卻對不上時，沒有任何流程會報錯 —— 索引照產、契約行
照印、正式稿照發，只是歷史永遠沒被讀到。症狀跟這張票要修的那句散文一模一樣。

所以這裡每條斷言的比對字串都是**從 SKILL.md 解出來的**，不是測試自己寫死的字面值：
寫死的話，文件打錯字時測試比對的是自己那份正確答案，照樣全綠。方向是
「文件寫什麼 → 腳本要印得出什麼」。

`cli_home`（流程 A 的 CLI 環境）與 `flow_b`（流程 B 的 `main()`）都從
`test_history_index.py` 借過來，不重造一份替身樹。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.unit.conftest import load_script
from tests.unit.test_history_index import _run_cli, cli_home, flow_b  # noqa: F401  fixture 靠名字解析

hi = load_script("history_index")

REPO = Path(__file__).resolve().parents[2]
SKILL_MD = REPO / "skills/comms/generate-meeting-notes/SKILL.md"
SECTION_HEADING = "## 流程 C：Main Synthesis"

# 這張票要換掉的那句散文：沒有路徑、沒有數量、沒有取得方式，於是 agent 每次都跳過。
PROSE = "同類型歷史會議記錄"

_RESULT_KEY = re.compile(r"RESULT_[A-Z_]+")

# 指標欄位的探針值。`render()` 把它們寫在哪個標籤後面，就是文件該告訴 agent 的標籤。
POINTER_NOTE = Path("/archive/系列/20260831/會議記錄_系列_20260831.md")
POINTER_URL = "https://docs.google.com/document/d/pointer-probe/edit"


# --------------------------------------------------------------------------- helpers


def flow_c_section() -> str:
    """SKILL.md 的「流程 C」一節（到下一個 `## ` 為止）。"""
    text = SKILL_MD.read_text(encoding="utf-8")
    start = text.find(SECTION_HEADING)
    assert start != -1, f"SKILL.md 找不到「{SECTION_HEADING}」一節"
    end = text.find("\n## ", start + len(SECTION_HEADING))
    return text[start:] if end == -1 else text[start:end]


def flow_c_intro() -> str:
    """流程 C 的導言（來源表、證據優先序、輸出規則）—— 到第一個 `### ` 小節為止。

    指標欄位的標籤要在這裡找，不能掃全節：Step 1 的 `RESULT_LOCAL_NOTE: <本機正式稿路徑>`
    與「Doc 名稱」本來就含「本機」「Doc」兩個字，掃全節的話那條斷言永遠是綠的。
    """
    section = flow_c_section()
    end = section.find("\n### ")
    return section if end == -1 else section[:end]


def source_table_keys() -> set[str]:
    """流程 C **第一張表**（來源表）裡的 `RESULT_*` key。

    只取導言裡第一個連續的 `|` 區塊 —— Step 1 還有一張參數表。
    """
    rows: list[str] = []
    for line in flow_c_intro().splitlines():
        if line.startswith("|"):
            rows.append(line)
        elif rows:
            break
    assert rows, "流程 C 找不到來源表"
    return set(_RESULT_KEY.findall("\n".join(rows)))


def history_key() -> str:
    """來源表裡代表歷史的那個契約 key。剛好一個，不然就說不出要比對哪個字串。"""
    keys = {k for k in source_table_keys() if "HISTORY" in k}
    assert len(keys) == 1, f"流程 C 來源表要剛好一列歷史契約 key，找到：{keys or '一列都沒有'}"
    return keys.pop()


def local_path_label() -> str:
    """`render()` 每場寫本機正式稿路徑時用的那個標籤。

    索引檔兩個指標欄位裡，**只有本機路徑是 agent 沿得動的** —— Doc URL 是給人開的
    （SKILL.md 別處已明寫 agent 開不了 URL），所以那一個不在這裡。
    """
    session = hi.Session(
        label="20260831", note_path=POINTER_NOTE, doc_url=POINTER_URL, outline=[(1, "議題一")]
    )
    labels = {
        head
        for head, _, value in (
            line.partition(": ") for line in hi.render("系列", "20260907", [session]).splitlines()
        )
        if value == str(POINTER_NOTE)
    }
    assert len(labels) == 1, f"render() 要剛好一個本機路徑欄位，找到：{labels or '一個都沒有'}"
    return labels.pop()


def output_rules() -> str:
    """流程 C 的「輸出規則」那一段（到 `### ` 小節為止）。"""
    section = flow_c_intro()
    start = section.find("輸出規則")
    assert start != -1, "流程 C 找不到「輸出規則」"
    end = section.find("\n### ", start)
    return section[start:] if end == -1 else section[start:end]


# --------------------------------------------------------------------------- 來源表


def test_history_is_a_contract_row_beside_the_transcript():
    """驗收條件 1：歷史在來源表裡是一列 `RESULT_*`，與 `RESULT_TRANSCRIPT` 同一張表。

    刪掉這條 → 歷史那列可以退回一句沒有 key 的散文，而下面兩條「腳本印的 key 跟文件
    寫的一樣」連要比對的字串都取不到，整組測試靜靜地不再守任何東西 —— 綠燈還在，
    這張票要修的病原封不動回來。
    """
    keys = source_table_keys()

    assert "RESULT_TRANSCRIPT" in keys, f"來源表裡沒有逐字稿那列：{keys}"
    assert history_key() in keys


def test_flow_a_prints_the_key_the_doc_tells_the_agent_to_read(cli_home: Path, tmp_path: Path):
    """流程 A（`history_index.py`）的 stdout 真的印得出文件寫的那個 key。

    刪掉這條 → SKILL.md 那格打錯字（`RESULT_HISTORY_IDX`）照樣全綠：索引產了，agent
    照著文件去 stdout 找那個 key 找不到，歷史又一次被跳過。「索引產了但沒人找得到」
    不會讓任何一步報錯，所以只能靠這條比對抓。
    """
    source_dir = tmp_path / "sources"
    source_dir.mkdir()

    proc = _run_cli(
        cli_home, "--meeting", "data", "--date", "20260907", "--output-dir", str(source_dir)
    )

    assert proc.returncode == 0, proc.stderr
    printed = {
        line.split(":", 1)[0] for line in proc.stdout.splitlines() if line.startswith("RESULT_")
    }
    assert history_key() in printed, proc.stdout


def test_flow_b_prints_the_same_key_as_flow_a(flow_b):
    """流程 B（`extract_audio_sources.main`）也印同一個 key。

    刪掉這條 → 只有其中一條入口印得出文件要的 key。走另一條進流程 C 的會議，歷史欄位
    永遠是空的，而兩邊各自的測試都還是綠的（各印各的名字也沒人比對）。
    """
    results, _ = flow_b

    assert history_key() in results, f"流程 B 的交棒契約少了它：{sorted(results)}"


# --------------------------------------------------------------------------- 指標與敘述


def test_the_local_path_label_matches_what_the_index_actually_writes():
    """文件叫 agent 沿指標讀全文時指的欄位名，要跟索引檔裡本機路徑那欄的標籤一致。

    刪掉這條 → 文件說去讀某個欄位而索引寫的是別的標籤，agent 掃完大綱決定要讀全文時
    沿不到指標。判斷指示在、索引也在，只有中間那一跳斷掉 —— 沒有任何斷言看得見。
    Doc URL 那欄不在這裡：它是給人開的，agent 開不了 URL。
    """
    label = local_path_label()

    assert label in flow_c_intro(), f"流程 C 的來源說明沒提到索引實際用的本機路徑欄位：{label}"


def test_the_flow_c_section_no_longer_asks_for_history_in_prose():
    """驗收條件 2：這一節不再出現那句沒有取得方式的散文。

    刪掉這條 → 散文可以跟契約行並存，而兩句話並存時 agent 照舊走成本低的那條
    （「找不到就算了」），契約行等於沒加。
    """
    assert PROSE not in flow_c_section(), f"流程 C 還留著「{PROSE}」這句散文"


def test_history_stays_last_in_the_evidence_order():
    """驗收條件 4：證據優先序仍是 逐字稿 > 索引 > 脈絡 > 歷史。

    刪掉這條 → 歷史被寫成與逐字稿同級（甚至更前面），正式稿就長得出本次會議沒講過的
    事實 —— 接地約束破在文件這一層，腳本再對也擋不住。
    """
    lines = [line for line in flow_c_intro().splitlines() if "證據優先序" in line]
    assert len(lines) == 1, f"流程 C 要剛好一行證據優先序，找到 {len(lines)} 行"

    # 四個來源各給兩種寫法（檔名或契約 key）—— 釘的是順序，不是這一行用哪種稱呼。
    order = [
        ("transcript.md", "RESULT_TRANSCRIPT"),
        ("extract.md", "RESULT_EXTRACT"),
        ("meeting-context.md", "RESULT_CONTEXT"),
        ("歷史", history_key()),
    ]
    positions = [
        min((lines[0].find(alias) for alias in aliases if alias in lines[0]), default=-1)
        for aliases in order
    ]
    assert -1 not in positions, lines[0]
    assert positions == sorted(positions), f"歷史沒有排在最後：{lines[0]}"


def test_the_output_rules_keep_the_history_index_out_of_the_formal_note():
    """驗收條件 5：歷史索引與「我參考了歷史記錄」這類 pipeline 敘述不進正式稿。

    刪掉這條 → 索引變成交棒契約的一員之後，它的路徑與「參考了哪幾場」會跟著被寫進
    發佈出去的 Doc。那是給 agent 看的中間產物，讀者看到的是一份摻著流程雜訊的會議記錄。
    """
    rules = output_rules()

    assert "agent 回報" in rules, "輸出規則沒有『只出現在 agent 回報裡』那條"
    assert "歷史" in rules or hi.INDEX_FILENAME in rules, f"輸出規則沒把歷史索引擋在正式稿外面：\n{rules}"
