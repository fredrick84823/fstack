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
- At most `--max-signals` validator calls per session (N=3 ≈ $0.12), so neither the queue
  nor the bill can run away on one session.
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


# Caps validator calls, not just captures. Each call is one `claude -p`; #43 measured
# ~$0.04 each, so N=3 is also the ~$0.12 per-session ceiling. Capping captures alone
# would leave a ten-skill session free to spend $0.40 before hitting any limit.
DEFAULT_MAX_SIGNALS = 3
DEFAULT_MODEL = "claude-sonnet-5"
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
    # CLAUDE_CODE_CHILD_SESSION is deliberately not a gate: it read "1" in a plain
    # interactive session on 2026-09-16, which silently skipped every real session.
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


def candidates(rows: Iterable[dict[str, Any]]) -> list[tuple[str, str]]:
    """`(skill, user message)` pairs — one proposed gap each, in transcript order.

    validate-gap.sh validates *a* claim; it does not go looking for one. Measured against
    the real validator (2026-09-15, haiku-4.5, 3 runs each): handing it a probe sentence
    in the `gap` slot and asking it to find the gap itself accepted **0/3** on a
    transcript that plainly contained one — it judged the probe, twice as `uncertain` and
    once as `placeholder`. Handing it every user turn joined together rejected as
    `misroute`, because a blob spanning two skills belongs to neither. Handing it one
    user sentence accepted **3/3**. So the candidate is one sentence.

    The skill paired with it is whichever Skill call most recently preceded it — the one
    that was running when the user said this. That is transcript order, not a guess about
    what the sentence means; the validator still re-checks attribution and rejects
    `misroute` when the pairing is wrong.
    """
    pairs: list[tuple[str, str]] = []
    current: str | None = None
    for row in rows:
        if row.get("isSidechain"):
            continue
        if row.get("type") == "assistant":
            for block in content_blocks(row):
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Skill":
                    skill = (block.get("input") or {}).get("skill")
                    if skill:
                        current = skill
        elif current:
            for message in user_messages([row]):
                pairs.append((current, message))
    return pairs


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


def render_known_signals(signals: list[dict[str, str]]) -> str:
    """`<signal_id>\t<gap>` per line — validate-gap.sh's fourth positional argument."""
    return "\n".join(f"{item['signal_id']}\t{normalize(item['gap'])}" for item in signals)


def normalize(value: str) -> str:
    return " ".join(value.split())


# --- validator -------------------------------------------------------------------


