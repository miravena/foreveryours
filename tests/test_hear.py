import os
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pipeline import hear


class TestHearFallback(unittest.TestCase):
    def test_hosted_asr_failure_falls_back_to_local_whisper(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "input.wav"
            audio.write_bytes(b"audio")
            client = SimpleNamespace(
                audio=SimpleNamespace(
                    transcriptions=SimpleNamespace(
                        create=unittest.mock.Mock(side_effect=ConnectionError("offline"))
                    )
                )
            )
            with patch.dict(os.environ, {"ASR_BACKEND": "nebius", "NEBIUS_API_KEY": "configured"}), \
                    patch("pipeline.nebius_client.get_client", return_value=client), \
                    patch.object(hear, "_transcribe_local", return_value=("I fell down", {"wpm": 0.0, "avg_pause_s": 0.0})) as local:
                result = hear.transcribe(audio, return_metrics=True)

            self.assertEqual(result[0], "I fell down")
            local.assert_called_once_with(audio, True)

    def test_hosted_and_local_fail_with_safe_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "input.wav"
            audio.write_bytes(b"audio")
            client = SimpleNamespace(
                audio=SimpleNamespace(
                    transcriptions=SimpleNamespace(
                        create=unittest.mock.Mock(side_effect=TimeoutError)
                    )
                )
            )
            with patch.dict(os.environ, {"ASR_BACKEND": "nebius"}), \
                    patch("pipeline.nebius_client.get_client", return_value=client), \
                    patch.object(hear, "_transcribe_local", side_effect=ImportError("missing")):
                with self.assertRaisesRegex(RuntimeError, "hosted ASR and local Whisper fallback both failed"):
                    hear.transcribe(audio)

    def test_probe_duration_real_wav_and_garbage(self):
        # probe_duration reads a real WAV's length and refuses garbage.
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "two.wav"
            with wave.open(str(wav), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(16000)
                w.writeframes(b"\0\0" * 32000)
            self.assertAlmostEqual(hear.probe_duration(wav), 2.0, delta=0.1)
            garbage = Path(tmp) / "garbage.wav"
            garbage.write_bytes(b"not audio at all" * 10)
            with self.assertRaises(hear.AudioInputError):
                hear.probe_duration(garbage)


if __name__ == "__main__":
    unittest.main()
