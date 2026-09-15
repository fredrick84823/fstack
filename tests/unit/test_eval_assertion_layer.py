"""`tests/eval/grade.py` 這層判讀自己要有 unit 守著。

#14 的陷阱表指給 issue #11 的就是這條：

> 驗收腳本進不了 CI（要真憑證或 subagent），它自己的靜默失敗沒人守
> → 在 unit test 測**斷言層**，每壞一件事必須且**只有**對應那條變紅

`tests/eval/run_eval.py` 要起 `claude -p` 子行程、要花錢，進不了 CI，所以 `grade()`
的顏色只能靠這一支守。沒有這道，eval 印出來的通過率是一個沒人守的數字 ——
`grade()` 被寫成永遠回全 True，三份語料照樣滿分，不會有任何東西變紅。

所以這裡每份負面樣本都**只弄壞一件事**，而斷言打在整份 dict 的相等上，不是
「有東西紅了」。判準互相污染（弄壞 A 順手把 B 也判紅）跟判準整組失效一樣會讓
eval 的分數失去意義，而只驗「有東西紅了」的寫法**兩種都看不見**。

樣本裡的探針一律從 `grade.py` 的公開常數插進去，不寫死字面值：寫死的話語料換詞時，
測試比對的是自己那份舊答案，照樣全綠 —— 跟 `test_history_handoff_contract.py`
從 SKILL.md 解字串是同一個理由。

三個 case 各有自己的一份正式稿樣本。共用一份的話，某個 case 的判準抓到的其實是
別個 case 種的料，那條判準就再也不會因為自己的語料壞掉而變紅。

**判準放寬過的地方，放寬本身要另外釘。** 實跑對著真的產出校準掉三處誤判
（`old_never_stands_alone` 收太緊、`UNADDRESSED` 的詞太短、引言排除用行首形狀比對），
而放寬只留一份「該綠時綠」的樣本是守不住的：往回收緊會紅，往外寬到沒有鑑別力
**不會紅**。所以每一處放寬都配一組「放寬到這裡為止」的樣本，兩個方向各釘一次。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.eval.grade import (
    CARRYOVER,
    CASES,
    DISCUSSION_LAYER,
    GARBLE,
    NEW_DECISION,
    OLD_DECISION,
    OVERRIDE,
    TERM,
    UNADDRESSED,
    grade,
    passed,
)
from tests.eval.run_eval import ARMS, build_prompt, flow_c, handoff
from tests.unit.layout_contract import LAYER_RANK
from tests.unit.test_history_handoff_contract import history_key, source_table_keys

FIXTURES = Path(__file__).resolve().parents[2] / "tests/eval/fixtures"

# 樣本挑定的說法，寫成**字面值**再由 `test_the_sample_wordings_are_still_in_the_tables`
# 對回詞表。靠 `OVERRIDE[0]` 這種位置索引的話，詞表重排會靜靜改寫每一份樣本，
# 而樣本被改掉這件事沒有任何斷言看得見。
OVERRIDDEN = "推翻"      # OVERRIDE 裡挑的：最直白的那個說法
CHANGED_TO = "改為"      # OVERRIDE 裡挑的：正式稿真正會寫的那個說法
NOT_MENTIONED = "未提及"  # UNADDRESSED 裡挑的

# 每個 case 的判準名 —— 這就是 grade() 對 run_eval.py 承諾的形狀。
CRITERIA: dict[str, tuple[str, ...]] = {
    "glossary": ("restores_term",),
    "dropped-todo": ("surfaces_carryover", "marks_it_unaddressed"),
    "overridden-decision": (
        "adopts_new_decision",
        "marks_the_override",
        "old_never_stands_alone",
    ),
}


# --- 樣本：正式稿 Markdown ------------------------------------------------
# 每個 case 一支 builder，變動的只有「那件被種進去的料」，其餘骨架固定 ——
# 這樣正面與負面樣本的差異剛好就是判準宣稱在量的那一件事。


def glossary_note(term: str) -> str:
    """術語校正的正式稿；`term` 是正式稿裡真的寫出來的那個名字。"""
    return f"""# **會議記錄：評測_術語校正 20260831**

