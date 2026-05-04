#!/usr/bin/env python3
"""Fetch recent PRs from active GitHub repos.

Discovers active repos by checking mtime of files in thoughts/repos/.
For each repo, fetches PRs (open + recently merged) authored by the user.

Usage:
    uv run python skills/start-day/scripts/fetch_github.py \
        --thoughts-dir /Users/fredrick/thoughts/repos --within-days 7 --output -
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import enforce_tz_taipei, normalize_task_name

FALLBACK_OWNER = "tagtoo"
WORKSPACE_ROOT = Path.home() / "Desktop" / "01_Work" / "workspace"

_GH_LOGIN: str | None = None


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _gh_login() -> str:
    """Return the authenticated GitHub username (cached)."""
    global _GH_LOGIN
    if _GH_LOGIN is None:
        r = _run(["gh", "api", "user", "--jq", ".login"], check=False)
        _GH_LOGIN = r.stdout.strip() if r.returncode == 0 else "fredrick"
    return _GH_LOGIN


def _find_active_repos(thoughts_dir: Path, within_days: int) -> set[str]:
    """Return set of repo names with mtime within within_days."""
    cutoff = datetime.now().timestamp() - within_days * 86400
    active = set()
    for md in thoughts_dir.glob("*/shared/**/*.md"):
        if md.stat().st_mtime >= cutoff:
            active.add(md.parts[len(thoughts_dir.parts)])
    for md in thoughts_dir.glob("*/fredrick/**/*.md"):
        if md.stat().st_mtime >= cutoff:
            active.add(md.parts[len(thoughts_dir.parts)])
    return active


def _resolve_repo_fullname(repo_name: str) -> str | None:
    """Try to get OWNER/NAME via local git remote, else fallback to tagtoo/name."""
    local_path = WORKSPACE_ROOT / repo_name
    if local_path.exists():
        try:
            r = _run(["git", "-C", str(local_path), "remote", "get-url", "origin"], check=False)
            if r.returncode == 0:
                url = r.stdout.strip()
                # Parse https://github.com/OWNER/REPO.git or git@github.com:OWNER/REPO.git
                import re
                m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", url)
                if m:
                    return m.group(1)
        except Exception:
            pass
    # Fallback: assume tagtoo owner
    return f"{FALLBACK_OWNER}/{repo_name}"


def _filter_prs_within_window(prs: list[dict], since_iso: str) -> list[dict]:
    """Return only PRs whose relevant date falls within the window.

    For merged PRs, use mergedAt — updatedAt can be bumped by CI/labels long after
    the actual merge and would incorrectly pass old PRs through the window.
    For open/closed PRs, fall back to updatedAt.
    """
    from dateutil.parser import parse as parse_dt
    cutoff = parse_dt(since_iso)
    result = []
    for pr in prs:
        merged_at = pr.get("mergedAt")
        state = pr.get("state", "").upper()
        date_str = merged_at if (state == "MERGED" and merged_at) else pr.get("updatedAt", "")
        if date_str:
            try:
                if parse_dt(date_str) < cutoff:
                    continue
            except Exception:
                pass
        result.append(pr)
    return result


def _fetch_prs(full_name: str, since_iso: str) -> list[dict]:
    """Fetch open + recently-closed PRs authored by @me within the time window."""
    try:
        r = _run([
            "gh", "pr", "list",
            "--repo", full_name,
            "--author", "@me",
            "--state", "all",
            "--json", "number,title,url,updatedAt,state,mergedAt",
            "--limit", "50",
        ], check=False)
        if r.returncode != 0:
            return []
        prs = json.loads(r.stdout)
        return _filter_prs_within_window(prs, since_iso)
    except Exception:
        return []


def fetch_tasks(thoughts_dir: Path, within_days: int) -> list[dict]:
    enforce_tz_taipei()
    active_repos = _find_active_repos(thoughts_dir, within_days)
    since_dt = datetime.now(timezone.utc) - timedelta(days=within_days)
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    tasks: list[dict] = []

    for repo_name in sorted(active_repos):
        full_name = _resolve_repo_fullname(repo_name)
        if full_name is None:
            print(f"⚠️  Could not resolve repo for '{repo_name}', skipping", file=sys.stderr)
            continue

        prs = _fetch_prs(full_name, since_iso)
        if prs is None:
            print(f"⚠️  Could not fetch PRs for {full_name}, skipping", file=sys.stderr)
            continue

        for pr in prs:
            title = pr.get("title", "").strip()
            pr_state = pr.get("state", "open").lower()
            merged_at = pr.get("mergedAt")
            if merged_at or pr_state == "merged":
                status = "completed"
                status_raw = "merged"
            elif pr_state == "closed":
                status = "completed"
                status_raw = "closed"
            else:
                status = "in-progress"
                status_raw = "open"
            tasks.append({
                "name": normalize_task_name(title),
                "name_raw": title,
                "status": status,
                "sources": [
                    {
                        "kind": "github_pr",
                        "id": str(pr.get("number", "")),
                        "url": pr.get("url") or pr.get("html_url"),
                        "status_raw": status_raw,
                        "last_updated": pr.get("updatedAt", ""),
                    }
                ],
                "conflict": None,
                "depends_on": [],
                "card_id": None,
            })

    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch tasks from GitHub")
    parser.add_argument(
        "--thoughts-dir",
        default=str(Path.home() / "thoughts" / "repos"),
        help="Path to thoughts/repos directory",
    )
    parser.add_argument("--within-days", type=int, default=7)
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    tasks = fetch_tasks(Path(args.thoughts_dir), args.within_days)
    result = json.dumps(tasks, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(result)
    else:
        Path(args.output).write_text(result, encoding="utf-8")


if __name__ == "__main__":
    main()
