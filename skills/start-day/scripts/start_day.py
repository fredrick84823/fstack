#!/usr/bin/env python3
"""Orchestrator: fetch → merge → render → write to Heptabase.

Usage:
    TZ=Asia/Taipei uv run python skills/start-day/scripts/start_day.py
    TZ=Asia/Taipei uv run python skills/start-day/scripts/start_day.py --dry-run
    TZ=Asia/Taipei uv run python skills/start-day/scripts/start_day.py --sprint-json /tmp/sprint_cards.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import enforce_tz_taipei, iso_week_id
from merge import merge
from render import render_journal_section
from heptabase_writer import (
    append_conflict_note,
    append_journal,
    check_heptabase_alive,
    ensure_card,
)

SKILL_ROOT = Path(__file__).parent.parent
THOUGHTS_DIR = Path.home() / "thoughts" / "repos"


def _run_fetcher(cmd: list[str]) -> list[dict]:
    """Run a fetcher subprocess and return parsed JSON list."""
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        msg = r.stderr.strip() or f"exit code {r.returncode}"
        raise RuntimeError(f"Fetcher failed: {' '.join(cmd)}\n{msg}")
    return json.loads(r.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily task board orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Print markdown, skip Heptabase writes")
    parser.add_argument("--week-id", default=None, help="Override ISO week (e.g. 2026-W18)")
    parser.add_argument("--sprint-json", default=None, help="Pre-fetched sprint whiteboard cards (from SKILL.md MCP step)")
    args = parser.parse_args()

    enforce_tz_taipei()
    today = datetime.now().strftime("%Y-%m-%d")
    week_id = args.week_id or iso_week_id()

    # Pre-flight: heptabase alive check (skip in dry-run)
    if not args.dry_run:
        if not check_heptabase_alive():
            print("❌ Heptabase desktop is not running. Start it with: heptabase start", file=sys.stderr)
            sys.exit(1)

    print(f"📅 {today} ({week_id})", flush=True)

    # Fetch from all sources (abort on any failure)
    uv_run = ["uv", "run", "--project", str(SKILL_ROOT)]

    print("⏳ Fetching gsheet...", flush=True)
    gsheet_tasks = _run_fetcher(uv_run + ["python", str(SKILL_ROOT / "scripts/fetch_gsheet.py"), "--owner", "fredrick", "--within-days", "7"])

    print("⏳ Fetching GitHub...", flush=True)
    github_tasks = _run_fetcher(uv_run + ["python", str(SKILL_ROOT / "scripts/fetch_github.py"), "--thoughts-dir", str(THOUGHTS_DIR), "--within-days", "7"])

    print("⏳ Fetching Heptabase week tag...", flush=True)
    heptabase_tag_tasks = _run_fetcher(uv_run + ["python", str(SKILL_ROOT / "scripts/fetch_heptabase.py"), "--week-id", week_id])

    # Sprint whiteboard cards (optional, from MCP pre-step in SKILL.md)
    sprint_tasks: list[dict] = []
    if args.sprint_json:
        sprint_path = Path(args.sprint_json)
        if sprint_path.exists():
            sprint_tasks = json.loads(sprint_path.read_text())
            print(f"ℹ️  Sprint whiteboard: {len(sprint_tasks)} cards", flush=True)
        else:
            print(f"⚠️  --sprint-json path not found: {args.sprint_json}", file=sys.stderr)

    heptabase_tasks = heptabase_tag_tasks + sprint_tasks

    # Cold start notice
    if not heptabase_tasks:
        print(f"⚠️  本週首次執行（{week_id} tag 不存在），從 gsheet + github 建立新卡片", flush=True)

    # Merge
    tasks = merge(gsheet_tasks, github_tasks, heptabase_tasks)

    if not tasks:
        print("✅ 今日無任務")
        return

    # Render markdown
    markdown = render_journal_section(tasks, week_id, today)
    print("\n--- PREVIEW ---")
    print(markdown)
    print("---")

    if args.dry_run:
        print("🔸 Dry run: skipping Heptabase writes")
        _print_summary(tasks, new_cards=0, is_dry_run=True)
        return

    # Write to Heptabase
    new_cards = 0
    conflict_count = 0

    # Only create cards for active tasks; completed PRs don't need Heptabase cards
    tasks_needing_card = [t for t in tasks if not t.get("card_id") and t["status"] != "completed"]
    tasks_with_conflict = [t for t in tasks if t.get("conflict")]

    for task in tasks_needing_card:
        print(f"🆕 Creating card: {task['name_raw'][:50]}", flush=True)
        card_id = ensure_card(task, week_id)
        task["card_id"] = card_id
        new_cards += 1

    for task in tasks_with_conflict:
        if task.get("card_id"):
            print(f"⚠️  Appending conflict note: {task['name_raw'][:50]}", flush=True)
            append_conflict_note(task["card_id"], task["conflict"], today)
            conflict_count += 1

    print("📓 Writing to journal...", flush=True)
    append_journal(today, markdown)

    _print_summary(tasks, new_cards=new_cards, conflict_count=conflict_count)


def _print_summary(tasks: list[dict], new_cards: int = 0, conflict_count: int = 0, is_dry_run: bool = False) -> None:
    total = len(tasks)
    in_progress = sum(1 for t in tasks if t["status"] == "in-progress")
    completed = sum(1 for t in tasks if t["status"] == "completed")
    dry_label = " (dry run)" if is_dry_run else ""
    print(f"\n✅ 完成{dry_label}：{total} 任務（進行中 {in_progress} / 已完成 {completed}）｜新建卡 {new_cards} 張｜衝突 {conflict_count} 個")


if __name__ == "__main__":
    main()
