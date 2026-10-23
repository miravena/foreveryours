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
# scripts/smoke.sh runs the suite in a copy without .git; HEAD-sha tests need a checkout.
IN_GIT_CHECKOUT = (ROOT / ".git").exists()

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


class TestStagedVoice(unittest.TestCase):
    """#207: the Piper voice ships with the Space only as the complete default pair."""

    def _stage(self, voice_files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        voice_dir = Path(tmp.name) / "voice"
        voice_dir.mkdir()
        for name in voice_files:
            (voice_dir / name).write_bytes(b"x")
        dest = Path(tmp.name) / "dest"
        dest.mkdir()
        return dest, deploy.stage(dest, "6.0.0", "cpu-basic", "f" * 40, voice_dir=voice_dir)

    def test_complete_voice_pair_is_staged(self):
        dest, staged = self._stage(deploy.VOICE_FILES)
        for name in deploy.VOICE_FILES:
            self.assertIn(str(Path(deploy.VOICE_DIR) / name), staged)
            self.assertTrue((dest / deploy.VOICE_DIR / name).is_file())

    def test_half_a_voice_or_another_voice_is_not_staged(self):
        other = ["en_US-lessac-medium.onnx", "en_US-lessac-medium.onnx.json"]
        dest, staged = self._stage(deploy.VOICE_FILES[:1] + other)
        self.assertFalse((dest / "models").exists())
        self.assertFalse([s for s in staged if s.startswith("models")])

    def test_staged_voice_is_the_one_speak_defaults_to(self):
        speak_src = (ROOT / "pipeline" / "speak.py").read_text(encoding="utf-8")
        self.assertIn(f'"{deploy.VOICE_DIR}/{deploy.VOICE_FILES[0]}"', speak_src)


class TestStagedSpace(unittest.TestCase):
    def _stage(self, hardware="cpu-basic", build_sha="f" * 40):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name)
        deploy.stage(dest, "6.0.0", hardware, build_sha)
        return dest

    @unittest.skipUnless(IN_GIT_CHECKOUT, "needs a git checkout (no .git here, e.g. scripts/smoke.sh's copy)")
    def test_build_info_holds_the_full_head_sha(self):
        # Default (no sha passed) records HEAD of this checkout; webapp shows its first 7.
        dest = self._stage(build_sha=None)
        sha = (dest / "BUILD_INFO").read_text(encoding="utf-8")
        self.assertEqual(sha, deploy.git_head_sha() + "\n")
        self.assertRegex(sha.strip(), r"^[0-9a-f]{40}$")
        self.assertIn("BUILD_INFO", deploy.stage(Path(tempfile.mkdtemp()), "6.0.0", "cpu-basic", "a" * 40))

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

    SHA = "0123456789abcdef0123456789abcdef01234567"
    TOKEN = "hf_SENTINEL_never_printed_0000"

    def _run(self, hardware="zero-a10g", requested=None, dirty=False, argv_extra=(), env=None):
        from types import SimpleNamespace
        from unittest import mock
        api = mock.MagicMock()
        api.get_space_runtime.return_value = SimpleNamespace(hardware=hardware, requested_hardware=requested)
        argv = ["deploy", "me/demo", "--hardware", "zero-a10g", "--gradio-version", "6.0.0", *argv_extra]
        hub = SimpleNamespace(HfApi=lambda **kw: api)
        if env is None:
            env = {"HF_TOKEN": self.TOKEN, "NEBIUS_API_KEY": ""}
        printed = []
        with mock.patch("sys.argv", argv), mock.patch.dict("sys.modules", {"huggingface_hub": hub}), \
                mock.patch.dict(deploy.os.environ, env, clear=True), \
                mock.patch.object(deploy, "stage", return_value=[]), \
                mock.patch.object(deploy, "git_head_sha", return_value=self.SHA), \
                mock.patch.object(deploy, "git_tree_is_dirty", return_value=dirty), \
                mock.patch("builtins.print", side_effect=lambda *a, **k: printed.append(" ".join(map(str, a)))):
            rc = deploy.main()
        return rc, api, "\n".join(printed)

    def _deploy(self, hardware, requested):
        rc, api, _ = self._run(hardware, requested)
        self.assertEqual(rc, 0)
        self.assertEqual(api.create_repo.call_args.kwargs["space_hardware"], "zero-a10g")
        return api.request_space_hardware.call_args_list

    def test_dirty_tree_is_refused_unless_dry_run(self):
        rc, api, out = self._run(dirty=True)
        self.assertEqual(rc, 2)
        self.assertIn("dirty", out.lower())
        api.upload_folder.assert_not_called()
        rc, api, _ = self._run(dirty=True, argv_extra=("--dry-run",))
        self.assertEqual(rc, 0)
        api.upload_folder.assert_not_called()

    def test_build_sha_variable_set_and_token_never_printed(self):
        rc, api, out = self._run()
        self.assertEqual(rc, 0)
        api.add_space_variable.assert_any_call("me/demo", "BUILD_SHA", self.SHA)
        self.assertIn(self.SHA[:7], out)
        self.assertNotIn(self.TOKEN, out)

    def test_missing_hf_token_refuses_before_any_hub_call(self):
        # Negative control for the deploy guard: with HF_TOKEN unset the script must
        # exit non-zero naming HF_TOKEN, touch nothing on the Hub, and print no secret.
        # Removing the `if not token` guard makes this fail (HfApi runs, rc becomes 0).
        nebius = "nebius_SENTINEL_never_printed_1111"
        for unset in ({"NEBIUS_API_KEY": nebius}, {"HF_TOKEN": "", "NEBIUS_API_KEY": nebius}):
            with self.subTest(env=sorted(unset)):
                rc, api, out = self._run(env=unset)
                self.assertNotEqual(rc, 0)
                self.assertIn("HF_TOKEN", out)
                self.assertNotIn(nebius, out)
                self.assertNotIn(self.TOKEN, out)
                api.create_repo.assert_not_called()
                api.add_space_secret.assert_not_called()
                api.upload_folder.assert_not_called()

    def test_workflow_skips_with_a_notice_when_the_secret_is_missing(self):
        wf = (ROOT / ".github" / "workflows" / "deploy-space.yml").read_text()
        self.assertIn("HF_TOKEN: ${{ secrets.HF_TOKEN_FY_SPACE }}", wf)
        self.assertIn('if [ -z "$HF_TOKEN" ]; then', wf)
        self.assertIn("::notice::Repo secret HF_TOKEN_FY_SPACE is not set; skipping the Space deploy.", wf)

    def test_pending_switch_away_is_overridden(self):
        self.assertTrue(self._deploy("zero-a10g", "cpu-basic"))

    def test_existing_space_on_other_hardware_is_moved(self):
        self.assertTrue(self._deploy("cpu-basic", None))

    def test_already_there_is_left_alone(self):
        self.assertFalse(self._deploy("zero-a10g", "zero-a10g"))
        self.assertFalse(self._deploy("zero-a10g", None))


if __name__ == "__main__":
    unittest.main()
