"""Deploy this repository's VS Code configuration to the machine it runs on.

    bin/vscode-settings status                what `apply` would change; writes nothing
    bin/vscode-settings apply                 write settings.json and keybindings.json
    bin/vscode-settings extensions [GROUP...] install the missing extensions (default: core)
    bin/vscode-settings docs                  regenerate the files generated from the sources

Exit status: 0 done or nothing to do, 1 something is pending or failed, 2 the request or a
file cannot be used. Standard library only, Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# A string literal comes first in each pattern, so that what it holds is never taken for a
# comment or a trailing comma.
_COMMENT = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.S)
_TRAILING_COMMA = re.compile(r'"(?:\\.|[^"\\])*"|,(?=\s*[\]}])')
_SECTION = re.compile(r"^\s*// == (.+) ==\s*$")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*\.[A-Za-z0-9][A-Za-z0-9-]*")

_EMACS_MODIFIERS = {"ctrl": "C-", "alt": "M-", "shift": "S-", "cmd": "s-"}
_EMACS_NAMES = {"enter": "RET", "space": "SPC", "tab": "TAB", "escape": "ESC", "backspace": "DEL"}
_SHIFTED = dict(zip("`1234567890-=[];',./\\", '~!@#$%^&*()_+{}:"<>?|'))

_MAC_CODE = "Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"


class ConfigError(Exception):
    """A file cannot be used as it is; the message names it."""


class UsageError(Exception):
    """The request cannot be carried out on this machine or with these arguments."""


def parse_jsonc(text: str, source: str, expect: type | None = None):
    """Read JSON with comments and trailing commas; a repeated key in one object is an error."""

    def unique(pairs):
        keys = [key for key, _ in pairs]
        repeated = sorted({key for key in keys if keys.count(key) > 1})
        if repeated:
            raise ValueError(f"repeated key {repeated[0]!r}")
        return dict(pairs)

    def not_json(constant):
        raise ValueError(f"{constant} is not JSON")

    def keep_strings(match):
        # Comments become spaces, newlines kept, so that an error still names the right line.
        return match.group() if match.group().startswith('"') else re.sub(r"[^\n]", " ", match.group())

    strict = _TRAILING_COMMA.sub(keep_strings, _COMMENT.sub(keep_strings, text))
    try:
        value = json.loads(strict, object_pairs_hook=unique, parse_constant=not_json)
    except ValueError as error:
        raise ConfigError(f"{source}: {error}") from error
    if expect is not None and not isinstance(value, expect):
        raise ConfigError(f"{source}: expected {'an object' if expect is dict else 'an array'}")
    return value


def deep_merge(base: dict, over: dict) -> dict:
    """Overlay `over` on `base`: objects merge key by key at every depth, anything else replaces."""
    merged = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def differences(old: dict, new: dict, path: tuple = ()) -> list:
    """List (path, old, new) for each leaf of `new` that `old` lacks or holds differently.

    Values are compared and returned as JSON text, so that `true` is not `1`.
    """
    found = []
    for key, value in new.items():
        before = old.get(key)
        if isinstance(value, dict) and isinstance(before, dict):
            found += differences(before, value, (*path, key))
            continue
        was = json.dumps(before, sort_keys=True) if key in old else "absent"
        now = json.dumps(value, sort_keys=True)
        if was != now:
            found.append(((*path, key), was, now))
    return found


def deployment_plan(settings: tuple, rules: tuple) -> dict:
    """Decide what `apply` writes: {file name: (what changes, new content)}.

    Each argument is (baseline, machine-local, deployed). Nothing changes for a file whose
    list of changes is empty. Deployed settings keep every key that neither the baseline nor
    the machine sets: the result is deployed, overlaid by (baseline overlaid by machine-local).
    Key bindings are the baseline rules then the machine-local ones; a rule is compared as
    JSON text, and the order of the rules counts, since VS Code lets the later rule win.
    """
    baseline, local, deployed = settings
    target = deep_merge(deployed, deep_merge(baseline, local))
    report = [f"{' > '.join(path)}: {was} -> {now}" for path, was, now in differences(deployed, target)]
    plan = {"settings.json": (report, json.dumps(target, indent=2, ensure_ascii=False) + "\n")}

    baseline, local, deployed = rules
    wanted = [json.dumps(rule, sort_keys=True) for rule in baseline + local]
    present = [json.dumps(rule, sort_keys=True) for rule in deployed]
    report = []
    if present != wanted:
        report = [f"{len(wanted)} rules to write"] + [
            f"drops {rule}" for rule in present if rule not in wanted
        ]
    lines = ",\n".join("  " + json.dumps(rule, ensure_ascii=False) for rule in baseline + local)
    plan["keybindings.json"] = (report, f"[\n{lines}\n]\n")
    return plan


def emacs_notation(key: str) -> str:
    """Write a VS Code key such as `ctrl+x shift+o` the way Emacs does: `C-x O`."""
    strokes = []
    for stroke in key.split():
        *modifiers, name = stroke.split("+")
        if not name or set(modifiers) - set(_EMACS_MODIFIERS):
            raise ConfigError(
                f"{key!r}: a stroke is modifiers among {sorted(_EMACS_MODIFIERS)}, then a key"
            )
        if "shift" in modifiers and (name in _SHIFTED or (len(name) == 1 and name.isalpha())):
            modifiers.remove("shift")
            name = _SHIFTED.get(name, name.upper())
        elif len(name) > 1:
            name = _EMACS_NAMES.get(name, f"<{name}>")
        prefix = "".join(text for modifier, text in _EMACS_MODIFIERS.items() if modifier in modifiers)
        strokes.append(prefix + name)
    if not strokes:
        raise ConfigError("an empty key")
    return " ".join(strokes)


def described_rules(text: str, source: str) -> list:
    """Read the key bindings source as lines: (section, description, rule) for each rule.

    A rule is one line that starts with `{`; its description is the comment lines just above
    it; `// == Title ==` starts a section.
    """
    section, description, found = "", [], []
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        heading = _SECTION.match(line)
        if heading:
            section, description = heading.group(1), []
        elif stripped.startswith("//"):
            description.append(stripped[2:].strip())
        elif stripped.startswith("{"):
            rule = parse_jsonc(stripped.rstrip(","), f"{source}:{number}", dict)
            if not isinstance(rule.get("key"), str) or not isinstance(rule.get("command"), str):
                raise ConfigError(f"{source}:{number}: a rule needs a `key` and a `command`, both text")
            found.append((section, " ".join(description), rule))
            description = []
        else:
            description = []
    return found


def manifest_findings(manifest: dict) -> list:
    """Say what is wrong with an extension manifest; an empty list means it can be used."""
    entries = manifest.get("extensions")
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        return ["`extensions` must be a list of objects"]
    findings = []
    for entry in entries:
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not _IDENTIFIER.fullmatch(identifier):
            findings.append(f"{identifier!r} is not a publisher.name identifier")
        findings += [
            f"{identifier!r} has no {field}"
            for field in ("group", "purpose")
            if not isinstance(entry.get(field), str) or not entry[field].strip()
        ]
    groups = {str(entry.get("id")).lower(): entry.get("group") for entry in entries}
    if len(groups) != len(entries):
        findings.append("an identifier is listed twice (case is ignored)")
    for pair in manifest.get("exclusive", []):
        names = {str(name).lower() for name in pair} if isinstance(pair, list) else set()
        if len(names) != 2 or len(pair) != 2:
            findings.append(f"exclusive {pair!r} must name two different extensions")
        elif names - set(groups):
            findings.append(
                f"exclusive {pair!r} names {sorted(names - set(groups))}, which is not listed"
            )
        elif all(groups[name] == "core" for name in names):
            findings.append(f"exclusive {pair!r} are both in the core group")
    return findings


def generated_files(keybindings_text: str, manifest: dict) -> dict:
    """Return {repository path: content} for every file generated from the sources."""
    page = [
        "# Key bindings",
        "",
        "Generated by `bin/vscode-settings docs` from `user/keybindings.json`.",
        "Do not edit; regenerate it.",
        "",
        "These are the rules this repository adds, in the order VS Code reads them: where two",
        "rules share a key, the later one wins when its condition holds. The *Emacs* column is the",
        "key as Emacs writes it (`C-` is Control, `M-` is Alt or Option, `s-` is Command). A command",
        "that starts with `-` removes a binding that VS Code or an extension would otherwise add.",
        "The keys of the Emacs keymap extension itself are not repeated here.",
    ]
    section = None
    for rule_section, description, rule in described_rules(keybindings_text, "user/keybindings.json"):
        if rule_section != section:
            section = rule_section
            page += [
                "",
                f"## {section}",
                "",
                "| Emacs | VS Code | Does | Command | When |",
                "|---|---|---|---|---|",
            ]
        cells = [emacs_notation(rule["key"]), rule["key"], rule["command"], rule.get("when", "")]
        code = [f"`{cell}`".replace("|", "\\|") if cell else "" for cell in cells]
        does = description.replace("|", "\\|")
        page.append(f"| {code[0]} | {code[1]} | {does} | {code[2]} | {code[3]} |")
    core = [entry["id"] for entry in manifest["extensions"] if entry["group"] == "core"]
    recommendations = json.dumps({"recommendations": core}, indent=2)
    banner = "// Generated by `bin/vscode-settings docs` from user/extensions.json. Do not edit.\n"
    return {
        "docs/reference/keybindings.md": "\n".join(page) + "\n",
        ".vscode/extensions.json": banner + recommendations + "\n",
    }


def user_dir(platform: str, env, home: Path) -> Path:
    """Return the directory where VS Code keeps the user's settings.json on this platform."""
    if platform == "linux":
        return Path(env.get("XDG_CONFIG_HOME") or home / ".config") / "Code" / "User"
    if platform == "darwin":
        return home / "Library" / "Application Support" / "Code" / "User"
    raise UsageError(f"unsupported platform {platform!r}: only Linux and macOS are handled")


