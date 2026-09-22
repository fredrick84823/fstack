# clean-room-implement eval workspace

Grades whether the [`clean-room-implement`](../../engineering/clean-room-implement/SKILL.md) skill's agents
actually take the expected actions. The skill's contract is process isolation, and an
orchestrator can print a convincing report without ever spawning a distinct agent — so
nothing here grades the final report. Assertions read the execution trace and the git
history the run left behind.

## Layout

```text
bin/run_wave.sh        launch with-skill and baseline runs detached, same wave
bin/run_case.sh        one variant: private fixture copy -> claude -p -> artifacts
bin/parse_trace.py     stream-json -> per-agent tools, files, bash, spawn depth
cases/case1/prompt.txt the task, with the /clean-room-implement prefix
cases/case1/grade.py   behavioral assertions for that case
fixtures/              committed starting repos, one per case
iteration-N/           benchmark.json + benchmark.md for each round
```

`runs/` is local output and is not committed: transcripts run to megabytes and carry
absolute paths.

## Running one

```bash
bin/run_wave.sh case1                 # both variants, detached
python3 cases/case1/grade.py runs/<run-dir> | python3 -m json.tool
```

A with-skill run costs roughly $8–10 and takes 20–35 minutes; the baseline is seconds.

## How roles are identified

By behavior, never by the name the orchestrator picked. Whoever writes or commits
`mytool/` is the implementer; whoever writes or commits `tests/` is the tester. A run
that renames its agents still grades correctly.

Writes are attributed from `Write`/`Edit` tool calls, from the files of the commit each
actor's `git commit` produced, and — for roles that must not write at all — from write
verbs aimed at repository paths inside `Bash` commands.
