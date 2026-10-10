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
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*\.[A-Za-z0-9][A-Za-z0-9-]*$")

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

    def keep_strings(match):
        # Comments become spaces, newlines kept, so that an error still names the right line.
        return match.group() if match.group().startswith('"') else re.sub(r"[^\n]", " ", match.group())

    strict = _TRAILING_COMMA.sub(keep_strings, _COMMENT.sub(keep_strings, text))
    try:
        value = json.loads(strict, object_pairs_hook=unique)
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


def emacs_notation(key: str) -> str:
    """Write a VS Code key such as `ctrl+x shift+o` the way Emacs does: `C-x O`."""
    strokes = []
    for stroke in key.split():
        *modifiers, name = stroke.split("+")
        if "shift" in modifiers and (name in _SHIFTED or (len(name) == 1 and name.isalpha())):
            modifiers.remove("shift")
            name = _SHIFTED.get(name, name.upper())
        elif len(name) > 1:
            name = _EMACS_NAMES.get(name, f"<{name}>")
        prefix = "".join(text for modifier, text in _EMACS_MODIFIERS.items() if modifier in modifiers)
        strokes.append(prefix + name)
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
        if not isinstance(identifier, str) or not _IDENTIFIER.match(identifier):
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
        unknown = [name for name in pair if str(name).lower() not in groups]
        if len(pair) != 2 or unknown:
            findings.append(f"exclusive {pair!r} must name two listed extensions")
        elif all(groups[name.lower()] == "core" for name in pair):
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
    """Decide (missing, blocked) for the requested groups, comparing identifiers without case.

    An extension is blocked when its exclusive partner is installed, or is requested in the
    same call and listed first in the pair.
    """
    known = {entry["group"] for entry in manifest["extensions"]}
    unknown = sorted(set(groups) - known)
    if unknown:
        raise UsageError(f"unknown group {unknown[0]!r}; the groups are: {', '.join(sorted(known))}")
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
        if first in have or first in wanted:
            blocked.add(second)
        elif second in have:
            blocked.add(first)
    return (
        [identifier for identifier in missing if identifier.lower() not in blocked],
        [identifier for identifier in missing if identifier.lower() in blocked],
    )


def read_optional(path: Path, kind: type):
    """Parse a file that may be absent or empty; either is the empty document of that kind."""
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return parse_jsonc(text, str(path), kind) if text.strip() else kind()


def load_manifest(repo: Path) -> dict:
    """Read and check the extension manifest of the repository."""
    source = "user/extensions.json"
    manifest = parse_jsonc((repo / source).read_text(encoding="utf-8"), source, dict)
    findings = manifest_findings(manifest)
    if findings:
        raise ConfigError(f"{source}: " + "; ".join(findings))
    return manifest


def write_file(path: Path, text: str, backup: Path) -> None:
    """Replace `path` in one step, after copying what was there into `backup`.

    The first content ever replaced is kept as `<name>.original`, the latest as `<name>.previous`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        if path.exists():
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup / f"{path.name}.previous")
            if not (backup / f"{path.name}.original").exists():
                shutil.copy2(path, backup / f"{path.name}.original")
            shutil.copymode(path, temporary)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def cmd_deploy(repo: Path, user: Path, write: bool) -> int:
    """`status` and `apply`: read everything, decide both files, report, then write if asked."""
    local = user.parent / "vscode-settings.local"
    for name in ("settings.json", "keybindings.json"):
        if (user / name).is_symlink():
            raise ConfigError(f"{user / name} is a symbolic link; it is not replaced")
    baseline = parse_jsonc(
        (repo / "user/settings.json").read_text(encoding="utf-8"), "user/settings.json", dict
    )
    rules = parse_jsonc(
        (repo / "user/keybindings.json").read_text(encoding="utf-8"), "user/keybindings.json", list
    )
    deployed_settings = read_optional(user / "settings.json", dict)
    deployed_rules = read_optional(user / "keybindings.json", list)
    settings = deep_merge(
        deployed_settings, deep_merge(baseline, read_optional(local / "settings.json", dict))
    )
    rules = rules + read_optional(local / "keybindings.json", list)

    report = [
        f"{' > '.join(path)}: {was} -> {now}"
        for path, was, now in differences(deployed_settings, settings)
    ]
    pending = {"settings.json": (report, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")}
    if deployed_rules != rules:
        report = [f"{len(rules)} rules to write"]
        report += [f"drops {json.dumps(rule)}" for rule in deployed_rules if rule not in rules]
        lines = ",\n".join("  " + json.dumps(rule, ensure_ascii=False) for rule in rules)
        pending["keybindings.json"] = (report, f"[\n{lines}\n]\n")

    print(f"machine-local directory: {local}" + ("" if local.is_dir() else " (absent)"))
    changed = False
    for name, (report, text) in pending.items():
        if not report:
            continue
        changed = True
        print(f"{user / name}: {'written' if write else 'apply would change'}")
        print("\n".join(f"  {line}" for line in report))
        if write:
            write_file(user / name, text, local / "backup")
    if not changed:
        print("in sync: nothing to apply")
    return 1 if changed and not write else 0


def run_code(code: str, arguments: list) -> str:
    """Run VS Code's command line with a deadline; return what it printed."""
    result = subprocess.run([code, *arguments], capture_output=True, text=True, timeout=900)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
    return result.stdout


def cmd_extensions(repo: Path, groups: list) -> int:
    """`extensions`: install what the requested groups lack, in one call, then say what happened."""
    manifest = load_manifest(repo)
    candidates = [Path("/") / _MAC_CODE, Path.home() / _MAC_CODE]
    code = shutil.which("code") or next((str(path) for path in candidates if path.is_file()), None)
    if code is None:
        raise UsageError(
            "the `code` command was not found; in VS Code run "
            "'Shell Command: Install 'code' command in PATH' from the Command Palette"
        )
    missing, blocked = extensions_to_install(
        manifest, groups, run_code(code, ["--list-extensions"]).split()
    )
    still_missing = []
    if missing:
        run_code(
            code,
            [argument for identifier in missing for argument in ("--install-extension", identifier)],
        )
        installed = run_code(code, ["--list-extensions"]).split()
        still_missing = extensions_to_install(manifest, groups, installed)[0]
    for identifier in missing:
        print(f"{identifier}: {'STILL MISSING' if identifier in still_missing else 'installed'}")
    for identifier in blocked:
        print(f"{identifier}: not installed, its exclusive partner is installed or comes first")
    if not missing and not blocked:
        print(f"nothing to install for: {', '.join(groups)}")
    return 1 if still_missing or blocked else 0


def cmd_docs(repo: Path) -> int:
    """`docs`: rewrite the files generated from the sources."""
    keybindings = (repo / "user/keybindings.json").read_text(encoding="utf-8")
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
