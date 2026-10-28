#!/usr/bin/env python3
"""Validate the workspace's tracked Git submodules without network access."""
from configparser import ConfigParser
from pathlib import Path
import tomllib
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

    # Keep system package declarations in mise, never inline apt in Actions.
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    if "apt-get" in workflow or "mise run ci:packages-integration" not in workflow or "mise run ci:node-dependencies" not in workflow:
        raise SystemExit("Workspace CI must bootstrap system packages through mise")

    # Native dependencies are owned by Platforms, not re-declared here.
    task_config = tomllib.loads((ROOT / "mise.toml").read_text())
    bootstrap = task_config.get("tasks", {}).get("ci:packages-integration", {}).get("run", "")
    if "cd repositories/platforms && mise -E ci run ci:packages-host" not in bootstrap:
        raise SystemExit("Integration package task must delegate to Platforms")

    shared = tomllib.loads((ROOT / "mise/shared.toml").read_text())
    if shared.get("bootstrap", {}).get("packages"):
        raise SystemExit("Workspace must not duplicate submodule-native packages")

    # Quality checks can run without submodules. When Platforms is initialized,
    # verify the owner still provides the delegated task and package declarations.
    platforms_config = ROOT / "repositories/platforms/mise.ci.toml"
    if platforms_config.is_file():
        owner = tomllib.loads(platforms_config.read_text())
        if "ci:packages-host" not in owner.get("tasks", {}):
            raise SystemExit("Pinned Platforms revision lacks ci:packages-host")
        declared = owner.get("bootstrap", {}).get("packages", {})
        required = {
            "apt:clang", "apt:libclang-dev", "apt:pkg-config",
            "apt:libasound2-dev", "apt:libudev-dev", "apt:libxkbcommon-dev",
            "apt:libwayland-dev", "apt:libx11-dev", "apt:libxkbcommon-x11-dev",
        }
        if not required.issubset(declared):
            raise SystemExit(f"Platforms is missing native packages: {sorted(required - set(declared))}")

    print(f"Validated {len(links)} pinned Xila submodules and delegated platform-native bootstrap")
    return 0


if __name__ == "__main__":
    sys.exit(main())
