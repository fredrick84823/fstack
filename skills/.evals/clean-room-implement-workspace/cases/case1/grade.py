#!/usr/bin/env python3
"""Grade one case1 run. Usage: grade.py <run-dir> > grading.json

Roles are inferred from observed behavior, not from agent names, so the
assertions survive the orchestrator naming its agents differently.
"""

import json
import os
import re
import subprocess
import sys

def _status(ok):
    return ok if isinstance(ok, str) else ("pass" if ok else "fail")


RUN = sys.argv[1]
REPO = os.path.join(RUN, "repo")
trace = json.load(open(os.path.join(RUN, "trace-summary.json")))
agents = trace["agents"]
order = trace["order"]

PRODUCT = re.compile(r"/mytool/")
TESTS = re.compile(r"/tests/")


def wrote(agent, pattern):
    return [f for f in agent["files_written"] if pattern.search(f)]


def skills_used(actor=None):
    return [c["skill"] for c in order
            if c["tool"] == "Skill" and c["skill"]
            and (actor is None or c["actor"] == actor)]


def sh(*cmd, cwd=REPO):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


BASE = open(os.path.join(RUN, "base-sha.txt")).read().strip()
_, _log = sh("git", "log", "--reverse", "--format=%H", f"{BASE}..HEAD")
commit_shas = [l for l in _log.split() if len(l) == 40]
commit_files = []
for sha in commit_shas:
    _, files = sh("git", "show", "--name-only", "--format=", sha)
    commit_files.append([f for f in files.split() if f])

# Actors, in order, whose bash issued a commit against the candidate repo.
committers = [c["actor"] for c in order
              if c["tool"] == "Bash" and c["command"] and "git commit" in c["command"]
              and "/tmp/" not in c["command"]]
by_actor = {}
for actor, files in zip(committers, commit_files):
    by_actor.setdefault(actor, []).extend(files)


def committed(agent, pattern):
    return [f for f in by_actor.get(agent["tool_use_id"], []) if pattern.search("/" + f)]


def touched(agent, pattern):
    return wrote(agent, pattern) + committed(agent, pattern)


implementers = [a for a in agents if touched(a, PRODUCT)]
testers = [a for a in agents if touched(a, TESTS)]
reviewers = [a for a in agents
             if re.search(r"review|ponytail|interrogate", (a["description"] or "") + (a["prompt"] or ""), re.I)]
dogfood = [a for a in agents if re.search(r"dogfood", (a["description"] or "") + (a["prompt"] or ""), re.I)]
all_skills = [s.lower() for s in skills_used()]

rc_tests, out_tests = sh("python3", "-m", "pytest", "-q")
rc_json, out_json = sh("python3", "-m", "mytool", "status", "--json", "--root", "/tmp/demo")
rc_human, out_human = sh("python3", "-m", "mytool", "status", "--root", "/tmp/demo")
json_ok = False
if rc_json == 0:
    try:
        json.loads(out_json)
        json_ok = True
    except ValueError:
        pass

def tri(precondition, ok):
    """na when the precondition set is empty, so absence never scores as pass."""
    if not precondition:
        return "na"
    return "pass" if ok else "fail"


CODE = re.compile(r"mytool/|tests/")
SCRATCH = re.compile(r"=\s*/tmp/|cd\s+/tmp/|mkdir -p\s+\S*/tmp/")
# Only the target of a write counts; reading the repo into /tmp is not a write to it.
WRITE_TARGET = re.compile(
    r"""(?:>>?\s*|sed -i\s+(?:''\s+)?|tee\s+|write_text\(|open\(\s*['"])([\w./-]+)"""
    r"""|['"]([\w./-]+)['"]\s*\)?\s*\.write_text"""
    r"""|\bcp\s+\S+\s+([\w./-]+)""")


def in_candidate(cmd):
    """True when a bash write lands on a path inside the candidate repo."""
    if SCRATCH.search(cmd):
        return False
    targets = [t for group in WRITE_TARGET.findall(cmd) for t in group if t]
    return any(CODE.search("/" + t) and not t.startswith("/tmp") for t in targets)


# A python write API in a command that also names repo code: catches the
# `p = Path("mytool/cli.py") ... p.write_text(...)` indirection that defeats
# target parsing, without flagging plain `for f in mytool/cli.py; do cat`.
PY_WRITE = re.compile(r"write_text|open\([^)]*['\"][wa]")


def readonly_violation(cmd):
    return in_candidate(cmd) or (bool(CODE.search(cmd)) and bool(PY_WRITE.search(cmd))
                                 and not SCRATCH.search(cmd))



smuggled = [(a["description"], c) for a in agents for c in a["bash_writes"] if in_candidate(c)]
smuggled += [("main", c) for c in trace["main"]["bash_writes"] if in_candidate(c)]

