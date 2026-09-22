#!/usr/bin/env python3
"""Turn a claude stream-json transcript into a deterministic trace summary.

Usage: parse_trace.py stream.jsonl > trace-summary.json

Attribution rule: an assistant/user event carries parent_tool_use_id equal to
the Agent tool_use id that spawned it. Events without one belong to the main
session. Subagent tool calls are forwarded, so every tool call has an owner.
"""

import json
import re
import sys

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# A Bash command can edit files too, which would escape tool-level attribution.
BASH_WRITE = re.compile(
    r"(sed -i|>>|(?<![0-9&])>[^>&|]|\btee\b|\bcp\b|\bmv\b|write_text|open\([^)]*['\"]w|"
    r"\bpatch\b|git apply|<<\s*['\"]?EOF)")


def load(path):
    raw = open(path).read()
    dec = json.JSONDecoder()
    objs, i = [], 0
    while i < len(raw):
        while i < len(raw) and raw[i] in " \n\r\t":
            i += 1
        if i >= len(raw):
            break
        obj, i = dec.raw_decode(raw, i)
        objs.append(obj)
    return objs


def main(path):
    objs = load(path)
    agents = {}      # tool_use_id -> agent record
    order = []       # flat, ordered tool calls
    result = {}
    session_id = None
    pending = {}   # child Agent tool_use id -> spawning actor

    for ev in objs:
        session_id = session_id or ev.get("session_id")
        etype, sub = ev.get("type"), ev.get("subtype", "")

        if sub == "task_started":
            agents[ev["tool_use_id"]] = {
                "task_id": ev.get("task_id"),
                "tool_use_id": ev["tool_use_id"],
                "subagent_type": ev.get("subagent_type"),
                "description": ev.get("description"),
                "prompt": ev.get("prompt"),
                "spawn_depth": ev.get("spawn_depth"),
                "spawned_by": None,
                "status": "started",
                "tools": [],
                "files_written": [],
                "files_read": [],
                "bash": [],
                "bash_writes": [],
            }
        elif sub == "task_updated":
            for a in agents.values():
                if a["task_id"] == ev.get("task_id"):
                    a["status"] = ev.get("patch", {}).get("status", a["status"])
        elif etype == "result":
            result = {k: ev.get(k) for k in
                      ("subtype", "is_error", "num_turns", "duration_ms",
                       "total_cost_usd", "subagent_stats", "result")}
        elif etype == "assistant":
            actor = ev.get("parent_tool_use_id")
            content = ev.get("message", {}).get("content") or []
            if isinstance(content, str):
                continue
            for b in content:
                if b.get("type") != "tool_use":
                    continue
                name, inp = b.get("name"), b.get("input") or {}
                call = {
                    "actor": actor or "main",
                    "tool": name,
                    "tool_use_id": b.get("id"),
                    "file_path": inp.get("file_path"),
                    "command": inp.get("command"),
                    "skill": inp.get("skill"),
                    "agent_name": inp.get("name") if name == "Agent" else None,
                }
                order.append(call)
                if name == "Agent":
                    # link parentage once the child's task_started lands
                    child = b.get("id")
                    pending.setdefault(child, actor or "main")
                owner = agents.get(actor)
                if owner is not None:
                    owner["tools"].append(name)
                    if name in WRITE_TOOLS and inp.get("file_path"):
                        owner["files_written"].append(inp["file_path"])
                    elif name == "Read" and inp.get("file_path"):
                        owner["files_read"].append(inp["file_path"])
                    elif name == "Bash" and inp.get("command"):
                        owner["bash"].append(inp["command"])
                        if BASH_WRITE.search(inp["command"]):
                            owner["bash_writes"].append(inp["command"])

    for child, parent in pending.items():
        if child in agents:
            agents[child]["spawned_by"] = parent

    main_calls = [c for c in order if c["actor"] == "main"]
    summary = {
        "session_id": session_id,
        "result": result,
        "agent_count": len(agents),
        "agents": list(agents.values()),
        "main": {
            "tools": [c["tool"] for c in main_calls],
            "files_written": [c["file_path"] for c in main_calls
                              if c["tool"] in WRITE_TOOLS and c["file_path"]],
            "bash": [c["command"] for c in main_calls if c["tool"] == "Bash" and c["command"]],
            "bash_writes": [c["command"] for c in main_calls
                            if c["tool"] == "Bash" and c["command"] and BASH_WRITE.search(c["command"])],
        },
        "order": order,
    }
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main(sys.argv[1])