def run_validator(
    validator: Path, skill: str, candidate: str, excerpt: str, known: str, env: dict[str, str],
) -> dict[str, Any] | None:
    """Ask #43's validator about one candidate sentence, or None if it did not answer.

    Positional contract: `<target_skill> <gap> [excerpt] [known_signals]`.

    The script is fail-closed: non-zero exit with nothing on stdout when `claude` or
    `jq` is missing. That distinction matters — a caller that reads silence as "reject"
    is fine, one that reads it as "accept" would accept everything the day auth expires.
    """
    try:
        completed = subprocess.run(
            [str(validator), skill, candidate, excerpt, known],
            text=True, capture_output=True, env=env, timeout=180,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        print(f"validate-gap: {completed.stderr.strip()[:200]}", file=sys.stderr)
        return None
    try:
        verdict = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    return verdict if isinstance(verdict, dict) else None


# --- capture ---------------------------------------------------------------------


def resolve_queue(cwd: Path, env: dict[str, str]) -> Path:
    """Same resolution order as capture-signal-core.sh: project queue wins, else the user's."""
    project = cwd / ".agents/skills/improve/signal-queue.md"
    if project.is_file():
        return project
    home = Path(env.get("AGENTS_SKILLS_HOME") or (Path(env.get("HOME", "~")).expanduser() / ".agents/skills"))
    return home / "improve/signal-queue.md"


def capture(state_script: Path, queue: Path, verdict: dict[str, Any], timestamp: str) -> str | None:
    """Hand the finding to the lifecycle state machine, which owns the lock and the dedup.

    `type` is always S2. `risk_class` is #43's taxonomy of *why a candidate was judged
    the way it was* (`valid_gap`, `misroute`, `one_shot_pref`, …); the queue's `type` is
    S1/S2/S3 severity. They are different questions, so the verdict's answer to one is
    stored as itself rather than bent into the other.

    `--duplicate-of` routes a repeat the validator recognised by meaning into the same
    branch as one matched by text, so the regression rule lives in exactly one place.
    """
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.touch(exist_ok=True)
    completed = subprocess.run(
        [
            sys.executable, str(state_script), "capture",
            "--queue", str(queue),
            "--memory-dir", str(queue.parent / "memory"),
            "--timestamp", timestamp,
            "--target-skill", str(verdict["target_skill"]),
            "--type", "S2",
            "--source", "session classifier",
            "--gap", str(verdict["gap"]),
            "--evidence-quote", str(verdict.get("evidence_quote") or ""),
            "--expected", str(verdict.get("expected") or ""),
            "--actual", str(verdict.get("actual") or ""),
            "--risk-class", str(verdict.get("risk_class") or ""),
            "--duplicate-of", str(verdict.get("duplicate_of") or ""),
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
        return {"skipped": reason, "skills": [], "calls": 0, "captured": [], "deduped": []}

    skills = skills_used(rows)
    if not skills:
        # The cheap exit that makes this affordable: no Skill ran, so there is nothing to
        # attribute a gap to, and the model is never called.
        return {"skipped": "no skill invoked", "skills": [], "calls": 0, "captured": [], "deduped": []}

    messages = user_messages(rows)
    excerpt = build_excerpt(skills, messages)
    queue = resolve_queue(Path(payload.get("cwd") or "."), env)
    scripts = Path(__file__).resolve().parent
    validator = Path(env.get("IMPROVE_VALIDATOR") or scripts / "validate-gap.sh")
    child_env = dict(env)
    child_env.setdefault("IMPROVE_VALIDATOR_MODEL", args.model)

    state_script = scripts / "signal_state.py"
    memory_dir = queue.parent / "memory"
    # Most recent last: a correction late in a session is the one still worth acting on,
    # and the budget is spent from that end.
    queued = candidates(rows)[-args.max_signals:]
    captured: list[dict[str, Any]] = []
    deduped: list[dict[str, Any]] = []
    for skill, candidate in queued:
        prior = known_signals(scripts / "memory.sh", memory_dir, skill)
        verdict = run_validator(
            validator, skill, candidate, excerpt, render_known_signals(prior), child_env,
        )
        if verdict is None:
            continue
        duplicate_of = str(verdict.get("duplicate_of") or "")
        # A duplicate arrives as a *reject* carrying an id — the schema forbids an accept
        # from pointing at an existing signal. So the id is read before the verdict is,
        # otherwise every semantic duplicate is dropped on the floor instead of counted.
        if not duplicate_of and verdict.get("verdict") != "accept":
            continue
        signal_id = capture(state_script, queue, verdict, args.timestamp)
        if not signal_id:
            continue
        entry = {"signal_id": signal_id, "target_skill": verdict["target_skill"],
                 "risk_class": verdict.get("risk_class")}
        # capture echoes back the id it actually touched: the existing signal when the
        # repeat was absorbed, a fresh one when the gap came back after being resolved.
        if duplicate_of and signal_id == duplicate_of:
            deduped.append(entry)
        else:
            captured.append(entry)
    return {"skipped": None, "skills": skills, "calls": len(queued),
            "captured": captured, "deduped": deduped}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-signals", type=int,
        default=int(os.environ.get("IMPROVE_MAX_SIGNALS", DEFAULT_MAX_SIGNALS)),
        help="validator calls per session, which also bounds signals captured (default 3)",
    )
    parser.add_argument("--model", default=os.environ.get("IMPROVE_VALIDATOR_MODEL", DEFAULT_MODEL))
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
