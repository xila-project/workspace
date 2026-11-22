"""Validate the versions of the pinned Xila operating system repositories."""

import argparse
from pathlib import Path
import re
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[2]
LOCKSTEP = ("core", "platforms", "tools")
VERSION = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
SOURCE = re.compile(
    r"git\+https://github\.com/xila-project/([a-z_]+)(?:\.git)?\?([^#]+)#([0-9a-f]{40})",
    re.IGNORECASE,
)


def read_toml(path):
    with path.open("rb") as handle:
        return tomllib.load(handle)


def check_versions(repositories, tag=None):
    versions = {
        repository: read_toml(repositories / repository / "Cargo.toml")["workspace"]["package"]["version"]
        for repository in LOCKSTEP
    }
    version = versions["core"]
    if not re.fullmatch(VERSION, version):
        raise ValueError(f"Core workspace version must use X.Y.Z, found {version}")
    for repository in LOCKSTEP[1:]:
        if versions[repository] != version:
            raise ValueError(
                f"{repository} workspace version {versions[repository]} differs from Core {version}"
            )
    # Older pins predate xila-version. Candidates must use Core's Cargo-derived RUNNING.
    version_manifest = repositories / "core/libraries/version/Cargo.toml"
    if version_manifest.exists() or tag is not None:
        if not version_manifest.exists() or read_toml(version_manifest)["package"]["version"] != {
            "workspace": True
        }:
            raise ValueError("xila-version must inherit Core's workspace version")
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"expected release tag v{version}, found {tag}")
    return version


def check_lockfile(lockfile, revisions):
    for package in read_toml(lockfile)["package"]:
        source = package.get("source", "")
        match = SOURCE.fullmatch(source)
        if match:
            repository, reference, revision = match.groups()
            repository = repository.lower()
            if repository in revisions and reference != "branch=main":
                raise ValueError(f"{lockfile.parent.name}/Cargo.lock must track {repository} main")
            if repository in revisions and revision != revisions[repository]:
                raise ValueError(
                    f"{lockfile.parent.name}/Cargo.lock locks {repository} to {revision}, "
                    f"but the workspace pins {revisions[repository]}"
                )


def git(directory, *arguments):
    return subprocess.check_output(["git", "-C", directory, *arguments], text=True).strip()


def check_candidate(root):
    repositories = root / "repositories"
    revisions = {}
    for repository in (*LOCKSTEP, "applications", "package_manager"):
        path = f"repositories/{repository}"
        revision = git(root, "rev-parse", f"HEAD:{path}")
        if git(repositories / repository, "rev-parse", "HEAD") != revision:
            raise ValueError(f"{path} is not checked out at workspace gitlink {revision}")
        revisions[repository] = revision
    for repository in (*LOCKSTEP, "applications"):
        check_lockfile(repositories / repository / "Cargo.lock", revisions)
    return revisions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="validate a release candidate against its proposed vX.Y.Z tag")
    args = parser.parse_args()
    try:
        version = check_versions(ROOT / "repositories", args.tag)
        if args.tag is not None:
            for repository, revision in check_candidate(ROOT).items():
                print(f"{repository}: {revision}")
        print(f"Xila version {version}")
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
