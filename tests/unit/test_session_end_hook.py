#!/usr/bin/env python3
"""SessionEnd hook adapter 的單元測試。

分類器每次跑完的結果只留在這支 hook 寫的 classifier.log 裡 —— 2026-09-16 之前它根本
不落地，跑完就沒了。所以這裡釘的是「寫下來而且留得住」：每跑一次多一行、行首有時間戳、
目錄不存在時自己建，而且 stderr 也要一起收進來。

hook 的 log 路徑是相對它自己算的（`$(dirname)/..`），直接跑 repo 裡那份會把 log 寫進
repo，所以測試把**真的那個檔案**複製進 temp 樹，classifier 換成印得出可辨識輸出的 stub。
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


HOOK = Path(__file__).resolve().parents[2] / (
    "skills/skill-evolution/improve/scripts/hooks/claude-session-end.sh"
)

STUB_CLASSIFIER = """import sys
print("classified:" + sys.stdin.read().strip())
"""

# 真正的分類器出事時只會留下 stderr：catch-all（session_classifier.py:409）印完就
# `sys.exit(0)`，stdout 一個字也沒有。這支 stub 模擬的就是那條路。
STUB_CLASSIFIER_CRASHES = """import sys
print("session_classifier: RuntimeError: " + sys.stdin.read().strip(), file=sys.stderr)
"""


class SessionEndHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        scripts = self.root / "scripts"
        (scripts / "hooks").mkdir(parents=True)
        self.hook = scripts / "hooks" / HOOK.name
        shutil.copy(HOOK, self.hook)
        self.classifier = scripts / "session_classifier.py"
        self.classifier.write_text(STUB_CLASSIFIER)
        self.log = self.root / "memory" / "classifier.log"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_hook(self, payload: str) -> None:
        subprocess.run(
            ["bash", str(self.hook)],
            input=payload,
            text=True,
            capture_output=True,
            check=True,
        )

    def log_lines(self) -> list[str]:
        return self.log.read_text().splitlines()

    def test_each_run_appends_a_timestamped_line_instead_of_replacing_the_last_one(self) -> None:
        # memory/ 這時還不存在：hook 在 set -e 底下跑，少了 mkdir -p 就是重導向失敗、整支
        # hook 非零退出 —— 第一次安裝的機器上分類器等於完全不會留下紀錄。
        self.assertFalse(self.log.parent.exists())
        self.run_hook('{"session_id":"first"}')
        self.run_hook('{"session_id":"second"}')

        lines = self.log_lines()
        self.assertEqual(len(lines), 2)
        # 第一次的結果還在：`>` 而不是 `>>` 的話只剩最後一次，而「上一個 session 發生什麼」
        # 正是這支 log 唯一的用途。
        self.assertIn('classified:{"session_id":"first"}', lines[0])
        self.assertIn('classified:{"session_id":"second"}', lines[1])
        self.assertRegex(lines[0], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    def test_a_classifier_that_only_writes_stderr_still_lands_in_the_log(self) -> None:
        # 分類器最有價值的輸出全走 stderr（catch-all、validate-gap 錯誤），而且它出事時
        # 是印完 stderr 就 exit 0 —— 少了 `2>&1`，這行診斷整個消失。更糟的是 hook 的
        # `printf '%s '` 不帶換行，兩次這種執行會黏成一行，log 行數還會無聲少算。
        self.classifier.write_text(STUB_CLASSIFIER_CRASHES)
        self.run_hook('{"session_id":"boom-first"}')
        self.run_hook('{"session_id":"boom-second"}')

        lines = self.log_lines()
        self.assertEqual(len(lines), 2)
        self.assertIn('session_classifier: RuntimeError: {"session_id":"boom-first"}', lines[0])
        self.assertIn('session_classifier: RuntimeError: {"session_id":"boom-second"}', lines[1])


if __name__ == "__main__":
    unittest.main()
