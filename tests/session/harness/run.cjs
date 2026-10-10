// Runs inside the VS Code that the session tests start (--extensionTestsPath).
// It observes and writes what it saw beside its own directory; the Python tests decide.
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");

exports.run = async function run() {
  // A command of an extension that has not started yet is not registered: its manifest
  // declares it, so both lists are needed to know every command.
  const declared = vscode.extensions.all.flatMap((extension) =>
    ((extension.packageJSON.contributes || {}).commands || []).map((command) => command.command)
  );
  const facts = {
    version: vscode.version,
    commands: [...new Set([...(await vscode.commands.getCommands(true)), ...declared])],
    extensions: vscode.extensions.all.map((extension) => extension.id),
  };
  fs.writeFileSync(path.join(__dirname, "..", "results.json"), JSON.stringify(facts));
};