**日期**：2026-08-31
**與會者**：Speaker1 (MLE)、Speaker2 (RD)

## 核心要點

* **閘道服務名稱統一為 {term} [已確認]**：文件與程式碼一律用這個寫法。

## 討論過程

### 議題一：閘道服務的名稱

**TL;DR** — 名稱以 {term} 為準。

#### 狀態

* `已確認` 服務名稱為 {term}
"""


def dropped_todo_note(item: str, status: str) -> str:
    """消失的待辦的正式稿；`item` 是被撈出來的待辦，`status` 是它被標成什麼。"""
    return f"""# **會議記錄：評測_消失的待辦 20260831**

**日期**：2026-08-31
**與會者**：Speaker1 (MLE)、Speaker2 (RD)

## 核心要點

* **上一場的待辦**：{item} —— {status}。

## 討論過程

### 議題一：本次聚焦的報表欄位

**TL;DR** — 欄位對照表這次就定案。

## 行動項目

| 負責人 | 待辦事項描述 | 交付物與驗證標準 | 部署狀態 |
| :--- | :--- | :--- | :--- |
| Speaker2 | {item} | 可重跑的驗證腳本 | 執行中 |
"""


def overridden_note(core: str, issue_body: str = "") -> str:
    """被推翻的決策的正式稿。

    `core` 是 `## 核心要點` 的條目，`issue_body` 是議題一 TL;DR 之後的整段 ——
    `#### ` 層的 heading 由呼叫端自己寫，因為**行落在哪一層**正是這個 case 的
    兩條判準在看的東西，不能被 builder 固定死。

    骨架本身刻意不含 `OLD_DECISION` / `NEW_DECISION` / `OVERRIDE` 任何一種說法，
    否則負面樣本會被骨架偷偷救活成綠的。
    """
    return f"""# **會議記錄：評測_被推翻的決策 20260831**

**日期**：2026-08-31
**與會者**：Speaker1 (MLE)、Speaker2 (RD)、Speaker3 (PM)

## 核心要點

{core}

## 討論過程

### 議題一：匯出格式

**TL;DR** — 以本次的結論為準。

