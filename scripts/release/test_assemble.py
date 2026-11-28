import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from assemble import check_sdk_artifacts, sdk_targets

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
        with self.assertRaisesRegex(ValueError, "not in TARGETS \\['xtensa-esp32s3-elf'\\]"):
            check_sdk_artifacts(SIX_TARGETS[:-1], artifacts, "1")

    def test_rejects_a_target_without_an_artifact(self):
        artifacts = [f"xila-sdk-{target}" for target in THREE_TARGETS]
        with self.assertRaisesRegex(ValueError, "missing \\['aarch64-unknown-linux-gnu'"):
            check_sdk_artifacts(SIX_TARGETS, artifacts, "1")
