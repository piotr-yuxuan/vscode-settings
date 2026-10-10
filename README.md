# VS Code settings

A VS Code configuration for someone who thinks in Emacs keys and works on a data engineering
stack: Snowflake, dbt, Airflow, Azure, Kubernetes, Terraform, GitHub, Python, SQL, and
architecture diagrams in LikeC4. A small tool deploys it; tests start the real VS Code with
it, on Linux and on macOS.

## Start here

```zsh
git clone https://github.com/piotr-yuxuan/vscode-settings.git ~/src/github.com/piotr-yuxuan/vscode-settings
cd ~/src/github.com/piotr-yuxuan/vscode-settings
bin/vscode-settings status       # what would change; writes nothing
bin/vscode-settings apply        # write settings.json and keybindings.json
bin/vscode-settings extensions   # install the core extensions
```

- [Getting started](docs/tutorials/getting-started.md) walks through these steps, on a Mac
  and on NixOS, and through the way without the tool: the two sources can be pasted into VS
  Code as they are.
- [A first day with this configuration](docs/tutorials/first-day.md) is the same working day
  as in the Emacs configuration this one mirrors: open, search, edit, arrange windows, commit.
- [Work on a managed laptop](docs/how-to/work-on-a-managed-laptop.md) covers what an employer's
  machine may refuse, and what to ask in the first week.

## What you get

- **Emacs keys.** The Awesome Emacs Keymap extension gives movement, the kill ring, the mark,
  `C-x` and `M-x`. On top of it, [about seventy rules](docs/reference/keybindings.md) mirror
  one Emacs configuration: `C-x g` for Magit, `C-c s r` to search the project, `C-c g` for
  changes, `C-c k` for tests, `C-c d` for the debugger. On a Mac every `Cmd` shortcut a
  colleague quotes still works.
- **Extensions by group.** [The manifest](user/extensions.json) gives each extension a
  one-line purpose. The core group is installed by default; the others (`sql`,
  `python-team`, `cloud`, `github`, `prose`, `look`, `shell-nix`, `ai`) on request:
  `bin/vscode-settings extensions cloud github`.
- **Settings with their reasons.** [The settings](user/settings.json) are commented. They
  tame what grabs too much (an extension that claims every `.sql` file, assistants switched
  on by default, telemetry) and never reformat a colleague's lines: format on save touches
  only the lines you changed.
- **Machine-local values kept apart.** What differs between machines, or names an employer,
  lives outside the repository, beside VS Code's own data. `local.example/` shows what goes
  there.

## How it is organised

| Path | Holds |
|---|---|
| `user/` | The sources: settings, key bindings, extension manifest |
| `local.example/` | Examples of machine-local files, for NixOS and for a Mac |
| `bin/vscode-settings` | The tool: `status`, `apply`, `extensions`, `docs` |
| `docs/` | [The documentation](docs/README.md), organised by [Diataxis](https://diataxis.fr/) |
| `tests/` | `tests/run static` needs no VS Code; `tests/run fast` also starts the real one |

The files VS Code reads are generated: edit the sources, then run `apply`. The settings
VS Code or you added by other means are kept.

## What is not verified yet

A step that nobody could run says so, on a line that starts with `Untested:`. Today that
covers every step on a Mac that the tests of GitHub Actions do not run, the keys themselves
(derived from the key maps, pressed by nobody yet), and anything that needs an account:
Snowflake, Azure, a team's repositories.

## For contributors and agents

The process, the tests and the writing rules are in [AGENTS.md](AGENTS.md). The licence is
the [EUPL-1.2](LICENSE).
