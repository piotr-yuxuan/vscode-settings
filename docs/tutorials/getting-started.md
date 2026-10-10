# Getting started

This tutorial installs the configuration on a new machine: a Mac first, then the differences
on NixOS. It takes about twenty minutes, most of it waiting for extensions. At the end VS
Code has the settings, the keys and the core extensions, and you know how to change them.
[A first day with this configuration](first-day.md) comes next.

Untested: on a Mac managed by an employer. GitHub Actions runs steps 2 to 5 on a plain macOS
machine at every push, so the commands themselves are known to work there; what a managed
machine adds is in [Work on a managed laptop](../how-to/work-on-a-managed-laptop.md).

## 1. Check what you need

- VS Code, started at least once.
- `git` and `python3`, version 3.9 or later. On a Mac both come with the command-line tools:
  `xcode-select -p` prints a path when they are installed.
- The `code` command. On a Mac, run *Shell Command: Install 'code' command in PATH* from the
  Command Palette (`Cmd+Shift+P`) if `code --version` is not found.

If the machine forbids running a script, or has no `python3`, go to
[Without the tool](#without-the-tool): everything can be done by hand.

## 2. Clone the repository

```zsh
git clone https://github.com/piotr-yuxuan/vscode-settings.git ~/src/github.com/piotr-yuxuan/vscode-settings
cd ~/src/github.com/piotr-yuxuan/vscode-settings
```

The address is the public one over HTTPS: it needs no key and no account.

## 3. See what would change

```zsh
bin/vscode-settings status
```

It writes nothing. It prints the machine-local directory, then each setting that `apply`
would add or change, and the number of key binding rules to write. Its exit status is 1,
because something is pending.

## 4. Add what is particular to this machine

What differs between machines, or names an employer, lives in the machine-local directory
that `status` just printed, outside the repository. Start from the example:

- On a Mac:

  ```zsh
  mkdir -p "$HOME/Library/Application Support/Code/vscode-settings.local"
  cp local.example/macos/settings.json "$HOME/Library/Application Support/Code/vscode-settings.local/"
  ```

- On NixOS:

  ```zsh
  mkdir -p ~/.config/Code/vscode-settings.local
  cp local.example/nixos/settings.json ~/.config/Code/vscode-settings.local/
  ```

Read the file you copied: each line says why it is there. The Mac example switches VS Code's
AI features off until you know which assistants the employer permits.

Run `bin/vscode-settings status` again: the lines of the file are now among the changes.

## 5. Apply, then install the extensions

```zsh
bin/vscode-settings apply
bin/vscode-settings extensions
```

`apply` writes `settings.json` and `keybindings.json` in VS Code's user directory. The
settings you already had are still there: `apply` only sets the keys this repository
manages. The files it replaced are in the `backup` directory of the machine-local directory:
`settings.json.original` is what was there the first time, `settings.json.previous` what
was there the last time.

`extensions` installs the core group in one call and prints a line for each extension:
`installed`, or `STILL MISSING` when VS Code refused it. Its exit status is 0 when nothing
is missing.

Restart VS Code. Then check:

```zsh
bin/vscode-settings status
```

It prints `in sync: nothing to apply`, and its exit status is 0.

## 6. Change something

1. In VS Code, press `M-x` (Alt+X, or Option+X on a Mac), type *Toggle Minimap* and press
   Enter. VS Code writes the change into its settings file.
2. Run `bin/vscode-settings status`. It shows `editor.minimap.enabled`, with the value VS
   Code wrote and the one the repository holds.
3. Decide where the change belongs. To keep the repository's value, run
   `bin/vscode-settings apply`. To keep yours on this machine only, write the line in the
   machine-local `settings.json`, then `apply`. To keep it everywhere, change
   `user/settings.json`, then `apply`.

A key binding works the same way, with one difference: `apply` replaces `keybindings.json`
whole, so a rule recorded in VS Code's Keyboard Shortcuts editor must be copied into
`user/keybindings.json`, or into the machine-local `keybindings.json`, before the next
`apply`. `status` names every rule that `apply` would drop.

## On NixOS

- VS Code runs in a sandbox that sees `~/.config/Code`, `~/.vscode` and `~/src` only. Clone
  the repository below `~/src`, or the terminal inside VS Code will not find it.
- Git's identity, the SSH and GnuPG keys and every cloud credential are outside the
  sandbox: commit and push from a terminal outside VS Code.
- The example sets `update.mode` to `none`, since Nix owns the version, and gives `M-0` to
  `M-9` back to prefix arguments.

Then run the tests:

```zsh
tests/run static
tests/run fast
```

`static` needs no VS Code. `fast` also starts the real VS Code without a window, inside the
sandbox, with the configuration this checkout generates; it reads and writes only `./tmp`.
Both end with `OK`.

## Without the tool

Untested: these steps follow from how VS Code reads its files; nobody has done them on a
machine that forbids scripts.

1. Open `user/settings.json` of this repository on GitHub and copy its content. In VS Code,
   run *Preferences: Open User Settings (JSON)* from the Command Palette, and paste. If
   the file already holds settings, keep them: paste the new ones inside the same braces.
2. Do the same with `user/keybindings.json` and *Preferences: Open Keyboard Shortcuts (JSON)*.
3. Open the folder of this repository in VS Code, if you could clone it. VS Code offers to
   install the recommended extensions, which are the core group. Otherwise install them one
   by one from the Extensions view, with the identifiers of `user/extensions.json`.
4. Add the lines of `local.example/macos/settings.json` that you need at the end of the user
   settings.

Later, `bin/vscode-settings status` on a machine where the tool runs shows what this way
missed.

## Where to go next

- [A first day with this configuration](first-day.md): the key check, then the daily moves.
- [Key bindings](../reference/keybindings.md): every rule this configuration adds.
- [Emacs to VS Code vocabulary](../reference/emacs-to-vs-code-vocabulary.md): the words, and
  a colleague's shortcut translated.
