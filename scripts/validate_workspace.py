#!/usr/bin/env python3
"""Validate the workspace's tracked Git submodules without network access."""
from configparser import ConfigParser
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"core", "platforms", "applications", "package_manager", "packages"}


def main() -> int:
    config = ConfigParser(interpolation=None)
    if not config.read(ROOT / ".gitmodules"):
        raise SystemExit("Missing .gitmodules")
    paths = {}
    for section in config.sections():
        if not section.startswith("submodule "):
            raise SystemExit(f"Unexpected .gitmodules section: {section}")
        path = config.get(section, "path")
        url = config.get(section, "url")
        branch = config.get(section, "branch", fallback="main")
        if path in paths or not path.startswith("repositories/") or ".." in Path(path).parts:
            raise SystemExit(f"Invalid or duplicate submodule path: {path}")
        expected_name = path.split("/", 1)[1]
        if url != f"https://github.com/xila-project/{expected_name}.git":
            raise SystemExit(f"Unexpected submodule URL: {path} -> {url}")
        if branch != "main":
            raise SystemExit(f"Unexpected tracked branch: {path} -> {branch}")
        paths[path] = expected_name

    if not REQUIRED.issubset(paths.values()):
        raise SystemExit(f"Missing integration repositories: {sorted(REQUIRED - set(paths.values()))}")

    output = subprocess.check_output(
        ["git", "ls-files", "--stage", "--", "repositories"],
        cwd=ROOT, text=True,
    )
    links = {}
    for line in output.splitlines():
        metadata, path = line.split("\t", 1)
        mode, sha, stage = metadata.split()
        if mode != "160000" or stage != "0" or len(sha) != 40:
            raise SystemExit(f"Invalid gitlink: {line}")
        links[path] = sha
    if set(paths) != set(links):
        raise SystemExit(f"Gitlinks and .gitmodules differ: configured={sorted(paths)}, tracked={sorted(links)}")

    print(f"Validated {len(links)} pinned Xila submodules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
