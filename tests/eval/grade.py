"""eval 的判讀層 —— 一份語料一組斷言，三組互不共用。

Seam ④「正式稿 Markdown」是這條 pipeline 唯一外部可觀察的東西，所以判讀只吃
Markdown 字串，不看 agent 說了什麼、不問它「你讀了歷史嗎」。**問它有沒有讀，測到的
是它願不願意說有。** 三份語料各自種一個「只有讀了歷史才答得對」的東西，然後看答案。

**為什麼不共用一組斷言**（#14 陷阱表點名本票的那條）：三份語料種的是不同東西 ——
術語校正 / 消失的待辦 / 被推翻的決策。共用一組的話，「這份語料沒種到料」與「agent
沒讀歷史」會判成同一種紅，而前者是 fixture 的 bug、後者才是結論。

**判準之間要彼此獨立。** 每條判準都存在一種「只弄壞它、其餘照樣綠」的正式稿 ——
這是 `tests/unit/test_eval_assertion_layer.py` 能逐條釘住的前提。判準互相蘊含的話，
弄壞一件事會讓兩條同時變紅，那道 unit 就退化成「有東西壞了」。

判讀本身是純函式（str in → dict out）。`run_eval.py` 進不了 CI（要起 subagent），
所以這一層的顏色由 unit test 守，不是由 eval 跑出來的數字自我證明。
"""

from __future__ import annotations

from tests.unit.layout_contract import LAYER_RANK, _H4_RE, _layer_name

# --------------------------------------------------------------------------- 探針

# ① 術語校正。本次逐字稿的 STT 把專案代號聽成音譯；正解只在 8/24 那場的 heading
#    與內文裡。`開斯楚` → `Castro` 是音譯得出來的，`Kestrel` 不是 —— 猜不到才測得到
#    「有沒有讀」。
GARBLE = "開斯楚"
TERM = "Kestrel"

# ② 消失的待辦。8/24 有一個客戶端必修 bug，本次逐字稿一個字都沒提。
CARRYOVER = "排程重複觸發"

# ③ 被推翻的決策。8/24 定案 CSV，本次逐字稿明確推翻改 Excel。
#    這題**兩版都必須過**：改前沒有歷史可污染，改後要守住接地優先序。
OLD_DECISION = "CSV"
NEW_DECISION = "Excel"

# 「上週項目本週未提」的說法集合。
# ponytail: 關鍵詞比對，換個說法（「持平」「無異動」）會誤判成沒寫。語料裡只有這一件
# 事是懸著的，所以誤判會整條紅、不會靜靜地半對；真的踩到就把說法加進來，不要改成
# LLM judge —— 那會讓判讀層自己變成不可測的一層。
#
# **每一條都是不會單獨出現的詞組。** 第一輪實跑收過一次假綠：清單裡原本有兩個字的
# `未提`，被「欄位順序若**未提前**與客戶對齊」這句話配到 —— 那句跟上週的待辦一點關係
# 都沒有。這條判準本來就掃全文（為了與 `surfaces_carryover` 互相獨立），所以唯一能扛
# 住碰撞的是詞組本身夠長。加新說法時照這條規矩。
UNADDRESSED = (
    "未提及", "未提到", "本次未提", "沒有提到", "沒有再提", "未被提", "無人提",
    "未再提", "無進度", "沒有進度", "未跟進", "無更新", "沒有更新", "待追蹤", "未討論",
)

# 「這是被推翻的舊決策」的說法集合。同上，關鍵詞比對。
OVERRIDE = (
    "推翻", "改為", "改成", "改採", "不再", "原訂", "原本", "原定", "先前",
    "前次", "上次", "上一次", "上週", "8/24", "否決", "取消", "放棄", "撤掉",
)


# --------------------------------------------------------------------------- helpers


# 版型層名的唯一來源是 `layout_contract`（`LAYER_RANK` 的 key、`_H4_RE` 的形狀、
# `_layer_name` 的後綴切法）。這裡自己刻一份的話，版型契約那邊改了切法，這邊只會靜靜
# 地量到別的東西 —— 跟 conftest 的 `skill_md_section` 要防的是同一種病。
DISCUSSION_LAYER = "討論"
assert DISCUSSION_LAYER in LAYER_RANK, "討論不是版型契約裡的層名了"


