#!/usr/bin/env python3
"""Audit monospace diagrams for alignment.

The point of this script is the one thing a model cannot eyeball: display width.
`中` occupies two terminal columns but `len()` reports one, so a diagram whose
labels mix CJK and ASCII looks aligned in the model's head and ragged on screen.

Usage:  verify.py -            read stdin — the common case, no file needed
        verify.py <file>...    for a diagram you'll keep editing
Exit 0 = clean, 1 = findings.
"""

import sys
import unicodedata

# Box-drawing glyphs that can legitimately sit on a vertical edge.
EDGE = set("│├┤┼┬┴┌┐└┘╭╮╰╯")
HEAVY = EDGE | set("─")
MAX_COLS = 80


def char_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def to_grid(line: str) -> tuple[dict[int, str], int]:
    """Map display column -> char, the way a terminal actually lays the line out."""
    grid, col = {}, 0
    for ch in line:
        grid[col] = ch
        col += char_width(ch)
    return grid, col


def blocks(lines: list[str]) -> list[tuple[int, list[str]]]:
    """Maximal runs of consecutive lines containing box glyphs, with 1-based start.

    A run of one is prose that happens to name a glyph, not a diagram, so it is
    dropped — otherwise every sentence mentioning `│` gets audited.
    """
    out, cur, start = [], [], 0
    for i, line in enumerate(lines, 1):
        if any(ch in HEAVY for ch in line):
            if not cur:
                start = i
            cur.append(line)
        elif cur:
            if len(cur) > 1:
                out.append((start, cur))
            cur = []
    if len(cur) > 1:
        out.append((start, cur))
    return out


def ascii_box_lines(block: list[str]) -> int:
    """Lines that look like an ASCII-style box border (+---+), for mix detection."""
    n = 0
    for line in block:
        s = line.strip()
        if s.startswith("+") and s.endswith("+") and set(s) <= set("+-"):
            n += 1
    return n


def check_block(start: int, block: list[str], report) -> None:
    grids = [to_grid(l) for l in block]

    for offset, (grid, total) in enumerate(grids):
        if total > MAX_COLS:
            report(start + offset, f"行寬 {total} 欄，超過 {MAX_COLS}（終端會折行）")

    if ascii_box_lines(block) and any(ch in HEAVY for l in block for ch in l):
        report(start, "同一張圖混用 ┌─┐ 與 +---+ 兩套框線字元")

    # Box runs: a ┌…┐ row opens one, the matching └…┘ row closes it. Every row in
    # between must carry an edge glyph at both columns, or the box has a hole /
    # the right edge has drifted — which is what CJK width does to a diagram.
    open_rows: list[tuple[int, int, int]] = []  # (row index, left col, right col)
    for i, (grid, _) in enumerate(grids):
        left = right = None
        for col in sorted(grid):
            if grid[col] in "┌╭":
                left = col if left is None else left
            if grid[col] in "┐╮":
                right = col
        if left is not None and right is not None and right > left:
            open_rows.append((i, left, right))

    for i, left, right in open_rows:
        close = None
        for j in range(i + 1, len(grids)):
            grid = grids[j][0]
            if grid.get(left) in ("└", "╰") and grid.get(right) in ("┘", "╯"):
                close = j
                break
            if grid.get(left) in ("└", "╰") or grid.get(right) in ("┘", "╯"):
                got_l = grid.get(left, " ")
                got_r = grid.get(right, " ")
                report(
                    start + j,
                    f"下框線沒對齊上框線：期望 └ 在第 {left} 欄、┘ 在第 {right} 欄，"
                    f"實得 {got_l!r} 與 {got_r!r}",
                )
                close = j
                break
        if close is None:
            continue
        # Collect per side so one drifted box is one finding, not one per row.
        for col, side in ((left, "左"), (right, "右")):
            drift: dict[int, list[int]] = {}
            for j in range(i + 1, close):
                grid, total = grids[j]
                if grid.get(col) in EDGE:
                    continue
                actual = next(
                    (c for c in sorted(grid, reverse=True) if grid[c] in EDGE), total
                )
                drift.setdefault(actual, []).append(start + j)
            for actual, rows in drift.items():
                where = ", ".join(map(str, rows))
                delta = actual - col
                shift = f"往{'右' if delta > 0 else '左'}移 {abs(delta)} 欄" if delta else "缺框線"
                report(
                    start + i,
                    f"{side}框線該在第 {col} 欄，第 {where} 行落在第 {actual} 欄（{shift}）",
                )


def verify(name: str, text: str) -> int:
    findings = []

    def report(line_no: int, msg: str) -> None:
        findings.append(f"{name}:{line_no}: {msg}")

    for start, block in blocks(text.splitlines()):
        check_block(start, block, report)

    for f in findings:
        print(f)
    return len(findings)


def main(argv: list[str]) -> int:
    targets = argv[1:] or ["-"]
    total = 0
    for t in targets:
        if t == "-":
            total += verify("<stdin>", sys.stdin.read())
        else:
            with open(t, encoding="utf-8") as fh:
                total += verify(t, fh.read())
    if total:
        print(f"\n{total} 處對齊問題", file=sys.stderr)
        return 1
    print("對齊無問題")
    return 0


def _selftest() -> None:
    good = "┌────────┐\n│ 中文   │\n└────────┘"
    assert verify("t", good) == 0, "等寬中文的正確圖不該被判紅"

    # `中文` is 4 columns, not 2 — counting characters puts ┐ two columns early.
    bad = "┌────────┐\n│ 中文     │\n└────────┘"
    assert verify("t", bad) > 0, "右框線飄移應該被抓到"

    hole = "┌────────┐\n  中文    │\n└────────┘"
    assert verify("t", hole) > 0, "框線斷掉應該被抓到"

    assert char_width("中") == 2 and char_width("a") == 1
    print("selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        _selftest()
    else:
        sys.exit(main(sys.argv))
