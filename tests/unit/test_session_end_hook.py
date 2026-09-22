#!/usr/bin/env python3
"""SessionEnd hook adapter 的單元測試。

分類器每次跑完的結果只留在這支 hook 寫的 classifier.log 裡 —— 2026-09-16 之前它根本
不落地，跑完就沒了。所以這裡釘的是「寫下來而且留得住」：每跑一次多一行、行首有時間戳、
目錄不存在時自己建。

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


class SessionEndHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        scripts = self.root / "scripts"
        (scripts / "hooks").mkdir(parents=True)
        self.hook = scripts / "hooks" / HOOK.name
        shutil.copy(HOOK, self.hook)
        (scripts / "session_classifier.py").write_text(STUB_CLASSIFIER)
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
        return [line for line in self.log.read_text().splitlines() if line.strip()]

    def test_each_run_appends_a_timestamped_line_instead_of_replacing_the_last_one(self) -> None:
        self.run_hook('{"session_id":"first"}')
        self.run_hook('{"session_id":"second"}')

        lines = self.log_lines()
        self.assertEqual(len(lines), 2)
        # 第一次的結果還在：`>` 而不是 `>>` 的話只剩最後一次，而「上一個 session 發生什麼」
        # 正是這支 log 唯一的用途。
        self.assertIn('classified:{"session_id":"first"}', lines[0])
        self.assertIn('classified:{"session_id":"second"}', lines[1])
        for line in lines:
            self.assertRegex(line, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    def test_the_log_directory_is_created_when_it_is_missing(self) -> None:
        # hook 在 set -e 底下跑，memory/ 不存在時少了 mkdir -p 就是重導向失敗、整支 hook 非零
        # 退出 —— 第一次安裝的機器上分類器等於完全不會留下紀錄。
        self.assertFalse(self.log.parent.exists())
        self.run_hook('{"session_id":"fresh-install"}')
        self.assertEqual(len(self.log_lines()), 1)


if __name__ == "__main__":
    unittest.main()
