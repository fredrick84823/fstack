"""unit / integration 分家的機制本身。

驗收條件是「integration 在 CI 一律 skip」，而執行它的兩層都在 pytest 的收集階段 ——
`setup.cfg` 的 `testpaths`、`tests/integration/conftest.py` 的
`pytest_collection_modifyitems`。跑在 `tests/unit` 裡的測試碰不到那兩層：預設那一輪
根本不會收集 `tests/integration`，於是分家壞掉時沒有任何一條會紅。

所以這裡開子行程跑 pytest。marker 那三條打在**複製出來的迷你樹**上，不打真的
`tests/integration` —— 真的那支還有一層「本機沒安裝版就 skip」，用它斷言會變成
一條由環境決定顏色的測試，正是這個目錄要擋的東西。`testpaths` 那條沒得選，
它量的就是這個 repo 的設定。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_CONFTEST = ROOT / "tests" / "integration" / "conftest.py"
PROBE = "def test_probe():\n    pass\n"


def _pytest(*args: str, cwd: Path, ci: bool = False) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTEST_ADDOPTS": ""}
    env.pop("CI", None)
    if ci:
        env["CI"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-rs", "-q", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """迷你樹：一個 integration 目錄（掛真的 conftest）＋ 一個目錄外的 case。

    目錄外那個是 `pytest_collection_modifyitems` 拿到的 `items` 是**整場**收集結果、
    不是本目錄的證據 —— 少了目錄過濾，它會連目錄外的 case 一起標成 integration。
    """
    integration = tmp_path / "integration"
    integration.mkdir()
    shutil.copy2(INTEGRATION_CONFTEST, integration / "conftest.py")
    (integration / "test_inside.py").write_text(PROBE)

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "test_outside.py").write_text(PROBE)
    return tmp_path


def test_the_integration_directory_gets_the_marker_without_declaring_it(tree: Path):
    """marker 掛在目錄上而不是逐檔宣告：漏掛的檔案不會有人發現。"""
    selected = _pytest(".", "-m", "integration", "--collect-only", cwd=tree)

    assert "integration/test_inside.py::test_probe" in selected.stdout
    assert "outside/test_outside.py::test_probe" not in selected.stdout


def test_cases_outside_the_directory_keep_their_marker_alone(tree: Path):
    """`-m "not integration"` 必須還選得到目錄外的 case。

    不過濾目錄就會把全部標成 integration，症狀是這一輪把**全部** deselect 掉 ——
    看起來像「一個測試都沒有」而不是像錯誤。
    """
    rest = _pytest(".", "-m", "not integration", "--collect-only", cwd=tree)

    assert "outside/test_outside.py::test_probe" in rest.stdout
    assert "integration/test_inside.py::test_probe" not in rest.stdout


def test_ci_skips_the_integration_directory_and_nothing_else(tree: Path):
    """CI 上明示路徑也不能真的跑起來 —— 少了這層，多打一個路徑就會執行吃本機
    安裝版／真實外部服務的測試，顏色由環境決定。"""
    on_ci = _pytest(".", cwd=tree, ci=True)
    off_ci = _pytest(".", cwd=tree, ci=False)

    assert "1 passed" in on_ci.stdout and "1 skipped" in on_ci.stdout
    assert "CI 一律 skip" in on_ci.stdout
    assert "2 passed" in off_ci.stdout


def test_the_default_run_does_not_collect_integration_at_all():
    """第一層：`testpaths` 讓不帶路徑的 `pytest` 收不到 tests/integration。"""
    collected = _pytest("--collect-only", cwd=ROOT)

    assert "tests/unit/" in collected.stdout
    assert "tests/integration/" not in collected.stdout
