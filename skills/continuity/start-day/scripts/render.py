"""Render merged task list to markdown journal section.

Pure function: render_journal_section(tasks, week_id, today) -> str
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import normalize_task_name

NO_TASKS_SENTINEL = "今日無任務"


def render_journal_section(tasks: list[dict], week_id: str, today: str) -> str:
    """Return markdown for the 今日任務看板 section.

    Returns NO_TASKS_SENTINEL if tasks is empty.
    """
    if not tasks:
        return NO_TASKS_SENTINEL

    in_progress = [t for t in tasks if t["status"] == "in-progress"]
    completed = [t for t in tasks if t["status"] == "completed"]
    blocked = [t for t in tasks if t["status"] in ("blocked", "unknown")]

    lines: list[str] = [f"# 今日任務看板 — {today} ({week_id})", ""]

    if in_progress:
        lines.append("## 進行中")
        for task in in_progress:
            lines.extend(_render_task_item(task))
        lines.append("")

    if completed:
        lines.append("## 已完成（本週）")
        for task in completed:
            lines.extend(_render_task_item(task))
        lines.append("")

    if blocked:
        lines.append("## 阻塞 / 待確認")
        for task in blocked:
            lines.extend(_render_task_item(task))
        lines.append("")

    # Dependency tree (only if any task has depends_on)
    dep_section = _render_dep_tree(tasks)
    if dep_section:
        lines.append("## 🔗 依賴關係")
        lines.extend(dep_section)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_task_item(task: dict) -> list[str]:
    lines = []
    name = task["name_raw"]
    src_labels = _source_labels(task["sources"])

    header = f"- **{name}**"
    if src_labels:
        header += f" [{src_labels}]"
    if task.get("multi_match_warning"):
        header += " ⚠️ 多重比對"
    lines.append(header)

    if task.get("conflict"):
        lines.append(f"  - ⚠️ 衝突: {task['conflict']}")

    # Show progress note for in-progress and blocked/unknown tasks
    if task.get("progress_note") and task.get("status") in ("in-progress", "blocked", "unknown"):
        lines.append(f"  > {task['progress_note']}")

    # Show primary source URL
    for src in task["sources"]:
        if src.get("url") and src["kind"] in ("github_pr", "github_commit"):
            lines.append(f"  - 來源: {src['kind']} #{src['id']} → {src['url']}")
            break

    return lines


def _source_labels(sources: list[dict]) -> str:
    labels = []
    for src in sources:
        kind = src["kind"]
        if kind == "github_pr":
            labels.append(f"PR #{src['id']} {src['status_raw']}")
        elif kind == "github_commit":
            labels.append(f"commit {src['id']}")
        elif kind == "gsheet":
            labels.append(f"gsheet {src['status_raw']}")
        elif kind == "heptabase":
            labels.append("heptabase")
    return " / ".join(labels)


def _render_dep_tree(tasks: list[dict]) -> list[str]:
    """Render ASCII dependency tree. Returns [] if no dependencies."""
    tasks_with_deps = [t for t in tasks if t.get("depends_on")]
    if not tasks_with_deps:
        return []

    # Build name → status lookup
    name_status: dict[str, str] = {normalize_task_name(t["name"]): t["status"] for t in tasks}

    lines: list[str] = []
    for task in tasks_with_deps:
        deps = task["depends_on"]
        lines.append(f"└─ {task['name_raw']} ({task['status']})")
        for j, dep in enumerate(deps):
            dep_status = name_status.get(normalize_task_name(dep), "unknown")
            connector = "├─" if j < len(deps) - 1 else "└─"
            lines.append(f"   {connector} depends on: {dep} ({dep_status})")
        lines.append("")

    return lines
