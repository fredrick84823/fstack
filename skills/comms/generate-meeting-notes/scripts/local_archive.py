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


def clean_title_suffix(title_suffix: str | None) -> str:
    """把同日多場次的短識別碼清成可安全放進檔名／Doc 名的形式。"""
    if not title_suffix:
        return ""
    return re.sub(r"[\\/:*?\"<>|]+", "-", title_suffix).strip(" -_")


def note_title(series_name: str, date: str, title_suffix: str | None = None) -> str:
    """正式稿標題。Doc 名稱與本機檔名共用這個值，兩邊才不會漂開。"""
    title = f"會議記錄_{series_name}_{date}"
    cleaned = clean_title_suffix(title_suffix)
    return f"{title}_{cleaned}" if cleaned else title


def archive_paths(
    folder_name: str,
    date: str,
    title: str,
    root: Path | str = LOCAL_ARCHIVE_ROOT,
) -> tuple[Path, Path]:
    """回傳 (正式稿路徑, 側檔路徑)。純路徑組裝，不碰檔案系統。"""
    directory = Path(root) / folder_name / date
    return directory / f"{title}.md", directory / f"{title}{SIDECAR_SUFFIX}"


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
