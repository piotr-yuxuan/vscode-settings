"""Checks of what this repository tracks.

Each check takes text or values and returns findings, one string each; an empty list means
the input passes. `checks_test.py` gives every check an input it must reject and one it
must accept; `repository_test.py` applies them to the tracked files.
"""

from __future__ import annotations

import posixpath
import re

# The modifiers are those `tool.emacs_notation` can write, which the key reference needs.
_STROKE = re.compile(
    r"((ctrl|shift|alt|cmd)\+)*"
    r"([a-z0-9]|f[0-9]{1,2}|enter|escape|space|tab|backspace|delete|home|end"
    r"|up|down|left|right|[`\-=\[\];',./\\])"
)
_HOME = re.compile(r"/(?:home|Users)/[A-Za-z0-9_][\w.-]*")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PUBLIC_MAIL = ("@example.com", "@example.org", ".example")
_LINK = re.compile(r"""\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+["'(][^)]*)?\s*\)""")
_FENCED = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
# The en dash and the em dash, written by number so that this file holds neither.
_DASHES = (chr(0x2013), chr(0x2014))


def binding_findings(described: list) -> list:
    """Find the key binding rules that VS Code or a reader could not use.

    `described` is what `tool.described_rules` returns: (section, description, rule).
    """
    findings, seen = [], set()
    for _, description, rule in described:
        key, command = rule.get("key"), rule.get("command")
        if not isinstance(key, str) or not isinstance(command, str):
            findings.append(f"{rule!r}: `key` and `command` must be strings")
            continue
        if not description:
            findings.append(f"{key!r}: no description on the line above the rule")
        if not key or not all(_STROKE.fullmatch(stroke) for stroke in key.split(" ")):
            findings.append(f"{key!r}: not a key that this repository can read and document")
        identity = (key, command) if command.startswith("-") else (key, rule.get("when", ""))
        if identity in seen:
            findings.append(f"{key!r}: an earlier rule has the same key and the same condition")
        seen.add(identity)
    return findings


def terminal_findings(rules: list) -> list:
    """Find the rules that would take `C-c` or `C-x` away from the shell in the terminal.

    A rule is known to be off in the terminal when its condition is a conjunction that
    holds `!terminalFocus` or `editorTextFocus`; with an `||` nothing is known.
    """
    findings = []
    for rule in rules:
        if rule["key"].split(" ")[0] not in ("ctrl+c", "ctrl+x") or rule["command"].startswith("-"):
            continue
        when = rule.get("when", "")
        conjuncts = {part.strip() for part in when.split("&&")}
        if "||" in when or not conjuncts & {"!terminalFocus", "editorTextFocus"}:
            findings.append(
                f"{rule['key']!r}: starts with ctrl+c or ctrl+x and is not off in the terminal"
            )
    return findings


def private_findings(text: str, deny: list) -> list:
    """Find values that must not be published: home paths, e-mail addresses, denied terms.

    A denied term matches anywhere, whatever its case: a leak cannot be taken back, while a
    false alarm only costs a rewording. A term written with a leading `=` matches only
    where no letter or digit touches it, which is what a short acronym needs.
    """
    patterns = [("home directory path", _HOME), ("e-mail address", _EMAIL)]
    for term in deny:
        word = re.escape(term[1:] if term.startswith("=") else term)
        alone = rf"(?<![A-Za-z0-9]){word}(?![A-Za-z0-9])" if term.startswith("=") else word
        patterns.append(("denied term", re.compile(alone, re.I)))
    return [
        f"line {number}: {label} {match.group()!r}"
        for number, line in enumerate(text.splitlines(), 1)
        for label, pattern in patterns
        for match in pattern.finditer(line)
        if not (pattern is _EMAIL and match.group().endswith(_PUBLIC_MAIL))
    ]


def dash_findings(text: str) -> list:
    """Find the lines that hold an en dash or an em dash."""
    return [
        f"line {number}: Unicode dash"
        for number, line in enumerate(text.splitlines(), 1)
        if any(dash in line for dash in _DASHES)
    ]


def link_findings(page: str, pages: dict, tracked: set) -> list:
    """Find the links of a Markdown page that lead nowhere in the repository.

    `pages` maps each tracked Markdown path to its text, `tracked` holds every tracked path.
    A link is relative to its page; only a link with a scheme, such as `https:`, leaves the
    repository. Links inside code are not links. A fragment must be a heading of the target.
    """
    findings = []
    for target in _LINK.findall(_INLINE_CODE.sub("", _FENCED.sub("", pages[page]))):
        if re.match(r"[a-z][a-z0-9+.-]*:", target):
            continue
        relative, _, fragment = target.partition("#")
        resolved = (
            posixpath.normpath(posixpath.join(posixpath.dirname(page), relative)) if relative else page
        )
        if resolved not in tracked and not any(path.startswith(f"{resolved}/") for path in tracked):
            findings.append(f"{page}: link to {target!r}, which is not tracked")
        elif fragment and resolved in pages:
            headings = re.findall(r"^#+ (.+)$", _FENCED.sub("", pages[resolved]), re.M)
            anchors = {
                re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")
                for heading in headings
            }
            if fragment not in anchors:
                findings.append(f"{page}: link to {target!r}, which is not a heading of that page")
    return findings


def index_findings(index: str, pages: list) -> list:
    """Find the documentation pages that `docs/README.md` does not link exactly once.

    `pages` are paths relative to `docs/`, such as `how-to/name.md`.
    """
    return [
        f"docs/{page}: linked {index.count(f']({page})')} times from docs/README.md, not once"
        for page in pages
        if index.count(f"]({page})") != 1
    ]
