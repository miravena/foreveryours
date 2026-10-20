"""scripts/deploy_hf_space.py stages a Space that can boot (#11).

Offline: stages into a temp folder and inspects it. Nothing is uploaded and the
staged app is never imported (that would download the Whisper model).
"""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("deploy_hf_space", ROOT / "scripts" / "deploy_hf_space.py")
deploy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deploy)


def _local_modules() -> set[str]:
    """Top-level module names that resolve to this repo, not to an installed package."""
    names = {p.stem for p in ROOT.glob("*.py")}
    names |= {p.name for p in ROOT.iterdir() if (p / "__init__.py").is_file()}
    return names


def _imported_top_levels(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


class TestStagedSpace(unittest.TestCase):
    def _stage(self, hardware="cpu-basic"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name)
        deploy.stage(dest, "6.0.0", hardware)
        return dest

    def test_every_repo_module_the_space_imports_is_staged(self):
        # envload.py was missing once: app.py died with ModuleNotFoundError on boot.
        dest = self._stage()
        local = _local_modules()
        staged = {p.stem for p in dest.glob("*.py")} | {p.name for p in dest.iterdir() if p.is_dir()}
        for py in dest.rglob("*.py"):
            missing = (_imported_top_levels(py) & local) - staged
            self.assertFalse(missing, f"{py.relative_to(dest)} imports unstaged repo modules: {missing}")

    def test_never_stages_secrets_or_private_dirs(self):
        dest = self._stage()
        for name in (".env", "data", "out", "tests", "video", "docs"):
            self.assertFalse((dest / name).exists(), name)

    def test_zerogpu_adds_spaces_requirement_only_for_zerogpu(self):
        zero = (self._stage("zero-a10g") / "requirements.txt").read_text(encoding="utf-8")
        basic = (self._stage("cpu-basic") / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("\nspaces", zero)
        self.assertNotIn("\nspaces", basic)
        repo = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertEqual(basic, repo, "staging must not edit the repo requirements")

    def test_space_readme_pins_a_zerogpu_supported_python(self):
        readme = (self._stage("zero-a10g") / "README.md").read_text(encoding="utf-8")
        self.assertIn("app_file: app.py", readme)
        self.assertIn('python_version: "3.10.13"', readme)

    def test_app_registers_a_zerogpu_marker(self):
        # ZeroGPU refuses to boot without one @spaces.GPU function; app.py defines it
        # behind an optional import so local runs need no extra package.
        tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
        decorated = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and any("spaces.GPU" in ast.unparse(d) for d in n.decorator_list)
        ]
        self.assertTrue(decorated)



class TestHardwareRequest(unittest.TestCase):
    """main() asks for --hardware unless the Space is already on it or headed to it."""

    def _deploy(self, hardware, requested):
        from types import SimpleNamespace
        from unittest import mock
        api = mock.MagicMock()
        api.get_space_runtime.return_value = SimpleNamespace(hardware=hardware, requested_hardware=requested)
        argv = ["deploy", "me/demo", "--hardware", "zero-a10g", "--gradio-version", "6.0.0"]
        hub = SimpleNamespace(HfApi=lambda **kw: api)
        env = {"HF_TOKEN": "placeholder", "NEBIUS_API_KEY": ""}
        with mock.patch("sys.argv", argv), mock.patch.dict("sys.modules", {"huggingface_hub": hub}), \
                mock.patch.dict(deploy.os.environ, env, clear=True), \
                mock.patch.object(deploy, "stage", return_value=[]), \
                mock.patch("builtins.print"):
            self.assertEqual(deploy.main(), 0)
        self.assertEqual(api.create_repo.call_args.kwargs["space_hardware"], "zero-a10g")
        return api.request_space_hardware.call_args_list

    def test_pending_switch_away_is_overridden(self):
        self.assertTrue(self._deploy("zero-a10g", "cpu-basic"))

    def test_existing_space_on_other_hardware_is_moved(self):
        self.assertTrue(self._deploy("cpu-basic", None))

    def test_already_there_is_left_alone(self):
        self.assertFalse(self._deploy("zero-a10g", "zero-a10g"))
        self.assertFalse(self._deploy("zero-a10g", None))


if __name__ == "__main__":
    unittest.main()
