#!/usr/bin/env python3
"""Fetch current-week task cards from Heptabase via ISO week tag.

Usage:
    uv run python skills/start-day/scripts/fetch_heptabase.py \
        --week-id 2026-W18 --output -

Returns [] (empty list) if the week tag does not exist yet (cold start).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import enforce_tz_taipei, iso_week_id, normalize_task_name


def _run_heptabase(args: list[str]) -> dict | list | None:
    """Run heptabase CLI and parse JSON output. Returns None on error."""
    try:
        r = subprocess.run(
            ["heptabase"] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            print(f"⚠️  heptabase {' '.join(args)} failed: {r.stderr.strip()}", file=sys.stderr)
            return None
        return json.loads(r.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"⚠️  heptabase error: {e}", file=sys.stderr)
        return None


def _find_week_tag_id(week_id: str) -> str | None:
    """Return tag id for the given week, or None if not found."""
    result = _run_heptabase(["tag", "list", "--name-filter", week_id])
    if result is None:
        return None
    tags = result if isinstance(result, list) else result.get("tags", [])
    for tag in tags:
        if tag.get("name", "").strip() == week_id:
            return tag["id"]
    return None


def _get_tag_cards(tag_id: str) -> list[dict]:
    result = _run_heptabase(["tag", "cards", tag_id])
    if result is None:
        return []
    return result if isinstance(result, list) else result.get("cards", [])


def _parse_section(markdown: str, section_name: str) -> str:
    """Extract first non-empty line from a named ## section."""
    in_section = False
    lines: list[str] = []
    for line in markdown.splitlines():
        if re.match(rf"^##\s+{re.escape(section_name)}", line, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            if re.match(r"^##\s+", line):
                break
            stripped = line.strip().lstrip("- •*").strip()
            if stripped and not stripped.startswith("<!--"):
                lines.append(stripped)
    return " / ".join(lines[:2]) if lines else ""


def _parse_progress_note(markdown: str) -> str:
    """Extract progress note from ## Progress, ## Status Note, or ## Goal section."""
    for section in ("Progress", "Status Note", "進度", "Goal"):
        note = _parse_section(markdown, section)
        if note and note not in ("…", "..."):
            return note
    return ""


def _parse_depends_on(markdown: str) -> list[str]:
    """Extract task names from '## Depends on' section."""
    depends: list[str] = []
    in_section = False
    for line in markdown.splitlines():
        if re.match(r"^##\s+Depends on", line, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            if re.match(r"^##\s+", line):
                break
            stripped = line.strip().lstrip("- •*").strip()
            if stripped and not stripped.startswith("<!--"):
                depends.append(stripped)
    return [d for d in depends if d]


def _read_card_markdown(card_id: str) -> str | None:
    """Try to read card content as markdown via note read + conversion."""
    result = _run_heptabase(["note", "read", card_id])
    if result is None:
        return None
    # The CLI returns ProseMirror JSON; extract text content heuristically
    # by recursively pulling 'text' fields
    return _prosemirror_to_text(result)


def _prosemirror_to_text(node: dict | list | str | None) -> str:
    """Recursively extract text from ProseMirror JSON."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(_prosemirror_to_text(item) for item in node)
    if isinstance(node, dict):
        parts: list[str] = []
        node_type = node.get("type", "")
        # Headings become markdown headings
        if node_type == "heading":
            level = node.get("attrs", {}).get("level", 2)
            text = _prosemirror_to_text(node.get("content", []))
            return "#" * level + " " + text
        if node_type == "bulletList" or node_type == "orderedList":
            items = node.get("content", [])
            return "\n".join("- " + _prosemirror_to_text(item) for item in items)
        if "text" in node:
            parts.append(node["text"])
        if "content" in node:
            parts.append(_prosemirror_to_text(node["content"]))
        return "".join(parts)
    return ""


def fetch_tasks(week_id: str) -> list[dict]:
    enforce_tz_taipei()

    tag_id = _find_week_tag_id(week_id)
    if tag_id is None:
        print(f"ℹ️  Week tag '{week_id}' not found — cold start, returning empty list", file=sys.stderr)
        return []

    cards = _get_tag_cards(tag_id)
    tasks: list[dict] = []

    for card in cards:
        card_id = card.get("id", "")
        title = card.get("title", "").strip()
        if not title:
            continue

        # Try to read depends_on and progress_note from card content
        depends_on: list[str] = []
        progress_note: str = ""
        md = _read_card_markdown(card_id)
        if md:
            depends_on = _parse_depends_on(md)
            progress_note = _parse_progress_note(md)

        tasks.append({
            "name": normalize_task_name(title),
            "name_raw": title,
            "status": "unknown",  # heptabase cards don't carry status natively
            "sources": [
                {
                    "kind": "heptabase",
                    "id": card_id,
                    "url": None,
                    "status_raw": "card",
                    "last_updated": card.get("lastEditedTime", ""),
                }
            ],
            "conflict": None,
            "depends_on": depends_on,
            "card_id": card_id,
            "progress_note": progress_note,
        })

    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch tasks from Heptabase week tag")
    parser.add_argument(
        "--week-id",
        default=None,
        help="ISO week id like '2026-W18'; defaults to current week",
    )
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    week = args.week_id or iso_week_id()
    tasks = fetch_tasks(week)
    result = json.dumps(tasks, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(result)
    else:
        Path(args.output).write_text(result, encoding="utf-8")


if __name__ == "__main__":
    main()
