import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from publish import publish


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.revisions = dict.fromkeys(("core", "platforms", "tools", "workspace"), "f" * 40)
        self.files = [Path("firmware.bin")]
        for function in ("release_for", "tag_revision", "github", "verify_assets", "create_tag"):
            patcher = patch(f"publish.{function}")
            setattr(self, function, patcher.start())
            self.addCleanup(patcher.stop)
        self.release_for.return_value = {"draft": True, "target_commitish": "f" * 40}
        self.tag_revision.return_value = None

    def test_failed_upload_creates_no_tags(self):
        self.github.side_effect = subprocess.CalledProcessError(1, ["gh", "release", "upload"])
        with self.assertRaises(subprocess.CalledProcessError):
            publish("v0.1.0", self.revisions, self.files)
        self.create_tag.assert_not_called()

    def test_published_release_is_left_untouched(self):
        self.release_for.return_value["draft"] = False
        with self.assertRaisesRegex(ValueError, "already published"):
            publish("v0.1.0", self.revisions, self.files)
        self.github.assert_not_called()
        self.create_tag.assert_not_called()

    def test_tags_follow_verified_upload(self):
        steps = []
        self.github.side_effect = lambda *arguments: steps.append(arguments[1])
        self.verify_assets.side_effect = lambda *_: steps.append("verify")
        self.create_tag.side_effect = lambda *_: steps.append("tag")
        publish("v0.1.0", self.revisions, self.files)
        self.assertEqual(steps, ["upload", "verify", "tag", "tag", "tag", "tag", "edit"])
