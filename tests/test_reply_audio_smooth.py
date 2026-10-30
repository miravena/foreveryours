"""The reply player gets each sentence as short slices and a silent nudge, so the
browser has the whole sentence early and never waits for the end of the turn (#207).

Why (measured in a real browser): Gradio encodes streamed audio with one ffmpeg
process and the browser re-reads the HLS playlist about once per target duration
(the longest segment, rounded up). A whole-sentence chunk left the tail of the
sentence inside the encoder until the turn's generator ended, seconds later, and a
long first segment made the player look for more only every two seconds: a silence
of 1.2-2.4 s in the middle of a word. These tests pin the server side of the fix; the
before/after browser capture is in the pull request, since a unittest cannot play audio.
"""
from __future__ import annotations

import io
import tempfile
import time
import unittest
import wave
from pathlib import Path

import gradio as gr

import webapp
from tests.test_late_disclosure import LateDisclosureHarness

RATE = 22050


def _write_wav(path: Path, seconds: float, rate: int = RATE, sampwidth: int = 2) -> bytes:
    pcm = b"".join((1000 + i % 50).to_bytes(2, "little", signed=True) for i in range(int(rate * seconds)))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(sampwidth)
        w.setframerate(rate)
        w.writeframes(pcm if sampwidth == 2 else pcm[::2])
    return pcm


def _pcm(wav_bytes: bytes) -> tuple[int, bytes]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        return w.getframerate(), w.readframes(w.getnframes())


class TestHelpers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_a_sentence_is_cut_into_short_slices_that_rejoin_exactly(self):
        path = Path(self.tmp.name) / "s.wav"
        pcm = _write_wav(path, 1.0)
        parts, rate = webapp._reply_audio_parts(path)
        self.assertEqual(rate, RATE)
        self.assertEqual(len(parts), 3)  # 0.4 + 0.4 + 0.2 s
        joined = b""
        for part in parts:
            self.assertIsInstance(part, bytes)
            r, frames = _pcm(part)
            self.assertEqual(r, RATE)
            self.assertLessEqual(len(frames) / 2 / RATE, webapp._SLICE_S + 1e-6)
            joined += frames
        self.assertEqual(joined, pcm, "the slices must rejoin to the original samples")

    def test_a_short_sentence_is_one_slice(self):
        path = Path(self.tmp.name) / "s.wav"
        pcm = _write_wav(path, 0.3)
        parts, _ = webapp._reply_audio_parts(path)
        self.assertEqual(len(parts), 1)
        self.assertEqual(_pcm(parts[0])[1], pcm)

    def test_anything_that_is_not_16_bit_wav_goes_out_whole_as_the_path(self):
        bad = Path(self.tmp.name) / "bad.wav"
        bad.write_bytes(b"RIFF")
        self.assertEqual(webapp._reply_audio_parts(bad), ([str(bad)], None))
        missing = Path(self.tmp.name) / "none.wav"
        self.assertEqual(webapp._reply_audio_parts(missing), ([str(missing)], None))
        eight = Path(self.tmp.name) / "eight.wav"
        _write_wav(eight, 0.2, sampwidth=1)
        self.assertEqual(webapp._reply_audio_parts(eight), ([str(eight)], None))

    def test_the_nudge_is_a_millisecond_of_silence_at_the_stream_rate(self):
        rate, frames = _pcm(webapp._pump_chunk(RATE))
        self.assertEqual(rate, RATE)
        self.assertLessEqual(len(frames) / 2 / RATE, 0.0011)
        self.assertEqual(set(frames), {0})


class TestStreamedTurn(LateDisclosureHarness):
    """The real `_run_demo_turn_streaming_impl`, fake TTS writing real WAV sentences."""

    def setUp(self):
        super().setUp()
        self.written: list[bytes] = []

        def fake_speak(sentences, out_dir):
            for s in sentences:
                self._n += 1
                out_dir.mkdir(parents=True, exist_ok=True)
                p = Path(out_dir) / f"chunk_{self._n}.wav"
                self.written.append(_write_wav(p, 1.0))
                self.spoken.append((s, p))
                yield s, p

        def slow_audit(*_a, **_k):
            time.sleep(0.7)  # the background AUDIT thread the drain loop waits for
            return "SAFE", ""

        # The harness already patched these three names (and restores them in its
        # tearDown): reprogram those mocks rather than patching the same names twice,
        # which would restore the harness's mocks, not the real functions, afterwards.
        from pipeline import audit, speak, think

        speak.speak_sentences.side_effect = fake_speak
        audit.audit_reply.side_effect = slow_audit
        think.extract_new_memory.return_value = None

    @staticmethod
    def _audio_only(out) -> bool:
        return all(o == gr.skip() for i, o in enumerate(out) if i != 1)

    def run_turn(self):
        outs = list(self.start())
        webapp._join_previous_turn(next(o[5] for o in outs if isinstance(o[5], str)))
        return outs

    def test_sentence_audio_arrives_as_slices_and_rejoins(self):
        outs = self.run_turn()
        audio = [o[1] for o in outs if isinstance(o[1], bytes)]
        # three slices for the one 1.0 s sentence, then silent nudges only
        sentence_slices = [a for a in audio if len(_pcm(a)[1]) > 2 * 100]
        self.assertEqual(len(sentence_slices), 3, [len(_pcm(a)[1]) for a in audio])
        self.assertEqual(b"".join(_pcm(a)[1] for a in sentence_slices), self.written[0])
        first = next(o for o in outs if isinstance(o[1], bytes))
        self.assertIn("Companion replied", first[0], "the text rides the first slice")
        rest = [o for o in outs if isinstance(o[1], bytes) and o is not first]
        self.assertTrue(rest)
        for o in rest:
            self.assertTrue(self._audio_only(o), "later slices carry audio only")

    def test_silent_nudges_follow_the_sentence_while_the_audit_thread_is_awaited(self):
        outs = self.run_turn()
        done_idx = next(i for i, o in enumerate(outs) if self.is_done_final(o))
        nudges = [o for o in outs[done_idx + 1:] if isinstance(o[1], bytes)]
        self.assertGreaterEqual(len(nudges), 2, "no nudge while the drain loop waited")
        self.assertLessEqual(len(nudges), webapp._PUMP_MAX)
        for o in nudges:
            self.assertTrue(self._audio_only(o))
            rate, frames = _pcm(o[1])
            self.assertEqual(rate, RATE)
            self.assertEqual(set(frames), {0})
        self.assertIsNone(outs[done_idx][1], "the DONE-final yield still carries no audio")

    def test_no_audio_nudge_before_any_sentence_was_heard(self):
        outs = self.run_turn()
        first_audio = next(i for i, o in enumerate(outs) if isinstance(o[1], bytes))
        for o in outs[:first_audio]:
            self.assertFalse(isinstance(o[1], bytes))


if __name__ == "__main__":
    unittest.main()
