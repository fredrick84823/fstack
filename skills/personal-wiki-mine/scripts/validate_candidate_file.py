#!/usr/bin/env python3
"""Validate structural requirements for a personal-wiki-mine candidate file."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_SECTIONS = [
    "## Source Manifest",
    "## Source Coverage Audit",
    "### Whiteboard Coverage",
    "### Compensating Card Search",
    "### Missing Or Partial Signals",
    "## Heptabase Fetch Notes",
    "## GT Pattern Summary",
    "## Self-Audit",
    "## User Instructions",
    "## Overall Reflection",
]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def validate(path: Path) -> None:
    if not path.exists():
        fail(f"file does not exist: {path}")

    text = path.read_text(encoding="utf-8")

    if "status: awaiting-user-scoring" not in text:
        fail("frontmatter must include status: awaiting-user-scoring")

    if "lifecycle_state: candidate" not in text:
        fail("frontmatter must include lifecycle_state: candidate")

    if "source_protocol: bounded-source-brief-with-coverage-audit" not in text:
        fail("frontmatter must include source_protocol: bounded-source-brief-with-coverage-audit")

    for section in REQUIRED_SECTIONS:
        if section not in text:
            fail(f"missing section: {section}")

    candidate_count = len(re.findall(r"^## #\d+\. ", text, flags=re.MULTILINE))
    if candidate_count != 5:
        fail(f"expected 5 candidates, found {candidate_count}")

    evidence_count = len(re.findall(r"^\d+\. \[source:", text, flags=re.MULTILINE))
    if evidence_count < 15:
        fail(f"expected at least 15 source-linked evidence items, found {evidence_count}")

    required_candidate_fields = [
        "**證據**:",
        "**假說**:",
        "**反駁路徑**:",
        "**Filter 自評**:",
        "**所以下一步可能是**:",
        "[使用者區]",
    ]
    for field in required_candidate_fields:
        count = text.count(field)
        if count != 5:
            fail(f"expected 5 occurrences of {field}, found {count}")

    if "Source coverage sufficient?" not in text:
        fail("self-audit must include Source coverage sufficient? column")

    whiteboard_section = text.split("### Whiteboard Coverage", 1)[1].split(
        "### Compensating Card Search", 1
    )[0]
    if "`partial`" in whiteboard_section or "partial" in whiteboard_section.lower():
        compensation_section = text.split("### Compensating Card Search", 1)[1].split(
            "### Missing Or Partial Signals", 1
        )[0]
        if "| Query | Reason | Selected cards | Fully fetched? |" not in compensation_section:
            fail("partial whiteboard coverage requires compensating card search table")
        if "Yes" not in compensation_section and "Partially" not in compensation_section:
            fail("compensating card search must record fetch status")

    print("OK: candidate file is structurally valid")


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        print("Usage: validate_candidate_file.py <candidate-file>")
        raise SystemExit(2)
    validate(Path(argv[1]))


if __name__ == "__main__":
    main(sys.argv)
