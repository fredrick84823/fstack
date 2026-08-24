#!/usr/bin/env python3
"""Deprecated compatibility wrapper for extract_audio_sources.py."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    replacement = Path(__file__).with_name("extract_audio_sources.py")
    print(
        "⚠️  scripts/generate_meeting_notes.py is deprecated; "
        "use scripts/extract_audio_sources.py instead.",
        file=sys.stderr,
    )
    runpy.run_path(str(replacement), run_name="__main__")


if __name__ == "__main__":
    main()
