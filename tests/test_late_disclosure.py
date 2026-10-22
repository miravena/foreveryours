"""Office #23231: a disclosure spoken by the background AUDIT / lifestyle-
extraction thread after the streaming turn's DONE is recorded as told only
when the browser's generator actually dequeued and yielded its audio chunk.

The real `_speak_turn` / `_speak_disclosure` run here (only
`speak.speak_sentences` is faked), so their acknowledgement logic is under
test, and `audit.audit_reply` blocks on `release_background` so nothing the
background thread discloses can happen before a test allows it.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import webapp
from caregiver import CaregiverFlags
from memory.store import MemoryStore
from safety.fastpath import FastPathResult


class LateDisclosureHarness(unittest.TestCase):
    """Shared isolation + patches (TestProactiveButtons.setUp pattern)."""

    extract_result = "LIFESTYLE: SLEEP | Slept poorly"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp_dir.name)
        self.release_background = threading.Event()
        self.spoken: list[tuple[str, Path]] = []
        self._n = 0

        def fake_speak_sentences(sentences, out_dir):
            for s in sentences:
                self._n += 1
                out_dir.mkdir(parents=True, exist_ok=True)
                p = Path(out_dir) / f"chunk_{self._n}.wav"
                p.write_bytes(b"RIFF")
                self.spoken.append((s, p))
                yield s, p

        def held_audit(*_a, **_k):
            self.release_background.wait(timeout=30)
            return "DISTRESS", "possible distress"

        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", root / "sessions"),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", root / "data"),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
            patch("pipeline.orchestrator.fastpath.check",
                  return_value=FastPathResult(False, "none", None, None, None)),
            patch("pipeline.orchestrator.think.stream_reply", return_value=["Reply"]),
            patch("pipeline.orchestrator.speak.speak_sentences", side_effect=fake_speak_sentences),
            patch("pipeline.orchestrator.think.extract_new_memory", return_value=self.extract_result),
            patch("pipeline.orchestrator.audit.audit_reply", side_effect=held_audit),
            # Make the audio value of each yield identify its newest chunk.
            patch.object(webapp, "_combine_audio_chunks",
                         side_effect=lambda paths, _d: paths[-1] if paths else None),
        ]
        for p in self.patches:
            p.start()
        webapp._request_log.clear()

    def tearDown(self):
        self.release_background.set()
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    # -- helpers -----------------------------------------------------------
    def start(self):
        self.history: list[dict] = []
        return webapp.run_demo_turn_streaming(None, "I feel a bit low today", self.history, None)

    def settle(self, session_id: str) -> None:
        """Let the background thread finish and wait for it."""
        self.release_background.set()
        snapshot = list(webapp._bg_threads.get(session_id, []))
        webapp._join_previous_turn(session_id)
        for t in snapshot:
            t.join(timeout=10)
            self.assertFalse(t.is_alive(), "background thread did not finish")

    def stores(self, session_id: str):
        data_dir, _ = webapp._session_dirs(session_id)
        flags = CaregiverFlags(webapp.DEFAULT_PROFILE_ID, data_dir).all()
        lifestyle = [i for i in MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir).all()
                     if i.scope == "lifestyle"]
        return flags, lifestyle

    def disclosure_paths(self) -> list[str]:
        return [str(p) for s, p in self.spoken if s != "Reply"]

    def is_done_final(self, out) -> bool:
        return isinstance(out[2], list) and len(out[2]) > len(self.history)


class TestLateDisclosure(LateDisclosureHarness):

    def test_disclosure_after_consumer_closed_is_not_attested(self):
        # (a) The generator is exhausted before the background thread may
        # disclose anything; whatever it says afterwards reaches nobody.
        with patch.object(webapp, "_BG_JOIN_TIMEOUT_S", 0.5):
            gen = self.start()
            outs = []
            for out in gen:
                outs.append(out)
            sid = outs[-1][5]
            self.settle(sid)
        flags, lifestyle = self.stores(sid)
        self.assertTrue(flags, "audit DISTRESS should have recorded a flag")
        self.assertIs(flags[-1].disclosed_to_senior, False)
        self.assertEqual(lifestyle, [])

    def test_disclosure_after_done_is_streamed_and_attested(self):
        # (b) Released at the DONE-final yield: the disclosure provably
        # happens after DONE and is delivered by the drain.
        gen = self.start()
        outs, done_idx = [], None
        for out in gen:
            outs.append(out)
            if done_idx is None and self.is_done_final(out):
                done_idx = len(outs) - 1
                self.release_background.set()
        self.assertIsNotNone(done_idx, "no DONE-final yield observed")
        sid = outs[-1][5]
        self.settle(sid)

        late = outs[done_idx + 1:]
        disclosures = self.disclosure_paths()
        self.assertEqual(len(disclosures), 2, self.spoken)  # audit + lifestyle lines
        # Exactly one DONE-final yield, then one yield per late chunk, then
        # one panel-only refresh once the background thread has finished.
        self.assertEqual(len(late), 3, [o[1] for o in late])
        self.assertEqual(late[2][1], late[1][1])  # refresh carries the same audio
        late_audio = [o[1] for o in late if o[1] is not None]
        self.assertIn(disclosures[0], late_audio)
        self.assertIn(disclosures[1], late_audio)
        for o in late:  # additive: same final history, never a regression
            self.assertEqual(o[2], outs[done_idx][2])
        # The last yield (the panel-only refresh) was rendered after the
        # flag AND the lifestyle note were persisted.
        self.assertIn("Dad was told", outs[-1][3])
        self.assertIn("Slept poorly", outs[-1][3])

        flags, lifestyle = self.stores(sid)
        self.assertIs(flags[-1].disclosed_to_senior, True)
        self.assertEqual(len(lifestyle), 1)
        self.assertTrue(lifestyle[0].disclosure_attested)

    def test_drain_is_bounded_and_late_disclosure_is_refused(self):
        # (c) The background thread is held past the drain timeout.
        with patch.object(webapp, "_BG_JOIN_TIMEOUT_S", 0.5):
            gen = self.start()
            t0 = time.monotonic()
            outs = [out for out in gen]
            elapsed = time.monotonic() - t0
            self.assertLess(elapsed, 3.0, f"drain not bounded: {elapsed:.2f}s")
            sid = outs[-1][5]
            self.settle(sid)
        flags, lifestyle = self.stores(sid)
        self.assertIs(flags[-1].disclosed_to_senior, False)
        self.assertEqual(lifestyle, [])

    def test_enqueued_then_closed_chunk_is_not_attested(self):
        # (d) Unit level: a chunk put while the consumer is open but never
        # dequeued before close() is refused.
        consumer = webapp._ChunkConsumer()
        result = {}
        t = threading.Thread(target=lambda: result.setdefault(
            "ok", consumer.offer("late line", Path("x.wav"))))
        t.start()
        deadline = time.monotonic() + 5
        while consumer.queue.qsize() == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(consumer.queue.qsize(), 1, "offer never enqueued")
        consumer.close()
        t.join(timeout=5)
        self.assertIs(result.get("ok"), False)
        # And once closed, a new offer is refused outright.
        self.assertIs(consumer.offer("later", Path("y.wav")), False)


if __name__ == "__main__":
    unittest.main()
