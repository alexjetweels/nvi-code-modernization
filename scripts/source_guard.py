#!/usr/bin/env python3
"""Record and verify the legacy source tree without executing anything in it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile


MAX_FILES = 1_000_000
CHUNK = 1 << 20


def _name(system):
    if not system or system in (".", "..") or any(c in system for c in "/\\\x00"):
        raise ValueError("system must be a folder name, not a path")
    return system


def _paths(workspace, system):
    root = Path(workspace).resolve()
    source = root / "legacy" / _name(system)
    if not source.is_dir():
        raise ValueError("legacy source does not exist")
    real_source = source.resolve()
    if real_source == Path.home().resolve() or real_source.parent == real_source:
        raise ValueError("legacy source points to the home directory or filesystem root")
    analysis = root / "analysis" / system
    if os.path.commonpath((str(root), str(analysis.resolve()))) != str(root):
        raise ValueError("analysis path escapes the workspace")
    return real_source, analysis / "SOURCE_SNAPSHOT.json"


def _hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(CHUNK)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def inventory(source):
    """Map relative paths to content fingerprints; links are recorded but never followed."""
    records = {}
    pending = [source]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name == ".git":
                    continue
                path = Path(entry.path)
                rel = path.relative_to(source).as_posix()
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISLNK(mode):
                    records[rel] = "link:" + os.readlink(path)
                elif stat.S_ISDIR(mode):
                    pending.append(path)
                elif stat.S_ISREG(mode):
                    records[rel] = "sha256:" + _hash_file(path)
                else:
                    records[rel] = "other:" + str(stat.S_IFMT(mode))
                if len(records) > MAX_FILES:
                    raise ValueError("source has more than %d entries; snapshot is incomplete" % MAX_FILES)
    return records


def snapshot(workspace, system):
    source, destination = _paths(workspace, system)
    if destination.is_symlink():
        raise ValueError("snapshot file is a link")
    if destination.exists():
        result = verify(workspace, system)
        if result["state"] != "clean":
            raise ValueError("existing source snapshot is not clean; preserve the original baseline")
        return {"state": "clean", "method": "SHA-256 snapshot", "detail": "existing snapshot verified", "files": []}
    records = inventory(source)
    value = {"v": 1, "sourcePathHash": hashlib.sha256(str(source).encode("utf-8")).hexdigest(),
             "files": records}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as stream:
        tmp = Path(stream.name)
        json.dump(value, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
    try:
        os.replace(tmp, destination)
    finally:
        if tmp.exists():
            tmp.unlink()
    return {"state": "clean", "method": "SHA-256 snapshot", "detail": "%d entries snapshotted" % len(records), "files": []}


def verify(workspace, system):
    source, saved = _paths(workspace, system)
    out = {"state": "unknown", "method": "SHA-256 snapshot", "detail": "", "files": []}
    if not saved.is_file() or saved.is_symlink():
        out["detail"] = "SOURCE_SNAPSHOT.json is missing or is a link"
        return out
    try:
        data = json.loads(saved.read_text(encoding="utf-8"))
        if data.get("v") != 1 or not isinstance(data.get("files"), dict):
            raise ValueError("invalid snapshot format")
        if data.get("sourcePathHash") != hashlib.sha256(str(source).encode("utf-8")).hexdigest():
            raise ValueError("snapshot belongs to a different source path")
        current = inventory(source)
    except (OSError, ValueError, AttributeError) as exc:
        out["detail"] = "source could not be verified (%s)" % type(exc).__name__
        return out
    old = data["files"]
    changed = sorted(path for path in old.keys() | current.keys() if old.get(path) != current.get(path))
    out["files"] = changed[:10]
    out["state"] = "changed" if changed else "clean"
    out["detail"] = "%d changed entries of %d checked" % (len(changed), len(current))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("snapshot", "verify"))
    parser.add_argument("system")
    parser.add_argument("--workspace", default=".")
    args = parser.parse_args(argv)
    try:
        result = snapshot(args.workspace, args.system) if args.action == "snapshot" else verify(args.workspace, args.system)
    except (OSError, ValueError) as exc:
        print("source_guard.py: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["state"] == "clean" else 1


if __name__ == "__main__":
    sys.exit(main())
