import tempfile
import unittest
from pathlib import Path

from validate import check_versions, check_lockfile


class ReleaseValidationTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.repositories = Path(temporary_directory.name)
        for repository in ("core", "platforms", "tools"):
            manifest = self.repositories / repository / "Cargo.toml"
            manifest.parent.mkdir()
            manifest.write_text('[workspace.package]\nversion = "0.1.0"\n')
        self.version_manifest = self.repositories / "core/libraries/version/Cargo.toml"

    def test_aligned_versions_with_matching_tag(self):
        self.version_manifest.parent.mkdir(parents=True)
        self.version_manifest.write_text("[package]\nversion.workspace = true\n")
        self.assertEqual(check_versions(self.repositories, "v0.1.0"), "0.1.0")

    def test_rejects_platforms_patch_drift(self):
        (self.repositories / "platforms/Cargo.toml").write_text(
            '[workspace.package]\nversion = "0.1.1"\n'
        )
        with self.assertRaisesRegex(ValueError, "platforms"):
            check_versions(self.repositories)

    def test_rejects_independently_versioned_running_crate(self):
        self.version_manifest.parent.mkdir(parents=True)
        self.version_manifest.write_text('[package]\nversion = "0.1.0"\n')
        with self.assertRaisesRegex(ValueError, "xila-version"):
            check_versions(self.repositories)

    def test_release_requires_running_crate(self):
        with self.assertRaisesRegex(ValueError, "xila-version"):
            check_versions(self.repositories, "v0.1.0")

    def test_rejects_tag_drift(self):
        self.version_manifest.parent.mkdir(parents=True)
        self.version_manifest.write_text("[package]\nversion.workspace = true\n")
        with self.assertRaisesRegex(ValueError, "v0.1.0"):
            check_versions(self.repositories, "v0.1.1")

    def test_rejects_lockfile_revision_outside_candidate(self):
        lockfile = self.repositories / "tools/Cargo.lock"
        revision = "a" * 40
        lockfile.write_text(
            f'[[package]]\nname = "xila"\n'
            f'source = "git+https://github.com/xila-project/core?branch=main#{revision}"\n'
        )
        check_lockfile(lockfile, {"core": revision})
        with self.assertRaisesRegex(ValueError, "tools.*core"):
            check_lockfile(lockfile, {"core": "b" * 40})

    def test_rejects_implicit_git_branch(self):
        lockfile = self.repositories / "tools/Cargo.lock"
        revision = "a" * 40
        lockfile.write_text(
            f'[[package]]\nname = "xila"\n'
            f'source = "git+https://github.com/xila-project/core#{revision}"\n'
        )
        with self.assertRaisesRegex(ValueError, "must track core main"):
            check_lockfile(lockfile, {"core": revision})
