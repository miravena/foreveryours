"""The browser reply player hears every sentence exactly once.

`_run_demo_turn_streaming_impl` used to recombine every chunk spoken so far
into a growing `combined_*.wav` on each sentence, again at DONE, again for
each late disclosure, and re-yield it on the panel-only refresh -- to a
non-streaming autoplay player, so each yield restarted the reply from the
beginning. These tests pin the per-chunk contract: each chunk's own path is
yielded once by the yield that carries it, `None` on the DONE-final yield and
the panel-only refresh, and the reply player is a streaming `gr.Audio` whose
every writer is a generator function.

`webapp._combine_audio_chunks` is deliberately NOT patched here: the real
audio values the generator yields are what is observed. The fake TTS writes
b"RIFF" only, so these tests prove delivery and acknowledgement, not Gradio's
encoding or audible playback.
"""
from __future__ import annotations

import inspect
import unittest
from pathlib import Path
from unittest.mock import patch

import gradio as gr

import webapp
from tests.test_late_disclosure import LateDisclosureHarness


class TestAudioOnce(LateDisclosureHarness):

    # -- helpers -----------------------------------------------------------
    def run_releasing_at_done(self):
        """Consume the turn to exhaustion, releasing the background thread at
        the DONE-final yield; return (outs, done_idx, session_id)."""
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
        return outs, done_idx, sid

    def broken_disclosure_speaker(self, break_path):
        """A fake `speak_sentences` that writes the reply chunk normally but
        hands every DISCLOSURE chunk to `break_path` instead of writing it."""

        def fake(sentences, out_dir):
            for s in sentences:
                self._n += 1
                out_dir.mkdir(parents=True, exist_ok=True)
                p = Path(out_dir) / f"chunk_{self._n}.wav"
                if s == "Reply":
                    p.write_bytes(b"RIFF")
                else:
                    break_path(p)
                self.spoken.append((s, p))
                yield s, p

        return fake

    def assert_disclosures_refused(self, outs, done_idx, sid):
        disclosures = self.disclosure_paths()
        self.assertEqual(len(disclosures), 2, self.spoken)  # audit + lifestyle
        audio = [o[1] for o in outs]
        for d in disclosures:
            self.assertNotIn(d, audio, "an unreadable chunk's path was yielded")
        for a in audio:  # never a path Gradio's stream_output could not open
            if isinstance(a, str):  # (the thinking yield carries gr.skip())
                self.assertTrue(webapp._chunk_readable(Path(a)), a)
        late = outs[done_idx + 1:]
        # One late yield per (refused) disclosure message, carrying no audio.
        self.assertGreaterEqual(len(late), len(disclosures), [o[1] for o in late])
        for o in late:
            self.assertIsNone(o[1])
        flags, lifestyle = self.stores(sid)
        self.assertTrue(flags, "audit DISTRESS should have recorded a flag")
        self.assertIs(flags[-1].disclosed_to_senior, False)
        self.assertEqual(lifestyle, [])

    # -- (a) ---------------------------------------------------------------
    def test_each_sentence_audio_is_yielded_exactly_once(self):
        # stream_reply yields TOKENS; think.sentence_chunks splits on
        # punctuation followed by whitespace, so these are three sentences.
        with patch("pipeline.orchestrator.think.stream_reply",
                   return_value=["First. ", "Second. ", "Third."]), \
             patch("pipeline.orchestrator.audit.audit_reply", return_value=("SAFE", "")), \
             patch("pipeline.orchestrator.think.extract_new_memory", return_value=None):
            self.history = []
            outs = list(webapp.run_demo_turn_streaming(None, "Hello there", self.history, None))
            sid = outs[-1][5]
            webapp._join_previous_turn(sid)

        chunks = [str(p) for _s, p in self.spoken]
        self.assertEqual(len(chunks), 3, self.spoken)  # nothing disclosed
        audio = [o[1] for o in outs]
        delivered = [a for a in audio if isinstance(a, str)]  # the thinking yield skips
        self.assertEqual(delivered, chunks, audio)  # in order, each once
        self.assertFalse(any("combined_" in str(a) for a in audio), audio)
        done = [o for o in outs if self.is_done_final(o)]
        self.assertTrue(done, "no DONE-final yield observed")
        self.assertIsNone(done[0][1], "DONE-final yield re-sent the reply audio")

    # -- (b) ---------------------------------------------------------------
    def test_late_disclosure_audio_is_yielded_exactly_once(self):
        outs, done_idx, sid = self.run_releasing_at_done()
        disclosures = self.disclosure_paths()
        self.assertEqual(len(disclosures), 2, self.spoken)
        late = outs[done_idx + 1:]
        late_audio = [o[1] for o in late]
        for d in disclosures:
            self.assertEqual(late_audio.count(d), 1, late_audio)
        all_audio = [o[1] for o in outs]
        for d in disclosures:
            self.assertEqual(all_audio.count(d), 1, all_audio)
        self.assertIsNone(outs[-1][1], "panel-only refresh re-sent audio")
        flags, lifestyle = self.stores(sid)
        self.assertIs(flags[-1].disclosed_to_senior, True)
        self.assertEqual(len(lifestyle), 1)
        self.assertTrue(lifestyle[0].disclosure_attested)

    # -- (c) ---------------------------------------------------------------
    def test_unreadable_chunk_is_refused_not_attested(self):
        # The disclosure chunk path is handed over but never written.
        with patch("pipeline.orchestrator.speak.speak_sentences",
                   side_effect=self.broken_disclosure_speaker(lambda p: None)):
            outs, done_idx, sid = self.run_releasing_at_done()
        self.assertFalse(any(Path(d).exists() for d in self.disclosure_paths()))
        self.assert_disclosures_refused(outs, done_idx, sid)

    # -- (d) ---------------------------------------------------------------
    def test_reply_player_is_streaming(self):
        demo = webapp.build_demo()
        players = [b for b in demo.blocks.values()
                   if isinstance(b, gr.Audio) and b.label == "Companion's reply"]
        self.assertEqual(len(players), 1, players)
        player = players[0]
        self.assertIs(player.streaming, True)
        self.assertIs(player.autoplay, True)
        writers = [f for f in demo.fns.values()
                   if any(o is player or getattr(o, "_id", None) == player._id
                          for o in f.outputs)]
        # Send, Enter and the four proactive buttons.
        self.assertEqual(len(writers), 6, [getattr(f, "name", f) for f in writers])
        for f in writers:
            self.assertTrue(inspect.isgeneratorfunction(f.fn),
                            f"{f.fn!r} writes the streaming player but is not a generator function")

    # -- (e) ---------------------------------------------------------------
    def test_unopenable_existing_chunk_is_refused_not_attested(self):
        # The disclosure chunk path EXISTS but cannot be read (a directory):
        # open() raises IsADirectoryError, an OSError -- no mocking.
        with patch("pipeline.orchestrator.speak.speak_sentences",
                   side_effect=self.broken_disclosure_speaker(lambda p: p.mkdir())):
            outs, done_idx, sid = self.run_releasing_at_done()
        self.assertTrue(all(Path(d).is_dir() for d in self.disclosure_paths()))
        self.assert_disclosures_refused(outs, done_idx, sid)


if __name__ == "__main__":
    unittest.main()
