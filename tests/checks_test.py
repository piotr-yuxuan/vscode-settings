"""Every check rejects what it must reject and accepts what it must accept."""

from __future__ import annotations

import unittest

from tests import checks

RULE = {"key": "ctrl+x g", "command": "magit.status", "when": "!terminalFocus"}


class BindingFindings(unittest.TestCase):
    def assert_rejected(self, described):
        self.assertNotEqual(checks.binding_findings(described), [])

    def test_well_formed_rules_pass(self):
        described = [
            ("Git", "Status", RULE),
            ("Git", "Removal", {"key": "alt+x g", "command": "-magit.status"}),
            ("Git", "Same key, another condition", dict(RULE, when="terminalFocus")),
            (
                "Keys",
                "Named and punctuation keys",
                {"key": "ctrl+alt+= f8 shift+enter", "command": "x"},
            ),
            ("Keys", "Navigation keys", {"key": "ctrl+home pageup", "command": "y"}),
        ]
        self.assertEqual(checks.binding_findings(described), [])

    def test_a_rule_without_a_description_is_rejected(self):
        self.assert_rejected([("Git", "", RULE)])

    def test_a_key_that_vscode_cannot_read_is_rejected(self):
        for key in ("C-x g", "control+x", "meta+x", "ctrl+", "ctrl+x  g", "Ctrl+X", "ctrl+x\n", ""):
            with self.subTest(key=key):
                self.assert_rejected([("Git", "Status", dict(RULE, key=key))])

    def test_a_rule_that_is_not_a_key_and_a_command_is_rejected(self):
        self.assert_rejected([("Git", "Status", {"key": "f8"})])

    def test_two_rules_with_the_same_key_and_condition_are_rejected(self):
        self.assert_rejected([("Git", "Status", RULE), ("Git", "Other", dict(RULE, command="other"))])

    def test_the_same_removal_twice_is_rejected(self):
        removal = {"key": "alt+x g", "command": "-magit.status"}
        self.assert_rejected([("Git", "Once", removal), ("Git", "Twice", removal)])


class TerminalFindings(unittest.TestCase):
    def test_rules_that_leave_the_shell_its_keys_pass(self):
        rules = [
            RULE,
            {"key": "ctrl+c r", "command": "format", "when": "editorTextFocus && !editorReadonly"},
            {"key": "ctrl+x g", "command": "-magit.status"},
            {"key": "f8", "command": "toggle"},
            {"key": "alt+c", "command": "send", "when": "terminalFocus"},
        ]
        self.assertEqual(checks.terminal_findings(rules), [])

    def test_a_ctrl_c_rule_that_may_be_active_in_the_terminal_is_rejected(self):
        conditions = (
            None,
            "isMac",
            "!editorTextFocus",
            "editorTextFocus || terminalFocus",
            "terminalFocus",
        )
        for when in conditions:
            rule = {"key": "ctrl+c t", "command": "x"} if when is None else dict(RULE, when=when)
            with self.subTest(when=when):
                self.assertNotEqual(checks.terminal_findings([rule]), [])


class PrivateFindings(unittest.TestCase):
    # The values a check must reject are assembled here, so that this file passes the check.
    HOMES = [
        "/ho" + "me/alice/src",
        "/Us" + "ers/alice",
        "/Us" + "ers/Alice",
        "/ho" + "me/_svc",
        "/ho" + "me/7of9",
    ]
    MAIL = "alice" + "@" + "corp.invalid"

    def test_public_text_passes(self):
        text = "Clone into ~/src, not /home/<name>. Write to someone@example.org or team@example.com.\n"
        self.assertEqual(
            checks.private_findings(text + "Acmeism, a macadam road.", ["Acme", "cad"]), []
        )

    def test_a_home_directory_path_is_rejected_with_its_line(self):
        for path in self.HOMES:
            with self.subTest(path=path):
                findings = checks.private_findings(f"first line\nsee {path}\n", [])
                self.assertEqual(len(findings), 1)
                self.assertIn("line 2", findings[0])

    def test_an_e_mail_address_is_rejected(self):
        self.assertNotEqual(checks.private_findings(f"write to {self.MAIL}", []), [])

    def test_a_denied_term_is_rejected_whatever_its_case_where_no_letter_touches_it(self):
        for text in (
            "at Acme, we",
            "ACME rules",
            "the acme.example host",
            "acme-corp",
            "acme_corp",
            "x/Acme Corp/y",
        ):
            with self.subTest(text=text):
                self.assertNotEqual(checks.private_findings(text, ["Acme"]), [])
        self.assertNotEqual(checks.private_findings("at Acme Corp today", ["acme corp"]), [])


