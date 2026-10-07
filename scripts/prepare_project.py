#!/usr/bin/env python3
"""Discover and prepare a bundled project with a top-level legacy source."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


EXCLUDED_DIRECTORIES = {"nvi-code-modernization", "modernized", "analysis", "legacy", "plugins"}


def discover_source(root: Path, system: str | None) -> Path:
    if system is not None:
        if not system or system in (".", "..") or any(char in system for char in "/\\\x00"):
            raise ValueError("system must be a single folder name")
        if system in EXCLUDED_DIRECTORIES or system.startswith("."):
            raise ValueError("system must name a top-level legacy source folder")
        source = root / system
        if not source.is_dir():
            raise ValueError(f"legacy source folder does not exist: {source}")
        return source
    candidates = sorted(
        path for path in root.iterdir()
        if path.is_dir() and not path.name.startswith(".") and path.name not in EXCLUDED_DIRECTORIES
    )
    if len(candidates) != 1:
        names = ", ".join(path.name for path in candidates) or "none"
        raise ValueError(f"expected one top-level legacy source folder; found: {names}. Pass its folder name explicitly")
    return candidates[0]


def prepare(workspace: Path, system: str | None = None) -> tuple[str, Path]:
    root = workspace.expanduser().resolve()
    source = discover_source(root, system)
    system = source.name
    if not source.is_dir() or source.is_symlink():
        raise ValueError(f"bundled legacy source is missing or is a link: {source}")
    if source.resolve() != source:
        raise ValueError("bundled legacy source must be a physical directory")
    output = root / "modernized"
    if output.resolve() != output or (output.exists() and not output.is_dir()):
        raise ValueError(f"new-code path is not a regular directory: {output}")
    legacy_root = root / "legacy"
    if legacy_root.exists() and (not legacy_root.is_dir() or legacy_root.resolve() != legacy_root):
        raise ValueError(f"legacy alias directory is not a physical directory: {legacy_root}")
    link = legacy_root / system
    if link.exists() or link.is_symlink():
        try:
            matching = os.path.samefile(link, source)
        except OSError:
            matching = False
        if not matching:
            raise ValueError(f"legacy alias points elsewhere: {link}")
    else:
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            link.symlink_to(Path("..") / system, target_is_directory=True)
        except OSError as error:
            if os.name != "nt":
                raise ValueError(f"cannot create legacy alias: {error}") from error
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(source)],
                capture_output=True, text=True, errors="replace", check=False,
            )
            if result.returncode != 0:
                message = result.stderr.strip() or result.stdout.strip()
                raise ValueError(f"cannot create legacy alias: {message}") from error
    if not os.path.samefile(link, source):
        raise ValueError(f"legacy alias does not resolve to bundled source: {link}")
    output.mkdir(exist_ok=True)
    return system, link


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("system", nargs="?", help="top-level legacy source folder; inferred when unique")
    parser.add_argument("--workspace", default=".", help="project root")
    args = parser.parse_args()
    try:
        system, link = prepare(Path(args.workspace), args.system)
    except (OSError, ValueError) as error:
        print(f"prepare_project.py: {error}", file=sys.stderr)
        return 1
    print(f"Ready: {system} (legacy/{system} -> {system}/)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
