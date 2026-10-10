# Work on a managed laptop

Each section is one task on a machine that an employer manages: what to ask before
installing, what to do when something is refused, and what to settle with the team in the
first week. [Getting started](../tutorials/getting-started.md) has the ordinary steps.

Untested: written without a managed machine at hand, from VS Code's documentation and the
manifests of the extensions. Treat each section as where to look, not as a recipe that ran.

## Ask before you install

Ask the people who manage the machine:

- Is VS Code provided, and may the `code` command be installed?
- Is there a list of allowed extensions, or a private marketplace?
- Does the network inspect TLS traffic, or need a proxy?
- May a personal public repository of editor settings be cloned, and its script run?
- Which AI assistants may read the company's code, and with which account?
- Is Settings Sync permitted? This configuration does not use it: leave it off, or it will
  compete with the repository for the same files.

If a script may not be run, use the steps *Without the tool* of the getting-started tutorial.

## See what the machine enforces

1. Press `M-x`, or `Cmd+Shift+P` before the keys are installed, and run *Developer: Policy
   Diagnostics*. It lists each policy that applies, with its value: the allowed extensions,
   the update mode, the telemetry level, the rules for AI features.
2. In the Settings editor, search `@policy`: a setting that the organisation manages shows a
   lock, and a value written in `settings.json` has no effect on it.

A setting of this repository that a policy overrides is harmless: VS Code ignores it.

## Install the extensions when the tool cannot

`bin/vscode-settings extensions` calls `code --install-extension`, which does not use the
system's proxy settings nor its certificate store. Behind a network that inspects traffic it
may fail where VS Code itself succeeds. Then:

1. Open the folder of this repository in VS Code.
2. Accept the prompt to install the recommended extensions, or open the Extensions view
   and search `@recommended`. The list is the core group of `user/extensions.json`.
3. Run `bin/vscode-settings extensions` again: it installs nothing, and prints what is
   still missing.

## Work without an extension that is refused

When the list of allowed extensions leaves one out, VS Code disables it without an error,
and `extensions` prints `STILL MISSING` for it. Ask for the core group, in this order: the
publishers that are vendors first (Microsoft, GitHub, HashiCorp, Red Hat, Snowflake, dbt
Labs), then the others, of which two decide how the keyboard feels:

- `tuttieee.emacs-mcx`, the Emacs keymap. Without it, copy
  `local.example/macos/keybindings.without-the-emacs-keymap.json` as `keybindings.json` into
  the machine-local directory and run `bin/vscode-settings apply`. It restores `M-x`,
  `C-x C-f`, `C-x b`, `C-x k`, `C-x C-s`, the window keys, `C-s`, `C-g`, `M-.` and word
  motion with VS Code's own commands. macOS itself keeps `C-a`, `C-e`, `C-f`, `C-b`, `C-n`,
  `C-p`, `C-k` and `C-d`. The mark, the kill ring and prefix arguments are lost: select with
  Shift, and cut, copy and paste with `C-w`, `M-w` and `C-y`.
- `kahole.magit`, edamagit. Without it, `C-x g` does nothing; the last rule of the same
  file sends it to VS Code's Source Control view.

A key bound to a command of a missing extension only shows a notification that the command
was not found; nothing else breaks.

## Keep the employer's values out of the repository

- Whatever names the employer goes in the machine-local `settings.json`: a proxy, a forge
  address, the path of the dbt binary, a profile name, words for the spelling dictionary.
  `local.example/macos/settings.json` lists the usual ones.
- Write the names that must never be published, one per line, in `deny.txt` in the same
  directory. The static tests then fail if one of them appears anywhere in a tracked file
  or in its name, whatever its case and even inside a longer word. For a short acronym
  that would match half the dictionary, start the line with `=`: it is then found only
  where it stands alone. The list stays on your machine: the tests of GitHub Actions do
  not have it.
- Do not commit to this repository from the work machine: its default git identity may be
  the employer's, and one commit would put that address in a public history. Take notes,
  and make the change from your own machine.

## Decide about AI assistants

The example for a Mac sets `chat.disableAIFeatures` to `true`, which hides VS Code's
built-in chat, inline suggestions and agents. Once you know the policy:

- An assistant is provided: remove the line, run `bin/vscode-settings apply`, and sign in
  with the account the employer gave you, never a personal one.
- Another assistant is permitted: install the `ai` group,
  `bin/vscode-settings extensions ai`, and read its keys in the Keyboard Shortcuts editor:
  on a Mac some of them take Option characters.

Two extensions of the core group have assistants of their own. The Snowflake one is switched
off in `user/settings.json` (`snowflake.coco.enabled`), since it sends code to the
warehouse and spends credits. Ask before switching it on.

## Settle with the team in the first week

Each answer changes one thing here. Until you have it, the defaults stand.

| Ask | The answer changes |
|---|---|
| Which dbt extension do you use, and is every project on dbt v2? | The core group has the official `dbtLabsInc.dbt`. For dbt Core 1.x with Power User, uninstall it (`code --uninstall-extension dbtLabsInc.dbt`) and run `bin/vscode-settings extensions sql`. The two are never installed together: from then on `extensions` leaves the official one out |
| How is SQL linted and formatted: SQLFluff, sqlfmt, or dbt's own linter? | Install `sqlfluff.vscode-sqlfluff` from the `sql` group, or set `dbt.lsp.linter.enabled` to `true` in the machine-local settings; never both |
| Do the checks enforce Ruff, or Black and isort? | See *Before your first save* in [the first-day tutorial](../tutorials/first-day.md); for Black, install the `python-team` group |
| Which type checker gates a merge, and where is it configured? | `basedpyright.analysis.typeCheckingMode` in the machine-local settings, from `all` down to `standard` |
| Terraform or OpenTofu? | The core group has `HashiCorp.terraform`. For OpenTofu, uninstall it (`code --uninstall-extension HashiCorp.terraform`) and run `bin/vscode-settings extensions cloud`, which installs the OpenTofu extension with the rest of that group |
| How do you sign in to Snowflake? | Nothing here; the connection is in Snowflake's own `connections.toml`, outside this repository |
| How is the cluster reached, and who writes Helm charts? | Install the `cloud` group, which needs `kubectl`, `helm` and the Azure `kubelogin` |
| Do the repositories commit a `.vscode` directory? | Their settings win over these for that repository; read them before changing anything |
| Are commits signed? | `git.enableCommitSigning` in the machine-local settings |
