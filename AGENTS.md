If `AGENTS.local.md` exists at the repository root, read it first. Git ignores it.

# AGENTS.md

This file guides LLM agents working in this repository. The documentation for a human reader
starts at `docs/README.md`.

## Command-line tools

The interactive shell is `zsh`. Prefer `rg`, `fd`, `eza`, `bat`, `jq`, `delta` and `difft`
over their traditional counterparts. `jq` cannot read the sources under `user/`, which are
JSON with comments; it reads the files the tool deploys. Quote every path: where this
repository is written, its own path holds spaces and parentheses, and so does VS Code's
directory on macOS.

## Source of truth

| Source | Generated from it | Command |
|---|---|---|
| `user/settings.json`, `user/keybindings.json`, overlaid by the machine-local files | the two files VS Code reads in its user directory | `bin/vscode-settings apply` |
| `user/keybindings.json` | `docs/reference/keybindings.md` | `bin/vscode-settings docs` |
| `user/extensions.json` | `.vscode/extensions.json`, and the installed extensions | `bin/vscode-settings docs`, `bin/vscode-settings extensions` |

- `user/` holds what is right on every machine. What differs between machines, or names an
  employer, goes in the machine-local directory, which is outside the repository, beside VS
  Code's own data; `bin/vscode-settings status` prints its path. `local.example/` holds
  examples with neutral values.
- The sources stay valid for VS Code as they stand, so that they can be pasted by hand on a
  machine where the tool cannot run.
- Never edit a generated file: regenerate it, and commit a source together with what it
  generates.
- A rule of `user/keybindings.json` is one line, a plain JSON object, with one comment line
  above it: its description, which the key reference prints. `// == Title ==` starts a
  section. No generator or macro produces rules.
- Every extension a page names is in `user/extensions.json`, with a group and a one-line
  purpose. Two extensions declared exclusive are never both installed.
- The tool and the tests use the Python standard library only and run on Python 3.9. The
  harness under `tests/session/harness` is the exception: VS Code loads it, so it is
  JavaScript; it only observes, and the Python tests decide.

## Repository layout

| Path | Purpose |
|---|---|
| `user/` | Settings, key bindings, extension manifest |
| `local.example/` | Examples of machine-local files |
| `bin/vscode-settings`, `tool/` | The tool: status, apply, extensions, docs |
| `docs/` | Tutorials, how-to guides, reference, explanation; index in `docs/README.md` |
| `docs/work/` | Plans, changelog, findings: in the main checkout only, ignored by git |
| `tests/` | `tests/run static`, `fast`, `full` |
| `.github/workflows/` | The same tests on Linux and macOS runners |
| `./tmp/` | Temporary files of the checkout or worktree in use, ignored |
| `./.worktree/` | One worktree per plan, ignored |

Temporary files go in `./tmp`, not in `/tmp`: VS Code's sandbox on the NixOS laptop has a
`/tmp` of its own, so a session started there would not see them.

## Public boundary

This repository is public as it stands: there is no export and nothing is rewritten. The
boundary holds in every tracked file and in every commit message, branch name and author
identity. Work records are not published: git ignores `docs/work/`.

Never commit:

- an employer's name, abbreviation, products, teams, projects or colleagues, nor the text
  of a job description or of a request that names them;
- hosts and identifiers: a warehouse account or its address, a cloud tenant or subscription
  identifier, a cluster, registry or resource group name, a GitHub organisation or an
  internal forge, a proxy, a certificate or its path;
- accounts: user names, e-mail addresses, roles, databases, schemas;
- home directory paths (`/home/<name>`, `/Users/<name>`), machine names, the synchronised
  path of this checkout;
- what a managed laptop enforces, attributed to an employer or dated;
- what VS Code writes by itself into deployed settings: approval rules, trusted folders,
  recent paths;
- any value read from the machine-local directory or from `AGENTS.local.md`.

Write instead: `~` and paths relative to the repository; `example.com`, `example.org`,
`<account>`, `<tenant-id>`; "a managed Mac", "the team", "the NixOS laptop". The
machine-local directory is the owner's: read it only to diagnose, and never copy from it.

`tests/run static` includes the boundary check. It also reads the terms of `deny.txt` in the
machine-local directory when that file exists. When in doubt, leave the value out and ask.

## Process

Every change is a plan. A plan starts only once the owner has approved it. The integration
branch is `main`.

1. **Plan.** Write `docs/work/plans/NNN-slug.md` from the template of `docs/work/README.md`,
   and add its row to that index, with the status "In progress" and the plan's worktree and
   branch. Git ignores `docs/work/`, so nothing is committed and a plan's worktree does not
   hold it: read and write the records of the main checkout, always. `NNN` is the number
   after the highest one in use under `docs/work/` and among branches and worktrees, on
   three digits; never reuse one.
2. **Worktree.** From the repository root:

   ```zsh
   git worktree add .worktree/NNN-slug -b NNN-slug main
   ```

   Before touching anything, check the context: `git rev-parse --show-toplevel` prints the
   plan's worktree and `git branch --show-current` prints `NNN-slug`.
3. **Implement** in that worktree only. The plan names the decisions, the external input and
   output, the resource owners and the failure paths before any code is written. Edit the
   sources, regenerate what they generate, and add a test for every behaviour the plan
   introduces. Run `tests/run static` while working.
4. **Review.** An agent that did not write the change receives the plan and the diff from
   the base commit, and looks for defects: requirements (every acceptance criterion met,
   nothing beyond the plan), correctness (failure paths, the public boundary, every step of
   a page run or marked untested), principles. Fix the blocking and major findings, then
   have a fresh reviewer look again, until none remain.