def extensions_to_install(manifest: dict, groups: list, installed: list) -> tuple:
    """Decide (to install, blocked) for the requested groups, comparing identifiers without case.

    Of two exclusive extensions, the one that is installed blocks the other. When neither is
    installed and the first of the pair is requested, the first blocks the second.
    """
    have = {identifier.lower() for identifier in installed}
    missing = [
        entry["id"]
        for entry in manifest["extensions"]
        if entry["group"] in groups and entry["id"].lower() not in have
    ]
    wanted = {identifier.lower() for identifier in missing}
    blocked = set()
    for first, second in manifest.get("exclusive", []):
        first, second = first.lower(), second.lower()
        if first in have:
            blocked.add(second)
        elif second in have:
            blocked.add(first)
        elif first in wanted:
            blocked.add(second)
    return (
        [identifier for identifier in missing if identifier.lower() not in blocked],
        [identifier for identifier in missing if identifier.lower() in blocked],
    )


def read_text(path: Path) -> str:
    """Read a file as UTF-8 text; anything else is an error that names the file."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ConfigError(f"{path}: not UTF-8 text ({error})") from error


def read_optional(path: Path, kind: type):
    """Parse a file that may be absent or empty; either is the empty document of that kind."""
    text = read_text(path) if path.is_file() else ""
    return parse_jsonc(text, str(path), kind) if text.strip() else kind()


def load_manifest(repo: Path) -> dict:
    """Read and check the extension manifest of the repository."""
    source = "user/extensions.json"
    manifest = parse_jsonc(read_text(repo / source), source, dict)
    findings = manifest_findings(manifest)
    if findings:
        raise ConfigError(f"{source}: " + "; ".join(findings))
    return manifest


def write_file(path: Path, text: str, backup: Path) -> None:
    """Replace `path` in one step, keeping in `backup` a copy of what it held.

    The first content ever replaced stays as `<name>.original`, the latest as
    `<name>.previous`. A failure leaves the file, its backups and both directories as they
    were. A replaced file keeps its mode; a new one is readable by its owner only.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    kept, original = backup / f"{path.name}.kept", backup / f"{path.name}.original"
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        if path.exists():
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, kept)
            shutil.copymode(path, temporary)
        os.replace(temporary, path)
    except BaseException:
        for leftover in (Path(temporary), kept):
            leftover.unlink(missing_ok=True)
        raise
    if kept.exists():
        if not original.exists():
            shutil.copy2(kept, f"{original}.partial")
            os.replace(f"{original}.partial", original)
        os.replace(kept, backup / f"{path.name}.previous")


