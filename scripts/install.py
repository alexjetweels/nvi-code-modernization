#!/usr/bin/env python3
"""Install this plugin into an isolated migration workspace.

This command prepares local files. It does not invoke an AI host, run legacy code,
or install software into a user's home directory.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from uuid import uuid4


ROOT = Path(__file__).resolve().parent.parent
PACKAGE_FILES = (
    ".claude-plugin", "agents", "assets", "commands", "com.github.copilot",
    "hooks", "hosts", "scripts", "skills", "workflows", "plugin.json",
    "LICENSE", "README.md", "tsconfig.json",
)
HOSTS = ("claude", "codex", "copilot-cli", "copilot-vscode", "antigravity")
PLUGIN_NAME = "nvi-code-modernization"
MARKETPLACE_NAME = "nvi-code-modernization-local"
SYSTEM_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class InstallError(Exception):
    pass


def inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def assert_workspace_separate(workspace: Path, source: Path) -> None:
    if inside(workspace, source) or inside(source, workspace):
        raise InstallError("workspace and source must be separate directories; use a sibling migration workspace")


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InstallError(f"cannot read JSON at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InstallError(f"expected a JSON object at {path}")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def add_marketplace(path: Path, plugin_entry: dict) -> str:
    if path.exists():
        data = read_json(path)
        entries = data.get("plugins")
        if not isinstance(entries, list):
            raise InstallError(f"marketplace has no plugins list: {path}")
        matching = [entry for entry in entries if isinstance(entry, dict) and entry.get("name") == PLUGIN_NAME]
        if matching:
            if matching[0] != plugin_entry:
                raise InstallError(f"existing {PLUGIN_NAME} marketplace entry differs: {path}")
            return data.get("name", MARKETPLACE_NAME)
    else:
        data = {"name": MARKETPLACE_NAME,
                "description": "Locally installed code modernization plugin for this migration workspace",
                "owner": {"name": "Local workspace"}, "plugins": []}
        entries = data["plugins"]
    entries.append(plugin_entry)
    write_json(path, data)
    return data["name"]


def write_managed(path: Path, content: str, replace: bool) -> None:
    if path.exists():
        old = path.read_text(encoding="utf-8")
        if old == content:
            return
        if not replace:
            raise InstallError(f"existing file differs; inspect before replacing: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_package(destination: Path, replace: bool, installed_before: bool) -> str:
    version = read_json(ROOT / "plugin.json")["version"]
    if destination.is_symlink() or not inside(destination.resolve(), destination.parent.resolve()):
        raise InstallError("plugin destination escapes the migration workspace")
    if destination.exists() and read_json(destination / "plugin.json").get("name") != PLUGIN_NAME:
        raise InstallError(f"plugin destination contains a different package: {destination}")
    if destination.exists() and not replace:
        if not installed_before or read_json(destination / "plugin.json").get("name") != PLUGIN_NAME:
            raise InstallError(f"plugin destination already exists: {destination}; use --replace only for an installer-managed copy")
        return version
    if destination.exists() and not installed_before:
        raise InstallError(f"refusing to replace unmanaged plugin directory: {destination}")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    if not inside(parent.resolve(), parent.parent.resolve()):
        raise InstallError("plugin directory escapes the migration workspace")
    stage = parent / f".{PLUGIN_NAME}-stage-{uuid4().hex}"
    backup = parent / f".{PLUGIN_NAME}-backup-{uuid4().hex}"
    try:
        stage.mkdir()
        for name in PACKAGE_FILES:
            src = ROOT / name
            dst = stage / name
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            elif src.is_file():
                shutil.copy2(src, dst)
            else:
                raise InstallError(f"package input is missing: {src}")
        if destination.exists():
            rename_with_retry(destination, backup)
        try:
            rename_with_retry(stage, destination)
        except OSError:
            if backup.exists():
                rename_with_retry(backup, destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return version


def rename_with_retry(source: Path, target: Path) -> None:
    for attempt in range(6):
        try:
            source.rename(target)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.1 * (attempt + 1))


def ensure_legacy_link(link: Path, source: Path) -> None:
    if link.exists() or link.is_symlink():
        try:
            same = os.path.samefile(link, source)
        except OSError:
            same = False
        if not same:
            raise InstallError(f"legacy path already points elsewhere: {link}")
        return
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(source, target_is_directory=True)
    except OSError as exc:
        if os.name != "nt":
            raise InstallError(f"could not link legacy source: {exc}") from exc
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(source)],
            capture_output=True, text=True, errors="replace", check=False,
        )
        if result.returncode != 0:
            raise InstallError(f"could not create Windows junction: {result.stderr.strip() or result.stdout.strip()}") from exc


def activate_host(host: str, workspace: Path, replace: bool) -> str:
    plugin = workspace / "plugins" / PLUGIN_NAME
    if host == "claude":
        marketplace = add_marketplace(
            workspace / ".claude-plugin" / "marketplace.json",
            {"name": PLUGIN_NAME, "source": "./plugins/nvi-code-modernization"},
        )
        return f'In Claude Code: /plugin marketplace add "{workspace}"; then /plugin install {PLUGIN_NAME}@{marketplace}'
    if host == "codex":
        marketplace = add_marketplace(
            workspace / ".agents" / "plugins" / "marketplace.json",
            {"name": PLUGIN_NAME, "source": {"source": "local", "path": "./plugins/nvi-code-modernization"},
             "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"},
        )
        config = workspace / ".codex" / "config.toml"
        section = f'[plugins."{PLUGIN_NAME}@{marketplace}"]'
        old = config.read_text(encoding="utf-8") if config.exists() else ""
        if section not in old:
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(old.rstrip() + ("\n\n" if old.strip() else "") + section + "\nenabled = true\n", encoding="utf-8")
        return (f'Run: codex plugin marketplace add "{workspace}"; '
                f'then codex plugin add {PLUGIN_NAME}@{marketplace}. '
                "Restart Codex in this trusted workspace and invoke $nvi-code-modernization.")
    if host == "copilot-cli":
        return f'Run: copilot plugin install "{plugin}"; then /nvi-modernize <stage> <system>'
    if host == "copilot-vscode":
        pointer = (
            "---\nname: nvi-code-modernization\n"
            "description: Assess, migrate, and independently verify a legacy codebase. Use for modernization work.\n"
            "---\n\nRead `plugins/nvi-code-modernization/skills/nvi-code-modernization/SKILL.md` and its "
            "host compatibility reference. The installed plugin root is `plugins/nvi-code-modernization`. "
            "Use `--host copilot-vscode` when refreshing the report.\n"
        )
        write_managed(workspace / ".github" / "skills" / PLUGIN_NAME / "SKILL.md", pointer, replace)
        prompt = (plugin / "hosts" / "copilot-vscode" / "nvi-modernize.prompt.md").read_text(encoding="utf-8")
        write_managed(workspace / ".github" / "prompts" / "nvi-modernize.prompt.md", prompt, replace)
        return "Open this workspace in Copilot agent mode and invoke /nvi-modernize with a stage and system."
    if host == "antigravity":
        pointer = (
            "---\nname: nvi-code-modernization\n"
            "description: Assess, migrate, and independently verify a legacy codebase. Use for modernization work.\n"
            "---\n\nRead `plugins/nvi-code-modernization/skills/nvi-code-modernization/SKILL.md` and its "
            "host compatibility reference. The installed plugin root is `plugins/nvi-code-modernization`. "
            "Use `--host antigravity` when refreshing the report.\n"
        )
        write_managed(workspace / ".agents" / "skills" / PLUGIN_NAME / "SKILL.md", pointer, replace)
        workflow = (plugin / "hosts" / "antigravity" / "nvi-modernize-workflow.md").read_text(encoding="utf-8")
        write_managed(workspace / ".agents" / "workflows" / "nvi-modernize.md", workflow, replace)
        return "Open this workspace in Antigravity and invoke /nvi-modernize with a stage and system."
    raise InstallError(f"unknown host: {host}")


def install(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    source = Path(args.source).expanduser().resolve(strict=True)
    if not source.is_dir():
        raise InstallError("--source must be a directory")
    if source == Path.home().resolve() or source.parent == source:
        raise InstallError("--source cannot be the home directory or filesystem root")
    if not SYSTEM_NAME.fullmatch(args.system):
        raise InstallError("--system must contain only letters, digits, '-' or '_', and start with a letter or digit")
    assert_workspace_separate(workspace, source)
    for relative in (".modernization", "plugins", "legacy", ".agents", ".codex", ".github", ".claude-plugin"):
        if not inside((workspace / relative).resolve(), workspace):
            raise InstallError(f"workspace directory escapes through a link: {relative}")
    generated_files = (
        ".modernization/install.json", ".claude-plugin/marketplace.json",
        ".agents/plugins/marketplace.json", ".agents/skills/nvi-code-modernization/SKILL.md",
        ".agents/workflows/nvi-modernize.md", ".codex/config.toml",
        ".github/skills/nvi-code-modernization/SKILL.md", ".github/prompts/nvi-modernize.prompt.md",
    )
    for relative in generated_files:
        target = workspace / relative
        if target.is_symlink() or not inside(target.resolve(), workspace):
            raise InstallError(f"generated file escapes through a link: {relative}")
    hosts = list(HOSTS) if "all" in args.host else list(dict.fromkeys(args.host))
    state_path = workspace / ".modernization" / "install.json"
    prior = read_json(state_path) if state_path.exists() else {}
    if prior and (prior.get("system") != args.system or Path(prior.get("source", "")).resolve() != source):
        raise InstallError("workspace is already bound to another system or source")
    workspace.mkdir(parents=True, exist_ok=True)
    plugin = workspace / "plugins" / PLUGIN_NAME
    ensure_legacy_link(workspace / "legacy" / args.system, source)
    version = copy_package(plugin, args.replace, bool(prior))
    prior_hosts = set(prior.get("hosts", []))
    steps = [activate_host(host, workspace, args.replace and host in prior_hosts) for host in hosts]
    merged_hosts = list(dict.fromkeys(list(prior.get("hosts", [])) + hosts))
    write_json(state_path, {"plugin": PLUGIN_NAME, "version": version, "system": args.system,
                            "source": str(source), "hosts": merged_hosts})
    print(f"Installed {PLUGIN_NAME} {version} in {workspace}")
    print(f"Legacy source: {source}")
    for step in steps:
        print(f"- {step}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="separate migration workspace, usually a sibling of the source")
    parser.add_argument("--source", required=True, help="existing legacy source directory")
    parser.add_argument("--system", required=True, help="short name for this system")
    parser.add_argument("--host", action="append", choices=HOSTS + ("all",), required=True)
    parser.add_argument("--replace", action="store_true", help="replace an installer-managed plugin copy and host shims")
    try:
        return install(parser.parse_args(argv))
    except (InstallError, OSError) as exc:
        print(f"install.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
