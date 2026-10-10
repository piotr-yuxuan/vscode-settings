# A first day with this configuration

This tutorial walks through the moves of an ordinary working day on a small practice
project: opening, searching, editing many files at once, arranging windows and committing.
It follows, section for section, the first day of the Emacs configuration this one mirrors,
so each section also says what differs from Emacs. It assumes
[Getting started](getting-started.md) is done, and takes about half an hour.

Untested: every key on this page is derived from the key maps of VS Code and of its
extensions. The tests check that each key is bound to a command that exists; nobody has
pressed them yet, and the keyboard check below has never met a Mac.

## How to read the keys

`C-x` means hold Control and press `x`; `M-x` means hold Alt, or Option on a Mac, and press
`x`; `C-x C-f` is two such presses in a row. `C-` is always Control, never Command. There is
no Super key in this configuration. A key written `Cmd+P` or `Ctrl+P` is one of VS Code's
own shortcuts, as a colleague would say it.

## Check your keyboard

On a Mac, Option is Meta, and Option also types characters. VS Code cannot tell the left
Option key from the right one, so the configuration protects the characters a UK keyboard
needs. Take two minutes, in a new file (`Cmd+N`) and then in a terminal (`C-c t`):

| Press | Expect | If not |
|---|---|---|
| Shift+3, in the file | `£` on a UK keyboard, `#` on a US one, `3` on a French one | Nothing: this only names your layout |
| Option+3, in the file (UK) | `#` | `apply` was not run, or a machine-local line set `emacs-mcx.enableDigitArgument` to `true` |
| Option+3, in the terminal (UK) | `#` | A machine-local line set `terminal.integrated.macOptionIsMeta` to `true` |
| Option+F, then Option+B, in the file | The cursor moves forward one word, then back | A character such as `ƒ` appears: the keymap extension is not running; see [Work on a managed laptop](../how-to/work-on-a-managed-laptop.md) |
| Control+Space, then `C-n` | The selection grows by a line | macOS took the key to switch input source: turn that shortcut off in System Settings, Keyboard |
| `M-x`, then `C-g` | The Command Palette opens at once, then closes | It waits for a second key: the first rules of `user/keybindings.json` are not deployed |
| In the terminal: Option+B, then `C-r`, then `C-c` | Back one word; the shell's history search; the search is abandoned | A character such as `∫` appears: `apply` was not run |

Then, according to the layout:

- **UK.** Nothing to change.
- **US.** Option types no character you need. Enable the two lines of the machine-local
  `settings.json` that give `M-0` to `M-9` back and make Option a Meta key in the terminal,
  then run `bin/vscode-settings apply`.
- **French.** Brackets, braces and the backslash are typed with Option. Copy
  `local.example/macos/keybindings.json` into the machine-local directory, enable the lines
  marked French, then `apply`. For any other character that no longer types, run
  *Developer: Toggle Keyboard Shortcuts Troubleshooting* from `M-x`, press the key, and
  read which rule took it: a line that removes that rule gives the character back.

On Linux none of this applies: Alt types no character.

## Prepare a practice project

In a shell:

```zsh
mkdir -p ~/src/first-day/docs && cd ~/src/first-day
printf 'Widgets\n\nTo release, frobnicate the widget.\n' > README.txt
printf 'Release checklist\n\n- frobnicate twice\n' > docs/release-checklist.txt
printf 'def frobnicate(widget):\n    return widget.upper()\n\n\nprint(frobnicate("widget"))\n' > widgets.py
git init -q
git config user.name Practice
git config user.email practice@example.org
git config commit.gpgsign false
git add -A && git commit -q -m Initial
code ~/src/first-day
```

The project sits below `~/src` because the sandbox around VS Code on NixOS sees nothing
else. It has an identity of its own, so that the commit of this tutorial works there too,
and signs nothing with your key. VS Code opens the folder and asks whether you trust it:
answer yes.

## When you are lost

- `C-g` cancels whatever is going on: a half-typed key, a prompt, a search. Escape does too.
- `M-x` opens the Command Palette: type a few words of what you want, in any order of
  letters, and press Enter. Every command is there, with its key if it has one.
- `C-h k` opens the Keyboard Shortcuts editor. Click the keyboard icon at the right of its
  search field, then press a key: the list shows what that key does here.
- `C-h b` lists the keys this configuration adds.
- [The key reference](../reference/keybindings.md) lists them too, with a description.

What differs from Emacs: no panel lists the keys that can follow a prefix. After `C-c`, the
status bar only says that VS Code waits for the next key.

## Open, edit and save a file

1. Press `C-x C-f`, type `readme` and press Enter. The prompt at the top matches file names
   of the folder as you type; it is not a path prompt.
2. Go to the end of the file with `M->` and type a new line, such as *Ship it.*
3. Press `M-<` to go to the top, then `C-x C-s` to save.
4. Changed your mind? `C-/` undoes, one step at a time.

What differs from Emacs: undo is a line, not a tree. Redo is `Ctrl+Shift+Z`, or
`Cmd+Shift+Z` on a Mac.

## Move between files

