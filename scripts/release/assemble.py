"""Collect the tested downloads and release notes for a Xila candidate."""

import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

from validate import LOCKSTEP, ROOT, VERSION, check_candidate, check_versions, git

PLATFORMS = "xila-project/platforms"
SDK_TARGETS = ("x86_64-unknown-linux-gnu", "thumbv7em-none-eabihf", "riscv32imac-unknown-none-elf")


def github(*arguments):
    return subprocess.check_output(["gh", *arguments], text=True).strip()


def find_run(repository, workflow, event, revision):
    arguments = [
        "run", "list", "--repo", repository, "--workflow", workflow,
        "--event", event, "--branch", "main", "--status", "success",
        "--json", "databaseId,displayTitle,headSha",
    ]
    if event == "workflow_run":
        # The browser build checks out the triggering CI SHA. Its own workflow
        # run may be associated with a newer default-branch SHA.
        arguments += ["--limit", "100"]
    else:
        arguments += ["--commit", revision]
    for run in json.loads(github(*arguments)):
        if event == "workflow_run" and run["displayTitle"] != f"Browser demonstrations for {revision}":
            continue
        return str(run["databaseId"])
    raise ValueError(f"no successful {repository}/{workflow} run for {revision}")


def download(repository, run, artifact, destination):
    github(
        "run", "download", run, "--repo", repository,
        "--name", artifact, "--dir", str(destination),
    )


def archive(source, destination, name):
    def normalize(member):
        member.mtime = member.uid = member.gid = 0
        member.uname = member.gname = ""
        return member

    with destination.open("wb") as output, gzip.GzipFile(fileobj=output, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as package:
            package.add(source, arcname=name, filter=normalize)


def collect_downloads(revisions, output):
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        platforms_run = find_run(PLATFORMS, "ci.yml", "push", revisions["platforms"])
        native = staging / "native"
        download(PLATFORMS, platforms_run, "xila-native-linux-x86_64", native)
        binary = native / "native_example"
        binary.chmod(0o755)
        for board in ("nano-33-ble", "esp32s3", "esp32c6"):
            download(PLATFORMS, platforms_run, f"xila-{board}", output)
            expected = output / (f"{board}.bin" if board == "nano-33-ble" else f"{board}-flash.bin")
            if not expected.is_file():
                raise ValueError(f"missing {expected.name} in the Platforms CI artifact")

        browser_run = find_run(PLATFORMS, "demo.yml", "workflow_run", revisions["platforms"])
        download(PLATFORMS, browser_run, "xila-native-seed", native)
        if not (native / "native.img").is_file():
            raise ValueError("missing native.img in the Platforms browser demonstration run")
        archive(native, output / "xila-linux-x86_64.tar.gz", "xila-linux-x86_64")
        browser = staging / "browser"
        download(PLATFORMS, browser_run, "platform-demonstrations", browser)
        provenance = browser / "platform-revision.txt"
        if provenance.read_text().strip() != revisions["platforms"]:
            raise ValueError("the browser artifact was built from a different Platforms revision")
        provenance.unlink()
        archive(browser, output / "xila-browser.tar.gz", "demonstrations")

        core = "xila-project/core"
        core_run = find_run(core, "ci.yml", "push", revisions["core"])
        for target in SDK_TARGETS:
            sdk = staging / target
            download(core, core_run, f"xila-sdk-{target}", sdk)
            archives = list(sdk.glob("xila-sdk-*.tar.zst"))
            if len(archives) != 1 or (output / archives[0].name).exists():
                raise ValueError(f"expected one unique SDK archive for {target}")
            shutil.copyfile(archives[0], output / archives[0].name)


def release_notes(root, revisions, tag, previous_tag):
    notes = [f"# Xila {tag.removeprefix('v')}", ""]
    for repository in ("workspace", *LOCKSTEP):
        directory = root if repository == "workspace" else root / "repositories" / repository
        revision = revisions[repository]
        git(directory, "fetch", "--no-tags", "origin", "main")
        git(directory, "merge-base", "--is-ancestor", revision, "FETCH_HEAD")
        remote = f"https://github.com/xila-project/{repository}"
        if previous_tag:
            git(directory, "fetch", "--no-tags", "origin", f"refs/tags/{previous_tag}")
            baseline = git(directory, "rev-parse", "FETCH_HEAD^{commit}")
            git(directory, "merge-base", "--is-ancestor", baseline, revision)
            link = f"{remote}/compare/{baseline}...{revision}"
            history = f"{baseline}..{revision}"
        else:
            link = f"{remote}/commits/{revision}"
            history = revision
        changes = git(directory, "log", "--first-parent", "--format=- %s (%h)", history)
        notes += [f"## {repository}", "", f"[Review changes]({link})", "", changes or "No changes.", ""]
    return "\n".join(notes)


def main():
    output = ROOT / "target/release-candidate"
    try:
        tag = os.environ["XILA_RELEASE_TAG"]
        previous_tag = os.getenv("XILA_PREVIOUS_TAG", "")
        if previous_tag and not re.fullmatch(f"v{VERSION}", previous_tag):
            raise ValueError(f"invalid previous Xila tag {previous_tag}")
        if previous_tag == tag:
            raise ValueError("the previous release tag must differ from the candidate tag")
        if not previous_tag:
            tags = git(ROOT, "tag", "--list", "v*").splitlines()
            if any(re.fullmatch(f"v{VERSION}", existing) and existing != tag for existing in tags):
                raise ValueError("set the previous Xila tag when preparing a later release")
        check_versions(ROOT / "repositories", tag)
        revisions = {"workspace": git(ROOT, "rev-parse", "HEAD"), **check_candidate(ROOT)}
        notes = release_notes(ROOT, revisions, tag, previous_tag)
        output.mkdir(parents=True)
        collect_downloads(revisions, output)
        (output / "RELEASE_NOTES.md").write_text(notes)
        (output / "revisions.json").write_text(json.dumps(revisions, indent=2) + "\n")
        checksums = []
        for download_file in sorted(output.iterdir()):
            with download_file.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            checksums.append(f"{digest}  {download_file.name}\n")
        (output / "SHA256SUMS").write_text("".join(checksums))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
