"""The real VS Code, without a window, started with the configuration this repository generates.

By default everything VS Code reads and writes is a private directory under `./tmp`, and no
extension is installed. VS Code is started through the `code` command of the machine, so on
the NixOS laptop it runs inside its sandbox, which can see `./tmp`.

With `VSCODE_SETTINGS_INSTALLED=1` the test starts VS Code on the machine's own directories
instead, after `apply` and `extensions` were run there. That is for a throwaway machine such
as a continuous integration runner, never for the owner's laptop.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tool import vscode_settings as tool

REPO = Path(__file__).resolve().parent.parent.parent
INSTALLED = os.environ.get("VSCODE_SETTINGS_INSTALLED") == "1"

# Commands of extensions: unknown to a session that installs none, so not checked there.
OF_EXTENSIONS = ("emacs-mcx.", "magit.", "snowflake.", "dbt.", "likec4.")


class Session(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        needed = ["code", "Xvfb"] if sys.platform == "linux" else ["code"]
        missing = [program for program in needed if shutil.which(program) is None]
        if sys.platform not in ("linux", "darwin") or missing:
            raise unittest.SkipTest(
                f"needs Linux or macOS with {needed}; missing: {missing or sys.platform}"
            )
        (REPO / "tmp").mkdir(exist_ok=True)
        session = Path(tempfile.mkdtemp(prefix="session-", dir=REPO / "tmp"))
        cls.addClassCleanup(shutil.rmtree, session, ignore_errors=True)
        shutil.copytree(REPO / "tests/session/harness", session / "harness")
        (session / "workspace").mkdir()

        deploy = ["status"] if INSTALLED else ["--user-dir", str(session / "user-data/User"), "apply"]
        with contextlib.redirect_stdout(io.StringIO()):
            cls.deployed = tool.main(deploy)
        command = [
            "code",
            f"--extensionDevelopmentPath={session / 'harness'}",
            f"--extensionTestsPath={session / 'harness/run.cjs'}",
            "--disable-workspace-trust",
            "--skip-welcome",
            "--skip-release-notes",
            "--disable-updates",
            "--disable-telemetry",
            "--password-store=basic",
            # Either flag keeps `code` running until VS Code has exited. On macOS `--wait`
            # would wait for ever: it watches a marker file that a test run never deletes.
            "--verbose" if sys.platform == "darwin" else "--wait",
            str(session / "workspace"),
        ]
        if not INSTALLED:
            command[1:1] = [
                f"--user-data-dir={session / 'user-data'}",
                f"--extensions-dir={session / 'extensions'}",
            ]
        environment = dict(os.environ)
        with contextlib.ExitStack() as cleanup:
            if sys.platform == "linux":
                display = cleanup.enter_context(
                    subprocess.Popen(
                        ["Xvfb", "-displayfd", "1", "-screen", "0", "1920x1080x24", "-nolisten", "tcp"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                    )
                )
                cleanup.callback(display.terminate)
                environment.pop("WAYLAND_DISPLAY", None)
                environment.update(
                    DISPLAY=f":{display.stdout.readline().strip()}", XDG_SESSION_TYPE="x11"
                )
                command[1:1] = ["--ozone-platform=x11", "--disable-gpu"]
            try:
                cls.process = subprocess.run(
                    command, env=environment, capture_output=True, text=True, timeout=240
                )
            except subprocess.TimeoutExpired as expired:
                # Kept as a result, so that the tests fail with what VS Code printed.
                cls.process = subprocess.CompletedProcess(
                    command, -1, "", f"timed out: {expired.stderr!r}"
                )
        results = session / "results.json"
        cls.facts = json.loads(results.read_text(encoding="utf-8")) if results.is_file() else None

    def test_vscode_starts_with_the_configuration_and_runs_the_harness(self):
        self.assertEqual(self.deployed, 0, "the configuration is not deployed, or not in sync")
        self.assertEqual(self.process.returncode, 0, self.process.stderr[-2000:])
        self.assertIsNotNone(self.facts, "VS Code wrote no results:\n" + self.process.stderr[-2000:])
        self.assertTrue(self.facts["version"])

    def test_every_key_is_bound_to_a_command_that_vscode_knows(self):
        self.assertIsNotNone(self.facts)
        source = (REPO / "user/keybindings.json").read_text(encoding="utf-8")
        bound = {rule["command"].lstrip("-") for rule in tool.parse_jsonc(source, "rules", list)}
        unknown = sorted(bound - set(self.facts["commands"]))
        if not INSTALLED:
            unknown = [command for command in unknown if not command.startswith(OF_EXTENSIONS)]
        self.assertEqual(unknown, [])

    @unittest.skipUnless(INSTALLED, "needs the extensions, which only an installed VS Code has")
    def test_every_core_extension_is_installed(self):
        self.assertIsNotNone(self.facts)
        manifest = tool.load_manifest(REPO)
        core = {entry["id"].lower() for entry in manifest["extensions"] if entry["group"] == "core"}
        self.assertEqual(
            sorted(core - {identifier.lower() for identifier in self.facts["extensions"]}), []
        )


if __name__ == "__main__":
    unittest.main()
