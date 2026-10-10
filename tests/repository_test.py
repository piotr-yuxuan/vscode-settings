"""The checks, applied to what this repository tracks."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from tests import checks
from tool import vscode_settings as tool

REPO = Path(__file__).resolve().parent.parent


def tracked_text() -> dict:
    """Return {path: text} for every file git tracks or would track, deleted ones left out."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    paths = [path for path in listing.stdout.split("\0") if path and (REPO / path).is_file()]
    return {path: (REPO / path).read_text(encoding="utf-8") for path in paths}


class Repository(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = tracked_text()

    def assert_no_findings(self, findings):
        self.assertEqual(findings, [], "\n" + "\n".join(findings))

    def test_every_settings_file_is_an_object_without_a_repeated_key(self):
        names = [name for name in self.files if name.endswith("settings.json")]
        self.assertIn("user/settings.json", names)
        for name in names:
            with self.subTest(file=name):
                tool.parse_jsonc(self.files[name], name, dict)

    def test_every_key_bindings_file_is_usable_by_vscode_and_by_a_reader(self):
        names = [name for name in self.files if "/keybindings" in name and name.endswith(".json")]
        self.assertIn("user/keybindings.json", names)
        for name in names:
            with self.subTest(file=name):
                rules = tool.parse_jsonc(self.files[name], name, list)
                described = tool.described_rules(self.files[name], name)
                # What the reference page is made from is what VS Code reads: no rule spans lines.
                self.assertEqual([rule for _, _, rule in described], rules)
                self.assert_no_findings(checks.binding_findings(described))
                self.assert_no_findings(checks.terminal_findings(rules))

    def test_the_manifest_is_coherent(self):
        tool.load_manifest(REPO)

    def test_the_generated_files_are_current(self):
        generated = tool.generated_files(self.files["user/keybindings.json"], tool.load_manifest(REPO))
        for name, text in generated.items():
            with self.subTest(file=name):
                self.assertEqual(self.files.get(name), text, "run bin/vscode-settings docs")

    def test_nothing_private_is_tracked(self):
        machine_local = (
            tool.user_dir(sys.platform, os.environ, Path.home()).parent / "vscode-settings.local"
        )
        deny = machine_local / "deny.txt"
        terms = deny.read_text(encoding="utf-8").split() if deny.is_file() else []
        for name, text in self.files.items():
            with self.subTest(file=name):
                self.assert_no_findings(checks.private_findings(text, terms))

    def test_no_file_holds_a_unicode_dash(self):
        for name, text in self.files.items():
            if name != "LICENSE":
                with self.subTest(file=name):
                    self.assert_no_findings(checks.dash_findings(text))

    def test_every_link_between_pages_leads_somewhere(self):
        pages = {name: text for name, text in self.files.items() if name.endswith(".md")}
        for name in pages:
            with self.subTest(file=name):
                self.assert_no_findings(checks.link_findings(name, pages, set(self.files)))

    def test_every_page_is_in_the_index_once(self):
        kinds = ("docs/tutorials/", "docs/how-to/", "docs/reference/", "docs/explanation/")
        pages = [name[len("docs/") :] for name in self.files if name.startswith(kinds)]
        self.assertTrue(pages)
        self.assert_no_findings(checks.index_findings(self.files["docs/README.md"], pages))

    def test_the_python_sources_pass_ruff(self):
        if shutil.which("ruff") is None:
            self.skipTest("ruff is not installed")
        for arguments in (["check", "--quiet"], ["format", "--check", "--quiet"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    ["ruff", *arguments, "."], cwd=REPO, capture_output=True, text=True, timeout=120
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
