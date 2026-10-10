"""What the tool must do, as examples taken from plan 001, not from the code."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tool import vscode_settings as tool

MANIFEST = {
    "exclusive": [["official.dbt", "other.dbt"]],
    "extensions": [
        {"id": "Some.Keymap", "group": "core", "purpose": "Keys."},
        {"id": "official.dbt", "group": "core", "purpose": "dbt."},
        {"id": "other.dbt", "group": "sql", "purpose": "The alternative."},
        {"id": "some.linter", "group": "sql", "purpose": "Lint."},
    ],
}

RULES = """// A header that describes the file.
[
  // == Git ==

  // Status of the repository
  { "key": "ctrl+x g", "command": "magit.status", "when": "!terminalFocus" },
  // Either side
  // of a choice
  { "key": "ctrl+c shift+o", "command": "a.b", "when": "x || y" },

  // == Files ==
  { "key": "f8", "command": "toggle" }
]
"""


class ParseJsonc(unittest.TestCase):
    def test_comments_and_trailing_commas_are_accepted(self):
        text = '// header\n{\n  "a": 1, /* inline */\n  "b": [1, 2,],\n}\n'
        self.assertEqual(tool.parse_jsonc(text, "example"), {"a": 1, "b": [1, 2]})

    def test_what_looks_like_a_comment_or_a_trailing_comma_inside_a_string_is_kept(self):
        text = '{"url": "https://example.org/a", "glob": "/* x */", "end": "a, ]"}'
        self.assertEqual(
            tool.parse_jsonc(text, "example"),
            {"url": "https://example.org/a", "glob": "/* x */", "end": "a, ]"},
        )

    def test_a_repeated_key_is_an_error_that_names_the_file_and_the_key(self):
        with self.assertRaisesRegex(tool.ConfigError, "example.*'a'"):
            tool.parse_jsonc('{"a": 1, "b": {"c": 1}, "a": 2}', "example")

    def test_malformed_text_is_an_error_that_names_the_file(self):
        with self.assertRaisesRegex(tool.ConfigError, "example"):
            tool.parse_jsonc('{"a": ', "example")

    def test_an_array_where_an_object_is_expected_is_an_error(self):
        with self.assertRaisesRegex(tool.ConfigError, "example"):
            tool.parse_jsonc("[1]", "example", dict)


class DeepMerge(unittest.TestCase):
    def test_objects_merge_key_by_key_at_every_depth(self):
        base = {"[python]": {"formatter": "ruff", "hints": "on"}, "kept": 1}
        over = {"[python]": {"hints": "off"}, "added": 2}
        self.assertEqual(
            tool.deep_merge(base, over),
            {"[python]": {"formatter": "ruff", "hints": "off"}, "kept": 1, "added": 2},
        )

    def test_an_array_replaces_an_array_whole(self):
        self.assertEqual(tool.deep_merge({"rulers": [80, 120]}, {"rulers": [100]}), {"rulers": [100]})

    def test_neither_input_is_changed(self):
        base, over = {"a": {"b": 1}}, {"a": {"c": 2}}
        tool.deep_merge(base, over)
        self.assertEqual((base, over), ({"a": {"b": 1}}, {"a": {"c": 2}}))


class Differences(unittest.TestCase):
    def test_equal_documents_have_none(self):
        self.assertEqual(tool.differences({"a": {"b": [1]}}, {"a": {"b": [1]}}), [])

    def test_a_changed_leaf_is_named_by_its_path(self):
        self.assertEqual(tool.differences({"a": {"b": 1}}, {"a": {"b": 2}}), [(("a", "b"), "1", "2")])

    def test_a_new_key_is_reported_as_absent_before(self):
        self.assertEqual(tool.differences({}, {"a.b": True}), [(("a.b",), "absent", "true")])

    def test_true_is_not_one(self):
        self.assertEqual(tool.differences({"a": 1}, {"a": True}), [(("a",), "1", "true")])


class EmacsNotation(unittest.TestCase):
    def test_keys_read_as_an_emacs_user_writes_them(self):
        examples = {
            "ctrl+x g": "C-x g",
            "alt+o": "M-o",
            "ctrl+x shift+o": "C-x O",
            "ctrl+c z shift+a": "C-c z A",
            "ctrl+h ctrl+d": "C-h C-d",
            "ctrl+alt+=": "C-M-=",
            "alt+shift+4": "M-$",
            "ctrl+shift+.": "C->",
            "f8": "<f8>",
            "ctrl+enter": "C-RET",
            "cmd+enter": "s-RET",
            "shift+enter": "S-RET",
        }
        for key, expected in examples.items():
            with self.subTest(key=key):
                self.assertEqual(tool.emacs_notation(key), expected)


class DescribedRules(unittest.TestCase):
    def test_each_rule_carries_its_section_and_the_comment_above_it(self):
        self.assertEqual(
            tool.described_rules(RULES, "example"),
            [
                (
                    "Git",
                    "Status of the repository",
                    {"key": "ctrl+x g", "command": "magit.status", "when": "!terminalFocus"},
                ),
                (
                    "Git",
                    "Either side of a choice",
                    {"key": "ctrl+c shift+o", "command": "a.b", "when": "x || y"},
                ),
                ("Files", "", {"key": "f8", "command": "toggle"}),
            ],
        )


class GeneratedFiles(unittest.TestCase):
    def setUp(self):
        self.files = tool.generated_files(RULES, MANIFEST)

    def test_the_key_reference_has_one_row_per_rule_under_its_section(self):
        page = self.files["docs/reference/keybindings.md"]
        self.assertIn("## Git\n", page)
        self.assertIn(
            "| `C-x g` | `ctrl+x g` | Status of the repository | `magit.status` | `!terminalFocus` |",
            page,
        )
        self.assertLess(page.index("## Git"), page.index("## Files"))
        self.assertIn("| `<f8>` | `f8` |  | `toggle` |  |", page)

    def test_a_pipe_in_a_cell_does_not_break_the_table(self):
        self.assertIn("`x \\|\\| y`", self.files["docs/reference/keybindings.md"])

    def test_the_key_reference_says_it_is_generated(self):
        self.assertIn("Do not edit; regenerate it.", self.files["docs/reference/keybindings.md"])

    def test_the_recommendations_are_the_core_group(self):
        recommended = tool.parse_jsonc(self.files[".vscode/extensions.json"], "generated")
        self.assertEqual(recommended, {"recommendations": ["Some.Keymap", "official.dbt"]})


class UserDir(unittest.TestCase):
    def test_linux(self):
        self.assertEqual(tool.user_dir("linux", {}, Path("/h")), Path("/h/.config/Code/User"))

    def test_linux_with_a_configuration_home(self):
        self.assertEqual(
            tool.user_dir("linux", {"XDG_CONFIG_HOME": "/x"}, Path("/h")), Path("/x/Code/User")
        )

    def test_macos(self):
        self.assertEqual(
            tool.user_dir("darwin", {}, Path("/h")), Path("/h/Library/Application Support/Code/User")
        )

    def test_another_platform_is_refused(self):
        with self.assertRaises(tool.UsageError):
            tool.user_dir("win32", {}, Path("/h"))


class ManifestFindings(unittest.TestCase):
    def test_a_coherent_manifest_has_none(self):
        self.assertEqual(tool.manifest_findings(MANIFEST), [])

    def test_each_defect_is_found(self):
        entry = {"id": "a.b", "group": "core", "purpose": "P."}
        defects = {
            "an identifier that is not publisher.name": {"extensions": [dict(entry, id="edamagit")]},
            "the same identifier twice, whatever the case": {
                "extensions": [entry, dict(entry, id="A.B")]
            },
            "no purpose": {"extensions": [dict(entry, purpose="")]},
            "no group": {"extensions": [{"id": "a.b", "purpose": "P."}]},
            "an exclusive pair that names an unknown extension": {
                "extensions": [entry],
                "exclusive": [["a.b", "c.d"]],
            },
            "an exclusive pair installed together by default": {
                "extensions": [entry, dict(entry, id="c.d")],
                "exclusive": [["a.b", "c.d"]],
            },
            "no list of extensions": {"extension": []},
        }
        for defect, manifest in defects.items():
            with self.subTest(defect=defect):
                self.assertNotEqual(tool.manifest_findings(manifest), [])


class ExtensionsToInstall(unittest.TestCase):
    def test_only_the_requested_groups_and_only_what_is_missing(self):
        self.assertEqual(
            tool.extensions_to_install(MANIFEST, ["core"], ["some.keymap"]), (["official.dbt"], [])
        )

    def test_an_unknown_group_is_refused(self):
        with self.assertRaisesRegex(tool.UsageError, "nope"):
            tool.extensions_to_install(MANIFEST, ["nope"], [])

    def test_an_extension_whose_exclusive_partner_is_installed_is_blocked(self):
        self.assertEqual(
            tool.extensions_to_install(MANIFEST, ["sql"], ["Official.DBT"]),
            (["some.linter"], ["other.dbt"]),
        )

    def test_of_two_exclusive_extensions_requested_together_the_first_listed_wins(self):
        self.assertEqual(
            tool.extensions_to_install(MANIFEST, ["core", "sql"], ["some.keymap"]),
            (["official.dbt", "some.linter"], ["other.dbt"]),
        )


class Deployment(unittest.TestCase):
    """The tool against a small repository and a private user directory."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.repo, self.user = self.root / "repo", self.root / "data" / "User"
        self.local = self.root / "data" / "vscode-settings.local"
        (self.repo / "user").mkdir(parents=True)
        self.user.mkdir(parents=True)
        self.write(
            self.repo / "user/settings.json", '{\n  // why\n  "managed": 1,\n  "[python]": {"a": 1},\n}'
        )
        self.write(
            self.repo / "user/keybindings.json", '[\n  // B\n  {"key": "f8", "command": "base"},\n]'
        )
        printing = mock.patch("builtins.print")
        self.output = printing.start()
        self.addCleanup(printing.stop)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def deployed(self, name):
        return json.loads((self.user / name).read_text(encoding="utf-8"))

    def printed(self):
        return "\n".join(" ".join(map(str, call.args)) for call in self.output.call_args_list)

    def test_apply_keeps_what_the_repository_does_not_set(self):
        self.write(self.user / "settings.json", '{"mine": true, "[python]": {"b": 2}, "managed": 0}')
        self.assertEqual(tool.cmd_deploy(self.repo, self.user, write=True), 0)
        self.assertEqual(
            self.deployed("settings.json"), {"mine": True, "[python]": {"b": 2, "a": 1}, "managed": 1}
        )

    def test_a_machine_local_value_wins_over_the_baseline(self):
        self.write(self.local / "settings.json", '{"managed": 2, "local": "x"}')
        tool.cmd_deploy(self.repo, self.user, write=True)
        self.assertEqual(
            self.deployed("settings.json"), {"managed": 2, "[python]": {"a": 1}, "local": "x"}
        )

    def test_key_bindings_are_the_baseline_rules_then_the_machine_local_ones(self):
        self.write(self.local / "keybindings.json", '[{"key": "f8", "command": "local"}]')
        tool.cmd_deploy(self.repo, self.user, write=True)
        self.assertEqual(
            self.deployed("keybindings.json"),
            [{"key": "f8", "command": "base"}, {"key": "f8", "command": "local"}],
        )

    def test_status_writes_nothing_and_says_whether_apply_would(self):
        self.assertEqual(tool.cmd_deploy(self.repo, self.user, write=False), 1)
        self.assertFalse((self.user / "settings.json").exists())
        tool.cmd_deploy(self.repo, self.user, write=True)
        self.assertEqual(tool.cmd_deploy(self.repo, self.user, write=False), 0)

    def test_a_second_apply_changes_nothing(self):
        tool.cmd_deploy(self.repo, self.user, write=True)
        before = {path: path.stat().st_mtime_ns for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(tool.cmd_deploy(self.repo, self.user, write=True), 0)
        after = {path: path.stat().st_mtime_ns for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_a_setting_changed_in_vscode_shows_in_status(self):
        tool.cmd_deploy(self.repo, self.user, write=True)
        self.write(self.user / "settings.json", '{"managed": 5, "[python]": {"a": 1}}')
        self.output.reset_mock()
        self.assertEqual(tool.cmd_deploy(self.repo, self.user, write=False), 1)
        self.assertIn("managed", self.printed())

    def test_a_rule_that_apply_would_drop_is_named_first(self):
        self.write(self.user / "keybindings.json", '[{"key": "f9", "command": "added.in.vscode"}]')
        tool.cmd_deploy(self.repo, self.user, write=False)
        self.assertIn("added.in.vscode", self.printed())

    def test_the_file_found_at_first_is_kept_once_and_the_last_one_each_time(self):
        self.write(self.user / "settings.json", '{"first": 1}')
        tool.cmd_deploy(self.repo, self.user, write=True)
        self.write(self.user / "settings.json", '{"second": 2}')
        tool.cmd_deploy(self.repo, self.user, write=True)
        backup = self.local / "backup"
        self.assertEqual(json.loads((backup / "settings.json.original").read_text()), {"first": 1})
        self.assertEqual(json.loads((backup / "settings.json.previous").read_text()), {"second": 2})

    def test_the_mode_of_a_replaced_file_is_kept(self):
        self.write(self.user / "settings.json", "{}")
        (self.user / "settings.json").chmod(0o640)
        tool.cmd_deploy(self.repo, self.user, write=True)
        self.assertEqual(stat.S_IMODE((self.user / "settings.json").stat().st_mode), 0o640)

    def test_an_unreadable_deployed_file_stops_everything_before_any_write(self):
        self.write(self.user / "keybindings.json", "[ not json")
        with self.assertRaisesRegex(tool.ConfigError, "keybindings.json"):
            tool.cmd_deploy(self.repo, self.user, write=True)
        self.assertFalse((self.user / "settings.json").exists())
        self.assertEqual((self.user / "keybindings.json").read_text(), "[ not json")

    def test_an_empty_deployed_file_is_an_empty_document(self):
        self.write(self.user / "settings.json", "")
        self.assertEqual(tool.cmd_deploy(self.repo, self.user, write=True), 0)
        self.assertEqual(self.deployed("settings.json"), {"managed": 1, "[python]": {"a": 1}})

    def test_a_symbolic_link_is_not_replaced(self):
        self.write(self.root / "elsewhere.json", "{}")
        (self.user / "settings.json").symlink_to(self.root / "elsewhere.json")
        with self.assertRaisesRegex(tool.ConfigError, "symbolic link"):
            tool.cmd_deploy(self.repo, self.user, write=True)
        self.assertTrue((self.user / "settings.json").is_symlink())


class Extensions(unittest.TestCase):
    """The tool with a stand-in for `code`, the only stub: the process boundary."""

    STAND_IN = """#!/bin/sh
echo "$*" >> "$STATE/calls"
case "$1" in
--list-extensions) cat "$STATE/installed" ;;
--install-extension)
    for argument in "$@"; do
        case "$argument" in
        --install-extension | refused.*) ;;
        *) echo "$argument" >> "$STATE/installed" ;;
        esac
    done
    ;;
esac
"""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "bin").mkdir()
        (self.root / "repo/user").mkdir(parents=True)
        code = self.root / "bin/code"
        code.write_text(self.STAND_IN, encoding="utf-8")
        code.chmod(0o755)
        (self.root / "installed").write_text("Some.Keymap\n", encoding="utf-8")
        environment = {
            "PATH": f"{self.root / 'bin'}{os.pathsep}{os.environ['PATH']}",
            "STATE": str(self.root),
        }
        for patch in (mock.patch.dict(os.environ, environment), mock.patch("builtins.print")):
            patch.start()
            self.addCleanup(patch.stop)

    def manifest(self, manifest):
        (self.root / "repo/user/extensions.json").write_text(json.dumps(manifest), encoding="utf-8")

    def calls(self):
        return (self.root / "calls").read_text(encoding="utf-8").splitlines()

    def test_everything_missing_is_installed_in_one_call(self):
        self.manifest(MANIFEST)
        self.assertEqual(tool.cmd_extensions(self.root / "repo", ["core", "sql"]), 1)
        self.assertEqual(
            self.calls(),
            [
                "--list-extensions",
                "--install-extension official.dbt --install-extension some.linter",
                "--list-extensions",
            ],
        )

    def test_nothing_missing_means_no_install_call_and_success(self):
        self.manifest({"extensions": [{"id": "some.keymap", "group": "core", "purpose": "Keys."}]})
        self.assertEqual(tool.cmd_extensions(self.root / "repo", ["core"]), 0)
        self.assertEqual(self.calls(), ["--list-extensions"])

    def test_an_extension_still_missing_after_the_call_is_a_failure(self):
        self.manifest({"extensions": [{"id": "refused.extension", "group": "core", "purpose": "P."}]})
        self.assertEqual(tool.cmd_extensions(self.root / "repo", ["core"]), 1)

    def test_everything_installed_after_the_call_is_a_success(self):
        self.manifest({"extensions": [{"id": "new.extension", "group": "core", "purpose": "P."}]})
        self.assertEqual(tool.cmd_extensions(self.root / "repo", ["core"]), 0)

    def test_without_the_code_command_the_tool_says_how_to_get_it(self):
        self.manifest(MANIFEST)
        with mock.patch.dict(os.environ, {"PATH": str(self.root / "empty")}):
            with mock.patch.object(Path, "is_file", return_value=False):
                with self.assertRaisesRegex(tool.UsageError, "code"):
                    tool.cmd_extensions(self.root / "repo", ["core"])


class Main(unittest.TestCase):
    def test_an_invalid_source_is_exit_status_2(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(tool, "REPO", Path(directory)), mock.patch("sys.stderr"):
                (Path(directory) / "user").mkdir()
                (Path(directory) / "user/settings.json").write_text("{", encoding="utf-8")
                (Path(directory) / "user/keybindings.json").write_text("[]", encoding="utf-8")
                self.assertEqual(tool.main(["--user-dir", directory, "status"]), 2)


if __name__ == "__main__":
    unittest.main()
