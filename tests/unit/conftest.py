"""`generate-meeting-notes` 的 unit test harness。

三個工具，每個都在擋一種**假綠**：

`sent_kwargs` / `sent_body` —— 斷言打在**送出去的 request**，不是 mock 的回傳值。
斷言回傳值等於沒測：把一個必要參數從 API 呼叫裡拿掉，罐頭 JSON 照樣回來、測試照樣過。
沒有 call 可斷言時 **raise** 而不是回 MagicMock —— 回 mock 會讓下游每條斷言
vacuously true，那正是這兩個 helper 存在的唯一理由。raise 同時讓「拒絕路徑什麼都
沒送出去」變成可斷言的事：`pytest.raises(AssertionError, match="no call recorded")`。

`_qid` —— 自己供的 parametrize id 含非 ASCII 或反斜線，pytest 選不回來（exit 4），
mutmut 把那個 exit 4 記成 `killed`，印出假的全綠。這個 skill 的語料是繁中 markdown，
用 `repr()` 必踩。

`load_script` —— 腳本住在 `skills/comms/generate-meeting-notes/scripts/`，目錄名有連
字號，不是可 import 的套件路徑。路徑一律從**本檔案**推出來：mutmut 把原始碼與測試
一起複製進 `mutants/` 之後，這樣載到的是 mutant；寫死 repo 路徑的話載到的是原檔，
每顆 mutant 都會活下來，而且看起來像「測試沒鑑別力」而不是「載錯檔」。

harness 自己的契約釘在 `test_harness.py`。
"""

from __future__ import annotations

import importlib.util
import os
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills/comms/generate-meeting-notes/scripts"


@lru_cache(maxsize=None)
def load_script(name: str) -> ModuleType:
    """把 `scripts/<name>.py` 當模組載進來（`load_script("extract_audio_sources")`）。

    模組名一定要是**路徑推出來的那個**（分隔符換成點），不能自己取一個好看的。mutmut
    給 mutant 的 key 是 `get_mutant_name()` 從檔案路徑算的（`skills.comms.
    generate-meeting-notes.scripts.extract_audio_sources.x_<func>__mutmut_N`），而 trampoline
    記的是模組的 `__name__`。兩邊對不上 mutmut 會整輪停在「tests recorded trampoline hits
    but none match any mutant key」—— 名字裡有連字號在這裡不是問題，因為我們不靠 import
    system 解析它。

    同一個 process 內只載一次。mutmut 每顆 mutant 都是新 process，所以快取不會跨 mutant。
    """
    path = SCRIPTS / f"{name}.py"
    modname = str(path.relative_to(ROOT).with_suffix("")).replace(os.sep, ".")
    spec = importlib.util.spec_from_file_location(modname, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"載不進來：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _qid(value: str) -> str:
    """可被 pytest 再次選取的 node id。**不是** `repr(value)`。

    自己供的 `ids=` 只要含反斜線或非 ASCII，pytest 就選不回來（exit 4），mutmut 會把
    那個 exit 4 記成 `killed`，印出假的全綠。這個 skill 的語料是繁中 markdown，必踩。
    完整實測紀錄見 gdoc-mcp `tests/unit/test_text.py::_qid`。
    """
    return repr(value).encode("ascii", "backslashreplace").decode().replace("\\", "-")


def _resolve(service: MagicMock, path: tuple[str, ...]) -> MagicMock:
    """`_resolve(svc, ("documents", "batchUpdate"))` -> 代表 `svc.documents().batchUpdate`
    的那顆 mock。"""
    node = service
    for name in path[:-1]:
        node = getattr(node, name).return_value
    return getattr(node, path[-1])


def _describe(path: tuple[str, ...]) -> str:
    return f"service.{'().'.join(path)}()"


def sent_kwargs(service: MagicMock, *path: str) -> dict[str, Any]:
    """`service.<path...>()` 最後一次呼叫的 kwargs。

    沒有這樣的呼叫就 raise `AssertionError` —— 這裡回 MagicMock 會讓下游每條斷言
    vacuously true，那正是這個 helper 要防的病。
    """
    if not path:
        raise AssertionError("sent_kwargs() needs at least one attribute name")
    call = _resolve(service, path).call_args
    if call is None:
        raise AssertionError(f"no call recorded for {_describe(path)}")
    return dict(call.kwargs)


def sent_body(service: MagicMock, *path: str) -> dict[str, Any]:
    """`sent_kwargs(...)["body"]`；那次呼叫沒帶 `body=` 就 raise。"""
    kwargs = sent_kwargs(service, *path)
    if "body" not in kwargs:
        raise AssertionError(
            f"{_describe(path)} was called without body=; got {sorted(kwargs)}"
        )
    return kwargs["body"]
