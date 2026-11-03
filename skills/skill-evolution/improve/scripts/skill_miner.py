#!/usr/bin/env python3
"""Weekly skill miner: cluster a week of human sessions, keep what no skill already does.

The skill-candidate line used to wait for an agent to announce a candidate at the end
of a session. In a month that produced zero real candidates (2026-11-03 audit), and a
one-week clustering experiment found 21 of 22 recurring tasks already had a skill. So
this runs offline over the transcripts instead, and its first gate is the one thing
only the transcript knows: which skills each session actually invoked.

    sessions ── skip_reason / user_messages / fork dedup (session_classifier) ──┐
                                                                                  ▼
    cluster-sessions.sh (claude -p, sonnet) ──▶ judge() ──▶ candidate-queue.md
                                                  │
           cluster's task is a skill the sessions used ──▶ not a candidate
           a skill covers it, ≥3 sessions skipped it   ──▶ bypass:<skill>
           nothing covers it                           ──▶ new candidate

"An existing skill fell short" is the GAP line's job (session_classifier), not this one.
Every run also rewrites memory/stale-skills.md: installed skills with no use in 30 days,
for the daily digest to list. Nothing is ever deleted.
"""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Iterable, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_classifier import (  # noqa: E402
    distinct_by_first_prompt, normalize, read_transcript, skills_used, skip_reason, user_messages,
)

MIN_SESSIONS = 3
PROMPTS_PER_SESSION, PROMPT_CHARS = 6, 220
STALE_DAYS = 30


# --- inputs ----------------------------------------------------------------------


def installed_skills(home: Path) -> dict[str, str]:
    """`name -> description` for every skill directory under ~/.claude and ~/.agents."""
    found: dict[str, str] = {}
    for root in (home / ".claude/skills", home / ".agents/skills"):
        if not root.is_dir():
            continue
        for skill_md in sorted(root.glob("*/SKILL.md")):
            if skill_md.parent.name.startswith("."):  # backups like .generate-meeting-notes.bak-*
                continue
            found.setdefault(skill_md.parent.name, description(skill_md.read_text(errors="replace")))
    return found


def description(text: str) -> str:
    """The frontmatter `description:`, folded (`>`) or not, flattened to one line."""
    match = re.search(r"^description:[ \t]*(.*(?:\n[ \t]+.*)*)", text, re.M)
    if not match:
        return ""
    return normalize(re.sub(r"^[>|][-+]?", "", match.group(1).strip()))[:200]


def recent_transcripts(projects: Path, since: float) -> list[Path]:
    return sorted((p for p in projects.glob("*/*.jsonl") if p.stat().st_mtime >= since),
                  key=lambda p: p.stat().st_mtime)


def human_sessions(paths: Iterable[Path], home: Path) -> list[dict[str, Any]]:
    """One summary per session a human drove, forks and resumes counted once.

    Rows are read lazily and dropped after summarising: a week is ~500 transcripts.
    """
    def summaries() -> Iterator[tuple[dict[str, Any], list[dict[str, Any]]]]:
        for path in paths:
            rows = read_transcript(path)
            if skip_reason({}, rows):
                continue
            prompts = user_messages(rows)
            if not prompts:
                continue
            yield {
                "session": f"{path.parent.name}/{path.stem[:8]}",
                "project": re.sub(r"^-Users-[^-]+-", "", path.parent.name),
                "date": dt.date.fromtimestamp(path.stat().st_mtime).isoformat(),
                "prompts": [normalize(p)[:PROMPT_CHARS] for p in prompts[:PROMPTS_PER_SESSION]],
                "skills": skills_used(rows, home),
            }, rows

    kept = distinct_by_first_prompt(summaries())
    for index, session in enumerate(kept, 1):
        session["id"] = f"s{index}"
    return kept


def render_input(sessions: list[dict[str, Any]], skills: dict[str, str]) -> str:
    lines = ["===SESSIONS==="]
    for s in sessions:
        lines.append(f"\n### {s['id']} · {s['project']} · {s['date']}")
        lines.append("skills: " + (", ".join(s["skills"]) or "(none)"))
        lines += [f"- {p}" for p in s["prompts"]]
    lines.append("\n===INSTALLED_SKILLS===")
    lines += [f"{name}: {desc}" for name, desc in sorted(skills.items())]
    return "\n".join(lines) + "\n"