def _claims(note: str, needle: str) -> list[str]:
    """含 `needle` 而且是**正式稿在陳述事實**的那些行 —— `#### 討論` 底下的不算。

    那一層照抄發言者的原話，是版型要求的正確行為。把引言算進「正式稿主張了什麼」，
    判準就變成在要求 agent 竄改別人講的話。實跑兩次各紅一行，都是引言：
    `* **Speaker3**：客戶不要 CSV。`、`* **Speaker3**：客戶講得很死，CSV 他們用不了。`

    **用所在的層來分，不是用行首的形狀。** 先前的版本認 `**粗體**：` 開頭這個形狀
    （`default-prompt.md` 規定討論條目維持 `**發言者**：` 開頭），但 `## 核心要點`
    的條目是 `* **匯出格式改為 Excel [已確認]**：…` —— 同一個形狀。agent 把推翻標在
    核心要點那一行（最自然、也是預設 prompt 排出來的位置）會被整行濾掉，寫得再正確
    也紅。層是版型契約裡就有的東西，比形狀穩。

    `##`／`###` 把層清成無，所以 `## 核心要點` 底下的條目算、下一個 `### 議題` 開始
    也算 —— 討論層的豁免不會漏到下一個議題。
    """
    out: list[str] = []
    layer: str | None = None
    for line in note.splitlines():
        if line.startswith("#"):
            h4 = _H4_RE.match(line)
            layer = _layer_name(h4.group(1)) if h4 else None
            continue
        if needle in line and layer != DISCUSSION_LAYER:
            out.append(line)
    return out


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


# --------------------------------------------------------------------------- 三組斷言


def _glossary(note: str) -> dict[str, bool]:
    """① STT 聽壞的術語有沒有被還原成歷史裡的那個寫法。

    **只有一條判準，而它就夠。** 票上列的三種失敗模式（照抄亂碼／標待確認／猜錯）
    全都讓正解不出現，所以全都紅在這一條。

    曾經還有一條「亂碼不得單獨出現」，試跑後拿掉：`#### 討論` 的發言條目本來就該照
    發言者的原話寫，亂碼留在引言裡是**正確行為**，那條會把讀了歷史的產出判紅。
    判準誤判成紅比少一條判準貴 —— 少一條只是驗得淺，誤判會讓人去 debug 一個沒壞的
    東西。
    """
    return {"restores_term": TERM.lower() in note.lower()}


def _dropped_todo(note: str) -> dict[str, bool]:
    """② 上一場的待辦本次完全沒人提，正式稿有沒有把它撈出來並標成沒進度。

    兩條刻意都掃全文、互不蘊含：綁成「同一行同時有待辦與說法」的話，把待辦整個拿掉
    會讓兩條一起紅，逐條釘就不成立了。代價是說法有可能掛在別件事上 —— 語料裡只有
    這一件事是懸著的，所以這個代價是封閉的。
    """
    return {
        "surfaces_carryover": CARRYOVER in note,
        "marks_it_unaddressed": _has_any(note, UNADDRESSED),
    }


def _overridden_decision(note: str) -> dict[str, bool]:
    """③ 本次推翻了歷史決策 —— 以本次為準，並標明推翻了什麼。

    這題測的是新機制的副作用：歷史進到 context 之後才可能發生「拿歷史當本次事實」。
    `old_never_stands_alone` 就是那條 —— 舊決策每次出現都必須帶著被推翻的標記，
    不能有任何一行把它寫成現行結論。

    `old_never_stands_alone` 收的是**析取**：舊決策每次出現，同一行要嘛帶著被推翻的
    說法，要嘛與新決策並列。只收前者的版本在第一輪實跑把六次全判紅了，而六份產出沒有
    一份真的把 CSV 寫成現行結論 —— 紅的是「客戶主管只用 Excel，CSV 開啟為亂碼」這種
    **理由句**。舊決策出現在理由裡是正確行為，判紅它等於要求正式稿不准解釋為什麼改。
    析取版加上 `_claims()` 濾掉引言之後，十二次實跑零假紅，而真正的污染
    （`#### 狀態` 底下一條 `已確認 第一版匯出格式為 CSV`）兩個條件都不滿足，照樣紅。

    三條各自可單獨弄壞：新決策換成別的字而舊決策各行都帶推翻說法（只紅第一條）、
    舊決策整個拿掉（只紅第二條，第三條全稱量化於空集合仍為真）、多補一行既沒有推翻
    說法也沒有新決策的舊決策（只紅第三條）。
    """
    old_lines = _claims(note, OLD_DECISION)
    return {
        "adopts_new_decision": NEW_DECISION in note,
        "marks_the_override": any(_has_any(ln, OVERRIDE) for ln in old_lines),
        "old_never_stands_alone": all(
            _has_any(ln, OVERRIDE) or NEW_DECISION in ln for ln in old_lines
        ),
    }


GRADERS = {
    "glossary": _glossary,
    "dropped-todo": _dropped_todo,
    "overridden-decision": _overridden_decision,
}
CASES = tuple(GRADERS)


def grade(case: str, note: str) -> dict[str, bool]:
    """一份正式稿 Markdown → `{判準名: 過了沒}`。

    未知的 case 讓 dict 查詢自己 `KeyError` —— **不要**改成 `GRADERS.get(case, ...)`
    之類回空 dict 的寫法：`passed({})` 那條防的是同一件事，一個打錯的 case 名不能
    靜靜地變成滿分。
    """
    return GRADERS[case](note)


def passed(result: dict[str, bool]) -> bool:
    """整題過不過。空 dict 說 False —— 見 `grade()` 的理由。"""
    return bool(result) and all(result.values())