def cmd_deploy(repo: Path, user: Path, write: bool) -> int:
    """`status` and `apply`: read everything, decide both files, report, then write if asked."""
    local = user.parent / "vscode-settings.local"
    for name in ("settings.json", "keybindings.json"):
        if (user / name).is_symlink():
            raise ConfigError(f"{user / name} is a symbolic link; it is not replaced")
    plan = deployment_plan(
        (
            parse_jsonc(read_text(repo / "user/settings.json"), "user/settings.json", dict),
            read_optional(local / "settings.json", dict),
            read_optional(user / "settings.json", dict),
        ),
        (
            parse_jsonc(read_text(repo / "user/keybindings.json"), "user/keybindings.json", list),
            read_optional(local / "keybindings.json", list),
            read_optional(user / "keybindings.json", list),
        ),
    )
    print(f"machine-local directory: {local}" + ("" if local.is_dir() else " (absent)"))
    changed = {name: change for name, change in plan.items() if change[0]}
    for name, (report, text) in changed.items():
        print(f"{user / name}: {'written' if write else 'apply would change'}")
        print("\n".join(f"  {line}" for line in report))
        if write:
            write_file(user / name, text, local / "backup")
    if not changed:
        print("in sync: nothing to apply")
    return 1 if changed and not write else 0


