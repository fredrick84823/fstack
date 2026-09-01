"""Write tasks back to Heptabase: create cards, add tags, append journal.

All mutations go through this module. Only this file touches Heptabase state.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

SIMPLE_TASK_TEMPLATE = (Path(__file__).parent.parent / "templates" / "simple-task-card.md").read_text()

_HEPTABASE_OK: bool | None = None


def check_heptabase_alive() -> bool:
    """Return True if heptabase CLI is reachable."""
    global _HEPTABASE_OK
    if _HEPTABASE_OK is not None:
        return _HEPTABASE_OK
    r = subprocess.run(["heptabase", "--version"], capture_output=True, text=True, timeout=10)
    _HEPTABASE_OK = r.returncode == 0
    return _HEPTABASE_OK


def ensure_card(task: dict, week_tag: str) -> str:
    """Ensure a Heptabase card exists for the task; return card_id.

    If task already has a card_id, just ensure the week tag is applied.
    Otherwise, create a new note card from the simple-task-template.
    """
    if not check_heptabase_alive():
        raise RuntimeError("Heptabase desktop is not running. Run `heptabase start` first.")

    card_id = task.get("card_id")

    if not card_id:
        title = task["name_raw"]
        # Title is set by the first `# heading` line; replace the template heading
        body = SIMPLE_TASK_TEMPLATE.replace("[template] Simple Task Card Template", title)
        r = subprocess.run(
            ["heptabase", "note", "create", "--content", body],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            raise RuntimeError(f"Failed to create card for '{title}': {r.stderr.strip()}")
        import json
        result = json.loads(r.stdout)
        card_id = result["id"]

    # Add week tag (heptabase tag add auto-creates if tag doesn't exist)
    subprocess.run(
        ["heptabase", "tag", "add", "--tag", week_tag, "--cardId", card_id],
        capture_output=True, text=True, timeout=30,
    )

    return card_id


def append_conflict_note(card_id: str, conflict_text: str, today: str) -> None:
    """Append a conflict warning line to the card's Note section."""
    if not check_heptabase_alive():
        return
    note_line = f"\n## Note\n- [{today}] ⚠️ 衝突: {conflict_text}\n"
    subprocess.run(
        ["heptabase", "note", "append", card_id, "--content", note_line],
        capture_output=True, text=True, timeout=30,
    )


def append_journal(today: str, markdown: str) -> None:
    """Append markdown to today's Heptabase journal."""
    if not check_heptabase_alive():
        raise RuntimeError("Heptabase desktop is not running.")
    r = subprocess.run(
        ["heptabase", "journal", "append", today, "--content", markdown],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(f"Failed to append journal: {r.stderr.strip()}")
