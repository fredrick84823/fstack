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

`child_env` —— 起子行程時用它算 `env=`。mutmut 的 stats pass 把 `MUTANT_UNDER_TEST`
放進環境，子行程（與孫行程）會繼承；被插樁的模組看到它就去載 mutmut 的設定，而設定是
**相對 cwd** 找的。測試把 cwd 釘在 `/` 的地方（那個釘子在測「路徑不從 cwd 推」）於是
整輪 mutation 停在 stats collection。

`load_script` —— 腳本住在 `skills/comms/generate-meeting-notes/scripts/`，目錄名有連
字號，不是可 import 的套件路徑。路徑一律從**本檔案**推出來：mutmut 把原始碼與測試
一起複製進 `mutants/` 之後，這樣載到的是 mutant；寫死 repo 路徑的話載到的是原檔，
每顆 mutant 都會活下來，而且看起來像「測試沒鑑別力」而不是「載錯檔」。

**寫測試時的第四種假綠，不在這三個工具裡：`@pytest.fixture(scope="module")`。**
把被測函式的呼叫結果快取起來之後，只有**第一條**測試真的呼叫到它，其餘拿現成的值。
`make test` 照樣全綠 —— 但 mutmut 靠 trampoline 記「哪條測試碰過哪個函式」，快取住的
呼叫不會再碰，於是那個函式的覆蓋測試清單只剩一條，挑覆蓋測試時整份比對都選不上，
mutant 活著。實測（2026-09-14，`test_gdocs_request_shape.py`）：`_markdown_to_gdocs`
的存活 58 → 3、整體 kill rate 74.5% → 93.2%，差別只在拿掉 `scope="module"`。

這種假綠**兩道事後守衛都看不見**（例外是 0、🫥 也是 0），症狀只是「分數沒殺光」，
而沒人會去查一個本來就不滿分的數字。純函式便宜，讓每條測試自己呼叫一次。

**第六種，只在「手動注入 bug 驗鑑別力」時發作：`__pycache__` 的 mtime 只有秒解析度。**
同一秒內連續寫兩次同一個 `.py`（還原 → 注入，或注入 → 還原 → 再注入），Python 認為
原始碼沒變，重用舊的 `.pyc` —— **跑的是上一版的碼**，注入的 bug 從來沒被執行過，測試
當然全綠，而實驗會被記成「這個 bug 沒有測試抓得到」。實測（#36）：同一個注入，同秒寫入
時 `open_items` 回舊答案 7、間隔 1 秒回新答案 0。同一次事故裡還有一個注入沒被還原就
留在工作樹上，也是同一個原因讓它一路綠到被人逐行讀碼才發現。

注入實驗一律這樣跑：

```bash
rm -rf skills/comms/generate-meeting-notes/scripts/__pycache__ tests/unit/__pycache__
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/unit -q -p no:cacheprovider
```

`load_script` 幫不上忙 —— 它每次都從路徑載，但 `exec_module` 照樣會走 `__pycache__`。

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
def load_script(name: str, base: Path | None = None) -> ModuleType:
    """把 `<base>/<name>.py` 當模組載進來（`load_script("extract_audio_sources")`）。

    `base` 預設是這支 skill 的 `scripts/`；repo 層的模組傳 `ROOT / "bin"`。預設值在**呼叫時**
    才解析（不是掛在簽名上）—— 綁在簽名上的話 `monkeypatch.setattr(conftest, "SCRIPTS", …)`
    就改不到它，而 harness 自己的契約測試正是那樣換路徑的。

    模組名一定要是**路徑推出來的那個**（分隔符換成點），不能自己取一個好看的。mutmut
    給 mutant 的 key 是 `get_mutant_name()` 從檔案路徑算的（`skills.comms.
    generate-meeting-notes.scripts.extract_audio_sources.x_<func>__mutmut_N`），而 trampoline
    記的是模組的 `__name__`。兩邊對不上 mutmut 會整輪停在「tests recorded trampoline hits
    but none match any mutant key」—— 名字裡有連字號在這裡不是問題，因為我們不靠 import
    system 解析它。

    同一個 process 內只載一次。mutmut 每顆 mutant 都是新 process，所以快取不會跨 mutant。
    """
    path = (SCRIPTS if base is None else base) / f"{name}.py"
    modname = str(path.relative_to(ROOT).with_suffix("")).replace(os.sep, ".")
    spec = importlib.util.spec_from_file_location(modname, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"載不進來：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MUTANT_VAR = "MUTANT_UNDER_TEST"


def child_env(**overrides: str) -> dict[str, str]:
    """子行程的環境：`os.environ` 的複本，去掉 `MUTANT_VAR`，再套上 `overrides`。

    mutmut 的 stats pass 用 `MUTANT_UNDER_TEST=stats` 起測試行程，子行程與**孫行程**
    都會繼承它（`run()` 起 shell 腳本、腳本自己再起 `python3 parity.py` 就是兩層）。
    `mutants/` 底下那份被插樁的模組看到它會去載 mutmut 的設定，而設定是**相對 cwd**
    找的 —— cwd 被釘在 `/` 的地方那裡沒有 `setup.cfg`，子行程以
    `FileNotFoundError: Could not figure out where the code to mutate is` 收場。
    症狀是整輪 mutation 停在 stats collection，一個數字都印不出來。
    真實呼叫端不會帶著那個變數，所以剔除它測到的才是真的介面。

    **只能動子行程的 `env=`，絕對不要碰 `os.environ` 本身**（`monkeypatch.delenv`、
    autouse fixture 清掉它都不行）：測試行程自己就是 mutmut 用那個變數啟動的，
    trampoline 靠它決定要啟用哪顆 mutant。在行程內刪掉 → 每顆 mutant 都跑到原始碼 →
    整輪靜靜地量不到東西，而且兩道事後守衛都看不見（例外是 0、🫥 也是 0），
    印出來的是滿分假綠。這是這份清單裡第五種假綠。
    """
    env = {k: v for k, v in os.environ.items() if k != MUTANT_VAR}
    env.update(overrides)
    return env


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


SKILL_MD = Path(__file__).resolve().parents[2] / "skills/comms/generate-meeting-notes/SKILL.md"


def skill_md_section(heading: str) -> str:
    """SKILL.md 的某一節（`## ` 開頭到下一個 `## ` 為止）。

    SKILL.md 當**程式碼**審，所以有不只一支測試要對著某一節下斷言（版本來源檢查、
    流程 C 的交棒契約）。切節那幾行手刻兩份之後，改掉其中一份的切法只會讓另一支
    靜靜地量到別的範圍 —— 那種假綠沒有任何斷言看得見。
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    start = text.find(heading)
    assert start != -1, f"SKILL.md 找不到「{heading}」一節"
    end = text.find("\n## ", start + len(heading))
    return text[start:] if end == -1 else text[start:end]
