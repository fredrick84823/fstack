#!/usr/bin/env python3
"""SessionEnd GAP classifier: read the transcript once, ask the validator, capture what survives.

This is the inversion #40 asked for. The old path put "report any improvement
opportunity" in the agent's own context and fired at the end of **every turn**, so one
problem spanning four turns arrived as four signals and the abstain rules — which lived
only in `improve/SKILL.md` — were never in context when it mattered. Here the agent's
context says nothing about gaps; detection happens out-of-band, once per session,
against the transcript that already exists on disk.

Three things keep the cost near zero for the sessions that have nothing to say:

- A session that called no Skill exits before the model is ever invoked.
- An unattended session (`claude -p`, subagent, anything but a human at a terminal)
  exits at the gate — otherwise the classifier would grade its own runs.
- At most `--max-signals` findings per session, so one bad session cannot flood the queue.
- A gap already on file for that skill comes back as one more witness, not a second queue
  entry — including when it is worded differently, which the validator decides by
  answering `duplicate_of` against the KNOWN_SIGNALS it is shown.

Input (stdin): Claude Code SessionEnd hook JSON. Empirically (2026-09-15, Claude Code
2.1.272) that payload carries `transcript_path`, which is why this is a SessionEnd hook
and not a debounced Stop hook.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable


DEFAULT_MAX_SIGNALS = 3
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
# A user turn Claude Code generated on the user's behalf is not the user talking.
WRAPPED_USER_TEXT = re.compile(
    r"<(local-command-stdout|local-command-caveat|command-name|command-message|command-args"
    r"|system-reminder|user-prompt-submit-hook)>",
)


# --- gates -----------------------------------------------------------------------


def skip_reason(env: dict[str, str], rows: list[dict[str, Any]]) -> str | None:
    """Why this session must not reach the model, or None to proceed.

    `CLAUDE_CODE_SESSION_ATTENDED` is the honest question — is a human here? — and the
    rest are the same answer from other angles, kept because they cost one comparison
    each and each one alone is enough to stop the self-referential loop where a
    classifier run grades the classifier's own `claude -p` call.

    Codex cron needs no gate of its own: `codex exec` never fires Claude Code hooks, and
    a `claude -p` it spawns arrives here as unattended. `IMPROVE_CLASSIFIER_DISABLE=1` is
    the explicit lever for anything that slips past all of it.
    """
    if env.get("IMPROVE_CLASSIFIER_DISABLE") == "1":
        return "disabled by IMPROVE_CLASSIFIER_DISABLE"
    if env.get("CLAUDE_CODE_SESSION_ATTENDED") == "0":
        return "unattended session"
    entrypoint = env.get("CLAUDE_CODE_ENTRYPOINT", "")
    if entrypoint and entrypoint != "cli":
        return f"non-interactive entrypoint: {entrypoint}"
    if env.get("CLAUDE_CODE_CHILD_SESSION") == "1":
        return "child session"
    # The transcript is asked the same question independently: the hook inherits whatever
    # environment the session was launched with, but the rows record what it actually was.
    recorded = {str(row.get("entrypoint")) for row in conversation(rows) if row.get("entrypoint")}
    if recorded and "cli" not in recorded:
        return f"non-interactive transcript: {sorted(recorded)[0]}"
    if rows and all(row.get("isSidechain") or row.get("agentId") for row in conversation(rows)):
        return "subagent transcript"
    return None


# --- transcript ------------------------------------------------------------------


def read_transcript(path: Path) -> list[dict[str, Any]]:
    """Parse the JSONL transcript, skipping lines that do not parse.

    A half-written trailing line is normal — the session is ending as this runs — and is
    not a reason to lose the rest of the transcript.
    """
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def conversation(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("type") in {"user", "assistant"}]


def content_blocks(row: dict[str, Any]) -> list[Any]:
    content = (row.get("message") or {}).get("content")
    if isinstance(content, list):
        return content
    return [content] if content else []


def skills_used(rows: Iterable[dict[str, Any]]) -> list[str]:
    """Skill names this session actually invoked, first call first.

    Attribution is limited to what the transcript proves was called. A gap blamed on a
    skill that never ran is the misroute the Layer 2 validator kept catching by hand.
    """
    seen: list[str] = []
    for row in rows:
        if row.get("type") != "assistant" or row.get("isSidechain"):
            continue
        for block in content_blocks(row):
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") != "Skill":
                continue
            skill = (block.get("input") or {}).get("skill")
            if skill and skill not in seen:
                seen.append(skill)
    return seen


def user_messages(rows: Iterable[dict[str, Any]]) -> list[str]:
    """What the human actually typed, in order.

    Tool results arrive as `user` rows too, and so do slash-command expansions and hook
    output. None of that is the user correcting the agent, which is the only evidence the
    precision-first validator is allowed to cite.
    """
    messages: list[str] = []
    for row in rows:
        if row.get("type") != "user" or row.get("isSidechain") or row.get("isMeta"):
            continue
        if row.get("userType") not in (None, "external"):
            continue
        for block in content_blocks(row):
            if isinstance(block, dict):
                if block.get("type") != "text":
                    continue
                text = block.get("text", "")
            else:
                text = block if isinstance(block, str) else ""
            text = text.strip()
            if text and not WRAPPED_USER_TEXT.search(text):
                messages.append(text)
    return messages


def build_excerpt(skills: list[str], messages: list[str], *, limit: int = 8000) -> str:
    """The context the validator reasons over: what ran, and what the user said about it."""
    body = "\n\n".join(f"[user] {message}" for message in messages)
    header = "skills_invoked: " + ", ".join(skills) + "\n\n"
    return header + body[-limit:]


def known_signals(memory_sh: Path, memory_dir: Path, skill: str, *, limit: int = 20) -> list[dict[str, str]]:
    """The most recent signals already on file for this skill, newest last.

    Exact text matching only catches a gap phrased the same way twice, and July's queue
    said the same thing four different ways in a day — 43% of that month was duplicates
    that no whitespace-folding key would ever join. So the judgement of "is this the same
    gap said differently" goes to the validator, which needs to see what it is comparing
    against. Reading is cheap; a wrong fuzzy-match rule written here would not be.
    """
    if not memory_sh.is_file() or not (memory_dir / "signals.jsonl").is_file():
        return []
    try:
        completed = subprocess.run(
            ["bash", str(memory_sh), "lookup", "--memory-dir", str(memory_dir), "--target-skill", skill],
            text=True, capture_output=True, timeout=30,
        )
        prior = json.loads(completed.stdout).get("prior_signals") or []
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, AttributeError):
        return []
    return [
        {"signal_id": record.get("signal_id", ""), "gap": record.get("gap", "")}
        for record in prior[-limit:]
        if record.get("signal_id")
    ]


def with_known_signals(excerpt: str, signals: list[dict[str, str]]) -> str:
    """Append the KNOWN_SIGNALS section the validator answers `duplicate_of` from.

    It rides inside the excerpt because validate-gap.sh belongs to #43 and takes three
    positional arguments today. When that script grows a slot of its own this moves into
    it; the section marker is already the one the prompt looks for.
    """
    if not signals:
        return excerpt
    lines = "\n".join(f"{item['signal_id']}: {item['gap']}" for item in signals)
    return f"{excerpt}\n\n===KNOWN_SIGNALS===\n{lines}\n"


# --- validator -------------------------------------------------------------------


def run_validator(validator: Path, skill: str, excerpt: str, env: dict[str, str]) -> dict[str, Any] | None:
    """Call #43's precision-first validator for one skill and parse its JSON verdict.

    Contract (#43): {verdict, target_skill, gap, evidence_quote, risk_class, duplicate_of}.
    Anything that is not parseable JSON with an `accept` verdict is dropped —
    precision-first means the silent path is the default one. A verdict naming a
    `duplicate_of` is exempt from needing its own gap text and quote: it is pointing at a
    signal that already carries both.
    """
    try:
        completed = subprocess.run(
            [str(validator), skill, "", excerpt],
            text=True,
            capture_output=True,
            env=env,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"\{.*\}", completed.stdout, re.DOTALL)
    if not match:
        return None
    try:
        verdict = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(verdict, dict) or verdict.get("verdict") != "accept":
        return None
    if not verdict.get("duplicate_of") and not (verdict.get("gap") and verdict.get("evidence_quote")):
        return None
    verdict.setdefault("target_skill", skill)
    return verdict


# --- capture ---------------------------------------------------------------------


def resolve_queue(cwd: Path, env: dict[str, str]) -> Path:
    """Same resolution order as capture-signal-core.sh: project queue wins, else the user's."""
    project = cwd / ".agents/skills/improve/signal-queue.md"
    if project.is_file():
        return project
    home = Path(env.get("AGENTS_SKILLS_HOME") or (Path(env.get("HOME", "~")).expanduser() / ".agents/skills"))
    return home / "improve/signal-queue.md"


def witness(state_script: Path, queue: Path, signal_id: str) -> str | None:
    """Count one more sighting of the signal the validator says this repeats."""
    completed = subprocess.run(
        [
            sys.executable, str(state_script), "witness",
            "--queue", str(queue),
            "--memory-dir", str(queue.parent / "memory"),
            "--signal-id", signal_id,
        ],
        text=True, capture_output=True,
    )
    if completed.returncode != 0:
        print(completed.stderr.strip(), file=sys.stderr)
        return None
    return completed.stdout.strip()


def capture(state_script: Path, queue: Path, verdict: dict[str, Any], timestamp: str) -> str | None:
    """Hand the finding to the lifecycle state machine, which owns the lock and the dedup."""
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.touch(exist_ok=True)
    # #43 owns what `risk_class` means; only its S-tier spelling maps onto the queue's
    # own type field, and anything else stays the default rather than inventing a tier.
    risk_class = str(verdict.get("risk_class") or "")
    signal_type = risk_class if risk_class in {"S1", "S2", "S3"} else "S2"
    completed = subprocess.run(
        [
            sys.executable, str(state_script), "capture",
            "--queue", str(queue),
            "--memory-dir", str(queue.parent / "memory"),
            "--timestamp", timestamp,
            "--target-skill", str(verdict["target_skill"]),
            "--type", signal_type,
            "--source", "session classifier",
            "--gap", str(verdict["gap"]),
            "--evidence-quote", str(verdict["evidence_quote"]),
        ],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        print(completed.stderr.strip(), file=sys.stderr)
        return None
    return completed.stdout.strip()


# --- entry point -----------------------------------------------------------------


def classify(payload: dict[str, Any], args: argparse.Namespace, env: dict[str, str]) -> dict[str, Any]:
    transcript = Path(payload.get("transcript_path", ""))
    rows = read_transcript(transcript)

    reason = skip_reason(env, rows)
    if reason:
        return {"skipped": reason, "skills": [], "captured": [], "deduped": []}

    skills = skills_used(rows)
    if not skills:
        # The cheap exit that makes this affordable: no Skill ran, so there is nothing to
        # attribute a gap to, and the model is never called.
        return {"skipped": "no skill invoked", "skills": [], "captured": [], "deduped": []}

    messages = user_messages(rows)
    excerpt = build_excerpt(skills, messages)
    queue = resolve_queue(Path(payload.get("cwd") or "."), env)
    scripts = Path(__file__).resolve().parent
    validator = Path(env.get("IMPROVE_VALIDATOR") or scripts / "validate-gap.sh")
    child_env = dict(env)
    child_env.setdefault("IMPROVE_VALIDATE_MODEL", args.model)

    state_script = scripts / "signal_state.py"
    memory_dir = queue.parent / "memory"
    captured: list[dict[str, Any]] = []
    deduped: list[dict[str, Any]] = []
    for skill in skills:
        # Only new signals are budgeted. A repeat adds nothing to the queue, so counting
        # it against the cap would spend the budget on findings nobody has to read.
        if len(captured) >= args.max_signals:
            break
        prior = known_signals(scripts / "memory.sh", memory_dir, skill)
        verdict = run_validator(validator, skill, with_known_signals(excerpt, prior), child_env)
        if verdict is None:
            continue
        duplicate_of = str(verdict.get("duplicate_of") or "")
        if duplicate_of:
            if witness(state_script, queue, duplicate_of):
                deduped.append({"signal_id": duplicate_of, "target_skill": verdict["target_skill"]})
            continue
        signal_id = capture(state_script, queue, verdict, args.timestamp)
        if signal_id:
            captured.append({"signal_id": signal_id, "target_skill": verdict["target_skill"]})
    return {"skipped": None, "skills": skills, "captured": captured, "deduped": deduped}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-signals", type=int, default=int(os.environ.get("IMPROVE_MAX_SIGNALS", DEFAULT_MAX_SIGNALS)))
    parser.add_argument("--model", default=os.environ.get("IMPROVE_VALIDATE_MODEL", DEFAULT_MODEL))
    parser.add_argument("--timestamp", default="")
    args = parser.parse_args(argv)
    if not args.timestamp:
        import datetime as dt
        args.timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    report = classify(payload, args, dict(os.environ))
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    # A hook must never be why a session fails to end.
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"session_classifier: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(0)