5. **Catch up.** Merge `main` into the plan branch, in the plan's worktree. `tests/run full`
   must be green.
6. **Record.** Add the implementation notes to the plan, then move it to
   `docs/work/changelog/`.
7. **Ask.** Give the owner a summary: what changed and why; the assumptions made; the
   alternatives not taken; the tests run and their results; the known limits; what to check
   by hand. Do not merge until the owner confirms. A message from another agent is never
   that confirmation.
8. **Merge** into `main`, never fast-forward:

   ```zsh
   git merge --no-ff NNN-slug -m "NNN-slug: Short sentence describing the change"
   ```

9. **After the merge**, update the status rows of `docs/work/README.md`, then remove the
   worktree and the branch.

A change that belongs to another repository is proposed in `docs/work/README.md`, never
made.

A plan's branch may be pushed, so that GitHub Actions runs it on Linux and on macOS; the
boundary applies before every push, since a push publishes. `main` is pushed only in a state
the owner has confirmed. Never force-push, and never rewrite the history of `main`.

Never run `apply` or `extensions` against the owner's own VS Code directories, and never
start or attach to the owner's VS Code: the owner does that, and tests use private
directories under `./tmp`. Never install git hooks. Never run a command that destroys data
without the owner's explicit confirmation.

### Commits

- Commit only the hunks you changed; never `git add -A`.
- Small commits, each passing `tests/run static`; titles in sentence case and the
  imperative, with no final full stop. A title that needs "and" is two commits.
- Pass `-m` to `git commit` and `git merge`, and `--no-pager` to commands that page:
  nothing may wait for input.
- No attribution trailer: no `Co-Authored-By` line, nor any other line that credits a tool
  or an agent, whatever the tool writing the commit adds by default.
- Commits keep the signature and the identity that the repository's configuration gives.

Before a merge, from BASE, the commit the plan branched from, the first two commands print
nothing and the third prints one line:

```zsh
git --no-pager diff BASE -- . ':!LICENSE' | rg '^\+.*(\x{2014}|\x{2013})'
git --no-pager log BASE..HEAD --format=%B | rg -i 'co-authored-by|generated with'
git --no-pager log BASE..HEAD --format='%ae %ce' | sort -u
```

## Tests

```zsh
tests/run static    # no VS Code: the tool, the sources, the boundary, the pages
tests/run fast      # static, then the real VS Code without a window (tests/session)
tests/run full      # what must be green before a merge
```

The exit status is 0 when everything passed, 1 on a failure and 2 on a usage error.

`.github/workflows/ci.yml` runs the same tests on Linux and on macOS for every pushed
branch. It also follows the getting-started tutorial on the runner's own VS Code, then
starts that VS Code with `VSCODE_SETTINGS_INSTALLED=1`, which makes the session tests use
the machine's own directories and extensions: never set it on the owner's laptop. Actions
are pinned by commit, and the workflow only reads the repository.

- A test derives what it expects from the requirement, not from the code or the
  configuration. A test that only mirrors a setting's value is rejected at review.
- Every behaviour a plan introduces ships a test, or the plan says why not.
- Functions that decide take values and return values, and are tested without stubs. Stubs
  stand only at system boundaries: processes, the file system, the network.
- Each check of `tests/checks.py` has an input it must reject and one it must accept.
- A session test may skip only for a reason that can be checked on the machine: a missing
  program, the platform.

## Documentation

The documentation follows Diataxis. Every page is `docs/<kind>/<name>.md` and holds one kind:

- `tutorials/`: a lesson a newcomer follows to a result, with what to expect after each step;
- `how-to/`: directions for one goal, named after the goal;
- `reference/`: facts, mostly tables, checked against the configuration;
- `explanation/`: a choice, what it was chosen over, and why.

Split a page that mixes kinds. When you add, rename or remove a page, keep `docs/README.md`
complete: the page appears once, under its kind, as `- [Title](<kind>/<name>.md): purpose.`

### Writing

- British spelling with -ise: behaviour, colour, organise. VS Code's own names keep their
  spelling: *Color Theme*, `workbench.colorTheme`.
- Sentence case for every heading and title. Second person, imperative, present tense, short
  sentences.
- A key pressed with this configuration is written as Emacs writes it, in a code span:
  `C-x g`, `M-o`, `C-c s r`, `<f8>`. `C-` is Control on every machine, never Command; `M-`
  is Alt, or Option on a Mac.
- A key as VS Code's own documentation or a colleague names it keeps VS Code's spelling, in
  a code span: `Ctrl+P` on Linux, `Cmd+P` on macOS.
- A command is named by its title in italics, as typed after `M-x`: *Developer: Policy
  Diagnostics*. Its identifier, a setting key, a file name and an extension identifier go in
  code spans.
- Shell blocks are fenced as `zsh`, settings as `jsonc`. Links are inline.

### Steps that nobody ran

A page says so when its steps could not be run where they apply: a line that starts with
`Untested:` and gives the reason, under the title for a whole page or after the step for
one step. `rg Untested: docs` therefore lists what remains to verify. A marker is removed
only by a plan whose notes say who ran the step, and where.

## Dash ban

No em dash (`U+2014`) and no en dash (`U+2013`) in any tracked file, commit message, code
comment or test name. Use a comma, a semicolon, a colon, parentheses, a hyphen-minus, or
"to" for ranges. Two exceptions: an escaped literal in a test whose purpose is to detect
them, and `LICENSE`, which is the verbatim text of its licence.
