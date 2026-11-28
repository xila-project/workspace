import unittest
from pathlib import Path
from unittest.mock import patch

from assemble import sdk_targets


class SdkTargetsTests(unittest.TestCase):
    @patch("assemble.git")
    def test_reads_targets_from_the_pinned_commit(self, git):
        core = Path("repositories/core")
        revision = "a" * 40
        git.return_value = """
import build_dependency

TARGETS = {
    "x86_64-unknown-linux-gnu": {"flags": []},
    "xtensa-esp32s3-elf": build_dependency.options(),
}
"""
        self.assertEqual(
            sdk_targets(core, revision), ["x86_64-unknown-linux-gnu", "xtensa-esp32s3-elf"],
        )
        git.assert_called_once_with(core, "show", f"{revision}:tools/sdk/build.py")

    @patch("assemble.git")
    def test_rejects_missing_or_invalid_target_lists(self, git):
        for source in (
            "OTHER_TARGETS = {'x86_64-unknown-linux-gnu': {}}",
            "TARGETS = {}",
            "TARGETS = {target: {}}",
            "TARGETS = {'x86_64-unknown-linux-gnu': {}, 'x86_64-unknown-linux-gnu': {}}",
        ):
            with self.subTest(source=source):
                git.return_value = source
                with self.assertRaisesRegex(ValueError, "must define TARGETS"):
                    sdk_targets(Path("repositories/core"), "a" * 40)
