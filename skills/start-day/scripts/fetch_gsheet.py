#!/usr/bin/env python3
"""Fetch active tasks from the Tagtoo work progress Google Sheet.

Usage:
    uv run python skills/start-day/scripts/fetch_gsheet.py \
        --owner fredrick --within-days 14 --output -
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Allow running from repo root without installing as package
sys.path.insert(0, str(Path(__file__).parent))
from common import enforce_tz_taipei, normalize_task_name

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("ERROR: Missing deps. Run: uv pip install gspread google-auth", file=sys.stderr)
    sys.exit(1)

SPREADSHEET_ID = "1ZkO6j_VU_hOcMoV78UzTGXTN8NzNzsPuOcGFhtP92LY"
WORKSHEET_NAME = "2025-工作進度表"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
DEFAULT_CRED_PATH = Path.home() / ".config" / "gsheet-progress-sync" / "service_account.json"

# Column indices (1-based) matching gsheet schema
COL_TASK_NAME = 1   # 大類別 (task name)
COL_OWNER = 4       # 負責人
COL_STATUS = 5      # 狀態
COL_PROGRESS = 6    # 進度說明
COL_LAST_UPDATED = 7  # 最後更新日期


def _col(row: list, idx: int) -> str:
    return row[idx - 1] if len(row) >= idx else ""


def _try_adc():
    try:
        import google.auth
        creds, _ = google.auth.default(scopes=SCOPES)
        return gspread.authorize(creds)  # type: ignore[arg-type]
    except Exception:
        return None


def _try_service_account():
    cred_path = Path(os.environ.get("GSHEET_SERVICE_ACCOUNT_PATH", str(DEFAULT_CRED_PATH)))
    if not cred_path.exists():
        return None
    try:
        creds = Credentials.from_service_account_file(str(cred_path), scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception:
        return None


def _get_worksheet() -> gspread.Worksheet:
    for attempt in [_try_adc, _try_service_account]:
        gc = attempt()
        if gc is None:
            continue
        try:
            return gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
        except Exception:
            continue
    print(
        "ERROR: Could not open gsheet. Check credentials (ADC or service account).",
        file=sys.stderr,
    )
    sys.exit(1)


def _parse_date(date_str: str) -> datetime | None:
    """Try common date formats used in the sheet."""
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def fetch_tasks(owner: str, within_days: int) -> list[dict]:
    enforce_tz_taipei()
    ws = _get_worksheet()
    rows = ws.get_all_values()
    if not rows:
        return []

    cutoff = datetime.now() - timedelta(days=within_days)
    tasks = []

    for row in rows[1:]:  # skip header
        task_name = _col(row, COL_TASK_NAME).strip()
        row_owner = _col(row, COL_OWNER).strip()
        status_raw = _col(row, COL_STATUS).strip()
        progress_note = _col(row, COL_PROGRESS).strip()
        last_updated_str = _col(row, COL_LAST_UPDATED).strip()

        if not task_name:
            continue
        if row_owner.lower() != owner.lower():
            continue
        if status_raw in ("完成", "Completed", "Done"):
            continue

        last_updated_dt = _parse_date(last_updated_str)
        if last_updated_dt:
            # Date present: exclude if older than cutoff
            if last_updated_dt < cutoff:
                continue
        else:
            # No date: only include actively in-progress tasks; drop old paused/blocked ones
            if _map_status(status_raw) != "in-progress":
                continue

        status = _map_status(status_raw)
        tasks.append({
            "name": normalize_task_name(task_name),
            "name_raw": task_name,
            "status": status,
            "sources": [
                {
                    "kind": "gsheet",
                    "id": "",
                    "url": f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}",
                    "status_raw": status_raw,
                    "last_updated": last_updated_str,
                }
            ],
            "conflict": None,
            "depends_on": [],
            "card_id": None,
            "progress_note": progress_note,
        })

    return tasks


def _map_status(raw: str) -> str:
    raw_lower = raw.lower()
    if "進行" in raw_lower or "in progress" in raw_lower or "wip" in raw_lower:
        return "in-progress"
    if "完成" in raw_lower or "done" in raw_lower or "completed" in raw_lower:
        return "completed"
    if "阻塞" in raw_lower or "blocked" in raw_lower or "待" in raw_lower or "暫停" in raw_lower:
        return "blocked"
    return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch tasks from Google Sheet")
    parser.add_argument("--owner", default="fredrick", help="Owner name to filter by")
    parser.add_argument("--within-days", type=int, default=7, help="Max days since last update")
    parser.add_argument("--output", default="-", help="Output path (- for stdout)")
    args = parser.parse_args()

    tasks = fetch_tasks(args.owner, args.within_days)

    result = json.dumps(tasks, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(result)
    else:
        Path(args.output).write_text(result, encoding="utf-8")


if __name__ == "__main__":
    main()
