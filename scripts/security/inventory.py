#!/usr/bin/env python3
"""Prepare the public-repository inventory and report each scanned source revision."""
from configparser import ConfigParser
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ORGANIZATION = "xila-project"


def repository_matrix(gitmodules: Path) -> dict:
    config = ConfigParser(interpolation=None)
    if not config.read(gitmodules):
        raise ValueError("Missing .gitmodules")
    names = {"workspace"}
    for section in config.sections():
        path = config.get(section, "path")
        name = path.removeprefix("repositories/")
        if path != f"repositories/{name}" or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise ValueError(f"Invalid inventory repository: {path}")
        if config.get(section, "url") != f"https://github.com/{ORGANIZATION}/{name}.git":
            raise ValueError(f"Unexpected inventory remote: {path}")
        names.add(name)
    projects = [
        {"repository": f"{ORGANIZATION}/{name}",
         # Nanobom slugs must begin with an ASCII letter or digit.
         "project": "github-community" if name == ".github" else name.lower()}
        for name in sorted(names)
    ]
    if len({project["project"] for project in projects}) != len(projects):
        raise ValueError("Inventory repositories produce duplicate Nanobom project slugs")
    return {"include": projects}


def output(name: str, value: str) -> None:
    print(value)
    destination = os.environ.get("GITHUB_OUTPUT")
    if destination:
        with open(destination, "a", encoding="utf-8") as stream:
            stream.write(f"{name}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["repositories", "source-revision", "credentials"])
    args = parser.parse_args()
    if args.command == "repositories":
        output("matrix", json.dumps(repository_matrix(ROOT / ".gitmodules"), separators=(",", ":")))
    elif args.command == "source-revision":
        revision = subprocess.check_output(
            ["git", "-C", str(ROOT / "source"), "rev-parse", "HEAD"], text=True
        ).strip()
        if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
            raise ValueError("Scanned checkout has an invalid source revision")
        output("sha", revision)
    elif not os.environ.get("NANOBOM_TOKEN", "").strip():
        raise SystemExit("Set the organization Actions secret NANOBOM_TOKEN to a Nanobom whole-organization upload token before running this workflow.")


if __name__ == "__main__":
    main()
