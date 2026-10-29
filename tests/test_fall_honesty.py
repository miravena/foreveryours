"""Tests for #11: after a fast-path fall/crisis flag is disclosed to the
senior, THINK's prompt states that fact (the [SAFETY FLAGS SENT THIS SESSION]
block, think.build_prompt's session_flags), and a deterministic guard
(orchestrator.enforce_flag_honesty) strips any denial sentence before it
reaches speak() -- on the same turn's continuation and on every later turn of
the session alike.
"""
import re
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from caregiver import CaregiverFlags
from memory.store import MemoryStore
from pipeline import think
from safety import fastpath
from pipeline.orchestrator import TurnResult, enforce_flag_honesty, run_turn

FALL_Q = "Did you tell Sarah about my fall?"

_DENIAL_RE = re.compile(r"haven't told|didn't tell|not told", re.IGNORECASE)


class TestFallHonesty(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.data_dir = Path(self.temp_dir.name) / "data"
        self.audio_dir = Path(self.temp_dir.name) / "audio"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore("test_dad", self.data_dir)
        self.flags = CaregiverFlags("test_dad", self.data_dir)

    def _speak_capture(self, spoken_texts):
        """_speak_turn stand-in: consumes the given sentence generator (so
        the real filter_sentences() / enforce_flag_honesty() logic actually
        runs), records every text it was handed, and reports non-empty audio
        so disclosed_to_senior reflects a real spoken disclosure."""

        def side_effect(sentences, *_args, **_kwargs):
            texts = [s for s in sentences if s and s.strip()]
            spoken_texts.extend(texts)
            if not texts:
                return "", [], None
            path = self.audio_dir / f"s{len(spoken_texts)}.wav"
            return " ".join(texts), [path], 0.1

        return side_effect

    @patch("pipeline.orchestrator._speak_turn")
    @patch("pipeline.orchestrator.think.stream_reply")
    def test_fall_turn_continuation_carries_flag_and_strips_denial(self, mock_stream, mock_speak):
        spoken_texts: list[str] = []
        mock_speak.side_effect = self._speak_capture(spoken_texts)
        mock_stream.return_value = iter(["I'm here. I haven't told Sarah anything yet."])

        result = run_turn(
            "I fell down earlier and I'm scared.",
            self.store, self.flags, self.audio_dir, caregiver_name="Sarah",
        )
        # A fast-path turn runs no AUDIT/extraction background thread.
        self.assertIsNone(result.background_thread)

        # The fall flag was actually disclosed (speak above reported audio).
        stored = self.flags.all()
        self.assertEqual(len(stored), 1)
        self.assertTrue(stored[0].disclosed_to_senior)

        # (1) The continuation's prompt carries the session-flags block.
        call = mock_stream.call_args
        messages = think.build_prompt(*call.args, **call.kwargs)
        prompt_text = "\n".join(m["content"] for m in messages)
        self.assertIn("[SAFETY FLAGS SENT THIS SESSION]", prompt_text)

        # (2) The continuation text returned by run_turn is denial-free.
        self.assertNotRegex(result.reply_text, _DENIAL_RE)

        # (3) Every text actually handed to speak() this turn is denial-free.
        self.assertTrue(spoken_texts)
        for text in spoken_texts:
            self.assertNotRegex(text, _DENIAL_RE)

    @patch("pipeline.orchestrator.audit.audit_reply", return_value=("OK", "casual"))
    @patch("pipeline.orchestrator.think.extract_new_memory", return_value=None)
    @patch("pipeline.orchestrator._speak_turn")
    @patch("pipeline.orchestrator.think.stream_reply")
    def test_next_turn_after_fall_carries_flag_and_strips_denial(
        self, mock_stream, mock_speak, mock_extract, mock_audit
    ):
        spoken_texts: list[str] = []
        mock_speak.side_effect = self._speak_capture(spoken_texts)

        mock_stream.return_value = iter(["I'm here. I haven't told Sarah anything yet."])
        first = run_turn(
            "I fell down earlier and I'm scared.",
            self.store, self.flags, self.audio_dir, caregiver_name="Sarah",
        )
        stored = self.flags.all()
        self.assertEqual(len(stored), 1)
        self.assertTrue(stored[0].disclosed_to_senior)

        spoken_texts.clear()
        mock_stream.return_value = iter([
            "I'm so glad you asked. I haven't told Sarah anything yet-I only "
            "share safety concerns with family if I'm worried about your "
            "immediate well-being. But I'm telling you now that you're ok."
        ])
        # The caller carries the session-scoped flag list forward (#11),
        # the same way webapp.py/main.py carry `history` -- never re-derived
        # from flags.all(), which would also pick up a disclosure left over
        # from a DIFFERENT session's run against this same profile file.
        second = run_turn(
            "Did you tell Sarah about my fall?",
            self.store, self.flags, self.audio_dir, caregiver_name="Sarah",
            session_flags=first.session_flags,
        )
        if second.background_thread:
            second.background_thread.join(timeout=10)

        # (1) The next turn's prompt still carries the session-flags block.
        call = mock_stream.call_args
        messages = think.build_prompt(*call.args, **call.kwargs)
        prompt_text = "\n".join(m["content"] for m in messages)
        self.assertIn("[SAFETY FLAGS SENT THIS SESSION]", prompt_text)

        # (2) The next turn's reply is denial-free.
        self.assertNotRegex(second.reply_text, _DENIAL_RE)

        # (3) Every text handed to speak() on the next turn is denial-free.
        self.assertTrue(spoken_texts)
        for text in spoken_texts:
            self.assertNotRegex(text, _DENIAL_RE)

    def test_no_flag_leaves_reply_untouched(self):
        text = "I'm so glad you asked. I haven't told Sarah anything yet."
        self.assertEqual(enforce_flag_honesty(text, False), text)

    @patch("pipeline.orchestrator._speak_turn")
    @patch("pipeline.orchestrator.think.stream_reply")
    def test_session_isolation_does_not_leak_other_session_flags(self, mock_stream, mock_speak):
        """Privacy firewall (rule 15): a flag disclosed in one session must
        never surface in a LATER, separate session's prompt just because the
        two share the same on-disk CaregiverFlags file (the way main.py's
        day2/beat4 CLI runs, or a reloaded caregiver panel, do). `flags` here
        already has the fall flag from a prior session (same store, same
        profile) persisted to disk; this call starts a fresh session with an
        explicit empty `session_flags=[]` -- the main.py pattern for a shared
        store -- so it must not inherit it."""
        spoken_texts: list[str] = []
        mock_speak.side_effect = self._speak_capture(spoken_texts)
        mock_stream.return_value = iter(["I'm here. I haven't told Sarah anything yet."])
        run_turn(
            "I fell down earlier and I'm scared.",
            self.store, self.flags, self.audio_dir, caregiver_name="Sarah",
            session_flags=[],
        )
        stored = self.flags.all()
        self.assertEqual(len(stored), 1)
        self.assertTrue(stored[0].disclosed_to_senior)

        # A brand-new session against the SAME flags store/profile: a fresh
        # empty session_flags, simulating a fresh process (e.g.
        # `python main.py beat2` run the next day against the same data_dir)
        # instead of carrying the previous call's TurnResult.session_flags
        # forward.
        mock_stream.return_value = iter(["Hi again, how are you feeling today?"])
        fresh_session_result = run_turn(
            "How are you?", self.store, self.flags, self.audio_dir, caregiver_name="Sarah",
            session_flags=[],
        )
        if fresh_session_result.background_thread:
            # Not a fast-path turn, so run_turn starts the AUDIT/extraction
            # background thread -- join it before the test's tempdir
            # cleanup runs, or its file access can race the teardown.
            fresh_session_result.background_thread.join(timeout=10)
        call = mock_stream.call_args
        messages = think.build_prompt(*call.args, **call.kwargs)
        prompt_text = "\n".join(m["content"] for m in messages)
        self.assertNotIn("[SAFETY FLAGS SENT THIS SESSION]", prompt_text)
        self.assertEqual(fresh_session_result.session_flags, [])

    def test_guard_leaves_unrelated_denials_about_the_senior_alone(self):
        """The false-positive the review bounce found: a denial whose object
        is "you" (the senior) is not a family-notification denial at all and
        must survive even when a flag was disclosed this session."""
        unrelated = "I haven't told you how much I enjoy our afternoon chats."
        self.assertEqual(enforce_flag_honesty(unrelated, True, "Sarah", question=FALL_Q), unrelated)

    def test_guard_rewrites_a_pronoun_denial_not_just_the_name(self):
        """A second review round caught a false NEGATIVE in the first fix: a
        denial naming the caregiver by name was rewritten, but one using a
        pronoun ("her") instead was not -- a false denial reaching speech.
        The guard excludes only a "told YOU" (the senior) denial, so a
        pronoun or name or "anyone" denial is rewritten the same way."""
        for denial in (
            "I haven't told her about your fall.",
            "I haven't told him about your fall.",
            "I haven't told anyone about your fall.",
            "I haven't told Sarah anything yet.",
        ):
            rewritten = enforce_flag_honesty(denial, True, "Sarah", question=FALL_Q)
            self.assertNotRegex(rewritten, _DENIAL_RE, denial)
            self.assertIn("Sarah", rewritten)

    def test_guard_keeps_a_denial_when_dad_asks_about_a_private_subject(self):
        """Review finding: after a fall flag, a true privacy answer must not
        become a false "I did let Sarah know". The guard decides from the
        question, so a question about anything but a disclosed event never
        triggers a rewrite, whatever the reply says."""
        for question, reply in (
            ("Did you tell Sarah about the biscuits?", "I haven't told her about it."),
            ("Don't tell Sarah about the biscuits.", "I haven't told Sarah, because that's between us."),
            ("Did you tell Sarah about my letter?", "I haven't told Sarah anything yet."),
            ("Did you tell Sarah my PIN?", "I haven't told Sarah your PIN."),
        ):
            self.assertEqual(enforce_flag_honesty(reply, True, "Sarah", question=question), reply, question)
        # No question known: never rewrite.
        self.assertEqual(enforce_flag_honesty("I haven't told her.", True, "Sarah"), "I haven't told her.")

    def test_guard_rewrites_only_for_the_event_of_a_flag_actually_disclosed(self):
        fall = [fastpath.CAREGIVER_FLAG_TEXT["fall"]]
        driving = [fastpath.CAREGIVER_FLAG_TEXT["driving"]]
        crisis = [fastpath.CAREGIVER_FLAG_TEXT["crisis"]]
        reply = "I didn't tell her about that."
        drive_q = "Did you tell Sarah about my driving?"
        # A fall flag does not make a driving denial false.
        self.assertEqual(enforce_flag_honesty(reply, True, "Sarah", disclosed_texts=fall, question=drive_q), reply)
        out = enforce_flag_honesty(reply, True, "Sarah", disclosed_texts=driving, question=drive_q)
        self.assertNotRegex(out, _DENIAL_RE)
        self.assertEqual(out, "I did let Sarah know.")
        self.assertNotRegex(
            enforce_flag_honesty("I haven't told Sarah.", True, "Sarah", disclosed_texts=crisis,
                                 question="Did you tell Sarah I said I want to end my life?"),
            _DENIAL_RE,
        )

    def test_guard_rewrites_a_real_denial_even_with_an_unrelated_tell_you_later(self):
        """A third review round caught a false NEGATIVE: the "told you"
        exclusion was checked over the WHOLE sentence, so an unrelated "tell
        you" later in a compound sentence suppressed a real denial earlier
        in it. The exclusion is now tied to the matched denial verb itself."""
        denial = "I haven't told Sarah because I wanted to tell you first."
        rewritten = enforce_flag_honesty(denial, True, "Sarah", question=FALL_Q)
        self.assertNotRegex(rewritten, _DENIAL_RE, denial)

    @patch("pipeline.orchestrator.audit.audit_reply", return_value=("OK", "casual"))
    @patch("pipeline.orchestrator.think.extract_new_memory", return_value=None)
    @patch("pipeline.orchestrator._speak_turn")
    @patch("pipeline.orchestrator.think.stream_reply")
    def test_run_turn_never_reads_the_flags_store_for_session_flags(
        self, mock_stream, mock_speak, mock_extract, mock_audit
    ):
        """The flag file is the household's whole history, not this
        conversation: a disclosed flag already persisted there (another
        process, another browser tab under FY_SHARED_PROFILE=1) must not
        become "sent this session" for a caller that carries nothing
        (`session_flags` left at its default) -- there is no mode in which
        run_turn re-derives the fact from `flags.all()`."""
        self.flags.add(
            "Possible fall reported", severity="distress",
            disclosed_to_senior=True, source="fastpath",
        )
        self.assertTrue(any(f.disclosed_to_senior for f in self.flags.all()))

        spoken_texts: list[str] = []
        mock_speak.side_effect = self._speak_capture(spoken_texts)
        denial = "I'm so glad you asked. I haven't told Sarah anything yet."
        mock_stream.return_value = iter([denial])
        result = run_turn(
            "Did you tell Sarah about my fall?",
            self.store, self.flags, self.audio_dir, caregiver_name="Sarah",
        )
        if result.background_thread:
            result.background_thread.join(timeout=10)

        call = mock_stream.call_args
        messages = think.build_prompt(*call.args, **call.kwargs)
        prompt_text = "\n".join(m["content"] for m in messages)
        self.assertNotIn("[SAFETY FLAGS SENT THIS SESSION]", prompt_text)
        self.assertEqual(result.session_flags, [])
        # No disclosure happened in THIS conversation, so the guard must not
        # invent one: the model's sentence goes out as it was.
        self.assertRegex(result.reply_text, _DENIAL_RE)


class TestWebappTabIsolation(unittest.TestCase):
    """webapp.py carries the session flags per browser tab (#11), the way it
    carries `history`: under FY_SHARED_PROFILE=1 every tab shares one session
    id and one `data/` directory (the review-bounce scenario), so the only
    thing that tells two tabs apart is Gradio's per-tab `request.session_hash`
    -- a fall disclosed in tab A must reach tab A's next turn and never tab B's.
    `run_turn` is stubbed to record the `session_flags` it is handed."""

    FALL = "I fell down earlier and I'm scared."
    QUESTION = "Did you tell Sarah about my fall?"
    FLAG = "Possible fall reported"
    SIM = "Morning (Default)"

    def setUp(self):
        import webapp
        self.webapp = webapp
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        for p in (
            patch.object(webapp, "SHARED_PROFILE", True),
            patch.object(webapp, "DATA_DIR", root / "data"),
            patch.object(webapp, "AUDIO_DIR", root / "audio"),
            patch.object(webapp, "SESSIONS_DIR", root / "sessions"),
        ):
            p.start()
            self.addCleanup(p.stop)
        webapp.DATA_DIR.mkdir(parents=True, exist_ok=True)
        webapp.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        webapp._session_flags.clear()
        self.addCleanup(webapp._session_flags.clear)
        self.seen: list[tuple[str, list[str]]] = []

    def _stub_run_turn(self, transcript, store, flags, audio_dir, **kwargs):
        carried = list(kwargs.get("session_flags") or [])
        self.seen.append((transcript, list(carried)))
        if transcript == self.FALL:
            carried.append(self.FLAG)  # the fast-path's disclosed flag
        return TurnResult(transcript, "ok", session_flags=carried)

    @staticmethod
    def _tab(session_hash: str):
        return types.SimpleNamespace(session_hash=session_hash)

    def test_shared_profile_tabs_do_not_share_session_flags(self):
        webapp, sid = self.webapp, self.webapp.DEFAULT_PROFILE_ID
        tab_a, tab_b = self._tab("a" * 12), self._tab("b" * 12)
        with patch.object(webapp, "run_turn", side_effect=self._stub_run_turn):
            # Tab A: the fall. A fresh conversation carries nothing in.
            out = webapp.run_demo_turn(None, self.FALL, [], sid, self.SIM, tab_a)
            self.assertEqual(out[5], sid)
            self.assertEqual(self.seen[-1], (self.FALL, []))

            # Tab B, same shared session id and data/: must NOT be told
            # about tab A's fall.
            webapp.run_demo_turn(None, self.QUESTION, [], sid, self.SIM, tab_b)
            self.assertEqual(self.seen[-1], (self.QUESTION, []))

            # Tab A's next turn (streaming path) carries its own fall flag.
            outs = list(webapp.run_demo_turn_streaming(None, self.QUESTION, [], sid, self.SIM, tab_a))
            self.assertTrue(outs)
            self.assertEqual(self.seen[-1], (self.QUESTION, [self.FLAG]))

            # Tab B still knows nothing, on either path.
            list(webapp.run_demo_turn_streaming(None, self.QUESTION, [], sid, self.SIM, tab_b))
            self.assertEqual(self.seen[-1], (self.QUESTION, []))

            # A proactive turn in tab A (the button handlers, via the closure
            # Gradio injects the request into) carries the flag too.
            handler = webapp._proactive_streaming_handler("morning")
            list(handler([], sid, self.SIM, tab_a))
            self.assertEqual(self.seen[-1], ("[PROACTIVE_TRIGGER]", [self.FLAG]))

    def test_direct_callers_are_keyed_by_session_id(self):
        """Without a Gradio request (tests, scripts) the key is the bare
        session id: one conversation per id, and a household's removal
        (`_forget_session_flags`, called by `_end_session`/the sweeper) drops
        both its bare and its per-tab entries and nothing else."""
        webapp = self.webapp
        self.assertEqual(webapp._flags_key("sid"), "sid")
        self.assertEqual(webapp._flags_key("sid", self._tab("h")), "sid:h")
        webapp._set_session_flags("sid", ["x"])
        webapp._set_session_flags("sid:h", ["y"])
        webapp._set_session_flags("other", ["z"])
        self.assertEqual(webapp._get_session_flags("sid"), ["x"])
        self.assertEqual(webapp._get_session_flags("missing"), [])
        webapp._forget_session_flags("sid")
        self.assertEqual(webapp._get_session_flags("sid"), [])
        self.assertEqual(webapp._get_session_flags("sid:h"), [])
        self.assertEqual(webapp._get_session_flags("other"), ["z"])


if __name__ == "__main__":
    unittest.main()
