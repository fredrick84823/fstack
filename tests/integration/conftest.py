"""`tests/integration` 的分界機制：本目錄底下的 case 整包掛 `integration` marker，
CI 上整包 skip。

分家有兩層 —— `setup.cfg` 的 `testpaths` 讓預設 `pytest` 收不到這裡，本檔的 `CI` 判斷
讓明示 `pytest tests/integration` 在 CI 上也不會真的跑。少了第二層，CI 只要有人多打一個
路徑就會執行吃本機安裝版／真實外部服務的測試，顏色由環境決定。

marker 自動掛在目錄上而不是逐檔宣告：漏掛的檔案不會有人發現，而 `-m "not integration"`
會靜靜地把它算進 unit。

**`items` 是整場收集到的全部 case，不是本目錄的。** 不過濾就會把 tests/unit 也標成
integration —— 症狀是 `pytest tests/unit tests/integration -m "not integration"` 把**全部**
deselect 掉，看起來像「一個測試都沒有」而不是像錯誤。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def pytest_collection_modifyitems(config, items):
    ci = bool(os.environ.get("CI"))
    for item in items:
        if not item.path.is_relative_to(HERE):
            continue
        item.add_marker(pytest.mark.integration)
        if ci:
            item.add_marker(pytest.mark.skip(reason="integration 吃本機安裝版／真實外部服務，CI 一律 skip"))
