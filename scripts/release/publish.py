"""Publish a validated release candidate after every draft asset is uploaded."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from assemble import PLATFORMS, github
from validate import LOCKSTEP, ROOT, VERSION


def release_for(tag):
    pages = json.loads(github("api", "--paginate", "--slurp", f"repos/{PLATFORMS}/releases"))
    for page in pages:
        for release in page:
            if release["tag_name"] == tag:
                return release
    return None


def tag_revision(repository, tag):
    remote = f"https://github.com/xila-project/{repository}.git"
    reference = f"refs/tags/{tag}"
    output = subprocess.check_output(
        ["git", "ls-remote", remote, reference, f"{reference}^{{}}"], text=True,
    )
    revisions = {name: revision for revision, name in map(str.split, output.splitlines())}
    return revisions.get(f"{reference}^{{}}", revisions.get(reference))


def create_tag(repository, tag, revision):
    endpoint = f"repos/xila-project/{repository}/git"
    if repository == "workspace":
        release_url = f"https://github.com/{PLATFORMS}/releases/tag/{tag}"
        revision = github(
            "api", "--method", "POST", f"{endpoint}/tags",
            "-f", f"tag={tag}", "-f", f"message=Xila {tag[1:]}\n\n{release_url}",
            "-f", f"object={revision}", "-f", "type=commit", "--jq", ".sha",
        )
    github(
        "api", "--method", "POST", f"{endpoint}/refs",
        "-f", f"ref=refs/tags/{tag}", "-f", f"sha={revision}",
    )


def verify_assets(release, files):
    pages = json.loads(github(
        "api", "--paginate", "--slurp", f"repos/{PLATFORMS}/releases/{release['id']}/assets",
    ))
    uploaded = {asset["name"]: asset["digest"] for page in pages for asset in page}
    expected = {}
    for path in files:
        with path.open("rb") as stream:
            expected[path.name] = "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()
    if uploaded != expected:
        raise ValueError("Platforms draft assets differ from the validated release candidate")


def github_notes(tag, revisions, previous_tag):
    sections = []
    for repository in ("workspace", *LOCKSTEP):
        arguments = [
            "api", "--method", "POST", f"repos/xila-project/{repository}/releases/generate-notes",
            "-f", f"tag_name={tag}", "-f", f"target_commitish={revisions[repository]}",
            "--jq", ".body",
        ]
        if previous_tag:
            arguments += ["-f", f"previous_tag_name={previous_tag}"]
        sections.append(f"## {repository}\n\n{github(*arguments)}")
    return "\n\n".join(sections)


def publish(tag, revisions, files, previous_tag=""):
    existing = release_for(tag)
    if existing and not existing["draft"]:
        raise ValueError(f"Platforms release {tag} is already published")
    if existing and existing["target_commitish"] != revisions["platforms"]:
        raise ValueError(f"Platforms draft {tag} targets a different commit")
    repositories = (*LOCKSTEP, "workspace")
    tagged = {repository: tag_revision(repository, tag) for repository in repositories}
    for repository, revision in tagged.items():
        if revision and (not existing or revision != revisions[repository]):
            raise ValueError(f"tag {tag} already exists in {repository}; verify its release state")
    if not existing:
        with tempfile.TemporaryDirectory() as temporary:
            notes = Path(temporary) / "release-notes.md"
            notes.write_text(github_notes(tag, revisions, previous_tag))
            arguments = [
                "release", "create", tag, "--repo", PLATFORMS, "--draft",
                "--target", revisions["platforms"], "--title", f"Xila {tag[1:]}",
                "--notes-file", str(notes),
            ]
            if tag.startswith("v0."):
                arguments.append("--prerelease")
            github(*arguments)
        existing = release_for(tag)
        if not existing or not existing["draft"] or existing["target_commitish"] != revisions["platforms"]:
            raise ValueError("could not verify the Platforms draft release")
    if any(tagged.values()):
        # A retry after a tag operation can only finish the previously verified
        # draft. Never replace assets once any of its tags exists.
        verify_assets(existing, files)
    else:
        github("release", "upload", tag, "--repo", PLATFORMS, "--clobber", *map(str, files))
        verify_assets(existing, files)
    for repository in repositories:
        if not tagged[repository]:
            create_tag(repository, tag, revisions[repository])
    github("release", "edit", tag, "--repo", PLATFORMS, "--draft=false")


def main():
    try:
        tag = os.environ["XILA_RELEASE_TAG"]
        previous_tag = os.getenv("XILA_PREVIOUS_TAG", "")
        if not re.fullmatch(f"v{VERSION}", tag) or (previous_tag and not re.fullmatch(f"v{VERSION}", previous_tag)):
            raise ValueError("release tags must use vX.Y.Z")
        directory = ROOT / "target/release-candidate"
        revisions = json.loads((directory / "revisions.json").read_text())
        if revisions["workspace"] != os.environ["GITHUB_SHA"]:
            raise ValueError("candidate workspace commit differs from the workflow commit")
        subprocess.run(["sha256sum", "--check", "SHA256SUMS"], cwd=directory, check=True)
        publish(tag, revisions, sorted(directory.iterdir()), previous_tag)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
