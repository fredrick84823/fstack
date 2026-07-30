# Firstmate: Pi Coding-Agent Team Lead

Firstmate packages a small coding-agent team around Pi. The design is inspired by Kun Chen's FirstMate + Herdr + Pi setup discussed in [L8 Principal's Agentic Engineering Setup](https://www.youtube.com/watch?v=8ZgpAXe5V5w), while remaining a local fstack implementation.

## Architecture

```text
thought dump
    |
    +--> local project memory (secret-screened JSONL)
    |
    v
Firstmate (owns intent, coordination, and verification)
    |
    +--> firstmate_delegate [{ teammate, task }]
    |         |
    |         +--> isolated Pi: scout
    |         +--> isolated Pi: planner
    |         +--> isolated Pi: worker
    |         +--> isolated Pi: reviewer
    |
    +--> firstmate_memory remember | recall | forget | status
```

The public surface is intentionally small. One delegation tool handles both single and parallel work; one memory tool owns durable memory operations. Teammate discovery, subprocess lifecycle, concurrency, JSON event parsing, truncation, and storage permissions stay behind those interfaces.

## Delegation guarantees

- Every teammate has an explicit tool allowlist.
- Child Pi processes use isolated, ephemeral sessions.
- One task runs singly; multiple tasks run concurrently, up to four at once and eight total.
- Results preserve input order and are capped at 50 KB per task.
- Abort signals terminate child processes.
- Firstmate remains responsible for reviewing and verifying teammate output.

## Memory model

Firstmate stores global and project-scoped JSONL event logs. Automatic capture records ordinary user prompts as project thoughts because the intended interaction is free-form thought dumping. Explicit durable facts can be added with `firstmate_memory`.

Privacy boundaries:

- likely credentials and private keys are rejected;
- automatic capture can be disabled with `FIRSTMATE_AUTO_MEMORY=0`;
- memory remains local with restrictive permissions;
- project paths are represented by hashes in filenames;
- recall is count- and byte-bounded;
- recalled notes enter model context and therefore reach the selected provider.

Forget operations are tombstones, preserving an auditable append-only log while removing the target from future recall.

## Extension points

User teammates in `~/.pi/agent/firstmate/teammates/` override bundled definitions by name. Project teammates in `.pi/firstmate/teammates/` override both only when Pi trusts the project.
