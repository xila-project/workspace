"""Check inventory boundaries and Nanobom project naming without network access."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("inventory", Path(__file__).with_name("inventory.py"))
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


class InventoryTests(unittest.TestCase):
    def matrix(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitmodules"
            path.write_text(text)
            return inventory.repository_matrix(path)["include"]

    def test_workspace_is_included_without_initializing_submodules(self):
        projects = self.matrix('[submodule "core"]\npath = repositories/core\nurl = https://github.com/xila-project/core.git\n')
        self.assertEqual(projects, [
            {"repository": "xila-project/core", "project": "core"},
            {"repository": "xila-project/workspace", "project": "workspace"},
        ])

    def test_community_repository_uses_a_valid_nanobom_slug(self):
        projects = self.matrix('[submodule ".github"]\npath = repositories/.github\nurl = https://github.com/xila-project/.github.git\n')
        self.assertEqual(projects[0], {"repository": "xila-project/.github", "project": "github-community"})

    def test_community_mapping_cannot_overwrite_another_repository(self):
        with self.assertRaisesRegex(ValueError, "duplicate Nanobom project slugs"):
            self.matrix(
                '[submodule ".github"]\npath = repositories/.github\n'
                'url = https://github.com/xila-project/.github.git\n'
                '[submodule "github-community"]\npath = repositories/github-community\n'
                'url = https://github.com/xila-project/github-community.git\n'
            )

    def test_inventory_does_not_follow_external_remotes(self):
        with self.assertRaisesRegex(ValueError, "Unexpected inventory remote"):
            self.matrix('[submodule "core"]\npath = repositories/core\nurl = https://github.com/other/core.git\n')

    def test_inventory_rejects_paths_outside_repository_root(self):
        with self.assertRaisesRegex(ValueError, "Invalid inventory repository"):
            self.matrix('[submodule "core"]\npath = repositories/../other\nurl = https://github.com/xila-project/core.git\n')


if __name__ == "__main__":
    unittest.main()
