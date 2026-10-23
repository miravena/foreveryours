"""Plan-review builder notes, kept out of test_late_disclosure.py
so that module stays at exactly the four tests its acceptance check counts:

1. audit-only turn (extract_new_memory returns None): one late chunk, then
   a panel-only refresh that shows the persisted flag;
2. (moved) the "failed audio recombination" case is gone with the
   recombination itself: its replacement, an unreadable disclosure
   chunk is yielded as None and refused, lives in tests/test_audio_once.py
   (test_unreadable_chunk_is_refused_not_attested and
   test_unopenable_existing_chunk_is_refused_not_attested);
3. a browser disconnect (`gen.close()`) while a late disclosure chunk has
   been dequeued and is suspended at its yield: it is NOT attested.
"""
from __future__ import annotations

import time
import unittest

import webapp
from tests.test_late_disclosure import LateDisclosureHarness


class TestAuditOnlyLateDisclosure(LateDisclosureHarness):
    extract_result = None

    def test_audit_only_disclosure_streamed_then_panel_refreshed(self):
        gen = self.start()
        outs, done_idx = [], None
        for out in gen:
            outs.append(out)
            if done_idx is None and self.is_done_final(out):
                done_idx = len(outs) - 1
                self.release_background.set()
        sid = outs[-1][5]
        self.settle(sid)
        late = outs[done_idx + 1:]
        disclosures = self.disclosure_paths()
        self.assertEqual(len(disclosures), 1, self.spoken)
        self.assertEqual(len(late), 2)  # the disclosure chunk + panel refresh
        self.assertEqual(late[0][1], disclosures[0])
        self.assertIsNone(late[1][1])  # The refresh re-sends no audio
        self.assertNotIn("Dad was told", late[0][3])  # rendered before the flag existed
        self.assertIn("Dad was told", late[1][3])
        flags, lifestyle = self.stores(sid)
        self.assertIs(flags[-1].disclosed_to_senior, True)
        self.assertEqual(lifestyle, [])


class TestCloseAtLateYield(LateDisclosureHarness):

    def test_gen_close_while_late_chunk_is_suspended_at_yield(self):
        gen = self.start()
        done = False
        while True:
            out = next(gen)
            if not done and self.is_done_final(out):
                done = True
                self.release_background.set()
                continue
            if done and out[1] is not None and out[1] in self.disclosure_paths():
                break  # suspended at the late disclosure's yield, not yet acked
        sid = out[5]
        bg = list(webapp._bg_threads.get(sid, []))
        t0 = time.monotonic()
        gen.close()  # browser disconnect: GeneratorExit at that yield
        for t in bg:
            t.join(timeout=10)
        # Refused by close() itself, not by offer()'s 10 s ack timeout.
        self.assertLess(time.monotonic() - t0, 3.0)
        self.settle(sid)
        flags, lifestyle = self.stores(sid)
        self.assertIs(flags[-1].disclosed_to_senior, False)
        self.assertEqual(lifestyle, [])


if __name__ == "__main__":
    unittest.main()
