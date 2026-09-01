#!/usr/bin/env python3
"""Generate a deterministic README and Mermaid graph from dictionary entries."""

from __future__ import annotations

import argparse
import re
import sys
from collections import OrderedDict
from pathlib import Path

from validate_dictionary import Entry, list_value, validate_dictionary


DEFAULT_DESCRIPTION = "A concept dictionary arranged as a dependency-aware learning path."


def relative_link(entry: Entry, dictionary_dir: Path) -> str:
    return entry.path.relative_to(dictionary_dir).as_posix()


def render_index(entries: list[Entry], dictionary_dir: Path) -> str:
    sections: OrderedDict[tuple[int, str], list[Entry]] = OrderedDict()
    for entry in sorted(entries, key=lambda item: item.sort_key):
        key = (int(entry.metadata["section_order"]), str(entry.metadata["section"]))
        sections.setdefault(key, []).append(entry)

    lines = ["## Learning path", ""]
    for (number, name), section_entries in sections.items():
        lines.extend([f"### {number}. {name}", ""])
        for entry in section_entries:
            summary = str(entry.metadata.get("summary", "")).strip()
            lines.append(f"- [{entry.title}]({relative_link(entry, dictionary_dir)}) — {summary}")
        lines.append("")
    return "\n".join(lines).rstrip()


def mermaid_id(slug: str) -> str:
    return "concept_" + re.sub(r"[^a-zA-Z0-9_]", "_", slug)


def mermaid_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "&quot;")


def render_graph(entries: list[Entry]) -> str:
    by_slug = {entry.slug: entry for entry in entries}
    lines = ["## Concept graph", "", "```mermaid", "flowchart TD"]
    for entry in sorted(entries, key=lambda item: item.sort_key):
        lines.append(f'    {mermaid_id(entry.slug)}["{mermaid_label(entry.title)}"]')
    for entry in sorted(entries, key=lambda item: item.sort_key):
        for prerequisite in sorted(list_value(entry, "prerequisites")):
            if prerequisite in by_slug:
                lines.append(f"    {mermaid_id(prerequisite)} --> {mermaid_id(entry.slug)}")
    lines.append("```")
    return "\n".join(lines)


def default_title(dictionary_dir: Path) -> str:
    return dictionary_dir.name.replace("-", " ").replace("_", " ").title()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dictionary_dir", type=Path)
    parser.add_argument("--title", help="Dictionary title; defaults to the directory name.")
    parser.add_argument("--description", default=DEFAULT_DESCRIPTION)
    parser.add_argument("--template", type=Path, help="README template path.")
    parser.add_argument("--no-graph", action="store_true", help="Omit the Mermaid graph.")
    parser.add_argument("--check", action="store_true", help="Fail if README is not current.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dictionary_dir = args.dictionary_dir.resolve()
    entries, findings = validate_dictionary(dictionary_dir)
    errors = [item for item in findings if item.level == "error"]
    if errors:
        for item in errors:
            print(f"ERROR [{item.code}] {item.message}", file=sys.stderr)
        return 1

    template_path = args.template or Path(__file__).resolve().parent.parent / "templates" / "readme-template.md"
    template = template_path.read_text(encoding="utf-8")
    graph = "" if args.no_graph else render_graph(entries)
    rendered = (
        template.replace("{{TITLE}}", args.title or default_title(dictionary_dir))
        .replace("{{DESCRIPTION}}", args.description.strip())
        .replace("{{INDEX}}", render_index(entries, dictionary_dir))
        .replace("{{GRAPH}}", graph)
        .rstrip()
        + "\n"
    )
    readme = dictionary_dir / "README.md"
    if args.check:
        current = readme.read_text(encoding="utf-8") if readme.exists() else ""
        if current != rendered:
            print(f"README is out of date: {readme}", file=sys.stderr)
            return 1
        print(f"README is current: {readme}")
        return 0
    readme.write_text(rendered, encoding="utf-8")
    print(f"Generated {readme} from {len(entries)} entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
