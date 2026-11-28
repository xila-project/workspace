"""Collect the tested downloads and release notes for a Xila candidate."""

import ast
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
        if event == "workflow_run":
            if run["displayTitle"] != f"Browser demonstrations for {revision}":
                continue
        elif run["headSha"] != revision:
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

    with destination.open("wb") as output, gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as package:
            package.add(source, arcname=name, filter=normalize)


TARGET_NAME = re.compile(r"[a-z0-9_]+(-[a-z0-9_]+)+")
MUTATING_METHODS = {"clear", "pop", "popitem", "setdefault", "update", "__setitem__", "__delitem__", "__ior__"}


def sdk_targets(core, revision):
    path = "tools/sdk/build.py"
    location = f"Core {revision}:{path}"
    source = git(core, "show", f"{revision}:{path}")
    # Read the target keys without running the SDK builder or importing its dependencies.
    try:
        module = ast.parse(source, filename=path)
    except SyntaxError as error:
        raise ValueError(f"{location} is not valid Python: {error}") from error

    # A static read is correct only if the single literal assignment is the final value.
    for node in ast.walk(module):
        if isinstance(node, (ast.Subscript, ast.Attribute)) and isinstance(node.value, ast.Name) \
                and node.value.id == "TARGETS":
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)):
                raise ValueError(f"{location} changes TARGETS after its definition")
            if isinstance(node, ast.Attribute) and node.attr in MUTATING_METHODS:
                raise ValueError(f"{location} changes TARGETS with {node.attr}()")
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == "TARGETS":
            raise ValueError(f"{location} changes TARGETS after its definition")

    assignments = []
    for statement in module.body:
        if isinstance(statement, ast.Assign):
            names = statement.targets
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            names = [statement.target]
        else:
            continue
        if any(isinstance(name, ast.Name) and name.id == "TARGETS" for name in names):
            assignments.append(statement.value)
    stores = sum(
        isinstance(node, ast.Name) and node.id == "TARGETS" and isinstance(node.ctx, ast.Store)
        for node in ast.walk(module)
    )
    if not assignments:
        raise ValueError(f"{location} does not define TARGETS")
    if len(assignments) != 1 or stores != 1:
        raise ValueError(f"{location} assigns TARGETS more than once")

    value = assignments[0]
    if not isinstance(value, ast.Dict):
        raise ValueError(f"{location} must define TARGETS as a dictionary literal")
    if not value.keys:
        raise ValueError(f"{location} defines an empty TARGETS")
    if not all(isinstance(key, ast.Constant) and isinstance(key.value, str) for key in value.keys):
        raise ValueError(f"{location} must use literal string keys in TARGETS")
    targets = [key.value for key in value.keys]
    if len(targets) != len(set(targets)):
        raise ValueError(f"{location} has duplicate TARGETS keys")
    for target in targets:
        if not TARGET_NAME.fullmatch(target):
            raise ValueError(f"{location} has an invalid target name {target!r}")
    return targets


def collect_downloads(revisions, version, output, targets):
    major_minor = ".".join(version.split(".")[:2])
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        platforms_run = find_run(PLATFORMS, "ci.yml", "push", revisions["platforms"])
        native = staging / "native"
        download(PLATFORMS, platforms_run, "xila-native-linux-x86_64", native)
        binary = native / "native_example"
        binary.chmod(0o755)
        # Only device firmware is released. The Espressif CI images are built
        # with QEMU-only features (virtual display, no entropy source).
        download(PLATFORMS, platforms_run, "xila-nano-33-ble", output)
        if not (output / "nano-33-ble.bin").is_file():
            raise ValueError("missing nano-33-ble.bin in the Platforms CI artifact")

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
        for target in targets:
            sdk = staging / target
            try:
                download(core, core_run, f"xila-sdk-{target}", sdk)
            except subprocess.CalledProcessError as error:
                raise ValueError(
                    f"Core CI run {core_run} has no xila-sdk-{target} artifact for a target in TARGETS"
                ) from error
            expected_name = f"xila-sdk-{major_minor}-{target}.tar.zst"
            archives = list(sdk.glob("xila-sdk-*.tar.zst"))
            if len(archives) != 1 or archives[0].name != expected_name or (output / expected_name).exists():
                raise ValueError(f"expected one unique {expected_name} archive for {target}")
            shutil.copyfile(archives[0], output / expected_name)


def verify_main_ancestry(root, revisions):
    for repository, revision in revisions.items():
        directory = root if repository == "workspace" else root / "repositories" / repository
        git(directory, "fetch", "--no-tags", "origin", "main")
        git(directory, "merge-base", "--is-ancestor", revision, "FETCH_HEAD")


def release_notes(root, revisions, tag, previous_tag):
    notes = [f"# Xila {tag.removeprefix('v')}", ""]
    for repository in ("workspace", *LOCKSTEP):
        directory = root if repository == "workspace" else root / "repositories" / repository
        revision = revisions[repository]
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
        version = check_versions(ROOT / "repositories", tag)
        revisions = {"workspace": git(ROOT, "rev-parse", "HEAD"), **check_candidate(ROOT)}
        verify_main_ancestry(ROOT, revisions)
        notes = release_notes(ROOT, revisions, tag, previous_tag)
        # Read the targets first: a bad Core build script must not leave a partial output directory.
        targets = sdk_targets(ROOT / "repositories/core", revisions["core"])
        output.mkdir(parents=True)
        collect_downloads(revisions, version, output, targets)
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
