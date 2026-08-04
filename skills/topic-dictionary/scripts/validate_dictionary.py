#!/usr/bin/env python3
"""Validate a topic dictionary using only the Python standard library."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote


REQUIRED_FIELDS = (
    "title",
    "slug",
    "section",
    "section_order",
    "order",
    "summary",
    "prerequisites",
    "related",
)
REQUIRED_SECTIONS = (
    "What is it?",
    "Why does it exist?",
    "How does it work?",
    "When is it used?",
    "Common misconceptions",
    "Related concepts",
    "What to learn next",
)
MIN_SECTION_WORDS = {
    "What is it?": 18,
    "Why does it exist?": 20,
    "How does it work?": 25,
    "When is it used?": 18,
    "Common misconceptions": 15,
    "Related concepts": 8,
    "What to learn next": 8,
}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Entry:
    path: Path
    metadata: dict[str, Any]
    body: str

    @property
    def slug(self) -> str:
        return str(self.metadata.get("slug", ""))

    @property
    def title(self) -> str:
        return str(self.metadata.get("title", self.slug))

    @property
    def sort_key(self) -> tuple[int, int, str]:
        return (
            integer(self.metadata.get("section_order"), 10**9),
            integer(self.metadata.get("order"), 10**9),
            self.slug,
        )


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    message: str
    path: str | None = None

    def as_dict(self) -> dict[str, str]:
        result = {"level": self.level, "code": self.code, "message": self.message}
        if self.path:
            result["path"] = self.path
        return result


class FrontmatterError(ValueError):
    pass


def integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [parse_scalar(part) for part in inner.split(",")]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("missing opening frontmatter delimiter")
    try:
        closing = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration as exc:
        raise FrontmatterError("missing closing frontmatter delimiter") from exc

    metadata: dict[str, Any] = {}
    active_list: str | None = None
    for line_number, line in enumerate(lines[1:closing], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(("  - ", "- ")):
            if active_list is None:
                raise FrontmatterError(f"line {line_number}: list item has no key")
            item = line.split("-", 1)[1].strip()
            metadata[active_list].append(parse_scalar(item))
            continue
        if ":" not in line or line[0].isspace():
            raise FrontmatterError(f"line {line_number}: unsupported YAML syntax")
        key, raw = line.split(":", 1)
        key = key.strip()
        if not key or key in metadata:
            raise FrontmatterError(f"line {line_number}: invalid or duplicate key")
        if raw.strip():
            metadata[key] = parse_scalar(raw)
            active_list = None
        else:
            metadata[key] = []
            active_list = key
    return metadata, "\n".join(lines[closing + 1 :]).strip() + "\n"


def entry_paths(dictionary_dir: Path) -> list[Path]:
    concepts = dictionary_dir / "concepts"
    search_dir = concepts if concepts.is_dir() else dictionary_dir
    return sorted(
        path
        for path in search_dir.glob("*.md")
        if path.name.lower() != "readme.md" and not path.name.startswith("_")
    )


def load_entries(dictionary_dir: Path) -> tuple[list[Entry], list[Finding]]:
    entries: list[Entry] = []
    findings: list[Finding] = []
    for path in entry_paths(dictionary_dir):
        try:
            metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            entries.append(Entry(path=path, metadata=metadata, body=body))
        except (OSError, UnicodeError, FrontmatterError) as exc:
            findings.append(Finding("error", "frontmatter", str(exc), str(path)))
    if not entries:
        findings.append(
            Finding("error", "no-entries", "No concept entries were found.", str(dictionary_dir))
        )
    return entries, findings


def list_value(entry: Entry, field: str) -> list[str]:
    value = entry.metadata.get(field, [])
    return [str(item) for item in value] if isinstance(value, list) else []


def section_text(body: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)", re.MULTILINE | re.DOTALL
    )
    match = pattern.search(body)
    return match.group(1).strip() if match else ""


def normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def validate_entry_shape(entry: Entry) -> list[Finding]:
    findings: list[Finding] = []
    location = str(entry.path)
    for field in REQUIRED_FIELDS:
        if field not in entry.metadata:
            findings.append(Finding("error", "missing-field", f"Missing `{field}`.", location))
    for field in ("prerequisites", "related", "sources"):
        if field in entry.metadata and not isinstance(entry.metadata[field], list):
            findings.append(Finding("error", "field-type", f"`{field}` must be a list.", location))
    for field in ("section_order", "order"):
        value = entry.metadata.get(field)
        if not isinstance(value, int) or value < 1:
            findings.append(
                Finding("error", "field-type", f"`{field}` must be a positive integer.", location)
            )
    if not SLUG_RE.fullmatch(entry.slug):
        findings.append(Finding("error", "invalid-slug", f"Invalid slug `{entry.slug}`.", location))
    if entry.path.stem != entry.slug:
        findings.append(
            Finding(
                "error",
                "filename-mismatch",
                f"Filename `{entry.path.stem}` does not match slug `{entry.slug}`.",
                location,
            )
        )
    h1 = re.search(r"^#\s+(.+?)\s*$", entry.body, re.MULTILINE)
    if not h1 or h1.group(1) != entry.title:
        findings.append(Finding("error", "title-mismatch", "H1 must match `title`.", location))
    headings = set(HEADING_RE.findall(entry.body))
    for heading in REQUIRED_SECTIONS:
        if heading not in headings:
            findings.append(
                Finding("error", "missing-section", f"Missing `## {heading}`.", location)
            )
            continue
        words = re.findall(r"\b[\w'-]+\b", section_text(entry.body, heading), re.UNICODE)
        if len(words) < MIN_SECTION_WORDS[heading]:
            findings.append(
                Finding(
                    "warning",
                    "thin-section",
                    f"`{heading}` has {len(words)} words; expected at least {MIN_SECTION_WORDS[heading]}.",
                    location,
                )
            )
    summary_words = re.findall(r"\b[\w'-]+\b", str(entry.metadata.get("summary", "")))
    if len(summary_words) < 6:
        findings.append(
            Finding("warning", "weak-summary", "Summary is too short to orient a reader.", location)
        )
    return findings


def find_cycle(entries: list[Entry]) -> list[str] | None:
    graph = {entry.slug: list_value(entry, "prerequisites") for entry in entries}
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for dependency in graph.get(node, []):
            if dependency not in graph:
                continue
            if state.get(dependency, 0) == 1:
                start = stack.index(dependency)
                return stack[start:] + [dependency]
            if state.get(dependency, 0) == 0:
                cycle = visit(dependency)
                if cycle:
                    return cycle
        stack.pop()
        state[node] = 2
        return None

    for slug in sorted(graph):
        if state.get(slug, 0) == 0:
            cycle = visit(slug)
            if cycle:
                return cycle
    return None


def validate_links(entry: Entry) -> list[Finding]:
    findings: list[Finding] = []
    for raw_target in LINK_RE.findall(entry.body):
        target = raw_target.strip().strip("<>").split(maxsplit=1)[0]
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target_path = unquote(target.split("#", 1)[0])
        if target_path and not (entry.path.parent / target_path).resolve().exists():
            findings.append(
                Finding("error", "broken-link", f"Broken relative link `{target}`.", str(entry.path))
            )
    return findings


def validate_dictionary(dictionary_dir: Path) -> tuple[list[Entry], list[Finding]]:
    entries, findings = load_entries(dictionary_dir)
    if not entries:
        return entries, findings
    for entry in entries:
        findings.extend(validate_entry_shape(entry))
        findings.extend(validate_links(entry))

    by_slug: dict[str, Entry] = {}
    by_title: dict[str, Entry] = {}
    section_orders: dict[str, int] = {}
    positions: dict[tuple[int, int], Entry] = {}
    for entry in entries:
        if entry.slug in by_slug:
            findings.append(
                Finding("error", "duplicate-slug", f"Duplicate slug `{entry.slug}`.", str(entry.path))
            )
        by_slug[entry.slug] = entry
        normalized = normalized_name(entry.title)
        if normalized and normalized in by_title:
            findings.append(
                Finding("error", "duplicate-title", f"Duplicate title `{entry.title}`.", str(entry.path))
            )
        by_title[normalized] = entry
        section = str(entry.metadata.get("section", ""))
        section_order = integer(entry.metadata.get("section_order"), -1)
        if section in section_orders and section_orders[section] != section_order:
            findings.append(
                Finding("error", "section-order", f"Section `{section}` has inconsistent order.", str(entry.path))
            )
        section_orders[section] = section_order
        position = (section_order, integer(entry.metadata.get("order"), -1))
        if position in positions:
            findings.append(
                Finding("error", "duplicate-order", f"Learning position {position} is duplicated.", str(entry.path))
            )
        positions[position] = entry

    for entry in entries:
        for field in ("prerequisites", "related"):
            for target in list_value(entry, field):
                if target == entry.slug:
                    findings.append(
                        Finding("error", "self-reference", f"`{field}` contains its own slug.", str(entry.path))
                    )
                elif target not in by_slug:
                    findings.append(
                        Finding("error", "undefined-concept", f"`{field}` references `{target}`.", str(entry.path))
                    )
        for prerequisite in list_value(entry, "prerequisites"):
            if prerequisite in by_slug and by_slug[prerequisite].sort_key >= entry.sort_key:
                findings.append(
                    Finding(
                        "error",
                        "prerequisite-order",
                        f"Prerequisite `{prerequisite}` does not appear earlier.",
                        str(entry.path),
                    )
                )

    cycle = find_cycle(entries)
    if cycle:
        findings.append(
            Finding("error", "dependency-cycle", " -> ".join(cycle), str(dictionary_dir))
        )
    return sorted(entries, key=lambda entry: entry.sort_key), findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dictionary_dir", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable findings.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dictionary_dir = args.dictionary_dir.resolve()
    _, findings = validate_dictionary(dictionary_dir)
    errors = sum(item.level == "error" for item in findings)
    warnings = sum(item.level == "warning" for item in findings)
    if args.json:
        print(
            json.dumps(
                {
                    "dictionary": str(dictionary_dir),
                    "errors": errors,
                    "warnings": warnings,
                    "findings": [item.as_dict() for item in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for item in findings:
            prefix = f"{item.level.upper()} [{item.code}]"
            location = f" {item.path}:" if item.path else ""
            print(f"{prefix}{location} {item.message}")
        print(f"Validation complete: {errors} error(s), {warnings} warning(s).")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
