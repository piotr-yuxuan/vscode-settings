"""What the tool must do, as examples taken from plan 001, not from the code."""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tool import vscode_settings as tool

# Shaped like the real manifest: the default member of an exclusive pair is in the core
# group and listed first, its alternative is in an optional group, and identifiers have
# capitals, which VS Code may or may not keep when it lists what is installed.
MANIFEST = {
    "exclusive": [["Official.Dbt", "Other.Dbt"]],
    "extensions": [
        {"id": "Some.Keymap", "group": "core", "purpose": "Keys."},
        {"id": "Official.Dbt", "group": "core", "purpose": "dbt."},
        {"id": "Other.Dbt", "group": "sql", "purpose": "The alternative."},
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

    def test_a_trailing_comma_may_be_followed_by_a_comment(self):
        self.assertEqual(tool.parse_jsonc('{"a": 1, // last\n}', "example"), {"a": 1})

    def test_what_looks_like_a_comment_or_a_trailing_comma_inside_a_string_is_kept(self):
        text = '{"url": "https://example.org/a", "glob": "/* x */", "end": "a, ]"}'
        self.assertEqual(
            tool.parse_jsonc(text, "example"),
            {"url": "https://example.org/a", "glob": "/* x */", "end": "a, ]"},
        )

    def test_a_comment_marker_after_an_escaped_quote_is_still_inside_the_string(self):
        self.assertEqual(
            tool.parse_jsonc(r'{"say": "5\" // 12 inches"}', "example"), {"say": '5" // 12 inches'}
        )

    def test_an_escaped_quote_does_not_end_a_string(self):
        self.assertEqual(
            tool.parse_jsonc(r'{"a": "q\", ]", "b": "\\"}', "example"), {"a": 'q", ]', "b": "\\"}
        )

    def test_a_repeated_key_is_an_error_that_names_the_file_and_the_key(self):
        with self.assertRaisesRegex(tool.ConfigError, "example.*'a'"):
            tool.parse_jsonc('{"a": 1, "b": {"c": 1}, "a": 2}', "example")

    def test_malformed_text_is_an_error_that_names_the_file(self):
        for text in ('{"a": ', '{"a": NaN}', '{"a": Infinity}', '{"a": 1e999}', ""):
            with self.subTest(text=text):
                with self.assertRaisesRegex(tool.ConfigError, "example"):
                    tool.parse_jsonc(text, "example")

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

    def test_a_key_it_cannot_write_is_an_error_not_a_wrong_answer(self):
        for key in ("meta+x", "ctrl++", "hyper+a b", ""):
            with self.subTest(key=key):
                with self.assertRaises(tool.ConfigError):
                    tool.emacs_notation(key)


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

    def test_a_rule_without_a_key_or_a_command_is_an_error_that_names_its_line(self):
        for line in ('{ "key": "f8" }', '{ "command": "x" }', '{ "key": 8, "command": "x" }'):
            with self.subTest(line=line):
                with self.assertRaisesRegex(tool.ConfigError, "example:2"):
                    tool.described_rules(f"[\n  {line}\n]", "example")


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
        self.assertEqual(recommended, {"recommendations": ["Some.Keymap", "Official.Dbt"]})


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

    def test_each_defect_is_found_and_named(self):
        entry = {"id": "a.b", "group": "core", "purpose": "P."}
        other = dict(entry, id="c.d")
        defects = [
            ("edamagit", {"extensions": [dict(entry, id="edamagit")]}),
            ("a.b\\\\n", {"extensions": [dict(entry, id="a.b\n")]}),
            ("twice", {"extensions": [entry, dict(entry, id="A.B")]}),
            ("purpose", {"extensions": [dict(entry, purpose="")]}),
            ("group", {"extensions": [{"id": "a.b", "purpose": "P."}]}),
            ("c.d", {"extensions": [entry], "exclusive": [["a.b", "c.d"]]}),
            ("core", {"extensions": [entry, other], "exclusive": [["a.b", "c.d"]]}),
            ("exclusive", {"extensions": [entry], "exclusive": [["a.b", "A.B"]]}),
            ("exclusive", {"extensions": [entry], "exclusive": [5]}),
            ("exclusive", {"extensions": [entry], "exclusive": None}),
            ("exclusive", {"extensions": [entry], "exclusive": 5}),
            ("exclusive", {"extensions": [entry, other], "exclusive": [["a.b"]]}),
            ("extensions", {"extension": []}),
        ]
        for named, manifest in defects:
            with self.subTest(manifest=manifest):
                findings = tool.manifest_findings(manifest)
                self.assertEqual(len(findings), 1, findings)
                self.assertRegex(findings[0], named)


class ExtensionsToInstall(unittest.TestCase):
    """(to install, blocked) for the requested groups, given what is installed."""

    def decide(self, groups, installed, manifest=MANIFEST):
        return tool.extensions_to_install(manifest, groups, installed)

    def test_only_the_requested_groups_and_only_what_is_missing(self):
        self.assertEqual(self.decide(["core"], ["some.keymap"]), (["Official.Dbt"], []))

    def test_installed_identifiers_compare_without_case(self):
        self.assertEqual(self.decide(["core"], ["SOME.KEYMAP", "official.dbt"]), ([], []))

    def test_the_alternative_is_blocked_while_the_default_is_installed(self):
        self.assertEqual(self.decide(["sql"], ["Official.DBT"]), (["some.linter"], ["Other.Dbt"]))

    def test_the_default_is_blocked_while_the_alternative_is_installed(self):
        self.assertEqual(self.decide(["core"], ["some.keymap", "other.dbt"]), ([], ["Official.Dbt"]))

    def test_requested_together_and_neither_installed_the_first_listed_wins(self):
        self.assertEqual(
            self.decide(["core", "sql"], ["some.keymap"]),
            (["Official.Dbt", "some.linter"], ["Other.Dbt"]),
        )

    def test_the_alternative_alone_is_installed_when_the_default_is_neither_there_nor_asked(self):
        self.assertEqual(self.decide(["sql"], []), (["Other.Dbt", "some.linter"], []))

    def test_the_order_of_a_pair_only_matters_when_neither_is_installed(self):
        reversed_pair = dict(MANIFEST, exclusive=[["Other.Dbt", "Official.Dbt"]])
        self.assertEqual(
            self.decide(["sql"], ["official.dbt"], reversed_pair), (["some.linter"], ["Other.Dbt"])
        )
        self.assertEqual(
            self.decide(["core"], ["some.keymap", "other.dbt"], reversed_pair), ([], ["Official.Dbt"])
        )
        self.assertEqual(
            self.decide(["core", "sql"], ["some.keymap"], reversed_pair),
            (["Other.Dbt", "some.linter"], ["Official.Dbt"]),
        )


class DeploymentPlan(unittest.TestCase):
    """What `apply` would write, decided from values: (baseline, machine-local, deployed) twice."""

    RULE = {"key": "f8", "command": "toggle", "args": True}

    def plan(self, settings=({}, {}, {}), rules=([], [], [])):
        return tool.deployment_plan(settings, rules)

    def test_nothing_changes_when_the_deployed_files_already_hold_everything(self):
        plan = self.plan(
            ({"a": 1}, {"b": 2}, {"mine": 0, "a": 1, "b": 2}), ([self.RULE], [], [self.RULE])
        )
        self.assertEqual([report for report, _ in plan.values()], [[], []])

    def test_settings_keep_what_the_repository_does_not_set_and_the_machine_wins(self):
        settings = ({"a": 1, "[python]": {"x": 1}}, {"a": 2}, {"mine": True, "[python]": {"y": 2}})
        report, text = self.plan(settings)["settings.json"]
        self.assertEqual(json.loads(text), {"mine": True, "[python]": {"y": 2, "x": 1}, "a": 2})
        self.assertEqual(len(report), 2)

    def test_key_bindings_are_the_baseline_rules_then_the_machine_local_ones(self):
        local = {"key": "f8", "command": "local"}
        report, text = self.plan(rules=([self.RULE], [local], []))["keybindings.json"]
        self.assertEqual(json.loads(text), [self.RULE, local])
        self.assertTrue(report)

    def test_a_rule_whose_value_is_one_instead_of_true_is_a_change(self):
        report, _ = self.plan(rules=([self.RULE], [], [dict(self.RULE, args=1)]))["keybindings.json"]
        self.assertTrue(report)

    def test_the_same_rules_in_another_order_are_a_change(self):
        other = {"key": "f8", "command": "other"}
        report, _ = self.plan(rules=([self.RULE, other], [], [other, self.RULE]))["keybindings.json"]
        self.assertTrue(report)

    def test_a_deployed_rule_that_would_be_dropped_is_named(self):
        added = {"key": "f9", "command": "added.in.vscode"}
        report, _ = self.plan(rules=([self.RULE], [], [self.RULE, added]))["keybindings.json"]
        self.assertIn("added.in.vscode", "\n".join(report))


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

    def files(self):
        return {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

    def test_apply_writes_both_files_and_keeps_what_the_repository_does_not_set(self):
        self.write(self.user / "settings.json", '{"mine": true, "[python]": {"b": 2}, "managed": 0}')
        self.write(self.local / "settings.json", '{"local": "x"}')
        self.write(self.local / "keybindings.json", '[{"key": "f8", "command": "local"}]')
        self.assertEqual(tool.cmd_deploy(self.repo, self.user, write=True), 0)
        self.assertEqual(
            self.deployed("settings.json"),
            {"mine": True, "[python]": {"b": 2, "a": 1}, "managed": 1, "local": "x"},
        )
        self.assertEqual(
            self.deployed("keybindings.json"),
            [{"key": "f8", "command": "base"}, {"key": "f8", "command": "local"}],
        )

    def test_status_writes_nothing_and_says_whether_apply_would(self):
        before = self.files()
        self.assertEqual(tool.cmd_deploy(self.repo, self.user, write=False), 1)
        self.assertEqual(self.files(), before)
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

    def test_the_file_found_at_first_is_kept_once_and_the_last_one_each_time(self):
        self.write(self.user / "settings.json", '{"first": 1}')
        tool.cmd_deploy(self.repo, self.user, write=True)
        self.write(self.user / "settings.json", '{"second": 2}')
        tool.cmd_deploy(self.repo, self.user, write=True)
        backup = self.local / "backup"
        self.assertEqual(json.loads((backup / "settings.json.original").read_text()), {"first": 1})
        self.assertEqual(json.loads((backup / "settings.json.previous").read_text()), {"second": 2})

    def test_the_mode_of_a_replaced_file_is_kept_and_a_new_file_is_for_its_owner_only(self):
        self.write(self.user / "settings.json", "{}")
        (self.user / "settings.json").chmod(0o640)
        tool.cmd_deploy(self.repo, self.user, write=True)
        self.assertEqual(stat.S_IMODE((self.user / "settings.json").stat().st_mode), 0o640)
        self.assertEqual(stat.S_IMODE((self.user / "keybindings.json").stat().st_mode), 0o600)

    def test_a_write_that_fails_leaves_the_file_its_backups_and_the_directory_as_they_were(self):
        self.write(self.user / "settings.json", '{"first": 1}')
        tool.cmd_deploy(self.repo, self.user, write=True)
        self.write(self.user / "settings.json", '{"second": 2}')
        before = self.files()
        with mock.patch("os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                tool.cmd_deploy(self.repo, self.user, write=True)
        self.assertEqual(self.files(), before)

    def test_a_deployed_file_that_cannot_be_read_stops_everything_before_any_write(self):
        unreadable = {"not JSON": b"[ not json", "not UTF-8": b'["caf\xe9"]'}
        for reason, content in unreadable.items():
            with self.subTest(reason=reason):
                (self.user / "keybindings.json").write_bytes(content)
                before = self.files()
                with self.assertRaisesRegex(tool.ConfigError, "keybindings.json"):
                    tool.cmd_deploy(self.repo, self.user, write=True)
                self.assertEqual(self.files(), before)

    def test_the_first_content_is_kept_even_when_keeping_it_failed_once(self):
        self.write(self.user / "settings.json", '{"first": 1}')
        copy, calls = shutil.copy2, []

        def fail_the_second_copy(source, target):
            calls.append(target)
            if len(calls) == 2:
                raise OSError("disk full")
            return copy(source, target)

        with mock.patch("shutil.copy2", side_effect=fail_the_second_copy):
            with self.assertRaises(OSError):
                tool.cmd_deploy(self.repo, self.user, write=True)
        self.assertEqual(self.deployed("settings.json"), {"first": 1})
        tool.cmd_deploy(self.repo, self.user, write=True)
        original = self.local / "backup/settings.json.original"
        self.assertEqual(json.loads(original.read_text(encoding="utf-8")), {"first": 1})

    def test_a_machine_local_rule_that_is_not_a_key_and_a_command_stops_everything(self):
        for rules in ('[{"command": "x"}]', '[{"key": "f8", "command": "x"}, 42]', '["text"]'):
            with self.subTest(rules=rules):
                self.write(self.local / "keybindings.json", rules)
                before = self.files()
                with self.assertRaisesRegex(tool.ConfigError, "keybindings.json"):
                    tool.cmd_deploy(self.repo, self.user, write=True)
                self.assertEqual(self.files(), before)

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

    def test_docs_writes_the_generated_files(self):
        self.write(self.repo / "user/extensions.json", json.dumps(MANIFEST))
        self.write(self.repo / "user/keybindings.json", RULES)
        self.assertEqual(tool.cmd_docs(self.repo), 0)
        for name, text in tool.generated_files(RULES, MANIFEST).items():
            with self.subTest(file=name):
                self.assertEqual((self.repo / name).read_text(encoding="utf-8"), text)


class Extensions(unittest.TestCase):
    """The tool with a stand-in for `code`, the only stub: the process boundary."""

    STAND_IN = """#!/bin/sh
echo "$*" >> "$STATE/calls"
case "$1" in
--list-extensions)
    cat "$STATE/installed"
    exit "$(cat "$STATE/list-status")"
    ;;
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
        (self.root / "list-status").write_text("0", encoding="utf-8")
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
        calls = self.root / "calls"
        return calls.read_text(encoding="utf-8").splitlines() if calls.is_file() else []

    def installed(self):
        return (self.root / "installed").read_text(encoding="utf-8").split()

    def test_everything_missing_is_installed_in_one_call(self):
        self.manifest(MANIFEST)
        self.assertEqual(tool.cmd_extensions(self.root / "repo", ["core", "sql"]), 0)
        self.assertEqual(
            self.calls(),
            [
                "--list-extensions",
                "--install-extension Official.Dbt --install-extension some.linter",
                "--list-extensions",
            ],
        )

    def test_two_exclusive_extensions_are_never_both_installed(self):
        self.manifest(MANIFEST)
        (self.root / "installed").write_text("Some.Keymap\nother.dbt\n", encoding="utf-8")
        self.assertEqual(tool.cmd_extensions(self.root / "repo", ["core"]), 0)
        self.assertNotIn("Official.Dbt", self.installed())
        tool.cmd_extensions(self.root / "repo", ["core", "sql"])
        self.assertNotIn("Official.Dbt", self.installed())

    def test_nothing_missing_means_no_install_call_and_success(self):
        self.manifest({"extensions": [{"id": "some.keymap", "group": "core", "purpose": "Keys."}]})
        self.assertEqual(tool.cmd_extensions(self.root / "repo", ["core"]), 0)
        self.assertEqual(self.calls(), ["--list-extensions"])

    def test_an_extension_still_missing_after_the_call_is_a_failure(self):
        self.manifest({"extensions": [{"id": "refused.extension", "group": "core", "purpose": "P."}]})
        self.assertEqual(tool.cmd_extensions(self.root / "repo", ["core"]), 1)

    def test_a_listing_that_fails_is_a_failure_and_nothing_is_installed(self):
        self.manifest(MANIFEST)
        (self.root / "list-status").write_text("3", encoding="utf-8")
        with mock.patch("sys.stderr"), self.assertRaises(OSError):
            tool.cmd_extensions(self.root / "repo", ["core", "sql"])
        self.assertEqual(self.calls(), ["--list-extensions"])

    def test_an_unknown_group_is_refused_before_vscode_is_run(self):
        self.manifest(MANIFEST)
        with self.assertRaisesRegex(tool.UsageError, "nope"):
            tool.cmd_extensions(self.root / "repo", ["core", "nope"])
        self.assertEqual(self.calls(), [])

    def test_without_the_code_command_the_tool_says_how_to_get_it(self):
        self.manifest(MANIFEST)
        with mock.patch.dict(os.environ, {"PATH": str(self.root / "empty")}):
            with mock.patch.object(Path, "is_file", return_value=False):
                with self.assertRaisesRegex(tool.UsageError, "code"):
                    tool.cmd_extensions(self.root / "repo", ["core"])


class Main(unittest.TestCase):
    def status(self, settings: bytes) -> int:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "user").mkdir()
            (repo / "user/settings.json").write_bytes(settings)
            (repo / "user/keybindings.json").write_bytes(b"[]")
            with (
                mock.patch.object(tool, "REPO", repo),
                mock.patch("sys.stderr"),
                mock.patch("builtins.print"),
            ):
                return tool.main(["--user-dir", str(repo / "data/User"), "status"])

    def test_a_source_that_cannot_be_used_is_exit_status_2(self):
        for reason, settings in {
            "not JSON": b"{",
            "not UTF-8": b'{"a": "caf\xe9"}',
            "an array": b"[]",
        }.items():
            with self.subTest(reason=reason):
                self.assertEqual(self.status(settings), 2)

    def test_something_pending_is_exit_status_1(self):
        self.assertEqual(self.status(b'{"a": 1}'), 1)


if __name__ == "__main__":
    unittest.main()
