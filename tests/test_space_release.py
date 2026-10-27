"""The Space release flow is safe offline (#11): scripts/verify_space_sha.py and
.github/workflows/deploy-space.yml.

Nothing here touches the network: the verify script takes injected api/downloader/
client factories, and the workflow is read as YAML text.
"""
import importlib.util
import io
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-space.yml"
# scripts/smoke.sh runs the suite in a copy without .git; HEAD-sha tests need a checkout.
IN_GIT_CHECKOUT = (ROOT / ".git").exists()

_spec = importlib.util.spec_from_file_location("verify_space_sha", ROOT / "scripts" / "verify_space_sha.py")
vss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vss)

SHA = "0123456789abcdef0123456789abcdef01234567"
OLD = "fedcba9876543210fedcba9876543210fedcba98"
TOKEN = "hf_SENTINEL_never_printed_0000"


class FakeApi:
    def __init__(self, stages):
        self.stages = list(stages)

    def get_space_runtime(self, space_id):
        stage = self.stages.pop(0) if len(self.stages) > 1 else self.stages[0]
        return SimpleNamespace(stage=stage, hardware="zero-a10g", requested_hardware=None)


class FakeClient:
    def __init__(self, endpoints, build=SHA):
        self.endpoints = endpoints
        # Mirrors the Gradio config shape: the build line is a Markdown component value.
        self.config = {"components": [{"type": "markdown", "props": {"value": f"Build: `{build[:7]}`"}}]} \
            if build else {"components": []}

    def view_api(self, **kw):
        return {"named_endpoints": self.endpoints}


class TestVerify(unittest.TestCase):
    def _verify(self, deployed, expected=SHA, stages=("RUNNING",), **kw):
        log = io.StringIO()
        rc = vss.verify(
            "me/demo", expected,
            api_factory=lambda: FakeApi(stages),
            downloader=lambda space_id: deployed + "\n",
            client_factory=lambda space_id: FakeClient({"/run_demo_turn_streaming": {}}),
            sleep=lambda s: None, clock=_Clock(), log=lambda line: log.write(line + "\n"), **kw,
        )
        return rc, log.getvalue()

    def test_matching_sha_passes(self):
        rc, out = self._verify(SHA)
        self.assertEqual(rc, 0)
        self.assertIn("OK build 0123456", out)

    def test_older_sha_on_the_space_fails(self):
        rc, out = self._verify(OLD)
        self.assertEqual(rc, 1)
        self.assertIn("MISMATCH", out)

    def test_space_without_build_info_fails_with_a_hint(self):
        def missing(space_id):
            raise FileNotFoundError("BUILD_INFO")
        log = io.StringIO()
        rc = vss.verify("me/demo", SHA, downloader=missing, log=lambda l: log.write(l))
        self.assertEqual(rc, 1)
        self.assertIn("redeploy", log.getvalue())

    def test_wait_polls_until_running_then_verifies(self):
        rc, out = self._verify(SHA, stages=("BUILDING", "BUILDING", "APP_STARTING", "RUNNING"), wait_s=600)
        self.assertEqual(rc, 0)
        self.assertIn("stage BUILDING", out)
        self.assertIn("stage RUNNING", out)

    def test_wait_gives_up_on_build_error_or_timeout(self):
        with self.assertRaises(RuntimeError):
            self._verify(SHA, stages=("BUILDING", "BUILD_ERROR"), wait_s=600)
        with self.assertRaises(TimeoutError):
            self._verify(SHA, stages=("BUILDING",), wait_s=30)

    def test_smoke_waits_for_the_running_app_to_show_the_new_build(self):
        # BUILD_INFO in the repo already matches, but the old build is still serving,
        # then the Space restarts (connect fails), then the new build serves.
        served = [FakeClient({"/x": {}}, build=OLD), ConnectionError("503"), FakeClient({"/x": {}})]

        def factory(space_id):
            item = served.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        log = io.StringIO()
        rc = vss.verify("me/demo", SHA, wait_s=900, do_smoke=True, api_factory=lambda: FakeApi(["RUNNING"]),
                        downloader=lambda s: SHA, client_factory=factory, sleep=lambda s: None,
                        clock=_Clock(), log=lambda l: log.write(l + "\n"))
        self.assertEqual(rc, 0)
        self.assertEqual(served, [])
        self.assertIn("running app shows build fedcba9", log.getvalue())
        self.assertIn("running app shows build 0123456", log.getvalue())

    def test_smoke_fails_when_the_old_build_keeps_serving(self):
        with self.assertRaises(RuntimeError) as cm:
            vss.verify("me/demo", SHA, wait_s=60, do_smoke=True, api_factory=lambda: FakeApi(["RUNNING"]),
                       downloader=lambda s: SHA, client_factory=lambda s: FakeClient({"/x": {}}, build=OLD),
                       sleep=lambda s: None, clock=_Clock(), log=lambda l: None)
        self.assertIn("fedcba9", str(cm.exception))
        self.assertEqual(vss.main(["me/demo", "--sha", SHA, "--smoke"], downloader=lambda s: SHA,
                                  client_factory=lambda s: FakeClient({"/x": {}}, build=None)), 1)

    def test_default_client_uses_the_current_token_keyword(self):
        import inspect
        try:
            from gradio_client import Client
        except ImportError:  # pragma: no cover
            self.skipTest("gradio_client not installed")
        self.assertIn("token", inspect.signature(Client.__init__).parameters)
        self.assertIn("Client(space_id, token=_token()", (ROOT / "scripts" / "verify_space_sha.py").read_text())

    def test_smoke_needs_endpoints(self):
        rc, out = self._verify(SHA, do_smoke=True)
        self.assertEqual(rc, 0)
        self.assertIn("endpoints reachable", out)
        with self.assertRaises(RuntimeError):
            vss.verify("me/demo", SHA, do_smoke=True, downloader=lambda s: SHA,
                       client_factory=lambda s: FakeClient({}), log=lambda l: None)

    @unittest.skipUnless(IN_GIT_CHECKOUT, "needs a git checkout (no .git here, e.g. scripts/smoke.sh's copy)")
    def test_main_defaults_to_local_head_and_never_prints_the_token(self):
        from unittest import mock
        head = vss.local_head_sha()
        self.assertRegex(head, r"^[0-9a-f]{40}$")
        printed = io.StringIO()
        with mock.patch.dict(vss.os.environ, {"HF_TOKEN": TOKEN}), \
                mock.patch("sys.stdout", printed), mock.patch("sys.stderr", printed):
            rc = vss.main(["me/demo"], downloader=lambda s: head)
            self.assertEqual(rc, 0)
            rc = vss.main(["me/demo", "--sha", OLD], downloader=lambda s: head)
            self.assertEqual(rc, 1)
        self.assertNotIn(TOKEN, printed.getvalue())


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 20.0
        return self.t