def run_code(code: str, arguments: list, must_succeed: bool) -> str:
    """Run VS Code's command line with a deadline; return what it printed."""
    result = subprocess.run([code, *arguments], capture_output=True, text=True, timeout=900)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        if must_succeed:
            raise OSError(f"`code {' '.join(arguments)}` failed with status {result.returncode}")
    return result.stdout


def cmd_extensions(repo: Path, groups: list) -> int:
    """`extensions`: install what the requested groups lack, in one call, then say what happened."""
    manifest = load_manifest(repo)
    known = sorted({entry["group"] for entry in manifest["extensions"]})
    unknown = sorted(set(groups) - set(known))
    if unknown:
        raise UsageError(f"unknown group {unknown[0]!r}; the groups are: {', '.join(known)}")
    candidates = [Path("/") / _MAC_CODE, Path.home() / _MAC_CODE]
    code = shutil.which("code") or next((str(path) for path in candidates if path.is_file()), None)
    if code is None:
        raise UsageError(
            "the `code` command was not found; in VS Code run "
            "'Shell Command: Install 'code' command in PATH' from the Command Palette"
        )
    # A listing that fails says nothing about what is installed: it must not be read as "nothing".
    installed = run_code(code, ["--list-extensions"], must_succeed=True).split()
    missing, blocked = extensions_to_install(manifest, groups, installed)
    still_missing = []
    if missing:
        install = [
            argument for identifier in missing for argument in ("--install-extension", identifier)
        ]
        run_code(code, install, must_succeed=False)
        installed = run_code(code, ["--list-extensions"], must_succeed=True).split()
        still_missing = extensions_to_install(manifest, groups, installed)[0]
    for identifier in missing:
        print(f"{identifier}: {'STILL MISSING' if identifier in still_missing else 'installed'}")
    for identifier in blocked:
        print(f"{identifier}: left out, the extension it is exclusive with is installed or comes first")
    if not missing and not blocked:
        print(f"nothing to install for: {', '.join(groups)}")
    return 1 if still_missing else 0


def cmd_docs(repo: Path) -> int:
    """`docs`: rewrite the files generated from the sources."""
    keybindings = read_text(repo / "user/keybindings.json")
    for relative, text in generated_files(keybindings, load_manifest(repo)).items():
        (repo / relative).parent.mkdir(parents=True, exist_ok=True)
        (repo / relative).write_text(text, encoding="utf-8")
        print(f"generated {relative}")
    return 0


def main(argv: list) -> int:
    """Parse the command line, run one command, turn its errors into an exit status."""
    parser = argparse.ArgumentParser(prog="vscode-settings", description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--user-dir", type=Path, help="VS Code's User directory, if not the default one"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="what apply would change; writes nothing")
    commands.add_parser("apply", help="write settings.json and keybindings.json")
    commands.add_parser("docs", help="regenerate the files generated from the sources")
    install = commands.add_parser("extensions", help="install the missing extensions")
    install.add_argument("groups", nargs="*", help="groups of user/extensions.json (default: core)")
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "docs":
            return cmd_docs(REPO)
        if arguments.command == "extensions":
            return cmd_extensions(REPO, arguments.groups or ["core"])
        user = arguments.user_dir or user_dir(sys.platform, os.environ, Path.home())
        return cmd_deploy(REPO, user, write=arguments.command == "apply")
    except (ConfigError, UsageError) as error:
        print(f"vscode-settings: {error}", file=sys.stderr)
        return 2
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"vscode-settings: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
