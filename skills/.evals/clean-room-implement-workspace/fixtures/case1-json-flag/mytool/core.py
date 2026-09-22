"""Status gathering. No I/O formatting here."""

from __future__ import annotations


def gather_status(root: str) -> dict:
    """Return the raw status of a workspace root."""
    return {
        "root": root,
        "branch": "main",
        "tracked": 12,
        "modified": 3,
        "clean": False,
    }
