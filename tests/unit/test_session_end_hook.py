#!/usr/bin/env python3
"""SessionEnd hook adapter 的單元測試。

分類器每次跑完的結果只留在這支 hook 寫的 classifier.log 裡 —— 2026-09-16 之前它根本
不落地，跑完就沒了。所以這裡釘的是「寫下來而且留得住」：每跑一次都往後接、行首有時間戳、
目錄不存在時自己建，而且 stderr 也要一起收進來。一次執行落幾行由分類器印了幾股決定：
session_classifier.py:262 的 validate-gap 錯誤走 stderr、成功報告走 stdout，這種
一次兩行（第二行不帶時間戳）正是 `2>&1` 要接住的形狀。

hook 的 log 路徑是相對它自己算的（`$(dirname)/..`），直接跑 repo 裡那份會把 log 寫進
repo，所以測試把**真的那個檔案**複製進 temp 樹，classifier 換成兩股都印的 stub。
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "skills/skill-evolution/improve/scripts"
HOOK = SCRIPTS / "hooks/claude-session-end.sh"

STUB_CLASSIFIER = """import sys
payload = sys.stdin.read().strip()
print("classified:" + payload)                  # 成功路徑：session_classifier.py:400
print("crashed:" + payload, file=sys.stderr)    # 出事路徑：:409 catch-all，印完 exit 0
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

    def test_both_streams_of_every_run_land_in_the_log_instead_of_replacing_the_last_one(self) -> None:
        # memory/ 這時還不存在：hook 在 set -e 底下跑，少了 mkdir -p 就是重導向失敗、整支
        # hook 非零退出 —— 第一次安裝的機器上分類器等於完全不會留下紀錄。
        self.assertFalse(self.log.parent.exists())
        self.run_hook('{"session_id":"first"}')
        self.run_hook('{"session_id":"second"}')

        text = self.log.read_text()
        lines = text.splitlines()
        # 一次執行兩行：stderr 的診斷加 stdout 的報告。少了 `2>&1`，分類器最有價值的輸出
        # （catch-all、validate-gap 錯誤）整個消失；而 `printf '%s '` 不帶換行是刻意的，
        # 時間戳要黏在同一行行首，換成 '%s\n' 行數就會多出來。
        self.assertEqual(len(lines), 4)
        # 第一次的結果還在：`>` 而不是 `>>` 的話只剩最後一次，而「上一個 session 發生什麼」
        # 正是這支 log 唯一的用途。兩股誰先落地不斷言：stdout 對檔案是 block-buffered、
        # 退出才 flush，順序是 buffering 的副產物，不是契約。
        for payload in ('{"session_id":"first"}', '{"session_id":"second"}'):
            self.assertIn("classified:" + payload, text)
            self.assertIn("crashed:" + payload, text)
        self.assertRegex(lines[0], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


if __name__ == "__main__":
    unittest.main()
