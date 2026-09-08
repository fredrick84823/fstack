#!/usr/bin/env python3
"""
local_archive.py - 發佈時在本機留一份正式稿，並把 Doc URL 記在同名側檔。

Doc URL 只有發佈當下拿得到，事後要靠檔名回頭去 Drive 找。側檔就是為了記住它。

本機路徑與 Drive 路徑同形：
    ~/thoughts/global/shared/meeting-notes/{folder_name}/{YYYYMMDD}/
        會議記錄_{series_name}_{YYYYMMDD}[_{suffix}].md          正式稿
        會議記錄_{series_name}_{YYYYMMDD}[_{suffix}].meta.json   側檔

folder_name 沿用發佈流程算 Drive 資料夾時已經用的那個值，不另外設定。
"""

import json
import re
from pathlib import Path

LOCAL_ARCHIVE_ROOT = Path.home() / "thoughts" / "global" / "shared" / "meeting-notes"
SIDECAR_SUFFIX = ".meta.json"


def clean_for_filename(text: str | None) -> str:
    """把一段文字清成可安全放進檔名／Doc 名的形式。

    ponytail: 這個對應不是單射的——`a/b`、`a:b`、`a//b` 全部收斂到 `a-b`，同日兩場
    真的用這種識別碼就會撞成同一個檔名，而 `write_local_archive` 是覆寫語意，後寫的
    蓋掉前寫的。實務上的識別碼是 `am`/`pm`/`pc`/`phone`，不會撞，所以先接受。
    要升級的話是把對應改成單射（逐字元跳脫，例如 `%2F`），**不是**在寫入前偵測既有
    檔——那個檢查分不出「撞名」與「重跑同一場發佈」，而後者必須照常覆寫。
    """
    if not text:
        return ""
    return re.sub(r"[\\/:*?\"<>|]+", "-", text).strip(" -_")


def note_title(series_name: str, date: str, title_suffix: str | None = None) -> str:
    """正式稿標題。Doc 名稱與本機檔名共用這個值，兩邊才不會漂開。"""
    title = f"會議記錄_{series_name}_{date}"
    cleaned = clean_for_filename(title_suffix)
    return f"{title}_{cleaned}" if cleaned else title


def archive_paths(
    folder_name: str,
    date: str,
    title: str,
    root: Path | str = LOCAL_ARCHIVE_ROOT,
) -> tuple[Path, Path]:
    """回傳 (正式稿路徑, 側檔路徑)。純路徑組裝，不碰檔案系統。

    `title` 過一次檔名清洗：補齊腳本餵進來的是 Drive 上的 Doc 名，而 Drive 允許
    `/`，原樣當檔名會把檔案寫進另一個目錄。`folder_name` 與 `date` **不清洗** ——
    前者來自本機 config（不是外部輸入），後者傳什麼就是什麼。
    """
    directory = Path(root) / folder_name / date
    safe = clean_for_filename(title)
    return directory / f"{safe}.md", directory / f"{safe}{SIDECAR_SUFFIX}"


def sidecar_content(doc_url: str | None) -> str:
    """側檔內容。沒有 URL 時該欄位缺席——寫 None 會被下游當成可用的值。"""
    data = {"doc_url": doc_url} if doc_url else {}
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def write_local_archive(
    folder_name: str,
    date: str,
    title: str,
    content: str,
    doc_url: str | None = None,
    root: Path | str = LOCAL_ARCHIVE_ROOT,
) -> tuple[Path, Path]:
    """寫入正式稿與側檔，回傳兩者的路徑。"""
    note_path, sidecar_path = archive_paths(folder_name, date, title, root)
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(content, encoding="utf-8")
    sidecar_path.write_text(sidecar_content(doc_url), encoding="utf-8")
    return note_path, sidecar_path