class DashFindings(unittest.TestCase):
    def test_hyphens_pass(self):
        self.assertEqual(checks.dash_findings("a well-known range, 1 to 5 - no dash\n"), [])

    def test_an_en_dash_and_an_em_dash_are_rejected_with_their_lines(self):
        text = f"ok\n1{chr(0x2013)}5\nnever{chr(0x2014)}ever\n"
        self.assertEqual(checks.dash_findings(text), ["line 2: Unicode dash", "line 3: Unicode dash"])


class LinkFindings(unittest.TestCase):
    PAGES = {
        "docs/README.md": "# Index\n\n## How-to guides\n",
        "docs/how-to/a.md": "# A page\n\n## Step one: do it!\n",
    }
    TRACKED = {*PAGES, "user/settings.json", "docs/work/plans/001-x.md"}

    def findings(self, text):
        pages = dict(self.PAGES, **{"docs/how-to/page.md": text})
        return checks.link_findings(
            "docs/how-to/page.md", pages, self.TRACKED | {"docs/how-to/page.md"}
        )

    def test_links_that_lead_somewhere_pass(self):
        text = (
            "[page](a.md) [heading](a.md#step-one-do-it) [index](../README.md#how-to-guides)\n"
            "[file](../../user/settings.json) [directory](../work/plans) [web](https://example.org/x)\n"
            "[self](#top)\n\n# Top\n\n`[not a link](nowhere.md)`\n\n```\n[nor this](nowhere.md)\n```\n"
        )
        self.assertEqual(self.findings(text), [])

    def test_a_link_to_a_file_that_is_not_tracked_is_rejected(self):
        self.assertEqual(len(self.findings("[gone](b.md) and [fine](a.md)")), 1)

    def test_no_way_of_writing_a_link_escapes_the_check(self):
        links = (
            '[t](b.md "title")',
            "[t](<b.md>)",
            "[t](/docs/how-to/a.md)",
            "[t](~/a.md)",
            "[t]( b.md )",
        )
        for link in links:
            with self.subTest(link=link):
                self.assertEqual(len(self.findings(link)), 1)

    def test_a_fence_of_tildes_hides_links_and_a_heading_keeps_the_words_of_its_code(self):
        pages = dict(self.PAGES, **{"docs/how-to/a.md": "# A\n\n## The `apply` command\n"})
        pages["docs/how-to/page.md"] = (
            "[ok](a.md#the-apply-command) [gone](a.md#the--command)\n\n~~~\n[hidden](nowhere.md)\n~~~\n"
        )
        findings = checks.link_findings(
            "docs/how-to/page.md", pages, self.TRACKED | {"docs/how-to/page.md"}
        )
        self.assertEqual(len(findings), 1)
        self.assertIn("the--command", findings[0])

    def test_a_link_to_a_heading_that_does_not_exist_is_rejected(self):
        self.assertEqual(len(self.findings("[gone](a.md#step-two)")), 1)


class IndexFindings(unittest.TestCase):
    INDEX = "- [A](how-to/a.md): one.\n- [B](reference/b.md): two.\n"

    def test_pages_linked_once_pass(self):
        self.assertEqual(checks.index_findings(self.INDEX, ["how-to/a.md", "reference/b.md"]), [])

    def test_a_page_that_is_not_in_the_index_is_rejected(self):
        self.assertEqual(len(checks.index_findings(self.INDEX, ["how-to/a.md", "how-to/c.md"])), 1)

    def test_a_page_linked_twice_is_rejected(self):
        self.assertEqual(len(checks.index_findings(self.INDEX + self.INDEX, ["how-to/a.md"])), 1)


if __name__ == "__main__":
    unittest.main()
