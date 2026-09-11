"""議題版型檢查器 —— 吃一份會議記錄 Markdown，回報它符不符合版型契約。

Seam ④「正式稿 Markdown」是這條 pipeline 唯一外部可觀察的東西。prompt 的文字不是
契約，**產出的 Markdown 才是**，所以斷言全部掛在這裡，不去讀 prompt 一個字。

契約（每個 `### 議題` 區塊）：

    ### 議題N：<標題>
    **TL;DR** — <一句話>            必出現，緊接 H3
    #### 議題因果鏈[ · 承 M/D → M/D]  選填，與 #### 討論 同階（前後皆可）
    #### 討論                        必出現
    #### 決策理由                    選填
    #### 狀態                        必出現，每條 bullet 以 inline code 標記開頭
    #### 風險                        選填

選填層沒內容時整層不輸出，不得出現空 H4 或「無」「N/A」填充。
除 `#### 議題因果鏈` 的 ` · 承 M/D → M/D` 之外，層標題不得加後綴，同名層不得重複。

純函式，str in → dict out。不建 markdown parser，行掃描 ＋ 正規表示式就夠。
"""

from __future__ import annotations

import re
from collections import Counter
from itertools import groupby

# 層名與相對順序的唯一來源。因果鏈與討論同階：8/31 目標樣本的議題三是「因果鏈 → 討論」、
# 議題六是「討論 → 因果鏈」，兩種都是權威樣本自己的輸出。收斂到「因果鏈不得晚於決策理由」。
LAYER_RANK = {"議題因果鏈": 0, "討論": 0, "決策理由": 1, "狀態": 2, "風險": 3}
REQUIRED_LAYERS = ("討論", "狀態")
STATUS_VALUES = ("已確認", "執行中", "待驗證", "待確認", "待啟動", "腦力激盪")

_ISSUE_RE = re.compile(r"^###\s*議題")
_H4_RE = re.compile(r"^####\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*[*-]\s+(.*)$")
_STATUS_BULLET_RE = re.compile(r"^\s*[*-]\s+`([^`]+)`\s*\S")
_FILLER = {"無", "N/A"}


def _layer_name(heading: str) -> str:
    """`議題因果鏈 · 承 8/20 → 8/24` → `議題因果鏈`。"""
    return heading.split(" · ")[0].strip()


def count_tables(lines: list[str]) -> int:
    """連續的 `|` 開頭行算一個表格。"""
    return sum(k for k, _ in groupby(ln.lstrip().startswith("|") for ln in lines))


def _issue_spans(lines: list[str]) -> list[tuple[int, int, str]]:
    """(start, end, title)，end 為下一個 `### ` 或 `## ` 之前。"""
    starts = [i for i, ln in enumerate(lines) if _ISSUE_RE.match(ln)]
    spans = []
    for i, s in enumerate(starts):
        end = len(lines)
        for j in range(s + 1, len(lines)):
            if lines[j].startswith("### ") or lines[j].startswith("## "):
                end = j
                break
        spans.append((s, end, lines[s].lstrip("# ").strip()))
    return spans


def _check_issue(lines: list[str], s: int, e: int, title: str) -> list[str]:
    v: list[str] = []
    body = lines[s + 1 : e]

    # R1 TL;DR 必出現且緊接 H3
    first = next((ln for ln in body if ln.strip()), "")
    if not first.strip().startswith("**TL;DR**"):
        v.append(f"{title}：TL;DR 未緊接 H3（實際第一行：{first.strip()[:24]!r}）")

    h4s = [(i, _H4_RE.match(ln).group(1)) for i, ln in enumerate(body) if _H4_RE.match(ln)]
    names = [_layer_name(h) for _, h in h4s]

    # R3 層名白名單
    for raw, name in zip((h for _, h in h4s), names):
        if name not in LAYER_RANK:
            v.append(f"{title}：自創層名 `{raw}`")

    # R2 必出現層
    for req in REQUIRED_LAYERS:
        if req not in names:
            v.append(f"{title}：缺 `#### {req}`")

    # R3b 同一議題不得出現兩個同名層（禁掉後綴之後，模型的下一個出口就是直接重複）
    for name, n in Counter(names).items():
        if name in LAYER_RANK and n > 1:
            v.append(f"{title}：`#### {name}` 在同一議題出現 {n} 次")

    # R4 相對順序
    seen = [n for n in names if n in LAYER_RANK]
    rank = [LAYER_RANK[n] for n in seen]
    if rank != sorted(rank):
        v.append(f"{title}：層順序錯亂 {seen}")

    for k, (i, raw) in enumerate(h4s):
        name = _layer_name(raw)
        stop = h4s[k + 1][0] if k + 1 < len(h4s) else len(body)
        content = [ln for ln in body[i + 1 : stop] if ln.strip()]

        # R5 空層／填充層
        if not content or all(ln.strip() in _FILLER for ln in content):
            v.append(f"{title}：`#### {raw}` 是空層或填充層")

        # R6 狀態層的 bullet 一律 inline code 標記開頭，值在值域內
        if name == "狀態":
            for ln in content:
                if not _BULLET_RE.match(ln):
                    continue
                m = _STATUS_BULLET_RE.match(ln)
                if not m:
                    v.append(f"{title}：狀態 bullet 未用 inline code 標記：{ln.strip()[:30]!r}")
                elif m.group(1) not in STATUS_VALUES:
                    v.append(f"{title}：狀態標記 `{m.group(1)}` 不在值域內")

        # R8 表格不得落在 狀態／風險 底下
        if name in ("狀態", "風險") and count_tables(body[i + 1 : stop]):
            v.append(f"{title}：`#### {raw}` 底下出現表格")

    return v


def check_layout(md: str) -> dict:
    """str in → dict out。`ok` 為 True 代表符合版型契約。"""
    lines = md.replace("\r\n", "\n").split("\n")
    spans = _issue_spans(lines)

    violations: list[str] = []

    # R0 沒有任何 `### 議題` 就不是這個版型
    if not spans:
        violations.append("整份文件沒有任何 `### 議題` 區塊")

    for s, e, title in spans:
        violations += _check_issue(lines, s, e, title)

    # R7 inline code 狀態標記不得外溢到議題以外（核心要點／行動項目維持方括號與純文字）
    marks = [
        i
        for i, ln in enumerate(lines)
        for m in [_STATUS_BULLET_RE.match(ln)]
        if m and m.group(1) in STATUS_VALUES
    ]
    inside = {i for s, e, _ in spans for i in range(s, e)}
    violations += [
        f"第 {i + 1} 行：inline code 狀態標記外溢到議題區塊之外" for i in marks if i not in inside
    ]

    return {
        "ok": not violations,
        "violations": violations,
        "counts": {
            "issues": len(spans),
            "h4": sum(1 for ln in lines if _H4_RE.match(ln)),
            "inline_status": len(marks),
            "tables": count_tables(lines),
        },
    }
