"""Shared utilities for start-day skill."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any


def enforce_tz_taipei() -> None:
    """Force Asia/Taipei timezone; warn if it was not already set."""
    if os.environ.get("TZ") != "Asia/Taipei":
        print(
            "⚠️  TZ not set to Asia/Taipei — overriding to prevent ISO-week drift on UTC hosts.",
            file=sys.stderr,
        )
        os.environ["TZ"] = "Asia/Taipei"
        time.tzset()


def iso_week_id(now: datetime | None = None) -> str:
    """Return ISO week string like '2026-W18' using local (Asia/Taipei) time."""
    enforce_tz_taipei()
    if now is None:
        now = datetime.now()
    return now.strftime("%G-W%V")


def normalize_task_name(name: str) -> str:
    """Lower, strip emoji, strip common prefixes/suffixes, collapse whitespace."""
    # Strip emoji via unicode category
    name = re.sub(r"[\U00010000-\U0010ffff]", "", name, flags=re.UNICODE)
    name = re.sub(r"[\U0001F300-\U0001FAFF]", "", name)
    # Strip common prefixes
    name = re.sub(r"^\[(WIP|URGENT|urgent|wip|BLOCKED|blocked)\]\s*", "", name)
    # Strip trailing markers
    name = re.sub(r"\s*[-–—]\s*(WIP|wip|BLOCKED|blocked|draft|Draft)$", "", name)
    name = name.lower().strip()
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name)
    return name


def dump_json(data: Any) -> None:
    """Print JSON to stdout, UTF-8 safe."""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def json_output(tasks: list[dict]) -> None:
    dump_json(tasks)