def run_clusterer(clusterer: Path, text: str, env: dict[str, str]) -> dict[str, Any] | None:
    """The model's clusters, or None when it did not answer (fail-closed, never `[]`)."""
    try:
        done = subprocess.run([str(clusterer)], input=text, text=True, capture_output=True,
                              env=env, timeout=900)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"cluster-sessions: {exc}", file=sys.stderr)
        return None
    if done.returncode != 0:
        print(done.stderr.strip()[:300], file=sys.stderr)
        return None
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        return None


# --- gate ------------------------------------------------------------------------


def judge(clusters: list[dict[str, Any]], sessions: list[dict[str, Any]],
          installed: Iterable[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split the model's clusters into queue entries and drops (each with a reason).

    Gate 1 trusts the transcript over the model: a skill most of the cluster invoked
    covers the task even when the model said null (the 2026-11-03 experiment's
    mcp-usage-stats miss). A covered task is a candidate only as `bypass:<skill>`, and
    only when ≥3 of its sessions did the work without that skill.
    """
    by_id = {s["id"]: s for s in sessions}
    installed = set(installed)
    entries: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for cluster in clusters:
        ids = list(dict.fromkeys(i for i in cluster.get("session_ids", []) if i in by_id))
        if len(ids) < MIN_SESSIONS:
            dropped.append({"name": cluster.get("name"), "why": f"{len(ids)} sessions"})
            continue
        used = Counter(skill for i in ids for skill in by_id[i]["skills"])
        skill = cluster.get("existing_skill") if cluster.get("existing_skill") in installed else None
        majority = [name for name, n in used.most_common() if n * 2 >= len(ids)]
        if majority and (skill is None or used[skill] * 2 < len(ids)):
            skill = majority[0]
        hits = [i for i in ids if skill not in by_id[i]["skills"]] if skill else ids
        if skill and len(hits) < MIN_SESSIONS:
            dropped.append({"name": cluster.get("name"), "why": f"covered by {skill}"})
            continue
        dates = sorted(by_id[i]["date"] for i in hits)
        entries.append({
            "name": f"bypass:{skill}" if skill else cluster["name"],
            "kind": "bypassed" if skill else "new",
            "existing_skill": skill,
            "hit_count": len(hits),
            "first_seen": dates[0], "last_seen": dates[-1],
            "reason": cluster.get("reason") or cluster.get("task", ""),
            "task": cluster.get("task", ""),
            "steps": cluster.get("steps") or [],
            "invoker_hints": cluster.get("invoker_hints") or [],
            "sessions": [by_id[i]["session"] for i in hits],
        })
    return entries, dropped


# --- queue -----------------------------------------------------------------------


QUEUE_ENTRY = re.compile(r"^## \[[^\]]+\] (\S+)\n\n- \*\*status\*\*: (\w+)", re.M)


def pending_names(queue_text: str) -> set[str]:
    return {name for name, status in QUEUE_ENTRY.findall(queue_text) if status == "pending"}


def render_entry(entry: dict[str, Any], stamp: str, today: str) -> str:
    lines = [f"## [{stamp}] {entry['name']}", "", "- **status**: pending",
             f"- **kind**: {entry['kind']}"]
    if entry["existing_skill"]:
        lines.append(f"- **existing_skill**: {entry['existing_skill']}")
    lines += [
        f"- **hit_count**: {entry['hit_count']}",
        f"- **first_seen**: {entry['first_seen']}",
        f"- **last_seen**: {entry['last_seen']}",
        f"- **task**: {normalize(entry['task'])}",
        f"- **reason**: {normalize(entry['reason'])}",
        "- **steps**: |",
        *[f"  {n}. {normalize(step)}" for n, step in enumerate(entry["steps"], 1)],
        "- **invoker_hints**: " + "、".join(f"「{normalize(h)}」" for h in entry["invoker_hints"]),
        "- **sessions**: " + ", ".join(entry["sessions"]),
        f"- **source**: skill-miner {today}",
    ]
    return "\n".join(lines) + "\n"


# --- stale skills ----------------------------------------------------------------


def last_used(paths: Iterable[Path], home: Path) -> dict[str, float]:
    """`skill -> mtime of the newest transcript that used it`, over every transcript kept.

    Only lines that can name a skill are parsed ("kill" catches Skill and skills): the
    full 90-day history is over a gigabyte of JSON.
    """
    seen: dict[str, float] = {}
    for path in paths:
        mtime = path.stat().st_mtime
        rows = []
        with path.open(errors="replace") as handle:
            for line in handle:
                if "kill" in line or "command-name" in line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        for skill in skills_used(rows, home):
            seen[skill] = max(seen.get(skill, 0.0), mtime)
    return seen


def stale_report(installed: Iterable[str], used: dict[str, float], now: float, oldest: float) -> str:
    cutoff = now - STALE_DAYS * 86400
    stale = sorted((used.get(name, 0.0), name) for name in installed if used.get(name, 0.0) < cutoff)
    since = dt.date.fromtimestamp(oldest).isoformat()
    lines = [f"# {STALE_DAYS} 天未叫用的已安裝 skill", "",
             f"產生：{dt.date.fromtimestamp(now).isoformat()} · transcript 從 {since} 起 · 共 {len(stale)} 支 · 只列，不刪", ""]
    lines += [f"- {name}：" + (f"最後叫用 {dt.date.fromtimestamp(ts).isoformat()}" if ts else f"{since} 以來未叫用")
              for ts, name in stale]
    return "\n".join(lines) + "\n"


# --- entry point -----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    env = dict(os.environ)
    home = Path(env.get("HOME") or Path.home())
    improve = Path(env.get("AGENTS_SKILLS_HOME") or home / ".agents/skills") / "improve"
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--projects", type=Path, default=home / ".claude/projects")
    parser.add_argument("--queue", type=Path, default=improve / "candidate-queue.md")
    parser.add_argument("--stale-out", type=Path, default=improve / "memory/stale-skills.md")
    parser.add_argument("--dry-run", action="store_true", help="print entries, write nothing")
    args = parser.parse_args(argv)

    now = time.time()
    installed = installed_skills(home)
    sessions = human_sessions(recent_transcripts(args.projects, now - args.days * 86400), home)
    clusterer = Path(env.get("IMPROVE_MINER_CLUSTERER") or Path(__file__).resolve().parent / "cluster-sessions.sh")
    env["IMPROVE_CLASSIFIER_DISABLE"] = "1"  # the clusterer's own claude -p is not a session to grade
    answer = run_clusterer(clusterer, render_input(sessions, installed), env) if sessions else {"clusters": []}
    if answer is None:
        print(json.dumps({"error": "clusterer did not answer", "sessions": len(sessions)}))
        return 1
    entries, dropped = judge(answer["clusters"], sessions, installed)

    queue_text = args.queue.read_text() if args.queue.exists() else ""
    already = pending_names(queue_text)
    fresh = [e for e in entries if e["name"] not in already]
    stamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    rendered = "".join("\n" + render_entry(e, stamp, stamp[:10]) for e in fresh)

    every = sorted(args.projects.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime)
    stale = stale_report(installed, last_used(every, home), now, every[0].stat().st_mtime if every else now)
    if args.dry_run:
        print(rendered + "\n" + stale, file=sys.stderr)
    else:
        if rendered:
            with args.queue.open("a") as handle:
                handle.write(rendered)
        args.stale_out.parent.mkdir(parents=True, exist_ok=True)
        args.stale_out.write_text(stale)

    usage = answer.get("usage") or {}
    print(json.dumps({
        "sessions": len(sessions), "clusters": len(answer["clusters"]),
        "new": sum(e["kind"] == "new" for e in fresh), "bypassed": sum(e["kind"] == "bypassed" for e in fresh),
        "already_pending": [e["name"] for e in entries if e["name"] in already],
        "dropped": dropped,
        "tokens": {k: usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                                "cache_read_input_tokens", "output_tokens")},
        "cost_usd": answer.get("total_cost_usd"),
        "dry_run": args.dry_run,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