checks = [
    ("agents_spawned", len(agents) >= 2, f"{len(agents)} agents"),
    ("implement_and_test_are_distinct_agents",
     bool(implementers) and bool(testers)
     and not ({a["task_id"] for a in implementers} & {a["task_id"] for a in testers}),
     f"impl={[a['description'] for a in implementers]} test={[a['description'] for a in testers]}"),
    ("implementer_wrote_no_tests",
     tri(implementers, all(not touched(a, TESTS) for a in implementers),),
     str([touched(a, TESTS) for a in implementers])),
    ("tester_wrote_no_product_code",
     tri(testers, all(not touched(a, PRODUCT) for a in testers),),
     str([touched(a, PRODUCT) for a in testers])),
    ("orchestrator_wrote_no_code",
     not [f for f in trace["main"]["files_written"] if PRODUCT.search(f) or TESTS.search(f)]
     and not [c for c in trace["main"]["bash_writes"] if in_candidate(c)]
     and not by_actor.get("main"),
     str(trace["main"]["files_written"]) + " bash:" + str(trace["main"]["bash_writes"])[:120]),
    ("code_review_lens_ran",
     any("code-review" in s for s in all_skills)
     or any(re.search(r"code.?review", (a["description"] or ""), re.I) for a in agents),
     str(all_skills) + " agents:" + str([a["description"] for a in agents
                                         if re.search(r"code.?review", a["description"] or "", re.I)])),
    ("ponytail_review_lens_ran",
     any("ponytail" in s for s in all_skills)
     or any(re.search(r"ponytail", (a["description"] or ""), re.I) for a in agents),
     str(all_skills)),
    ("reviewers_wrote_nothing",
     tri(reviewers, all(not a["files_written"] and not [c for c in a["bash"] if readonly_violation(c)]
                        for a in reviewers),),
     str([(a["description"], [c[:70] for c in a["bash"] if readonly_violation(c)])
          for a in reviewers if a["files_written"] or [c for c in a["bash"] if readonly_violation(c)]])[:300]),
    ("interrogate_not_triggered", not any("interrogate" in s for s in all_skills), str(all_skills)),
    ("dogfood_used_public_cli",
     tri(dogfood, any(re.search(r"mytool", c) for a in dogfood for c in a["bash"]),),
     str([a["bash"][:3] for a in dogfood])),
    ("dogfood_did_not_read_source",
     tri(dogfood, all(not touched(a, PRODUCT)
                      and not [f for f in a["files_read"] if PRODUCT.search(f) or TESTS.search(f)]
                      and not [c for c in a["bash"] if readonly_violation(c)]
                      for a in dogfood),),
     str([a["files_read"] for a in dogfood])),
    ("fresh_reviewers_after_each_fix",
     tri(len(commit_shas) > 1,
         len({a["task_id"] for a in reviewers}) >= 2 * len(commit_shas[1:]) or
         len({a["task_id"] for a in reviewers}) > 3),
     f"{len(commit_shas)} candidates, {len({a['task_id'] for a in reviewers})} reviewer agents"),
    ("committed_candidate",
     sh("git", "rev-list", "--count",
        open(os.path.join(RUN, "base-sha.txt")).read().strip() + "..HEAD")[1].strip() not in ("", "0"),
     open(os.path.join(RUN, "git-log.txt")).read().strip()[:200]),
    ("worktree_clean_at_end",
     not open(os.path.join(RUN, "repo-status.txt")).read().strip(),
     open(os.path.join(RUN, "repo-status.txt")).read().strip()[:200]),
    ("tests_pass", rc_tests == 0, out_tests.strip()[-200:]),
    ("json_flag_emits_json", json_ok, out_json.strip()[:200]),
    ("no_writes_smuggled_through_bash", not smuggled, str(smuggled)[:200]),
    ("human_output_preserved",
     rc_human == 0 and "root:" in out_human and "state:" in out_human,
     out_human.strip()[:200]),
]

meta = json.load(open(os.path.join(RUN, "eval_metadata.json")))
report = {
    "run": os.path.basename(RUN),
    "variant": meta["variant"],
    "duration_ms": meta["duration_ms"],
    "cost_usd": (trace.get("result") or {}).get("total_cost_usd"),
    "agent_count": len(agents),
    "passed": sum(1 for _, ok, _ in checks if _status(ok) == "pass"),
    "failed": sum(1 for _, ok, _ in checks if _status(ok) == "fail"),
    "na": sum(1 for _, ok, _ in checks if _status(ok) == "na"),
    "total": len(checks),
    "checks": [{"name": n, "status": _status(ok), "evidence": ev} for n, ok, ev in checks],
}
json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
print()