class TestDeployWorkflow(unittest.TestCase):
    """The workflow never exposes the token to forks and never deploys unchecked."""

    @classmethod
    def setUpClass(cls):
        try:
            import yaml
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("PyYAML not installed")
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.wf = yaml.safe_load(cls.text)
        # YAML 1.1 reads the bare key `on` as boolean True.
        cls.on = cls.wf.get("on", cls.wf.get(True))

    def test_triggers_exclude_pull_request(self):
        self.assertEqual(set(self.on), {"push", "release", "workflow_dispatch"})
        self.assertEqual(self.on["push"]["branches"], ["main"])
        self.assertEqual(self.on["release"]["types"], ["published"])

    def test_docs_and_video_pushes_do_not_redeploy(self):
        ignored = self.on["push"]["paths-ignore"]
        for pattern in ("docs/**", "*.md", "**/*.md", "video/**"):
            self.assertIn(pattern, ignored)
        # Nothing the Space ships may be ignored, or a code fix would never reach judges.
        for pattern in ignored:
            for shipped in ("app.py", "webapp.py", "pipeline/", "safety/", "memory/",
                            "requirements.txt", "packages.txt", "samples/", "scripts/"):
                self.assertFalse(pattern.startswith(shipped) or pattern in ("**", "*"), pattern)
        self.assertNotIn("paths-ignore", self.on["release"] or {})

    def test_deploy_needs_tests_and_one_at_a_time(self):
        self.assertEqual(self.wf["jobs"]["deploy"]["needs"], "tests")
        self.assertIn("group", self.wf["concurrency"])
        self.assertFalse(self.wf["concurrency"]["cancel-in-progress"])
        self.assertEqual(self.wf["permissions"], {"contents": "read"})

    def test_token_comes_from_the_fy_space_secret_as_hf_token(self):
        self.assertEqual(self.wf["jobs"]["deploy"]["env"]["HF_TOKEN"], "${{ secrets.HF_TOKEN_FY_SPACE }}")
        self.assertNotIn("secrets.HF_TOKEN }}", self.text)
        self.assertNotIn("echo $HF_TOKEN", self.text)
        self.assertNotIn("${{ secrets.HF_TOKEN_FY_SPACE }}", self.text.replace(
            "HF_TOKEN: ${{ secrets.HF_TOKEN_FY_SPACE }}", ""), "the secret is referenced once, as env only")

    def test_hardware_is_one_setting_defaulting_to_cpu_basic(self):
        value = self.wf["env"]["SPACE_HARDWARE"]
        self.assertIn("vars.SPACE_HARDWARE", value)
        self.assertIn("'cpu-basic'", value)
        self.assertEqual(self.text.count("--hardware"), 1, "no second place chooses hardware")

    def test_steps_run_in_check_deploy_verify_order(self):
        names = [s.get("name", "") for s in self.wf["jobs"]["deploy"]["steps"]]
        order = [next(i for i, n in enumerate(names) if key in n)
                 for key in ("Decide", "Token check", "Deploy", "verify its sha", "Live judge")]
        self.assertEqual(order, sorted(order))
        steps = {s.get("name", ""): s for s in self.wf["jobs"]["deploy"]["steps"]}
        for name, step in steps.items():
            if name.startswith(("Deploy", "Wait", "Live")):
                self.assertIn("mode == 'deploy'", step["if"], name)
        self.assertIn('--hardware "$SPACE_HARDWARE"', steps["Deploy ${{ github.sha }} to the Space"]["run"])
        self.assertNotIn("zero-a10g", steps["Deploy ${{ github.sha }} to the Space"]["run"])
        self.assertIn("--max-calls", steps["Live judge check suite (small call cap)"]["run"])
        # Every deploy runs the live suite, releases included (HOW_TO_WORK_HERE.md).
        self.assertNotIn("event_name", steps["Live judge check suite (small call cap)"]["if"])


if __name__ == "__main__":
    unittest.main()