{issue_body}
"""


# 標明了推翻的那一行：同一行上有舊決策也有推翻的說法。
# 刻意寫成不帶粗體冒號的樸素條目，好讓「只紅一條」那幾份樣本紅的原因單一 ——
# 房規格式（`* **標題 [已確認]**：說明）另外有一條專屬測試在釘。
MARKED_OVERRIDE = (
    f"* 匯出格式{CHANGED_TO} {NEW_DECISION}，"
    f"{OVERRIDDEN}了 {OLD_DECISION} 的舊決議。"
)

# 房規格式的核心要點條目 —— 正式稿真的長這樣（見語料 20260824 那份）。
HOUSE_MARKED_OVERRIDE = (
    f"* **匯出格式{CHANGED_TO} {NEW_DECISION} [已確認]**："
    f"{OVERRIDDEN}了 {OLD_DECISION} 的舊決議。"
)

# 真正的污染：舊決策被寫成現行結論。沒有任何 OVERRIDE 說法，沒有新決策，
# 而且不在 `#### 討論` 底下 —— 三道放行條件一條都不沾。
STANDS_ALONE = f"* `已確認` 第一版匯出格式為 {OLD_DECISION}"

# 引言：`#### 討論` 的條目照抄發言者原話，判準不該要求 agent 竄改別人講的話。
QUOTE = f"* **Speaker3**：客戶不要 {OLD_DECISION}。"

GOOD = {
    "glossary": glossary_note(TERM),
    "dropped-todo": dropped_todo_note(CARRYOVER, f"本次逐字稿{NOT_MENTIONED}"),
    "overridden-decision": overridden_note(
        HOUSE_MARKED_OVERRIDE + "\n* 匯出欄位沿用線上報表。",
        f"#### 討論\n\n{QUOTE}\n\n#### 狀態\n\n* `已確認` 匯出格式{CHANGED_TO} {NEW_DECISION}",
    ),
}

# 每份只弄壞一條，其餘照樣綠。
ONLY_BROKEN = {
    # 正解不出現：照抄本次逐字稿裡 STT 聽壞的音譯。
    "restores_term": ("glossary", glossary_note(GARBLE)),
    # 歷史待辦整條沒被撈出來，但「本次沒提」的說法還在。
    "surfaces_carryover": (
        "dropped-todo",
        dropped_todo_note("報表欄位對照", f"本次逐字稿{NOT_MENTIONED}"),
    ),
    # 待辦撈出來了，卻沒標成本次沒提。這句就是實跑咬到的那種句子：
    # 「未提前」裡有「未提」，跟上週待辦無關 —— 詞表換長之後它不該再配到。
    "marks_it_unaddressed": (
        "dropped-todo",
        dropped_todo_note(CARRYOVER, "欄位順序若未提前與客戶對齊會重工"),
    ),
    # 標明了推翻，卻沒把本次的新決策寫進去。
    "adopts_new_decision": (
        "overridden-decision",
        overridden_note(
            f"* 匯出格式{CHANGED_TO}新格式，{OVERRIDDEN}了 {OLD_DECISION} 的舊決議。"
        ),
    ),
    # 採用了新決策，但舊決策整個沒提，於是沒有任何一行標明推翻了什麼。
    # 舊決策不出現時 old_never_stands_alone 為真（空集合），這份樣本同時釘住那個全稱量化。
    "marks_the_override": (
        "overridden-decision",
        overridden_note(f"* 匯出格式為 {NEW_DECISION}，以本次的結論為準。"),
    ),
    # 有一行標明了推翻，另一行卻把舊決策寫成現行結論 —— 歷史污染本次事實。
    "old_never_stands_alone": (
        "overridden-decision",
        overridden_note(MARKED_OVERRIDE + "\n" + STANDS_ALONE),
    ),
}

# 照抄亂碼那一種不在這裡：`ONLY_BROKEN["restores_term"]` 就是那份輸入。
GLOSSARY_FAILURES = {
    "flagged-unconfirmed": glossary_note(f"{GARBLE} [待確認]"),
    "wrong-guess": glossary_note("Castro"),
}

# `old_never_stands_alone` 放寬到哪裡為止。
# 每格是 (核心要點要多加的一行, 議題一的整段, 這條判準該回什麼)。
STANDS_ALONE_BOUNDARY = {
    # 析取的右半邊：同一行上舊決策旁邊就是新決策，讀者看得到改成什麼，不算污染。
    # （這一行沒有任何 OVERRIDE 說法 ——「換成」不在詞表裡。）
    "old-beside-new": (f"* 匯出格式從 {OLD_DECISION} 換成 {NEW_DECISION}。", "", True),
    # 排除的是**層**：同一句話擺在 `#### 討論` 底下是照抄別人的話，放行。
    "quote-under-discussion": ("", f"#### 討論\n\n{QUOTE}", True),
    # ……擺在 `#### 狀態` 底下就是正式稿自己在陳述事實，照判。
    # 這一組對照是整條規則的核心，兩格必須一起看。
    "same-quote-under-status": ("", f"#### 狀態\n\n{QUOTE}", False),
    # 層名比對前要照 `layout_contract._layer_name()` 去掉 ` · 承 M/D → M/D` 後綴。
    "discussion-heading-with-suffix": ("", f"#### 討論 · 承 8/24 → 8/31\n\n{QUOTE}", True),
    # 後綴不會把別的層變成討論層：因果鏈底下的行照算。
    "causal-chain-with-suffix": (
        "",
        f"#### 議題因果鏈 · 承 8/24 → 8/31\n\n{STANDS_ALONE}",
        False,
    ),
    # `###` 把「目前在哪一層」清成無，討論層的豁免不會漏到下一個議題去。
    "h3-resets-the-layer": (
        "",
        f"#### 討論\n\n* **Speaker1**：沒有其他意見。\n\n### 議題二：匯出欄位\n\n{STANDS_ALONE}",
        False,
    ),
    # 「核心要點底下的污染」不在這裡：那份正式稿與
    # `ONLY_BROKEN["old_never_stands_alone"]` 逐位元組相同，那條已經在擋了。
}


# --- 測試 -----------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=list(CASES))
def test_a_note_that_read_the_history_passes(case: str):
    """三個 case 各有一份「答對了」的正式稿，整題要過。

    刪掉這條，`grade()` 就沒有任何一條測試逼它說 True —— 一個永遠回全 False 的
    判讀層會讓 eval 印出 0/3，看起來像 skill 壞了，沒人會去懷疑是尺壞了。
    """
    assert passed(grade(case, GOOD[case]))


@pytest.mark.parametrize("criterion", list(ONLY_BROKEN), ids=list(ONLY_BROKEN))
def test_breaking_one_thing_reds_exactly_one_criterion(criterion: str):
    """每壞一件事，回來的 dict 必須**恰好只有**對應那條是 False。

    這是這一支存在的核心理由，兩個方向各擋一種假綠：
    該條沒紅 → 那條判準是裝飾品，eval 對那種失敗永遠盲；
    別條跟著紅 → 判準之間互相污染，紅的位置指不到真正壞掉的東西。

    斷言打在整份 dict 的相等上，順便釘住 key 集合：少一條判準、多一條判準、
    改個名字都會紅 —— run_eval.py 靠這些名字印報表。

    刪掉這條，整支檔案就只剩「該綠時綠」那幾條 —— `grade()` 被寫成永遠回全 True
    一個字都不會紅，而 eval 會印出漂亮的 3/3。這是本票唯一守著那件事的斷言。
    """
    case, note = ONLY_BROKEN[criterion]
    expected = {name: name != criterion for name in CRITERIA[case]}

    assert grade(case, note) == expected
    assert not passed(grade(case, note))


@pytest.mark.parametrize(
    "shape", list(STANDS_ALONE_BOUNDARY), ids=list(STANDS_ALONE_BOUNDARY)
)
def test_old_decision_is_excused_by_its_layer_not_by_its_wording(shape: str):
    """`old_never_stands_alone` 放寬到哪裡為止 —— 兩個方向同一支釘。

    實跑六次全紅在這一條，六份產出卻沒有一份真的把舊決策寫成現行結論：紅的是
    「客戶主管只用 Excel，CSV 開啟為亂碼」這種**理由句**，以及
    `#### 討論` 底下照抄的**發言引言**。判紅理由句等於要求正式稿不准解釋為什麼改，
    判紅引言等於要求 agent 竄改別人講的話。

    豁免看的是**所在的層**，不是句子長什麼樣 —— 這就是
    `quote-under-discussion` / `same-quote-under-status` 那一組對照：一模一樣的
    字串，換個層答案就要翻面。刪掉那一組，規則會靜靜退化回行首形狀比對，
    而房規格式的核心要點條目跟引言撞號，正確的產出會被判紅（上一版就是這樣）。

    另一個方向：寬到把 `core-section-pollution` 也放行，這條判準就再也抓不到
    任何東西，而它正是新機制唯一的副作用探針（歷史污染本次事實）。

    每份樣本的核心要點都夾著 `MARKED_OVERRIDE`，所以另外兩條判準恆綠 ——
    紅的只會是這一條，位置指得準。
    """
    extra, issue_body, expect = STANDS_ALONE_BOUNDARY[shape]
    core = MARKED_OVERRIDE + ("\n" + extra if extra else "")

    assert grade("overridden-decision", overridden_note(core, issue_body)) == {
        "adopts_new_decision": True,
        "marks_the_override": True,
        "old_never_stands_alone": expect,
    }


def test_the_house_core_bullet_can_carry_the_override_marker():
    """房規格式的核心要點條目要算數：`* **標題 [已確認]**：說明`。

    正式稿的核心要點就長這樣（見 `fixtures/overridden-decision` 的 20260824 那份），
    而 agent 最自然就是把「推翻了什麼」標在那裡。上一版的引言排除拿行首形狀比對
    （bullet 接粗體接冒號），跟這個房規格式撞號，整行被濾掉 ——
    寫得再正確的產出 `marks_the_override` 都是紅的，而紅的原因跟內容無關。

    刪掉這條，排除規則改回形狀比對不會有任何東西變紅，那個假紅會靜靜回來。
    """
    note = overridden_note(HOUSE_MARKED_OVERRIDE)

    assert grade("overridden-decision", note) == {
        "adopts_new_decision": True,
        "marks_the_override": True,
        "old_never_stands_alone": True,
    }


def test_the_override_marker_must_sit_on_the_old_decision_line():
    """標明推翻的說法要跟舊決策**同一行**，別處的 `OVERRIDE` 字眼救不了。

    `OVERRIDE` 詞表很寬（`上次`、`上週`、`原本`、`取消`…），正式稿裡到處都是。
    撐住這份寬度的是「只看含 `OLD_DECISION` 的行」這個範圍限制 ——
    刪掉這條、改成掃全文，`marks_the_override` 幾乎對任何正式稿都會說 True，
    這個 case 就只剩 `adopts_new_decision` 一條判準在做事了。
    """
    note = overridden_note(
        f"* 匯出格式為 {NEW_DECISION}，以本次的結論為準。\n"
        f"* 欄位設計沿用線上報表，{OVERRIDDEN}了原先的提案。"
    )

    assert grade("overridden-decision", note) == {
        "adopts_new_decision": True,
        "marks_the_override": False,
        "old_never_stands_alone": True,
    }


@pytest.mark.parametrize("mode", list(GLOSSARY_FAILURES), ids=list(GLOSSARY_FAILURES))
def test_every_glossary_failure_mode_misses_the_term(mode: str):
    """票上點名的三種失敗（照抄亂碼／標成待確認／猜錯成別的字）都要紅。

    三種的共同點是正解不出現，所以全部紅在 `restores_term` 這一條。刪掉這條，
    「標成 [待確認]」這種**看起來很負責**的輸出就可能被判成過 —— 那正是沒讀歷史時
    agent 最常給的答案，也正是這個 case 要抓的東西。

    這裡只驗正解出現與否，不驗「亂碼不得出現」：那條試跑過，同樣栽在發言引言上
    （逐字稿裡的人真的把亂碼念出來了），已經拿掉，不要加回來。
    """
    result = grade("glossary", GLOSSARY_FAILURES[mode])

    assert result == {"restores_term": False}


def test_every_unaddressed_phrase_is_long_enough_to_not_fire_by_accident():
    """`UNADDRESSED` 每一條至少 3 個字。

    剔掉的是 2 個字的 `未提`：實跑被「欄位順序若**未提前**與客戶對齊」配到，
    那句跟上週待辦無關，`marks_it_unaddressed` 假綠 —— 這個 case 於是對
    「待辦撈出來了卻沒標成沒提」整個失明，而分數看起來很漂亮。

    刪掉這條，往詞表裡加回一個短詞不會有任何東西變紅，假綠靜靜回來。
    """
    assert all(len(phrase) >= 3 for phrase in UNADDRESSED), UNADDRESSED


def test_an_unknown_case_raises_instead_of_grading_nothing():
    """case 名打錯要 `KeyError`，不是靜靜回一個空 dict。

    刪掉這條，`grade("glosary", note)` 回 `{}` 而 `passed({})` 一旦被寫成 `all([])`
    就是 True —— 一個 typo 靜靜地變成滿分，而且三份語料一份都沒判。
    """
    with pytest.raises(KeyError):
        grade("no-such-case", GOOD["glossary"])


def test_passed_says_no_to_an_empty_criteria_dict():
    """空 dict 算**不過**。

    `all([])` 是 True，所以這一條是刻意釘的：判準集合不小心變空
    （case 名打錯、判準表被清掉）時必須紅，不能靜靜滿分 ——
    一個打錯的 case 名就會變成滿分。

    `passed()` 的另外兩種形狀不在這裡：全真由 `test_a_note_that_read_the_history_passes`
    餵（`GOOD` 三份都是全真），一真一假由
    `test_breaking_one_thing_reds_exactly_one_criterion` 餵（那六份都斷言 `not passed`）。
    `grade()` 永遠不會回空 dict，所以只有這一種餵不到，要自己餵。
    """
    assert passed({}) is False


def test_cases_and_the_seeded_corpus_stay_in_lockstep():
    """`CASES` 與 `tests/eval/fixtures/` 底下的語料目錄要一一對得起來。

    兩邊各自看起來都對、卻對不上時沒有任何流程會報錯：種了語料卻沒進 `CASES`
    → 那份語料從來沒被判過，eval 照樣印滿分；`CASES` 有而語料沒有
    → run_eval 拿不到語料，失敗的原因會長得像 agent 的錯。

    刪掉這條，「少種一份語料」與「多一份沒人判的語料」都會變成無聲的 —— 通過率
    照印，分母卻不是你以為的那個。
    """
    assert set(CASES) == {p.name for p in FIXTURES.iterdir() if p.is_dir()}


def test_the_sample_wordings_are_still_in_the_tables():
    """樣本挑來用的那三個說法，必須真的還在詞表裡。

    樣本寫字面值是為了不被詞表重排靜靜改寫，代價是它跟詞表之間多了一條縫：
    詞表把 `推翻` 換成別的說法時，樣本還在用舊說法，於是「該綠時綠」那幾條
    會紅在一個跟判準邏輯無關的地方，訊息長得像判準壞了。

    刪掉這條，那種紅還是會發生，只是要花十分鐘才看得出來原因是詞表換過。
    """
    assert OVERRIDDEN in OVERRIDE
    assert CHANGED_TO in OVERRIDE
    assert NOT_MENTIONED in UNADDRESSED


def test_the_excused_layer_is_a_real_layout_contract_layer():
    """被豁免的層名要是版型契約裡真的有的層。

    判讀層與 `layout_contract` 各有一份層名，對不上時沒有任何流程會報錯 ——
    `DISCUSSION_LAYER` 打成 `討論過程`、或版型契約把層改名，豁免就對所有正式稿
    都不成立，`old_never_stands_alone` 悄悄退回嚴格版，實跑又會全紅在引言上。

    刪掉這條，那條縫沒有任何斷言看得見。
    """
    assert DISCUSSION_LAYER in LAYER_RANK


# --- 兩版 prompt 真的不一樣 -------------------------------------------------
# `run_eval.py` 進不了 CI，所以它組 prompt 的那幾支純函式跟判讀層一樣沒人守。
# 這裡不起子行程、不打網路 —— 只驗「餵給兩版 agent 的東西差在該差的地方」。


def _sources(tmp_path: Path) -> tuple[Path, Path]:
    """`build_prompt()` 會把檔案內容內嵌，所以要有真的檔。回 `(source_dir, index)`。"""
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    for name in ("transcript.md", "extract.md", "meeting-context.md"):
        (source_dir / name).write_text(f"# {name}\n", encoding="utf-8")
    index = tmp_path / "history-index.md"
    index.write_text("# 歷史索引\n\n* 2026-08-24｜本機: /x/y.md\n", encoding="utf-8")
    return source_dir, index


def _keys(handoff_text: str) -> set[str]:
    """交棒契約的 `RESULT_*` key 集合。"""
    return {line.split(":")[0] for line in handoff_text.splitlines()}


def test_only_the_after_arm_points_the_agent_at_a_history_index():
    """`after` 的流程 C 導言要提到索引，`before` 不能提 —— 這就是 eval 的自變數。

    `flow_c("after")` 讀的是**真的** `SKILL.md`，所以這條同時是「有人把索引那一列
    從流程 C 的來源表拿掉」的警報器（刻意的：eval 量的是現在出貨的那份）。

    刪掉這條，兩版導言變得一樣不會有任何東西變紅，eval 會老實地印出
    「改後沒有比較好」—— 那個結論讀起來像實驗結果，其實是實驗沒做。
    """
    assert "RESULT_HISTORY_INDEX" in flow_c("after")
    assert "RESULT_HISTORY_INDEX" not in flow_c("before")


@pytest.mark.parametrize("arm", ARMS, ids=list(ARMS))
def test_the_flow_c_intro_keeps_the_briefing_and_drops_the_publishing(arm: str):
    """導言要切在 Step 1 之前：交棒契約留著，發佈那段不能進 prompt。

    切點是「第一個 `### `」這個字面（`flow_c_intro()` 自己標了 ponytail），
    SKILL.md 動標題層級時它會往兩個方向壞，這條兩邊都擋：
    切太淺 → 建 Doc／發 Slack 的指示進了 prompt，eval 變成在測一份根本不該給的
    指示（而 `--permission-prompts none` 只擋得住執行，擋不住它污染輸出）；
    切過頭 → 導言整個被切光，兩版同時退化成空字串，18 跑全紅而沒人知道為什麼。

    刪掉這條，這兩種壞法都不會有顏色。
    """
    intro = flow_c(arm)

    assert intro.strip()
    assert "RESULT_TRANSCRIPT" in intro
    assert "create_gdoc_from_md" not in intro


def test_the_handoff_contract_differs_by_exactly_one_line(tmp_path: Path):
    """交棒契約兩版只能差在歷史那一列，其餘 `RESULT_*` key 一模一樣。

    自變數只有一個，實驗才成立。少給 `before` 一列別的（例如逐字稿路徑），
    `before` 會因為料不齊而答不出來，而那個紅會被讀成「舊版不會讀歷史」。

    刪掉這條，交棒契約多漏一列不會有任何東西變紅 —— eval 的對照組悄悄變成
    另一個實驗。
    """
    source_dir, index = _sources(tmp_path)

    without, with_index = handoff(source_dir, None), handoff(source_dir, index)

    assert "RESULT_HISTORY_INDEX" not in without
    assert "RESULT_HISTORY_INDEX" in with_index
    assert _keys(with_index) - _keys(without) == {"RESULT_HISTORY_INDEX"}
    assert _keys(without) - _keys(with_index) == set()


def test_the_handoff_prints_every_source_the_flow_c_table_names(tmp_path: Path):
    """流程 C 來源表點名的每一個 `RESULT_*`，`handoff()` 都要印得出來。

    方向是「**文件寫什麼 → runner 要印得出什麼**」，所以比對的 key 集合是從
    SKILL.md 的來源表解出來的（借 `test_history_handoff_contract.source_table_keys()`，
    不自己再刻一份）。這裡寫死一份 key 清單的話，文件改了名字時測試比對的是自己
    那份正確答案，照樣全綠 —— 跟那支存在的理由一模一樣。

    `RESULT_HISTORY_INDEX` 是唯一只有 `after` 印得出來的（那正是實驗的自變數），
    所以 `before` 那邊扣掉它再比。來源表裡還有一列 `references/default-prompt.md`
    不是契約 key，`RESULT_*` 的正則本來就撈不到它。

    上一條（`..._differs_by_exactly_one_line`）比的是兩版的**差集**，兩邊一起少同
    一個 key 差集不變 —— 所以它看不見「`RESULT_TRANSCRIPT` 那行被整行刪掉」。
    刪掉這條，那個壞法就零測試變紅：子 agent 拿不到主事實來源，兩版一起爛掉，
    而結果讀起來像「這個 skill 不會寫記錄」，不像「eval 壞了」。
    """
    source_dir, index = _sources(tmp_path)
    required = source_table_keys()
    history = history_key()

    assert required - {history} <= _keys(handoff(source_dir, None))
    assert required <= _keys(handoff(source_dir, index))


def test_the_two_arms_are_not_the_same_prompt(tmp_path: Path):
    """整份 prompt 兩版必須不同，而且差別就在歷史上。

    這是「兩版被做成同一份 prompt」的警報器 —— `arm` 沒接上、索引忘了傳、
    `flow_c()` 兩版回一樣的東西，任何一種都會讓 18 跑量到同一件事。
    那種壞法印出來的是「改後沒效果」，讀起來像結論而不像 bug，
    沒有這條就沒有任何東西會反駁它。
    """
    source_dir, index = _sources(tmp_path)

    before = build_prompt("before", source_dir, None)
    after = build_prompt("after", source_dir, index)

    assert before != after
    assert "RESULT_HISTORY_INDEX" not in before and index.name not in before
    assert "RESULT_HISTORY_INDEX" in after and index.name in after
