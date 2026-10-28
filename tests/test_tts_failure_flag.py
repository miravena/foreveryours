"""A fast-path emergency always leaves a caregiver flag, even
when speech synthesis returns nothing, raises, or hangs.

PreChangeRegressionTests are the negative control: each one fails (as an
assertion failure, never an error) on pre-change commit a12ec07 and passes
after the fix. HappyPathTests passes on both versions.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from caregiver import CaregiverFlags
from memory.store import MemoryStore
from pipeline import speak
from pipeline.orchestrator import run_turn
from safety import fastpath

FALL_PHRASE = "I fell down earlier and I'm scared"


class _TurnCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name) / "data"
        self.audio_dir = Path(self.temp_dir.name) / "audio"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.profile_id = "test_dad"
        self.store = MemoryStore(self.profile_id, self.data_dir)
        self.flags = CaregiverFlags(self.profile_id, self.data_dir)
        # THINK must raise NebiusNotConfigured so the fast-path turn completes offline.
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("NEBIUS_API_KEY", None)
        self.fast = fastpath.check(FALL_PHRASE)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run(self):
        try:
            return run_turn(
                transcript=FALL_PHRASE,
                memory_store=self.store,
                flags=self.flags,
                audio_out_dir=self.audio_dir,
                caregiver_name="Sarah",
            )
        except Exception as exc:
            self.fail(f"run_turn raised {exc!r}")

    def _assert_one_undisclosed_flag(self, result):
        self.assertTrue(self.fast.triggered)
        items = self.flags.all()
        self.assertEqual(len(items), 1, "fast-path flag must be recorded even without audio")
        self.assertFalse(items[0].disclosed_to_senior)
        self.assertTrue(items[0].text.startswith(self.fast.caregiver_flag))
        self.assertIn(self.fast.immediate_reply, result.reply_text)
        self.assertEqual(result.audio_paths, [])


class PreChangeRegressionTests(_TurnCase):
    @patch("pipeline.orchestrator._speak_turn", return_value=("Reply", [], 0.5))
    def test_flag_recorded_undisclosed_when_tts_returns_no_audio(self, _mock_speak):
        result = self._run()
        self._assert_one_undisclosed_flag(result)

    @patch("pipeline.orchestrator._speak_turn", side_effect=RuntimeError("piper hung"))
    def test_flag_recorded_undisclosed_when_tts_raises(self, _mock_speak):
        result = self._run()
        self._assert_one_undisclosed_flag(result)

    def test_every_subprocess_tier_carries_timeout(self):
        model = Path(self.temp_dir.name) / "voice.onnx"
        model.write_bytes(b"fake-onnx")
        model.with_suffix(".onnx.json").write_text("{}")
        out = self.audio_dir / "x.wav"
        piper_env = {"TTS_PIPER_MODEL": str(model), "TTS_BACKEND": "auto"}

        # Piper branch.
        mock_run = MagicMock()
        with patch.dict(os.environ, piper_env, clear=False), \
             patch("pipeline.speak._get_piper_cli", return_value="/usr/bin/piper"), \
             patch("pipeline.speak.subprocess.run", mock_run):
            speak._synthesize_file("Hello.", out, None)
        self.assertEqual(mock_run.call_args.args[0][0], "/usr/bin/piper")
        self.assertIn("timeout", mock_run.call_args.kwargs)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], speak.TTS_TIMEOUT_S)
        self.assertGreater(speak.TTS_TIMEOUT_S, 0)

        # espeak branch.
        mock_run = MagicMock()
        with patch("sys.platform", "linux"), \
             patch("pipeline.speak._get_piper_cli", return_value=None), \
             patch("pipeline.speak._get_espeak_cli", return_value="/usr/bin/espeak-ng"), \
             patch("pipeline.speak.subprocess.run", mock_run):
            speak._synthesize_file("Hello.", out, None)
        self.assertEqual(mock_run.call_args.args[0][0], "/usr/bin/espeak-ng")
        self.assertIn("timeout", mock_run.call_args.kwargs)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], speak.TTS_TIMEOUT_S)

        # Windows PowerShell branch.
        mock_run = MagicMock()
        with patch("sys.platform", "win32"), \
             patch("pipeline.speak._get_piper_cli", return_value=None), \
             patch("pipeline.speak.subprocess.run", mock_run):
            speak._synthesize_file("Hello.", out, None)
        self.assertEqual(mock_run.call_args.args[0][0], "powershell")
        self.assertIn("timeout", mock_run.call_args.kwargs)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], speak.TTS_TIMEOUT_S)

        # A hung Piper falls through to espeak.
        def piper_hangs(argv, *args, **kwargs):
            if argv[0] == "/usr/bin/piper":
                raise subprocess.TimeoutExpired(cmd=argv, timeout=1)
            return None

        mock_run = MagicMock(side_effect=piper_hangs)
        with patch.dict(os.environ, piper_env, clear=False), \
             patch("sys.platform", "linux"), \
             patch("pipeline.speak._get_piper_cli", return_value="/usr/bin/piper"), \
             patch("pipeline.speak._get_espeak_cli", return_value="/usr/bin/espeak-ng"), \
             patch("pipeline.speak.subprocess.run", mock_run):
            try:
                speak._synthesize_file("Hello.", out, None)
            except subprocess.TimeoutExpired as exc:
                self.fail(f"Piper TimeoutExpired escaped instead of falling through: {exc!r}")
        self.assertEqual(mock_run.call_count, 2)
        self.assertEqual(mock_run.call_args_list[1].args[0][0], "/usr/bin/espeak-ng")

    def test_run_turn_survives_every_tier_timing_out(self):
        model = Path(self.temp_dir.name) / "voice.onnx"
        model.write_bytes(b"fake-onnx")
        model.with_suffix(".onnx.json").write_text("{}")
        with patch.dict(os.environ, {"TTS_BACKEND": "auto"}, clear=False), \
             patch("sys.platform", "linux"), \
             patch("pipeline.speak.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="tts", timeout=1)), \
             patch("pipeline.speak._get_tts_engine", return_value=None), \
             patch("pipeline.speak._get_piper_cli", return_value="/usr/bin/piper"), \
             patch("pipeline.speak._get_piper_model", return_value=model), \
             patch("pipeline.speak._get_espeak_cli", return_value="/usr/bin/espeak-ng"):
            result = self._run()
        self._assert_one_undisclosed_flag(result)


class HappyPathTests(_TurnCase):
    @patch("pipeline.orchestrator._speak_turn", return_value=("Reply", [Path("reply.wav")], 0.5))
    def test_flag_disclosed_when_audio_exists(self, _mock_speak):
        self._run()
        items = self.flags.all()
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].disclosed_to_senior)


if __name__ == "__main__":
    unittest.main()
