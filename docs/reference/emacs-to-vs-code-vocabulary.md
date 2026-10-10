# Emacs to VS Code vocabulary

Three tables: the VS Code word for each Emacs word, a colleague's shortcut translated, and
what has no equivalent. The keys of this configuration are in
[the key reference](keybindings.md); [the first-day tutorial](../tutorials/first-day.md)
puts them to use.

Untested: the keys below are derived from the key maps of VS Code and of the Emacs keymap
extension; the tests check that each is bound to a command that exists, and nobody has
pressed them yet.

## Words

| Emacs | VS Code | Here |
|---|---|---|
| Buffer | Editor: an open file in a tab | `C-x b` lists the open ones |
| Window | Editor group | `C-x 2`, `C-x 3`, `M-o`, `C-x 1` |
| Frame | Window | |
| Minibuffer | Quick input: the prompt at the top of the window | `C-g` closes it |
| `M-x` | Command Palette | `M-x`; a colleague says `Ctrl+Shift+P` or `Cmd+Shift+P` |
| Mode line | Status bar | |
| Major mode | Language mode, shown in the status bar | *Change Language Mode* |
| Minor mode | No single notion: a setting or an extension | |
| Hook | No equivalent in settings; an extension reacts to events | |
| Project | Folder, or workspace when it holds several folders | `C-x f` opens a recent one |
| Dired, Treemacs | Explorer, in the side bar | `C-x d`, `C-x C-j`, `<f8>` |
| Kill ring | The clipboard, plus the kill ring of the keymap extension | `C-k`, `C-w`, `M-w`, `C-y`, `M-y` |
| Mark and region | Selection | `C-SPC`, then move |
| imenu | Go to Symbol in Editor; the Outline view | `M-g i`, `<f9>` |
| xref | Go to Definition, Go Back, Go to References | `M-.`, `M-,`, `M-?` |
| isearch, consult-line | Find, in a field at the top of the editor | `C-s`, `C-r` |
| grep, ripgrep | Search view; Quick Search | `C-c s g`, `C-c s r` |
| wgrep | Replace in Files | `M-x`, *Replace in Files* |
| Magit | edamagit; VS Code's own Source Control view | `C-x g` |
| diff-hl | Change marks at the left of the line | `C-c g n`, `C-c g p`, `C-c g d` |
| Flycheck error list | Problems panel | `M-g n` and `M-g p` go to the next and previous one |
| Compilation buffer | Tasks, with their output in the terminal panel | |
| Terminal buffers | Integrated terminal, in the panel | `C-c t` |
| dape | Run and Debug | `C-c d` and a letter |
| Test runner | Testing view | `C-c k` and a letter |
| apheleia | Format on save, on the lines you changed | `C-c r` formats the whole file |
| Init file | `settings.json` and `keybindings.json` | The sources under `user/`, then `bin/vscode-settings apply` |
| `local.el` | The machine-local files | `bin/vscode-settings status` prints their directory |
| Package | Extension | `user/extensions.json`, then `bin/vscode-settings extensions` |
| Customize | Settings editor | *Preferences: Open Settings (UI)* |
| `describe-key` | Keyboard Shortcuts editor, with its record button | `C-h k` |
| `describe-bindings` | The same editor, filtered | `C-h b` |
| Documentation at point | Hover | `C-h C-d` |
| Org | No equivalent; keep it in Emacs | |

## A colleague's shortcut

On a Mac, VS Code's own shortcuts use Command, and this configuration uses Control and
Option: nearly every shortcut a colleague quotes works as said. The exceptions are the few
that use Control: `Ctrl+G` (go to line) is cancel here, so use `M-g g`; `Ctrl+Space`
(suggestions) sets the mark, so use `M-/`.

On Linux, VS Code's own shortcuts use Control, and the Emacs keys take many of them:

| A colleague says | It does | Press here |
|---|---|---|
| `Ctrl+P` | Open a file by name | `C-x C-f` |
| `Ctrl+Shift+P` | Command Palette | The same, or `M-x` |
| `Ctrl+S` | Save | `C-x C-s` |
| `Ctrl+F` | Find in the file | `C-s` |
| `Ctrl+W` | Close the file | `C-x k` |
| `Ctrl+B` | Show or hide the side bar | `<f8>` |
| `Ctrl+J` | Show or hide the panel | `C-x j` |
| `Ctrl+/` | Comment the line | `C-;` |
| `Ctrl+D` | Select the next occurrence | `C-M-n` |
| `Ctrl+G` | Go to a line | `M-g g` |
| `Ctrl+C`, `Ctrl+X`, `Ctrl+V` | Copy, cut, paste | `M-w`, `C-w`, `C-y` |
| `Ctrl+Space` | Suggestions | `M-/` |
| `Ctrl+K` then another key | Many commands | `M-x`, then the name of the command |
| `F8`, `F9` | Next problem, breakpoint | `M-g n`, `C-c d b` |
| `Ctrl+Z`, `Ctrl+Shift+F`, `Ctrl+Shift+E`, `F12`, `F2` | Undo, search view, Explorer, definition, rename | The same |

When a shortcut is not in the table, press `M-x` and type what the colleague says it does:
the Command Palette shows the command and the key it has here.

## What has no equivalent

| In Emacs | Here |
|---|---|
| `C-s` lists the matching lines | A search field, with next and previous; `C-c s r` lists matches across the folder |
| `M-y` shows the kill ring with a preview | A list of the kill ring, without preview |
| The undo key opens a tree of states | Undo is a line; redo is `Ctrl+Shift+Z` or `Cmd+Shift+Z`; *Local History* keeps saved versions |
| `M-o` jumps to a window by letter | `M-o` goes to the next editor group |
| `C-x 1` hides the other windows, and they can come back | `C-x 1` merges the groups into one; the files stay open |
| wgrep edits search results as text | *Replace in Files*, rename, or several cursors |
| which-key lists what can follow a prefix | Nothing; `C-h b` and the key reference list the keys |
| `C-u`, `M-0` to `M-9` as prefix arguments | `C-u` only, unless the machine-local settings give the digits back |
| Every list is a buffer you can search and copy from | Views are not editors; only some can be searched |
| A project prefix, `s-p` | None; `C-x f` opens a recent folder, `C-x C-f` a file of the current one |
