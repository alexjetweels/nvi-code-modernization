# Changelog

Each release gets the same version in `plugin.json` and `.claude-plugin/plugin.json`.

## 2.0.0

- Added repository marketplaces for Claude Code and Codex so the plugin can be installed from a Git repository without running the workspace installer.
- Renamed the plugin and skill to `nvi-code-modernization`, and renamed user-facing commands to the `nvi-modernize` prefix. Existing installations under the previous identity need to be removed separately.
- Kept the workspace installer as an optional local setup helper.

## 1.1.0

- Added a portable Agent Plugins manifest and skill, a Copilot CLI command, and workspace shims for Antigravity and Copilot in VS Code.
- Added `scripts/install.py` to copy a versioned plugin into a migration workspace separate from the legacy source and prepare each host's local configuration.
- Added host-specific next-command text to the HTML report while keeping Claude's command names as the default.
- Added SHA-256 source snapshots to preflight and verification; existing workspaces without a snapshot retain the previous modification-time check.
- Fixed Claude manifest and command frontmatter issues found by `claude plugin validate`.

## 1.0.0

- **A front door.** `/code-modernization:modernize` asks what you want done (once), records it in `analysis/<system>/INTENT.md`, shows the road and gives the exact first command. `--source <path>` links the code so nothing has to be copied.
- **Same-stack version moves.** `modernize-uplift` catalogs what changes between two versions of the same technology, records a measured baseline, migrates one pilot unit and then the rest by playbook.
- **Independent proof.** `modernize-verify` re-runs the tests from clean, re-runs your own canary, tries inputs nobody used and gives each module one verdict, PROVEN, PARTLY PROVEN or NOT PROVEN, computed by a script from files it parses itself.
- **People decide what only they can.** `modernize-review` records a person's verdict on each flagged rule; the plan, the build and the tests read it. A difference the proof finds is accepted once per input by a person, never by the tool.
- **Comparison that fits real output.** Floating-point output can be compared within a declared, justified tolerance; masks and approvals are listed in the result.
- **Proportional rule extraction.** The same rule found in several files is folded into one, and the number of rules follows the size of the code.
- **A one-page report** (`REPORT.html`, works offline) with the proof, the rules, the map and a next step you can copy.
- **A live progress pane** (early access, terminal): the estate map, the rule review deck, the sign-off dialog and the proof at a glance.
- **Usage counts** (whole numbers only, off by switch): which commands run, how far a system gets, what the plugin runs on (operating system, python status, path problems on Windows), and which kinds of failure happen (python missing, blocked by a permission rule, model errors, the plugin's own script errors). Once per version and machine at session start it also says what it runs on. See the Telemetry section of the README.
