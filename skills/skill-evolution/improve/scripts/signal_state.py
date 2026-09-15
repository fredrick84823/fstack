#!/usr/bin/env python3
"""Transactional lifecycle state for improve signals.

signal-queue.md is the sole current-status authority. signals.jsonl is immutable
raw evidence, transitions.jsonl is an append-only decision log, and
skill-graph.json is a rebuildable lookup projection.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterator


HEADER_RE = re.compile(r"^## \[(?P<timestamp>[^]]+)] (?P<skill>.+)$")
FIELD_RE = re.compile(r"^- \*\*(?P<name>[^*]+)\*\*: ?(?P<value>.*)$")
ALLOWED_STATUS = {"pending", "resolved", "rejected", "deferred"}
TERMINAL_STATUS = ALLOWED_STATUS - {"pending"}


class StateError(RuntimeError):
    pass


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "unknown"


def make_signal_id(timestamp: str, target_skill: str, gap: str) -> str:
    digest = hashlib.sha1(f"{timestamp}|{target_skill}|{gap}".encode()).hexdigest()[:8]
    compact_ts = re.sub(r"[-:+T]", "", timestamp)
    return f"sig_{compact_ts}_{slugify(target_skill)}_{digest}"


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_gap(value: str) -> str:
    return " ".join(value.split())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise StateError(f"invalid JSONL at {path}:{number}: {exc}") from exc
    return records


def render_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in records)


def read_graph(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "updated_at": None, "signals": [], "claims": [], "eval_cases": [], "versions": []}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise StateError(f"invalid JSON at {path}: {exc}") from exc


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


@contextlib.contextmanager
def lifecycle_lock(queue: Path) -> Iterator[None]:
    lock_path = queue.parent / ".signal-lifecycle.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def parse_queue(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines(keepends=True)
    entries: list[dict[str, Any]] = []
    starts: list[tuple[int, re.Match[str]]] = []
    in_comment = False
    for index, line in enumerate(lines):
        if "<!--" in line:
            in_comment = True
        match = None if in_comment else HEADER_RE.match(line.rstrip("\n"))
        if match:
            starts.append((index, match))
        if "-->" in line:
            in_comment = False
    for position, (start, match) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        fields: dict[str, str] = {}
        for line in lines[start:end]:
            field_match = FIELD_RE.match(line.rstrip("\n"))
            if field_match:
                fields[field_match.group("name")] = field_match.group("value")
        entries.append({
            "start": start,
            "end": end,
            "timestamp": match.group("timestamp"),
            "target_skill": match.group("skill"),
            "fields": fields,
        })
    return entries


def queue_lines(path: Path) -> tuple[str, list[str], list[dict[str, Any]]]:
    text = path.read_text() if path.exists() else "# Signal Queue\n"
    return text, text.splitlines(keepends=True), parse_queue(text)


def find_queue_entry(entries: list[dict[str, Any]], signal_id: str) -> dict[str, Any]:
    matches = [entry for entry in entries if entry["fields"].get("signal_id") == signal_id]
    if len(matches) != 1:
        raise StateError(f"expected exactly one queue entry for {signal_id}, found {len(matches)}")
    return matches[0]


def update_entry_fields(lines: list[str], entry: dict[str, Any], updates: dict[str, str]) -> list[str]:
    block = list(lines[entry["start"]:entry["end"]])
    field_positions: dict[str, int] = {}
    last_field = 1
    for index, line in enumerate(block):
        match = FIELD_RE.match(line.rstrip("\n"))
        if match:
            field_positions[match.group("name")] = index
            last_field = index + 1
    for name, value in updates.items():
        rendered = f"- **{name}**: {value}\n"
        if name in field_positions:
            block[field_positions[name]] = rendered
        else:
            block.insert(last_field, rendered)
            last_field += 1
            field_positions[name] = last_field - 1
    return lines[:entry["start"]] + block + lines[entry["end"]:]


def ensure_unique(records: list[dict[str, Any]], signal_id: str, label: str, *, allow_missing: bool = False) -> dict[str, Any] | None:
    matches = [record for record in records if record.get("signal_id") == signal_id]
    if len(matches) > 1 or (not allow_missing and len(matches) != 1):
        raise StateError(f"expected {'at most' if allow_missing else 'exactly'} one {label} record for {signal_id}, found {len(matches)}")
    return matches[0] if matches else None


def raw_record_from_entry(entry: dict[str, Any], signal_id: str, *, recovered: bool = False) -> dict[str, Any]:
    fields = entry["fields"]
    return {
        "signal_id": signal_id,
        "timestamp": entry["timestamp"],
        "target_skill": entry["target_skill"],
        "affected_rule": fields.get("affected_rule", "unknown"),
        "gap_type": fields.get("gap_type", "unknown"),
        "expected_behavior": fields.get("expected_behavior", ""),
        "actual_behavior": fields.get("actual_behavior", ""),
        "evidence_count": 1,
        "status": "pending",
        "status_semantics": "captured_at_ingest",
        "type": fields.get("type", "S2"),
        "source": fields.get("source", "reconciliation recovery" if recovered else "unknown"),
        "gap": fields.get("gap", ""),
        "capture_recovered": recovered,
        "links": {"duplicates": [], "tested_by": [], "caused_false_positive": []},
    }


def graph_record_from_raw(raw: dict[str, Any], current_status: str) -> dict[str, Any]:
    return {
        "signal_id": raw["signal_id"],
        "timestamp": raw.get("timestamp"),
        "target_skill": raw.get("target_skill"),
        "affected_rule": raw.get("affected_rule", "unknown"),
        "gap_type": raw.get("gap_type", "unknown"),
        "status": current_status,
        "status_source": "signal-queue.md",
    }


def append_transition_once(path: Path, signal_id: str, from_status: str, to_status: str, decision_by: str, candidate_id: str) -> None:
    records = read_jsonl(path)
    decision_seed = f"{signal_id}|{to_status}|{candidate_id}"
    decision_id = "decision_" + hashlib.sha256(decision_seed.encode()).hexdigest()[:16]
    if any(record.get("decision_id") == decision_id for record in records):
        return
    records.append({
        "decision_id": decision_id,
        "signal_id": signal_id,
        "timestamp": now_iso(),
        "from_status": from_status,
        "to_status": to_status,
        "decision_by": decision_by,
        "candidate_id": candidate_id or None,
    })
    atomic_write(path, render_jsonl(records))


def reconcile_locked(queue: Path, memory_dir: Path, signal_id: str, apply: bool) -> dict[str, Any]:
    text, lines, entries = queue_lines(queue)
    entry = find_queue_entry(entries, signal_id)
    queue_status = entry["fields"].get("status", "pending")
    if queue_status not in ALLOWED_STATUS:
        raise StateError(f"invalid queue status {queue_status!r} for {signal_id}")

    raw_path = memory_dir / "signals.jsonl"
    graph_path = memory_dir / "skill-graph.json"
    raw_records = read_jsonl(raw_path)
    raw = ensure_unique(raw_records, signal_id, "raw signal", allow_missing=True)
    graph = read_graph(graph_path)
    graph_signals = graph.setdefault("signals", [])
    graph_record = ensure_unique(graph_signals, signal_id, "graph signal", allow_missing=True)

    report = {
        "signal_id": signal_id,
        "queue_status": queue_status,
        "raw_evidence": "present" if raw else "missing",
        "graph_status": graph_record.get("status") if graph_record else "missing",
        "memory_sync": entry["fields"].get("memory_sync", "missing"),
        "changes": [],
        "applied": apply,
    }
    if raw is None:
        report["changes"].append("create_missing_raw_evidence")
    if graph_record is None:
        report["changes"].append("create_missing_graph_projection")
    elif graph_record.get("status") != queue_status or graph_record.get("status_source") != "signal-queue.md":
        report["changes"].append("update_graph_projection")
    if entry["fields"].get("memory_sync") != "synced":
        report["changes"].append("mark_queue_memory_synced")

    if not apply:
        return report

    if raw is None:
        raw = raw_record_from_entry(entry, signal_id, recovered=True)
        raw_records.append(raw)
        atomic_write(raw_path, render_jsonl(raw_records))

    projected = graph_record_from_raw(raw, queue_status)
    if graph_record is None:
        graph_signals.append(projected)
    else:
        graph_record.clear()
        graph_record.update(projected)
    graph["updated_at"] = now_iso()
    atomic_write(graph_path, json.dumps(graph, ensure_ascii=False, indent=2) + "\n")

    # Re-read authority after projection commits, then update only its sync marker.
    _, current_lines, current_entries = queue_lines(queue)
    current_entry = find_queue_entry(current_entries, signal_id)
    current_lines = update_entry_fields(current_lines, current_entry, {"memory_sync": "synced"})
    atomic_write(queue, "".join(current_lines))
    return report


def command_capture(args: argparse.Namespace) -> None:
    queue = Path(args.queue).expanduser().resolve()
    memory_dir = Path(args.memory_dir).expanduser().resolve()
    signal_id = make_signal_id(args.timestamp, args.target_skill, args.gap)
    with lifecycle_lock(queue):
        text, lines, entries = queue_lines(queue)
        if any(entry["fields"].get("signal_id") == signal_id for entry in entries):
            raise StateError(f"duplicate queue signal_id: {signal_id}")
        raw_records = read_jsonl(memory_dir / "signals.jsonl")
        if ensure_unique(raw_records, signal_id, "raw signal", allow_missing=True) is not None:
            raise StateError(f"orphan raw signal_id already exists: {signal_id}")
        graph = read_graph(memory_dir / "skill-graph.json")
        if ensure_unique(graph.setdefault("signals", []), signal_id, "graph signal", allow_missing=True) is not None:
            raise StateError(f"orphan graph signal_id already exists: {signal_id}")

        suffix = "" if text.endswith("\n") else "\n"
        block = (
            f"{suffix}\n## [{args.timestamp}] {args.target_skill}\n\n"
            f"- **signal_id**: {signal_id}\n"
            f"- **type**: {args.type}\n"
            f"- **source**: {args.source}\n"
            f"- **gap**: {args.gap}\n"
            "- **status**: pending\n"
            "- **memory_sync**: pending\n"
        )
        atomic_write(queue, text + block)

        try:
            _, _, entries = queue_lines(queue)
            entry = find_queue_entry(entries, signal_id)
            raw = raw_record_from_entry(entry, signal_id)
            raw_records.append(raw)
            atomic_write(memory_dir / "signals.jsonl", render_jsonl(raw_records))
            graph["signals"].append(graph_record_from_raw(raw, "pending"))
            graph["updated_at"] = now_iso()
            atomic_write(memory_dir / "skill-graph.json", json.dumps(graph, ensure_ascii=False, indent=2) + "\n")
            reconcile_locked(queue, memory_dir, signal_id, apply=True)
        except Exception:
            _, failed_lines, failed_entries = queue_lines(queue)
            failed_entry = find_queue_entry(failed_entries, signal_id)
            failed_lines = update_entry_fields(failed_lines, failed_entry, {"memory_sync": "failed"})
            atomic_write(queue, "".join(failed_lines))
            raise
    print(signal_id)


def command_adopt_legacy(args: argparse.Namespace) -> None:
    queue = Path(args.queue).expanduser().resolve()
    memory_dir = Path(args.memory_dir).expanduser().resolve()
    with lifecycle_lock(queue):
        _, lines, entries = queue_lines(queue)
        queue_matches = [
            entry for entry in entries
            if not entry["fields"].get("signal_id")
            and entry["timestamp"] == args.timestamp
            and entry["target_skill"] == args.target_skill
            and normalize_gap(entry["fields"].get("gap", "")) == normalize_gap(args.gap)
        ]
        raw_records = read_jsonl(memory_dir / "signals.jsonl")
        raw_matches = [
            record for record in raw_records
            if record.get("timestamp") == args.timestamp
            and record.get("target_skill") == args.target_skill
            and normalize_gap(record.get("gap", "")) == normalize_gap(args.gap)
        ]
        if len(queue_matches) != 1 or len(raw_matches) != 1:
            raise StateError(f"legacy adoption requires one queue and one raw match; found queue={len(queue_matches)}, raw={len(raw_matches)}")
        signal_id = raw_matches[0]["signal_id"]
        if any(entry["fields"].get("signal_id") == signal_id for entry in entries):
            raise StateError(f"signal_id already used in queue: {signal_id}")
        lines = update_entry_fields(lines, queue_matches[0], {"signal_id": signal_id, "memory_sync": "pending"})
        atomic_write(queue, "".join(lines))
        reconcile_locked(queue, memory_dir, signal_id, apply=True)
    print(signal_id)


def command_prepare(args: argparse.Namespace) -> None:
    queue = Path(args.queue).expanduser().resolve()
    memory_dir = Path(args.memory_dir).expanduser().resolve()
    with lifecycle_lock(queue):
        _, lines, entries = queue_lines(queue)
        entry = find_queue_entry(entries, args.signal_id)
        status = entry["fields"].get("status", "pending")
        if status != "pending":
            raise StateError(f"cannot prepare {args.signal_id} from {status}")
        existing = entry["fields"].get("apply_intent")
        if existing and existing != args.candidate_id:
            if args.supersede_candidate_id != existing:
                raise StateError(f"conflicting apply_intent for {args.signal_id}: {existing}")
        # Validate projections before recording intent.
        reconcile_locked(queue, memory_dir, args.signal_id, apply=False)
        _, lines, entries = queue_lines(queue)
        entry = find_queue_entry(entries, args.signal_id)
        updates = {
            "apply_intent": args.candidate_id,
            "apply_state": "prepared",
            "prepared_at": now_iso(),
        }
        if existing and existing != args.candidate_id:
            updates["superseded_apply_intent"] = existing
        lines = update_entry_fields(lines, entry, updates)
        atomic_write(queue, "".join(lines))
    print(args.candidate_id)


def command_transition(args: argparse.Namespace) -> None:
    queue = Path(args.queue).expanduser().resolve()
    memory_dir = Path(args.memory_dir).expanduser().resolve()
    with lifecycle_lock(queue):
        _, lines, entries = queue_lines(queue)
        entry = find_queue_entry(entries, args.signal_id)
        current = entry["fields"].get("status", "pending")
        if args.to not in TERMINAL_STATUS:
            raise StateError(f"invalid terminal status: {args.to}")
        if current in TERMINAL_STATUS and current != args.to:
            raise StateError(f"conflicting terminal transition {current} -> {args.to}")
        if current not in {"pending", args.to}:
            raise StateError(f"illegal transition {current} -> {args.to}")
        candidate_id = args.candidate_id or ""
        if args.to == "resolved":
            intent = entry["fields"].get("apply_intent")
            if not candidate_id or intent != candidate_id:
                raise StateError("resolved transition requires matching --candidate-id and apply_intent")
        # Selected-signal preflight happens before lifecycle mutation.
        reconcile_locked(queue, memory_dir, args.signal_id, apply=False)

        if current == "pending":
            updates = {
                "status": args.to,
                "decision_by": args.decision_by,
                "decided_at": now_iso(),
                "memory_sync": "pending",
            }
            if candidate_id:
                updates.update({"candidate_id": candidate_id, "apply_state": "applied"})
            lines = update_entry_fields(lines, entry, updates)
            atomic_write(queue, "".join(lines))
        append_transition_once(memory_dir / "transitions.jsonl", args.signal_id, current, args.to, args.decision_by, candidate_id)
        try:
            reconcile_locked(queue, memory_dir, args.signal_id, apply=True)
        except Exception as exc:
            _, failed_lines, failed_entries = queue_lines(queue)
            failed_entry = find_queue_entry(failed_entries, args.signal_id)
            failed_lines = update_entry_fields(failed_lines, failed_entry, {"memory_sync": f"failed: {type(exc).__name__}"})
            atomic_write(queue, "".join(failed_lines))
            raise
    print(args.to)


def command_reconcile(args: argparse.Namespace) -> None:
    queue = Path(args.queue).expanduser().resolve()
    memory_dir = Path(args.memory_dir).expanduser().resolve()
    with lifecycle_lock(queue):
        report = reconcile_locked(queue, memory_dir, args.signal_id, apply=args.apply)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture")
    capture.add_argument("--queue", required=True)
    capture.add_argument("--memory-dir", required=True)
    capture.add_argument("--timestamp", required=True)
    capture.add_argument("--target-skill", required=True)
    capture.add_argument("--type", choices=["S1", "S2", "S3"], required=True)
    capture.add_argument("--source", required=True)
    capture.add_argument("--gap", required=True)
    capture.set_defaults(func=command_capture)

    adopt = subparsers.add_parser("adopt-legacy")
    adopt.add_argument("--queue", required=True)
    adopt.add_argument("--memory-dir", required=True)
    adopt.add_argument("--timestamp", required=True)
    adopt.add_argument("--target-skill", required=True)
    adopt.add_argument("--gap", required=True)
    adopt.set_defaults(func=command_adopt_legacy)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--queue", required=True)
    prepare.add_argument("--memory-dir", required=True)
    prepare.add_argument("--signal-id", required=True)
    prepare.add_argument("--candidate-id", required=True)
    prepare.add_argument("--supersede-candidate-id")
    prepare.set_defaults(func=command_prepare)

    transition = subparsers.add_parser("transition")
    transition.add_argument("--queue", required=True)
    transition.add_argument("--memory-dir", required=True)
    transition.add_argument("--signal-id", required=True)
    transition.add_argument("--to", choices=sorted(TERMINAL_STATUS), required=True)
    transition.add_argument("--decision-by", required=True)
    transition.add_argument("--candidate-id")
    transition.set_defaults(func=command_transition)

    reconcile = subparsers.add_parser("reconcile")
    reconcile.add_argument("--queue", required=True)
    reconcile.add_argument("--memory-dir", required=True)
    reconcile.add_argument("--signal-id", required=True)
    reconcile.add_argument("--apply", action="store_true")
    reconcile.set_defaults(func=command_reconcile)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except StateError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
