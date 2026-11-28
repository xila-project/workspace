import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import assemble
from assemble import check_sdk_artifacts, run_artifacts, sdk_targets

CORE = Path("repositories/core")
REVISION = "a" * 40

# Target lists of Core ac18ac34 (current pin) and 3f27bb4c (main on 2026-11-28).
THREE_TARGETS = ["x86_64-unknown-linux-gnu", "thumbv7em-none-eabihf", "riscv32imac-unknown-none-elf"]
SIX_TARGETS = [
    "x86_64-unknown-linux-gnu",
    "aarch64-unknown-linux-gnu",
    "thumbv7em-none-eabihf",
    "riscv32imac-unknown-none-elf",
    "riscv32imafc-unknown-none-elf",
    "xtensa-esp32s3-elf",
]


def build_script(targets):
    entries = "".join(f'    "{target}": {{"flags": []}},\n' for target in targets)
    return f"import build_dependency\n\nTARGETS = {{\n{entries}}}\n\nfor name in TARGETS:\n    print(TARGETS[name])\n"


class SdkTargetsTests(unittest.TestCase):
    @patch("assemble.git")
    def test_reads_targets_from_the_pinned_commit(self, git):
        for targets in (THREE_TARGETS, SIX_TARGETS):
            with self.subTest(count=len(targets)):
                git.reset_mock()
                git.return_value = build_script(targets)
                self.assertEqual(sdk_targets(CORE, REVISION), targets)
                git.assert_called_once_with(CORE, "show", f"{REVISION}:tools/sdk/build.py")

    @patch("assemble.git")
    def test_accepts_read_only_uses(self, git):
        git.return_value = (
            "TARGETS = {'a-b': {'flags': []}}\n"
            "for name, entry in TARGETS.items():\n    print(TARGETS.get(name), len(TARGETS))\n"
            "TARGETS['a-b']['flags'].append('-O2')\n"
        )
        self.assertEqual(sdk_targets(CORE, REVISION), ["a-b"])

    @patch("assemble.git")
    def test_accepts_an_annotated_assignment(self, git):
        git.return_value = "TARGETS: dict[str, dict] = {'xtensa-esp32s3-elf': {}}"
        self.assertEqual(sdk_targets(CORE, REVISION), ["xtensa-esp32s3-elf"])

    @patch("assemble.git")
    def test_rejects_missing_or_invalid_target_lists(self, git):
        for source, message in (
            ("TARGETS = {", "is not valid Python"),
            ("OTHER_TARGETS = {'x86_64-unknown-linux-gnu': {}}", "must define TARGETS"),
            ("TARGETS = dict(BASE)", "dictionary literal"),
            ("TARGETS = {}", "empty TARGETS"),
            ("TARGETS = {target: {}}", "literal string keys"),
            ("TARGETS = {**BASE}", "literal string keys"),
            ("TARGETS = {'x86_64-unknown-linux-gnu': {}, 'x86_64-unknown-linux-gnu': {}}", "duplicate"),
            ("TARGETS = {'../escape': {}}", "invalid target name"),
            ("TARGETS = {'a-b': {}}\nTARGETS = {'c-d': {}}", "more than once"),
            ("TARGETS = {'a-b': {}}\ndef f():\n    global TARGETS\n    TARGETS = {}", "more than once"),
            ("TARGETS = {'a-b': {}}\nTARGETS['c-d'] = {}", "changes TARGETS"),
            ("TARGETS = {'a-b': {}}\ndel TARGETS['a-b']", "changes TARGETS"),
            ("TARGETS = {'a-b': {}}\nTARGETS.update({'c-d': {}})", "update"),
            ("TARGETS = {'a-b': {}}\nTARGETS |= {'c-d': {}}", "changes TARGETS"),
            ("TARGETS = {'a-b': {}}\ndel TARGETS", "deletes TARGETS"),
            ("if True:\n    TARGETS = {'a-b': {}}", "top-level assignment"),
        ):
            with self.subTest(source=source):
                git.return_value = source
                with self.assertRaisesRegex(ValueError, message):
                    sdk_targets(CORE, REVISION)

    @patch("assemble.git")
    def test_passes_git_errors_to_the_caller(self, git):
        git.side_effect = subprocess.CalledProcessError(128, ["git", "show"])
        with self.assertRaises(subprocess.CalledProcessError):
            sdk_targets(CORE, REVISION)


class SdkArtifactTests(unittest.TestCase):
    def test_accepts_artifacts_that_match_the_targets(self):
        artifacts = ["xila-native-linux-x86_64", *(f"xila-sdk-{target}" for target in SIX_TARGETS)]
        check_sdk_artifacts(SIX_TARGETS, artifacts, "1")

    def test_rejects_a_target_that_the_static_read_missed(self):
        artifacts = [f"xila-sdk-{target}" for target in SIX_TARGETS]
        with self.assertRaisesRegex(ValueError, "built but not listed \\['xtensa-esp32s3-elf'\\]"):
            check_sdk_artifacts(SIX_TARGETS[:-1], artifacts, "1")

    def test_rejects_a_target_without_an_artifact(self):
        artifacts = [f"xila-sdk-{target}" for target in THREE_TARGETS]
        with self.assertRaisesRegex(ValueError, "listed but not built \\['aarch64-unknown-linux-gnu'"):
            check_sdk_artifacts(SIX_TARGETS, artifacts, "1")

    @patch("assemble.github")
    def test_joins_artifact_pages(self, github):
        # gh prints the jq result of each page on its own lines.
        github.return_value = "xila-sdk-a-b\nxila-native-linux-x86_64\nxila-sdk-c-d"
        self.assertEqual(run_artifacts("xila-project/core", "1"), ["xila-sdk-a-b", "xila-native-linux-x86_64", "xila-sdk-c-d"])
        self.assertIn("--paginate", github.call_args.args)


class DownloadTests(unittest.TestCase):
    @patch("assemble.subprocess.run")
    def test_reports_the_reason_from_gh(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "", "no artifact matches any of the names")
        with self.assertRaisesRegex(ValueError, "xila-sdk-a-b from xila-project/core run 7: no artifact matches"):
            assemble.download("xila-project/core", "7", "xila-sdk-a-b", Path("unused"))


class CandidateDirectoryTests(unittest.TestCase):
    def run_main(self, output, collect):
        patches = {
            "check_versions": "0.1.0", "check_candidate": {"core": REVISION}, "git": REVISION,
            "verify_main_ancestry": None, "release_notes": "notes", "sdk_targets": ["a-b"],
            "find_run": "1", "run_artifacts": ["xila-sdk-a-b"],
        }
        with patch.dict("os.environ", {"XILA_RELEASE_TAG": "v0.1.0"}), \
                patch.object(assemble, "ROOT", output.parent.parent), \
                patch.object(assemble, "collect_downloads", side_effect=collect):
            for name, value in patches.items():
                patcher = patch.object(assemble, name, return_value=value)
                patcher.start()
                self.addCleanup(patcher.stop)
            assemble.main()

    def test_removes_a_new_candidate_after_a_failure(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "target/release-candidate"
            def collect(*arguments):
                (output / "partial").write_text("x")
                raise ValueError("download failed")
            with self.assertRaisesRegex(SystemExit, "download failed"):
                self.run_main(output, collect)
            self.assertFalse(output.exists())

    def test_keeps_an_existing_candidate(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "target/release-candidate"
            output.mkdir(parents=True)
            (output / "previous").write_text("x")
            with self.assertRaisesRegex(SystemExit, "already exists"):
                self.run_main(output, lambda *arguments: None)
            self.assertTrue((output / "previous").exists())
