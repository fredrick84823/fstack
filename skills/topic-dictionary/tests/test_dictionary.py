from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
EXAMPLE_DIR = SKILL_DIR / "examples" / "http-caching"
EVALS_FILE = SKILL_DIR / "evals" / "evals.json"
sys.path.insert(0, str(SCRIPTS_DIR))

from validate_dictionary import validate_dictionary  # noqa: E402


class DictionaryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.dictionary = Path(self.temp_dir.name) / "dictionary"
        shutil.copytree(EXAMPLE_DIR, self.dictionary)

    def entry(self, slug: str) -> Path:
        return self.dictionary / "concepts" / f"{slug}.md"

    def replace(self, path: Path, old: str, new: str) -> None:
        content = path.read_text(encoding="utf-8")
        self.assertIn(old, content, f"Mutation target not found in {path}")
        path.write_text(content.replace(old, new, 1), encoding="utf-8")

    def codes(self) -> list[str]:
        _, findings = validate_dictionary(self.dictionary)
        return [finding.code for finding in findings]

    def run_validator(self, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "validate_dictionary.py"),
                str(self.dictionary),
                *extra_args,
            ],
            check=False,
            capture_output=True,
            text=True,
        )


class ValidatorTests(DictionaryTestCase):
    def test_clean_dictionary_has_no_findings(self) -> None:
        _, findings = validate_dictionary(self.dictionary)
        self.assertEqual([], findings)

    def test_broken_markdown_link_is_rejected(self) -> None:
        self.replace(
            self.entry("cache-control"),
            "[Cache freshness](cache-freshness.md)",
            "[Cache freshness](missing.md)",
        )
        self.assertIn("broken-link", self.codes())

    def test_undefined_prerequisite_node_is_rejected(self) -> None:
        self.replace(
            self.entry("cache-control"),
            '  - "cache-freshness"',
            '  - "missing-concept"',
        )
        self.assertIn("undefined-concept", self.codes())

    def test_duplicate_slug_node_is_rejected(self) -> None:
        shutil.copyfile(
            self.entry("resource-representation"),
            self.entry("duplicate-resource"),
        )
        codes = self.codes()
        self.assertIn("duplicate-slug", codes)
        self.assertNotIn("duplicate-edge", codes)

    def test_duplicate_relationship_edge_is_rejected(self) -> None:
        self.replace(
            self.entry("cache-freshness"),
            'related:\n  - "cache-control"',
            'related:\n  - "cache-control"\n  - "cache-control"',
        )
        codes = self.codes()
        self.assertIn("duplicate-edge", codes)
        self.assertNotIn("duplicate-slug", codes)

    def test_duplicate_prerequisite_edge_is_rejected(self) -> None:
        self.replace(
            self.entry("cache-control"),
            'prerequisites:\n  - "resource-representation"\n  - "cache-freshness"',
            'prerequisites:\n  - "resource-representation"\n  - "cache-freshness"\n  - "cache-freshness"',
        )
        self.assertIn("duplicate-edge", self.codes())

    def test_dependency_cycle_is_rejected(self) -> None:
        self.replace(
            self.entry("resource-representation"),
            "prerequisites: []",
            'prerequisites:\n  - "cache-control"',
        )
        self.assertIn("dependency-cycle", self.codes())

    def test_duplicate_learning_position_is_rejected(self) -> None:
        self.replace(
            self.entry("cache-control"),
            "section_order: 2\norder: 2",
            "section_order: 2\norder: 1",
        )
        self.assertIn("duplicate-order", self.codes())

    def test_glossary_style_section_produces_warning(self) -> None:
        path = self.entry("cache-control")
        content = path.read_text(encoding="utf-8")
        start = content.index("## How does it work?")
        end = content.index("## When is it used?")
        content = content[:start] + "## How does it work?\n\nIt works through directives.\n\n" + content[end:]
        path.write_text(content, encoding="utf-8")
        _, findings = validate_dictionary(self.dictionary)
        thin_sections = [
            finding
            for finding in findings
            if finding.code == "thin-section" and "How does it work?" in finding.message
        ]
        self.assertEqual(1, len(thin_sections))
        result = self.run_validator("--strict")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("WARNING [thin-section]", result.stdout)


class ReadmeTests(DictionaryTestCase):
    def run_generator(self, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "generate_readme.py"),
                str(self.dictionary),
                "--title",
                "HTTP Caching Dictionary",
                "--description",
                "A compact example showing how HTTP caching concepts build on one another.",
                *extra_args,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_checked_readme_is_current(self) -> None:
        result = self.run_generator("--check")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_checked_readme_detects_metadata_drift(self) -> None:
        self.replace(
            self.entry("resource-representation"),
            "A representation is the transferable form",
            "A representation is a transferable form",
        )
        result = self.run_generator("--check")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("README is out of date", result.stderr)

    def test_generation_is_deterministic_for_equal_inputs(self) -> None:
        other = Path(self.temp_dir.name) / "other"
        shutil.copytree(EXAMPLE_DIR, other)
        first = self.run_generator()
        self.assertEqual(0, first.returncode, first.stderr)
        second = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "generate_readme.py"),
                str(other),
                "--title",
                "HTTP Caching Dictionary",
                "--description",
                "A compact example showing how HTTP caching concepts build on one another.",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(
            (self.dictionary / "README.md").read_text(encoding="utf-8"),
            (other / "README.md").read_text(encoding="utf-8"),
        )


class EvalManifestTests(unittest.TestCase):
    def test_compact_eval_manifest_has_required_coverage(self) -> None:
        manifest = json.loads(EVALS_FILE.read_text(encoding="utf-8"))
        self.assertEqual("topic-dictionary", manifest["target_skill"])
        self.assertEqual(5, len(manifest["cases"]))
        self.assertEqual(6, len(manifest["semantic_rubric"]))
        case_types = {case["type"] for case in manifest["cases"]}
        self.assertEqual(
            {
                "rubric_scenario",
                "generalization",
                "adversarial_recall",
                "state_transition",
                "consistency",
            },
            case_types,
        )
        for case in manifest["cases"]:
            self.assertTrue(case["prompt"])
            self.assertTrue(case["expected_behavior"])
            self.assertTrue(case["must_not_do"])


if __name__ == "__main__":
    unittest.main()
