#!/usr/bin/env python3
"""CRAP = comp^2 * (1-cov)^3 + comp，逐函式。吃 `radon cc -j` 與 `coverage json` 的輸出。

用法：`make crap`（那個 target 會先把這兩份 json 產出來）。
高複雜度 ＋ 低覆蓋率的函式排最前面 —— 兩者只有一個高不算 crappy，乘起來才算。
"""

import json
import sys

RED = 30

cc = json.load(open(sys.argv[1]))
cov = {
    path: (set(d["executed_lines"]), set(d["missing_lines"]))
    for path, d in json.load(open(sys.argv[2]))["files"].items()
}

rows = []
for path, blocks in cc.items():
    executed, missing = cov.get(path, (set(), set()))
    for b in blocks:
        if b["type"] == "class":  # class 的 CC 是底下 method 的總和，會重複計數
            continue
        span = set(range(b["lineno"], b["endline"] + 1))
        hit, miss = len(executed & span), len(missing & span)
        ratio = hit / (hit + miss) if hit + miss else 1.0
        c = b["complexity"]
        rows.append((c**2 * (1 - ratio) ** 3 + c, path, b["name"], b["lineno"], c, ratio))

rows.sort(reverse=True)
print(f"{'CRAP':>7}  {'CC':>3}  {'COV':>6}  LOCATION")
for crap, path, name, lineno, c, ratio in rows:
    flag = f"  <-- RED (>{RED})" if crap > RED else ""
    print(f"{crap:7.1f}  {c:3d}  {ratio * 100:5.1f}%  {path}:{lineno} {name}{flag}")
print(f"\nfunctions: {len(rows)}, CRAP>{RED}: {sum(1 for r in rows if r[0] > RED)}")
