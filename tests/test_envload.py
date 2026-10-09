import os
import tempfile
import unittest
from pathlib import Path

from envload import load_repo_env


class LoadRepoEnvTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("FY_ENVLOAD_PROBE", None)
        self.addCleanup(os.environ.pop, "FY_ENVLOAD_PROBE", None)

    def test_parent_dotenv_is_not_picked_up(self):
        with tempfile.TemporaryDirectory() as parent:
            (Path(parent) / ".env").write_text("FY_ENVLOAD_PROBE=from-parent\n")
            child = Path(parent) / "worktree"
            child.mkdir()
            self.assertFalse(load_repo_env(child))
            self.assertNotIn("FY_ENVLOAD_PROBE", os.environ)

    def test_own_dotenv_is_loaded(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / ".env").write_text("FY_ENVLOAD_PROBE=own\n")
            self.assertTrue(load_repo_env(root))
            self.assertEqual(os.environ["FY_ENVLOAD_PROBE"], "own")

    def test_existing_environment_is_not_overridden(self):
        os.environ["FY_ENVLOAD_PROBE"] = "already"
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / ".env").write_text("FY_ENVLOAD_PROBE=file\n")
            load_repo_env(root)
        self.assertEqual(os.environ["FY_ENVLOAD_PROBE"], "already")


if __name__ == "__main__":
    unittest.main()