1. Press `C-x C-f`, type `check` and press Enter: the checklist opens.
2. Press `C-x k`: the checklist closes.
3. Press `C-x b`: the list shows the files that are open, the last used first. Press Enter
   to go back to the README.
4. Press `C-x f`: the list shows recent files and folders, the checklist you closed among
   them.

What differs from Emacs: `C-x b` lists open files only; a file you closed is under
`C-x C-f` or `C-x f`. There is no project prefix: to work in another folder, press `C-x f`
and pick it.

## Search

1. In the checklist, press `C-s` and type `frob`. The matches light up and the cursor goes
   to the first. `C-s` again goes to the next. Press Enter to stay there, or `C-g` to go
   back where you started.
2. Press `C-c s r` and type `frobnicate`: the matches of the whole folder appear as you
   type, each with a preview. Move with `C-n` and `C-p`, and press Enter to open one.

What differs from Emacs: `C-s` is a search field with next and previous, not a list of
matching lines.

## Edit every match at once

1. Press `M-x`, type *Replace in Files* and press Enter. The search view opens with two
   fields.
2. Type `frobnicate` in the first and `defrobnicate` in the second. Each match below shows
   the old text struck out and the new text beside it.
3. Click *Replace All*, at the right of the second field, and confirm. The files are
   changed.

What differs from Emacs: the results cannot be edited as text and written back. For a change
that is not one replacement, rename a symbol (`M-x`, *Rename Symbol*) or use several cursors
(`C-M-n` adds a cursor at the next occurrence of the selection).

## Arrange windows

1. Press `C-x 3` to split side by side, then `C-x 2` to split the current window again. You
   now have three windows, which VS Code calls editor groups.
2. Press `M-o`: the next window is selected. Press it again for the one after.
3. Press `C-x 1`: one window remains, and it holds the files of all three.
4. Press `<f8>` to hide the side bar, and again to show it. `C-x j` does the same for the
   panel at the bottom, where the terminal lives.

What differs from Emacs: `M-o` goes round the windows; it shows no letter to jump to one.

## Commit

1. Open `README.txt` and change a word. Save with `C-x C-s`. A coloured mark at the left of
   the line shows the change.
2. Press `M-<` to go to the top, then `C-c g n`: the cursor jumps to the change. `C-c g d`
   shows what it replaced; Escape closes that.
3. Press `C-x g`: edamagit shows the status of the repository, with the file you changed
   under *Unstaged changes*. Move to it with `C-n`, press `TAB` to see its changes, then `s`
   to stage them.
4. Press `c c` to commit. Type a message in the editor that opens, then press `C-c C-c` to
   commit, or `C-c C-k` to give up.
5. Press `q` to leave the status.

On NixOS this works here because the practice project has its own identity. In your real
repositories, commit from a terminal outside VS Code: the sandbox hides your git identity
and your keys.

## Let VS Code complete code

1. Press `C-x C-f` and open `widgets.py`.
2. On a new line at the end, type `frob` and stop. A list proposes `frobnicate`: press Enter
   to insert it.
3. Put the cursor on `frobnicate` in the last line and press `M-.`: you are at its
   definition. `M-,` comes back.

The first time, basedpyright needs a moment to read the folder. It reports everything it
can, as in Emacs: expect warnings in `widgets.py` about missing type annotations.

## Before your first save in a team's repository

Saving formats the lines you changed since the last commit, and only those, so a save never
rewrites a colleague's lines. What that means depends on the language:

- **Python** is formatted by Ruff, which reads the `[tool.ruff]` section of the project and
  ignores `[tool.black]` and `[tool.isort]`. The Emacs configuration saves with isort then
  Black on the whole file; this one does not. Before the first save, read the project's
  `pyproject.toml`. If it configures Black and not Ruff, add this line to the machine-local
  `settings.json` and run `bin/vscode-settings apply`:

  ```jsonc
  "[python]": { "editor.formatOnSave": false },
  ```

- **SQL, YAML, TOML and Markdown** are never formatted on save.
- **Terraform** is formatted whole by `terraform fmt`, which is the only style it has.
- A repository that sets `editor.formatOnSave` in its own `.vscode/settings.json` decides
  for itself: its setting wins over this one.

basedpyright checks the whole folder as strictly as it can. In a repository that never ran
a type checker that is thousands of diagnostics; the machine-local example has the line
that limits it to open files.

## See what a colleague sees

When something misbehaves, find out first whether it is this configuration or the project:

```zsh
code --profile stock ~/src/first-day
```

That window uses an empty profile named *stock*: VS Code's own settings and keys, and no
extension. Install there what the team's repository recommends, and you have what a
colleague has. Close the window to come back; your own profile is untouched.

## What stays in Emacs

Capturing a task, the agenda of the day and everything else that is Org have no equivalent
here. Keep them in Emacs.

## Where to go next

- [Emacs to VS Code vocabulary](../reference/emacs-to-vs-code-vocabulary.md): the VS Code
  word for each Emacs word, and a colleague's shortcut translated.
- [Work on a managed laptop](../how-to/work-on-a-managed-laptop.md): what the first week on
  an employer's machine asks for.
- [The documentation index](../README.md) lists everything else.

When you are done, delete the practice project:

```zsh
rm -rf ~/src/first-day
```
