"""Merge tasks from three sources into a unified, deduplicated task list.

Pure function: merge(gsheet, github, heptabase) -> list[Task]
No I/O, no side effects.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from common import normalize_task_name

try:
    from thefuzz import fuzz  # type: ignore[import-untyped]
except ImportError:
    from difflib import SequenceMatcher

    class fuzz:  # type: ignore[no-redef]
        @staticmethod
        def ratio(a: str, b: str) -> int:
            return int(SequenceMatcher(None, a, b).ratio() * 100)


FUZZY_THRESHOLD = 85  # ratio() returns 0–100


class CircularDependencyError(Exception):
    pass


def _fuzzy_match(name_a: str, name_b: str) -> bool:
    return fuzz.ratio(name_a, name_b) >= FUZZY_THRESHOLD


def _find_cluster(name: str, clusters: list[list[str]]) -> int | None:
    """Return index of the cluster that fuzzy-matches name, or None."""
    for i, cluster in enumerate(clusters):
        for existing in cluster:
            if _fuzzy_match(name, existing):
                return i
    return None


def _resolve_conflict(task: dict) -> dict:
    """Apply PR-precedence conflict resolution and set conflict message."""
    sources = task["sources"]
    pr_sources = [s for s in sources if s["kind"] == "github_pr"]
    gsheet_sources = [s for s in sources if s["kind"] == "gsheet"]

    if not pr_sources or not gsheet_sources:
        return task

    pr = pr_sources[0]
    gs = gsheet_sources[0]

    pr_status = "completed" if pr["status_raw"] in ("merged", "closed") else "in-progress"
    gs_status_raw = gs["status_raw"]
    gs_completed = gs_status_raw in ("完成", "Completed", "Done")
    gs_inprogress = "進行" in gs_status_raw or "in progress" in gs_status_raw.lower()

    conflict_msg: str | None = None

    if gs_completed and pr_status == "in-progress":
        task["status"] = "in-progress"
        conflict_msg = f"gsheet 顯示已完成，但 PR #{pr['id']} 尚未 merge"
    elif gs_inprogress and pr_status == "completed":
        task["status"] = "completed"
        conflict_msg = f"gsheet 顯示進行中，但 PR #{pr['id']} 已 merge"

    task["conflict"] = conflict_msg
    return task


def _detect_cycle(name: str, depends_on: list[str], task_map: dict[str, dict], visited: set[str], stack: set[str]) -> bool:
    """DFS cycle detection. Returns True if cycle found."""
    visited.add(name)
    stack.add(name)
    for dep in depends_on:
        dep_norm = normalize_task_name(dep)
        if dep_norm not in visited:
            dep_task = task_map.get(dep_norm)
            if dep_task and _detect_cycle(dep_norm, dep_task.get("depends_on", []), task_map, visited, stack):
                return True
        elif dep_norm in stack:
            return True
    stack.discard(name)
    return False


def merge(
    gsheet: list[dict],
    github: list[dict],
    heptabase: list[dict],
) -> list[dict]:
    """Merge three task lists into one deduplicated list.

    - Fuzzy-matches tasks by normalized name across all three sources
    - Applies PR-precedence conflict resolution
    - Detects circular dependencies (raises CircularDependencyError)
    - Flags multi-match warnings when multiple rows normalize to the same name
    """
    all_raw: list[dict] = gsheet + github + heptabase

    # Build clusters: each cluster = list of raw normalized names that fuzzy-match
    clusters: list[list[str]] = []
    cluster_tasks: list[list[dict]] = []

    for task in all_raw:
        norm = task["name"]
        idx = _find_cluster(norm, clusters)
        if idx is None:
            clusters.append([norm])
            cluster_tasks.append([task])
        else:
            # Don't merge two distinct Heptabase cards — different card_ids mean
            # they are genuinely separate tasks even if names are similar.
            new_card_id = task.get("card_id")
            existing_card_ids = {t["card_id"] for t in cluster_tasks[idx] if t.get("card_id")}
            if new_card_id and existing_card_ids and new_card_id not in existing_card_ids:
                clusters.append([norm])
                cluster_tasks.append([task])
                continue
            if norm not in clusters[idx]:
                clusters[idx].append(norm)
            cluster_tasks[idx].append(task)

    merged: list[dict] = []

    for tasks in cluster_tasks:
        if not tasks:
            continue

        # Pick canonical name: prefer heptabase card title, else gsheet, else github
        canonical = _pick_canonical(tasks)

        # Merge sources
        all_sources: list[dict] = []
        seen_source_ids: set[str] = set()
        for t in tasks:
            for src in t["sources"]:
                key = f"{src['kind']}:{src['id']}"
                if key not in seen_source_ids:
                    seen_source_ids.add(key)
                    all_sources.append(src)

        # Card id: from heptabase source if available
        card_id: str | None = None
        for t in tasks:
            if t.get("card_id"):
                card_id = t["card_id"]
                break

        # depends_on: from heptabase task if available
        depends_on: list[str] = []
        for t in tasks:
            if t.get("depends_on"):
                depends_on = t["depends_on"]
                break

        # progress_note: first non-empty across all sources (gsheet > heptabase)
        progress_note: str = ""
        for t in sorted(tasks, key=lambda x: 0 if any(s["kind"] == "gsheet" for s in x["sources"]) else 1):
            note = t.get("progress_note", "")
            if note:
                progress_note = note
                break

        # Status: prefer PR status, else gsheet, else heptabase, else first
        status = _pick_status(tasks, all_sources)

        # Multi-match warning: same source kind appears > 1 time in this cluster
        gsheet_tasks = [t for t in tasks if any(s["kind"] == "gsheet" for s in t["sources"])]
        multi_match_warning: str | None = None
        if len(gsheet_tasks) > 1:
            names = [t["name_raw"] for t in gsheet_tasks]
            multi_match_warning = f"多個 gsheet row 合併為同一任務: {names}"

        merged_task: dict[str, Any] = {
            "name": canonical["name"],
            "name_raw": canonical["name_raw"],
            "status": status,
            "sources": all_sources,
            "conflict": None,
            "depends_on": depends_on,
            "card_id": card_id,
            "multi_match_warning": multi_match_warning,
            "progress_note": progress_note,
        }

        # Conflict resolution
        merged_task = _resolve_conflict(merged_task)
        merged.append(merged_task)

    # Cycle detection on full merged list
    task_map = {normalize_task_name(t["name"]): t for t in merged}
    for task in merged:
        name_norm = normalize_task_name(task["name"])
        deps_norm = [normalize_task_name(d) for d in task.get("depends_on", [])]
        if deps_norm:
            visited: set[str] = set()
            stack: set[str] = set()
            if _detect_cycle(name_norm, deps_norm, task_map, visited, stack):
                raise CircularDependencyError(
                    f"循環依賴偵測：'{task['name']}' 的依賴鏈形成環"
                )

    return merged


def _pick_canonical(tasks: list[dict]) -> dict:
    """Pick the task whose name_raw should be the canonical display name."""
    for t in tasks:
        if t.get("card_id"):  # heptabase card
            return t
    for t in tasks:
        if any(s["kind"] == "gsheet" for s in t["sources"]):
            return t
    return tasks[0]


def _pick_status(tasks: list[dict], sources: list[dict]) -> str:
    pr_sources = [s for s in sources if s["kind"] == "github_pr"]
    if pr_sources:
        pr = pr_sources[0]
        return "completed" if pr["status_raw"] in ("merged", "closed") else "in-progress"
    gsheet_tasks = [t for t in tasks if any(s["kind"] == "gsheet" for s in t["sources"])]
    if gsheet_tasks:
        return gsheet_tasks[0]["status"]
    return tasks[0].get("status", "unknown")
