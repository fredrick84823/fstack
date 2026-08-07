---
name: spawn
description: Hand this session's handoff doc to a fresh Claude in a new cmux surface.
argument-hint: "Path to the handoff doc (optional — defaults to the one just written)"
disable-model-invocation: true
allowed-tools: Bash, Read
---

Launch a fresh agent in a new cmux surface, pointed at the handoff doc this session just wrote.

## 1. Resolve the handoff doc

Use, in order: the argument, the path the handoff skill wrote earlier in this conversation, or the newest handoff doc on disk:

```bash
ls -t "${TMPDIR%/}"/*.md thoughts/shared/handoffs/**/*.md 2>/dev/null | head -5
```

`handoff` writes to `$TMPDIR`; `create-handoff` writes under `thoughts/shared/handoffs/`.

Done when you have one absolute path that exists. If the newest-file fallback is ambiguous, show the candidates and ask which one.

## 2. Open the surface

```bash
cmux new-surface --type terminal --working-directory "$PWD" --focus true
```

Prints `OK surface:<n> pane:<n> workspace:<n>` — the new surface ref is the first token after `OK`. Done when you have that ref.

## 3. Send the resume command

```bash
cmux send --surface surface:<n> 'claude "Read <handoff-path> and continue the work described there."\n'
cmux rename-tab --surface surface:<n> "<3-5 word title of the handed-off work>"
```

`\n` inside the quoted text is what presses Enter — without it the command sits unrun.

## 4. Confirm it took

```bash
cmux read-screen --surface surface:<n> | tail -20
```

Done when the screen shows Claude started and holding the handoff path. If it shows a shell prompt or an error instead, fix and re-send rather than reporting success.

Report the surface ref and the handoff path, one line.
