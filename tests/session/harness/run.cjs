// Runs inside the VS Code that the session tests start (--extensionTestsPath).
// It observes and writes what it saw beside its own directory; the Python tests decide.
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");

exports.run = async function run() {
  // A command of an extension that has not started yet is not registered. Its manifest
  // names it, as a command or as the target of one of its own key bindings, so all three
  // lists are needed to know every command.
  const declared = vscode.extensions.all.flatMap((extension) => {
    const contributes = extension.packageJSON.contributes || {};
    return [...(contributes.commands || []), ...(contributes.keybindings || [])].map((entry) => entry.command);
  });
  const facts = {
    version: vscode.version,
    commands: [...new Set([...(await vscode.commands.getCommands(true)), ...declared])],
    extensions: vscode.extensions.all.map((extension) => extension.id),
  };
  fs.writeFileSync(path.join(__dirname, "..", "results.json"), JSON.stringify(facts));
};
