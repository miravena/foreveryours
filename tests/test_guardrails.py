"""Abuse guardrails and owner alerts (#37): input caps, the process-wide hosted-turn
budget, per-client limits, alerts, and the small hardening that shipped with them.

Offline, standard library only. Budgets and alerts run on an injected clock; the
webapp-level tests use a temp session directory and no real key.
"""
import os
import re
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import guardrails
import notify
import webapp
from guardrails import Config, Guardrails, OwnerAlerts
from memory.store import MemoryStore

T0 = 1_800_000_000.0  # a fixed instant; the clock below is advanced by hand
GOOD_IP = "8.8.8.8"
OTHER_IP = "1.1.1.1"
SECRET_TEXT = "SECRET-TYPED-TEXT-7731"
FAKE_UPLOAD = os.path.join(tempfile.gettempdir(), "fake.wav")


class Clock:
    def __init__(self, now: float = T0):
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_guard(clock=None, alerts_per_hour=6, **cfg):
    """A Guardrails on an injected clock whose alerts land in `sent` (title, body)."""
    clock = clock or Clock()
    sent: list = []
    alerts = OwnerAlerts(alerts_per_hour, clock, sender=lambda t, b: sent.append((t, b)),
                         spawn=lambda fn: fn())
    guard = Guardrails(Config(owner_alerts_per_hour=alerts_per_hour, **cfg), clock, alerts,
                       salt=b"test-salt", on_space=False)
    return guard, sent, clock


def request(peer="10.0.0.1", forwarded=None):
    headers = {"x-forwarded-for": forwarded} if forwarded is not None else {}
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


class TestInputCaps(unittest.TestCase):
    def test_typed_and_transcript_cap_boundary(self):
        guard, _, _ = make_guard()
        self.assertIsNone(guard.input_refusal("a" * 2000))
        refusal = guard.input_refusal("a" * 2001)
        self.assertIn("Nothing was sent", refusal)
        self.assertNotIn("a" * 20, refusal)  # the refusal never echoes the input

    def test_memo_char_cap_boundary_and_splitter_not_run_on_huge_text(self):
        guard, _, _ = make_guard()
        counter = MagicMock(return_value=1)
        self.assertIsNone(guard.memo_refusal("a" * 2000, counter))
        counter.reset_mock()
        self.assertIn("Nothing was saved", guard.memo_refusal("a" * 2001, counter))
        counter.assert_not_called()

    def test_memo_fact_cap_boundary(self):
        guard, _, _ = make_guard()
        self.assertIsNone(guard.memo_refusal("x", lambda t: 30))
        self.assertIn("31 separate facts", guard.memo_refusal("x", lambda t: 31))

    def test_caps_are_environment_variables_with_fallback_to_the_default(self):
        cfg = Config.from_env({"FY_MAX_INPUT_CHARS": "500", "FY_MAX_MEMO_FACTS": "abc",
                               "FY_MAX_MEMO_CHARS": "-3", "FY_CLIENT_IP_SOURCE": "nonsense"})
        self.assertEqual(cfg.max_input_chars, 500)
        self.assertEqual(cfg.max_memo_facts, 30)
        self.assertEqual(cfg.max_memo_chars, 2000)
        self.assertEqual(cfg.client_ip_source, "auto")

    def test_refusals_are_counted_and_alert_once_over_the_threshold(self):
        guard, sent, _ = make_guard(alert_refusals_per_hour=3)
        for _ in range(3):
            guard.input_refusal("a" * 2001)
        self.assertEqual(sent, [])
        for _ in range(5):
            guard.input_refusal("a" * 2001)
        self.assertEqual(len(sent), 1)
        self.assertIn("oversize", sent[0][0])


class _WebappCase(unittest.TestCase):
    """A temp session directory, no real key, a private Guardrails per test."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.guard, self.sent, self.clock = make_guard()
        for p in (
            patch.object(webapp, "SESSIONS_DIR", Path(self.temp_dir.name) / "sessions"),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
            patch.object(webapp, "GUARDRAILS", self.guard),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.temp_dir.cleanup)
        self.session_id, _ = webapp.init_session()

    def store(self) -> MemoryStore:
        data_dir, _ = webapp._session_dirs(self.session_id)
        return MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir, timezone_str=webapp.SENIOR_TIMEZONE)

    def memory_texts(self) -> list:
        return sorted(i.text for i in self.store().all())


class TestTypedInputRefusal(_WebappCase):
    def _forbid_everything_after_the_cap(self):
        """Nothing past the cap check may run for an oversize input, and the safety
        scan never sees more than the cap (it is the part that does not scale)."""
        for target, name in ((webapp, "_cap_decision"), (webapp, "run_turn")):
            p = patch.object(target, name, side_effect=AssertionError(f"{name} ran for an oversize input"))
            p.start()
            self.addCleanup(p.stop)
        real_check = webapp.fastpath.check

        def bounded_check(text, *args, **kwargs):
            self.assertLessEqual(len(text), 2000, "the safety scan saw an oversize input")
            return real_check(text, *args, **kwargs)

        p = patch.object(webapp.fastpath, "check", side_effect=bounded_check)
        p.start()
        self.addCleanup(p.stop)

    def test_oversize_typed_text_is_refused_without_model_safety_scan_or_state_change(self):
        self._forbid_everything_after_the_cap()
        before = self.memory_texts()
        text = "a " * 1001  # 2002 characters
        history = [{"role": "user", "content": "hi"}]
        for run, hands_back in (
            (lambda: webapp.run_demo_turn(None, text, list(history), self.session_id), False),
            (lambda: list(webapp.run_demo_turn_streaming(None, text, list(history), self.session_id))[-1], True),
        ):
            out = run()
            self.assertIn("Nothing was sent", out[0])
            self.assertEqual(out[2], history)         # history unchanged
            self.assertIsNone(out[7])
            if hands_back:  # the streaming handler is the one the page uses
                self.assertEqual(out[6], text)        # typed text handed back to the box
        self.assertEqual(self.memory_texts(), before)

    def test_exactly_2000_characters_goes_on_to_the_cap_decision(self):
        class Reached(Exception):
            pass

        with patch.object(webapp, "_cap_decision", side_effect=Reached):
            with self.assertRaises(Reached):
                webapp.run_demo_turn(None, "a" * 2000, [], self.session_id)
        with patch.object(webapp, "_cap_decision", side_effect=Reached):
            with self.assertRaises(Reached):
                list(webapp.run_demo_turn_streaming(None, "a" * 2000, [], self.session_id))

    def test_oversize_asr_transcript_is_refused_the_same_way(self):
        self._forbid_everything_after_the_cap()
        with patch.object(webapp.hear, "transcribe",
                          return_value=("word " * 500, {"wpm": 0.0, "avg_pause_s": 0.0})):
            out = webapp.run_demo_turn(FAKE_UPLOAD, None, [], self.session_id)
            streamed = list(webapp.run_demo_turn_streaming(FAKE_UPLOAD, None, [], self.session_id))[-1]
        for result in (out, streamed):
            self.assertIn("Nothing was sent", result[0])
            self.assertEqual(result[2], [])
            self.assertEqual(result[6], "")

    def test_a_long_input_that_starts_or_ends_with_an_emergency_still_gets_the_safety_reply(self):
        """Review of #37: the cap must not suppress a safety reply. The fast path sees
        only the head and the tail slice (each within the cap); the paid continuation
        is withheld and the family is flagged."""
        filler = "The weather was lovely and the garden looked nice today. " * 60
        for text in ("I fell down earlier and I'm scared. " + filler,
                     filler + " I fell down earlier and I'm scared."):
            sid, _ = webapp.init_session()
            for run in (
                lambda: webapp._run_demo_turn(None, text, [], sid),
                lambda: list(webapp.run_demo_turn_streaming(None, text, [], sid))[-1][:5],
            ):
                out = run()
                self.assertIn("letting your family know", out[0])
                self.assertIn("too long", out[0])
            self.assertIn("URGENT", webapp._format_caregiver_panel(sid))

    def test_an_emergency_buried_in_the_middle_of_a_huge_input_is_refused_unscanned(self):
        """The documented limit of the bounded scan: only the two ends are looked at."""
        self._forbid_everything_after_the_cap()
        text = ("The weather was lovely today. " * 100 + "I fell down earlier and I'm scared. "
                + "The garden looked nice. " * 100)
        out = webapp.run_demo_turn(None, text, [], self.session_id)
        self.assertIn("Nothing was sent", out[0])


class TestMemoRefusal(_WebappCase):
    def forbid_store_writes(self):
        p = patch.object(MemoryStore, "add", side_effect=AssertionError("a refused memo reached the store"))
        p.start()
        self.addCleanup(p.stop)

    def test_text_memo_over_the_char_cap(self):
        self.forbid_store_writes()
        memo = "Sarah visits on Friday. " * 90  # over 2000 characters
        panel, sid, box = webapp.save_caregiver_text_memo(memo, self.session_id)
        self.assertIn("Nothing was saved", panel)
        self.assertEqual(box, memo)  # handed back to the box to shorten

    def test_text_memo_over_the_fact_cap_and_at_it(self):
        memo31 = " ".join(f"Fact number {n} is here." for n in range(31))
        self.assertLessEqual(len(memo31), 2000)
        before = self.memory_texts()
        panel, _, box = webapp.save_caregiver_text_memo(memo31, self.session_id)
        self.assertIn("31 separate facts", panel)
        self.assertEqual(box, memo31)
        self.assertEqual(self.memory_texts(), before)
        memo30 = " ".join(f"Fact number {n} is here." for n in range(30))
        panel, _, box = webapp.save_caregiver_text_memo(memo30, self.session_id)
        self.assertNotIn("Nothing was saved", panel)
        self.assertEqual(box, "")
        self.assertGreater(len(self.memory_texts()), len(before))

    def test_voice_memo_transcript_over_the_cap(self):
        self.forbid_store_writes()
        with patch.object(webapp.hear, "transcribe", return_value="She visits on Friday. " * 100):
            panel, _ = webapp.save_caregiver_voice_memo(FAKE_UPLOAD, self.session_id)
        self.assertIn("Nothing was saved", panel)

    def test_interview_answer_over_the_cap(self):
        self.forbid_store_writes()
        state, _ = webapp.interview_next(None, self.session_id)
        answer = "She likes tea. " * 200
        panel, sid, state, text, box = webapp.interview_confirm(answer, state, self.session_id)
        self.assertIn("Nothing was saved", text)
        self.assertEqual(state["answered"], [])  # the question stays open
        self.assertEqual(box, answer)

    def test_the_store_writer_is_a_backstop(self):
        self.forbid_store_writes()
        with webapp._session_active(self.session_id, refuse_if_deleted=True):
            with self.assertRaises(webapp.MemoTooLarge):
                webapp._save_memo_text(self.session_id, "x" * 2001)


class TestGlobalBudget(unittest.TestCase):
    def test_hourly_cap_then_rolls_over(self):
        guard, _, clock = make_guard(global_turns_per_hour=3)
        self.assertEqual([guard.admit_hosted_turn(None) for _ in range(5)], [True] * 3 + [False] * 2)
        clock.advance(3601)
        self.assertTrue(guard.admit_hosted_turn(None))

    def test_daily_cap_resets_at_the_next_utc_day(self):
        guard, _, clock = make_guard(global_turns_per_day=4, global_turns_per_hour=100)
        self.assertEqual([guard.admit_hosted_turn(None) for _ in range(6)], [True] * 4 + [False] * 2)
        clock.advance(86400)
        self.assertTrue(guard.admit_hosted_turn(None))

    def test_refund_gives_the_slot_back(self):
        guard, _, _ = make_guard(global_turns_per_hour=1, client_turns_per_hour=1)
        allowed, ticket = guard.admit("c1")
        self.assertTrue(allowed)
        self.assertFalse(guard.admit_hosted_turn("c1"))
        guard.refund_hosted_turn(ticket)
        self.assertTrue(guard.admit_hosted_turn("c1"))

    def test_a_refund_removes_its_own_entry_not_a_newer_turns(self):
        guard, _, clock = make_guard(global_turns_per_hour=2, client_turns_per_hour=5)
        _, first = guard.admit("a")
        clock.advance(1000)
        guard.admit("b")  # admitted after A, before A is refunded
        guard.refund_hosted_turn(first)
        self.assertEqual(list(guard._hour), [T0 + 1000])
        clock.advance(2700)  # A's old slot would have expired by now; B's has not
        self.assertEqual(len(guard._hour), 1)
        self.assertTrue(guard.admit_hosted_turn(None))
        self.assertFalse(guard.admit_hosted_turn(None))  # still 2 per hour: B's turn counts in full
        guard.refund_hosted_turn(None)  # a turn admitted by the fail-open path has no ticket

    def test_an_accounting_bug_fails_open(self):
        guard, _, _ = make_guard()
        with patch.object(guard, "_admit", side_effect=RuntimeError("boom")):
            self.assertTrue(guard.admit_hosted_turn("c1"))

    def test_budget_is_thread_safe(self):
        guard, _, _ = make_guard(global_turns_per_hour=50, global_turns_per_day=1000)
        results, lock = [], threading.Lock()

        def worker():
            for _ in range(20):
                ok = guard.admit_hosted_turn(None)
                with lock:
                    results.append(ok)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count(True), 50)


class TestClientLimits(unittest.TestCase):
    def test_turns_per_hour_are_per_client(self):
        guard, _, clock = make_guard(client_turns_per_hour=2)
        self.assertEqual([guard.admit_hosted_turn("a") for _ in range(3)], [True, True, False])
        self.assertTrue(guard.admit_hosted_turn("b"))  # another visitor is untouched
        clock.advance(3601)
        self.assertTrue(guard.admit_hosted_turn("a"))

    def test_too_many_new_sessions_throttles_turns_but_never_the_page(self):
        guard, _, clock = make_guard(client_new_sessions_per_hour=3)
        for _ in range(3):
            guard.note_new_session("a")
        self.assertTrue(guard.admit_hosted_turn("a"))
        guard.note_new_session("a")  # the 4th: the page still loads, turns answer busy
        self.assertFalse(guard.admit_hosted_turn("a"))
        self.assertTrue(guard.admit_hosted_turn("b"))
        clock.advance(3601)
        self.assertTrue(guard.admit_hosted_turn("a"))

    def test_unknown_client_skips_per_client_limits_but_not_the_global_ones(self):
        guard, _, _ = make_guard(client_turns_per_hour=1, global_turns_per_hour=3)
        self.assertEqual([guard.admit_hosted_turn(None) for _ in range(4)], [True] * 3 + [False])

    def test_the_client_table_is_bounded(self):
        guard, _, clock = make_guard()
        with patch.object(guardrails, "_MAX_TRACKED_CLIENTS", 40):
            for n in range(200):
                clock.advance(1)
                guard.admit_hosted_turn(f"client-{n}")
        self.assertLessEqual(len(guard._clients), 40)

    def test_default_limits_let_a_normal_judge_session_through_untouched(self):
        guard = Guardrails(Config(), Clock(), OwnerAlerts(6, Clock(), sender=lambda t, b: self.fail("alert"),
                                                          spawn=lambda fn: fn()), salt=b"s", on_space=False)
        clock = guard._clock
        guard.note_new_session("judge")
        for _ in range(40):  # 40 turns over an hour
            clock.advance(90)
            self.assertIsNone(guard.input_refusal("Tell me about my day, please."))
            self.assertTrue(guard.admit_hosted_turn("judge"))
        guard.note_new_session("judge")
        self.assertTrue(guard.admit_hosted_turn("judge"))


class TestClientIdentity(unittest.TestCase):
    def test_forwarded_for_walks_from_the_right_past_internal_hops(self):
        f = guardrails.forwarded_client_ip
        self.assertEqual(f(GOOD_IP), GOOD_IP)
        self.assertEqual(f(f"{GOOD_IP}, 10.1.2.3"), GOOD_IP)
        self.assertEqual(f(f"{GOOD_IP},10.1.2.3, 172.16.0.9, 100.64.0.2"), GOOD_IP)
        self.assertEqual(f(f"{GOOD_IP}:5555"), GOOD_IP)
        self.assertEqual(f("[2001:4860:4860::8888], 10.0.0.2"), "2001:4860:4860::8888")

    def test_a_forged_prefix_never_picks_the_key(self):
        f = guardrails.forwarded_client_ip
        self.assertEqual(f(f"{OTHER_IP}, {GOOD_IP}, 10.0.0.1"), GOOD_IP)
        self.assertEqual(f(f"{OTHER_IP}, {GOOD_IP}"), GOOD_IP)

    def test_unreliable_headers_give_no_answer(self):
        f = guardrails.forwarded_client_ip
        for value in (None, "", "unknown", f"{GOOD_IP}, garbage", "10.0.0.1, 192.168.1.1", ", ,"):
            self.assertIsNone(f(value), value)

    def test_on_a_space_the_forwarded_header_is_used_not_the_proxy_peer(self):
        a = guardrails.client_ip(request("10.0.0.1", f"{GOOD_IP}, 10.0.0.1"), "auto", True)
        b = guardrails.client_ip(request("10.0.0.1", f"{OTHER_IP}, 10.0.0.1"), "auto", True)
        self.assertEqual((a, b), (GOOD_IP, OTHER_IP))
        self.assertIsNone(guardrails.client_ip(request("10.0.0.1"), "auto", True))  # no header: skip

    def test_off_a_space_the_peer_is_used_and_a_forwarded_header_is_ignored(self):
        self.assertEqual(guardrails.client_ip(request(GOOD_IP, OTHER_IP), "auto", False), GOOD_IP)
        self.assertEqual(guardrails.client_ip(request("127.0.0.1", OTHER_IP), "auto", False), "127.0.0.1")

    def test_source_override_and_missing_request(self):
        self.assertIsNone(guardrails.client_ip(request(GOOD_IP), "off", False))
        self.assertEqual(guardrails.client_ip(request("10.0.0.1", GOOD_IP), "forwarded", False), GOOD_IP)
        self.assertIsNone(guardrails.client_ip(None, "auto", True))

    def test_header_case_does_not_matter_for_a_plain_dict(self):
        req = SimpleNamespace(client=SimpleNamespace(host="10.0.0.1"), headers={"X-Forwarded-For": GOOD_IP})
        self.assertEqual(guardrails.client_ip(req, "forwarded", True), GOOD_IP)

    def test_client_key_is_a_salted_hash_not_the_address(self):
        a = Guardrails(Config(), Clock(), salt=b"one", on_space=True)
        b = Guardrails(Config(), Clock(), salt=b"two", on_space=True)
        req = request("10.0.0.1", f"{GOOD_IP}, 10.0.0.1")
        key = a.client_key(req)
        self.assertEqual(key, a.client_key(req))
        self.assertNotEqual(key, b.client_key(req))
        self.assertRegex(key, r"^[0-9a-f]{16}$")
        self.assertNotIn(GOOD_IP, key)
        self.assertNotEqual(key, a.client_key(request("10.0.0.1", f"{OTHER_IP}, 10.0.0.1")))
        self.assertIsNone(a.client_key(request("10.0.0.1")))  # unreliable: no key


class TestCapKeepsSafetyReplies(_WebappCase):
    """The shared budget behaves exactly like the per-session cap (#37): the fast
    path still speaks, discloses and flags; THINK, AUDIT and extraction are withheld."""

    def setUp(self):
        super().setUp()
        self.guard.config = Config(global_turns_per_hour=1, global_turns_per_day=100)
        self.assertTrue(self.guard.admit_hosted_turn(None))  # the hour is now spent
        for p in (
            patch.dict(os.environ, {"NEBIUS_API_KEY": "dummy-key-for-cap-test"}),
            patch("pipeline.think.stream_reply", side_effect=AssertionError("THINK ran while busy")),
            patch("pipeline.think.extract_memory_llm", side_effect=AssertionError("extraction ran while busy")),
        ):
            p.start()
            self.addCleanup(p.stop)

    def test_a_fall_still_gets_the_spoken_reply_and_the_flag(self):
        for run in (
            lambda sid: webapp._run_demo_turn(None, "I fell down earlier and I'm scared", [], sid),
            lambda sid: list(webapp.run_demo_turn_streaming(
                None, "I fell down earlier and I'm scared", [], sid))[-1][:5],
        ):
            sid, _ = webapp.init_session()
            out = run(sid)
            self.assertIn("letting your family know", out[0])
            self.assertIn("busy right now", out[0])
            self.assertNotIn("tomorrow", out[0])
            self.assertIn("URGENT", webapp._format_caregiver_panel(sid))

    def test_an_ordinary_turn_gets_the_busy_reply_and_no_model_call(self):
        with patch.object(webapp, "run_turn", side_effect=AssertionError("run_turn ran")):
            out = webapp._run_demo_turn(None, "Tell me about jazz", [], self.session_id)
            streamed = list(webapp.run_demo_turn_streaming(None, "Tell me about jazz", [], self.session_id))[-1]
        self.assertEqual(out[0], webapp.BUSY_REPLY)
        self.assertEqual(streamed[0], webapp.BUSY_REPLY)
        self.assertIn("try again shortly", webapp.BUSY_REPLY)

    def test_a_throttled_client_gets_the_same_behaviour(self):
        self.guard.config = Config(client_turns_per_hour=1)
        self.guard.admit_hosted_turn("client-x")
        out = webapp._run_demo_turn(None, "I can't breathe", [], self.session_id, client_key="client-x")
        self.assertIn("letting your family know", out[0])
        self.assertIn("busy right now", out[0])

    def test_the_session_cap_still_says_tomorrow_and_returns_the_shared_slot(self):
        self.guard.config = Config(global_turns_per_hour=5)
        with patch.object(webapp, "_rate_limit_ok", return_value=False):
            out = webapp._run_demo_turn(None, "Tell me about jazz", [], self.session_id)
        self.assertIn("daily request cap", out[0])
        self.assertEqual(len(self.guard._hour), 1)  # only the setUp turn; the refused one was refunded


class TestSessionCreationPaths(_WebappCase):
    """Every handler that can start a household counts it toward the client's limit."""

    def setUp(self):
        super().setUp()
        self.guard._on_space = True
        self.req = request("10.0.0.1", f"{GOOD_IP}, 10.0.0.1")
        self.key = self.guard.client_key(self.req)

    def started(self) -> int:
        return len(self.guard._clients[self.key]["sessions"]) if self.key in self.guard._clients else 0

    def test_handlers_without_a_session_count_the_new_one(self):
        calls = (
            lambda: webapp.save_caregiver_text_memo("Sarah visits on Friday.", None, self.req),
            lambda: webapp.save_caregiver_voice_memo(None, None, self.req),
            lambda: webapp.interview_confirm("", None, None, self.req),
            lambda: webapp.load_sample_family(None, self.req),
            lambda: webapp.init_session(self.req),
        )
        for n, call in enumerate(calls, start=1):
            call()
            self.assertEqual(self.started(), n)

    def test_a_turn_with_no_session_counts_the_new_one_but_an_existing_session_does_not(self):
        webapp.run_demo_turn(None, "Hello", [], None, "Morning (Default)", self.req)
        self.assertEqual(self.started(), 1)
        webapp.run_demo_turn(None, "Hello again", [], self.session_id, "Morning (Default)", self.req)
        self.assertEqual(self.started(), 1)

    def test_too_many_started_sessions_make_that_clients_turns_busy(self):
        self.guard.config = Config(client_new_sessions_per_hour=2)
        for _ in range(3):
            webapp.load_sample_family(None, self.req)
        self.assertFalse(self.guard.admit_hosted_turn(self.key))


class TestOwnerAlerts(unittest.TestCase):
    def test_daily_thresholds_fire_once_each(self):
        guard, sent, _ = make_guard(global_turns_per_day=10, global_turns_per_hour=100)
        for _ in range(14):  # 10 admitted, then 4 turned away
            guard.admit_hosted_turn(None)
        self.assertEqual([t for t, _ in sent],
                         ["ForeverYours demo: daily budget 50%", "ForeverYours demo: daily budget 80%",
                          "ForeverYours demo: daily budget used up"])
        self.assertIn("turns_today: 5", sent[0][1])
        self.assertIn("daily_cap: 10", sent[0][1])

    def test_a_refunded_turn_announces_no_usage_it_did_not_cause(self):
        """Review of #37: the shared budget is charged before the per-session cap runs."""
        guard, sent, _ = make_guard(global_turns_per_day=2, global_turns_per_hour=100)
        allowed, first = guard.admit(None)
        guard.commit_hosted_turn(first)
        self.assertEqual(len(sent), 1)  # 50%
        allowed, second = guard.admit(None)  # would take usage to 100% ...
        guard.refund_hosted_turn(second)  # ... but the session cap turned it away
        self.assertEqual(len(sent), 1)
        allowed, third = guard.admit(None)  # a turn that really goes ahead
        guard.commit_hosted_turn(third)
        self.assertEqual([t for t, _ in sent][1:], ["ForeverYours demo: daily budget 80%",
                                                    "ForeverYours demo: daily budget used up"])

    def test_thresholds_rearm_on_the_next_day(self):
        guard, sent, clock = make_guard(global_turns_per_day=2, global_turns_per_hour=100)
        for _ in range(3):
            guard.admit_hosted_turn(None)
        first_day = len(sent)
        clock.advance(86400)
        for _ in range(3):
            guard.admit_hosted_turn(None)
        self.assertEqual(len(sent), 2 * first_day)

    def test_hourly_cap_alerts_once_per_saturation(self):
        guard, sent, clock = make_guard(global_turns_per_hour=2, global_turns_per_day=1000)
        for _ in range(6):
            guard.admit_hosted_turn(None)
        self.assertEqual([t for t, _ in sent], ["ForeverYours demo: hourly cap reached"])
        clock.advance(3601)
        for _ in range(4):
            guard.admit_hosted_turn(None)
        self.assertEqual(len(sent), 2)

    def test_client_throttle_alerts_once_per_client_per_hour(self):
        guard, sent, clock = make_guard(client_turns_per_hour=1)
        for _ in range(5):
            guard.admit_hosted_turn("a")
        self.assertEqual(len(sent), 1)
        for _ in range(3):
            guard.admit_hosted_turn("b")
        self.assertEqual(len(sent), 2)  # a different visitor is a different alert
        clock.advance(3601)
        for _ in range(3):
            guard.admit_hosted_turn("a")
        self.assertEqual(len(sent), 3)

    def test_alert_rate_limit_holds_and_noisy_kinds_cannot_starve_budget_alerts(self):
        clock = Clock()
        sent: list = []
        alerts = OwnerAlerts(6, clock, sender=lambda t, b: sent.append(t), spawn=lambda fn: fn())
        results = [alerts.emit("client_throttled", {"turns_last_hour": n}) for n in range(5)]
        self.assertEqual(results, ["sent"] * 3 + ["suppressed"] * 2)  # noisy kinds: half the budget
        self.assertEqual([alerts.emit("hourly_cap", {"turns_last_hour": 1}) for _ in range(4)],
                         ["sent"] * 3 + ["suppressed"])
        self.assertEqual(len(sent), 6)  # never more than FY_OWNER_ALERTS_PER_HOUR
        clock.advance(3601)
        self.assertEqual(alerts.emit("hourly_cap", {"turns_last_hour": 1}), "sent")

    def test_nothing_is_sent_and_no_thread_started_unless_configured(self):
        alerts = OwnerAlerts(6, Clock(), env={})
        with patch("threading.Thread", side_effect=AssertionError("a thread was started")):
            self.assertEqual(alerts.emit("hourly_cap", {"turns_last_hour": 1}), "not_configured")
        self.assertFalse(alerts.configured())

    def test_a_failing_transport_never_raises_into_the_caller(self):
        def boom(title, body):
            raise OSError("connection refused to https://ntfy.sh/secret-topic")

        alerts = OwnerAlerts(6, Clock(), sender=boom, spawn=lambda fn: fn())
        with patch("sys.stderr") as err:
            self.assertEqual(alerts.emit("hourly_cap", {"turns_last_hour": 1}), "sent")
        logged = "".join(str(c.args[0]) for c in err.write.call_args_list)
        self.assertIn("OSError", logged)
        self.assertNotIn("secret-topic", logged)

    def test_delivery_runs_in_a_background_thread(self):
        done, where = threading.Event(), []

        def sender(title, body):
            where.append(threading.current_thread())
            done.set()

        OwnerAlerts(6, Clock(), sender=sender).emit("hourly_cap", {"turns_last_hour": 1})
        self.assertTrue(done.wait(5))
        self.assertIsNot(where[0], threading.main_thread())

    def test_webhook_is_a_plain_text_post_through_the_shared_transport(self):
        env = {"FY_OWNER_ALERT_WEBHOOK": "https://ntfy.sh/my-topic"}
        alerts = OwnerAlerts(6, Clock(), env=env, spawn=lambda fn: fn())
        with patch.object(notify, "post_http") as post:
            self.assertEqual(alerts.emit("daily_80", {"turns_today": 2400, "daily_cap": 3000}), "sent")
        url, data, headers = post.call_args.args
        self.assertEqual(url, "https://ntfy.sh/my-topic")
        self.assertIn(b"turns_today: 2400", data)
        self.assertTrue(headers["Content-Type"].startswith("text/plain"))
        self.assertIn("80%", headers["Title"])

    def test_smtp_uses_owner_specific_settings_through_the_shared_transport(self):
        env = {"FY_OWNER_ALERT_SMTP_HOST": "smtp.example.com", "FY_OWNER_ALERT_TO": "owner@example.com",
               "FY_OWNER_ALERT_SMTP_USER": "u", "FY_OWNER_ALERT_SMTP_PASSWORD": "p",
               # the caregiver channel's settings must not be read for owner alerts
               "FY_NOTIFY_SMTP_HOST": "caregiver-host.example.com"}
        alerts = OwnerAlerts(6, Clock(), env=env, spawn=lambda fn: fn())
        with patch.object(notify, "send_smtp") as smtp:
            alerts.emit("hourly_cap", {"turns_last_hour": 600})
        args = smtp.call_args.args
        self.assertEqual((args[0], args[1], args[5], args[6]), ("smtp.example.com", 587, "owner@example.com", "starttls"))

    def test_an_invalid_smtp_security_setting_falls_back_to_starttls_never_plaintext(self):
        env = {"FY_OWNER_ALERT_SMTP_HOST": "smtp.example.com", "FY_OWNER_ALERT_TO": "owner@example.com",
               "FY_OWNER_ALERT_SMTP_SECURITY": "startls"}
        alerts = OwnerAlerts(6, Clock(), env=env, spawn=lambda fn: fn())
        with patch.object(notify, "send_smtp") as smtp:
            alerts.emit("hourly_cap", {"turns_last_hour": 600})
        self.assertEqual(smtp.call_args.args[6], "starttls")

    def test_the_body_is_scrubbed_for_key_shaped_strings(self):
        sent: list = []
        alerts = OwnerAlerts(6, Clock(), sender=lambda t, b: sent.append(b), spawn=lambda fn: fn())
        with patch.dict(guardrails._EVENTS, {"hourly_cap": ("x", "token sk-abcdef123456789 leaked", False)}):
            alerts.emit("hourly_cap", {"turns_last_hour": 1})
        self.assertNotIn("sk-abcdef123456789", sent[0])

    def test_payloads_never_carry_input_text_session_ids_ips_or_client_hashes(self):
        guard, sent, _ = make_guard(
            global_turns_per_hour=2, global_turns_per_day=4, client_turns_per_hour=1,
            alert_refusals_per_hour=1)
        guard._on_space = True
        req = request("10.0.0.1", f"{GOOD_IP}, 10.0.0.1")
        key = guard.client_key(req)
        session_id = "0123456789abcdef0123456789abcdef"
        guard.input_refusal(SECRET_TEXT * 400)
        guard.input_refusal(SECRET_TEXT * 400)
        for _ in range(8):
            guard.admit_hosted_turn(key)
        guard.admit_hosted_turn(None)
        guard.admit_hosted_turn(None)
        guard.admit_hosted_turn(None)
        self.assertGreaterEqual(len(sent), 4)
        for title, body in sent:
            text = title + "\n" + body
            for forbidden in (SECRET_TEXT, session_id, GOOD_IP, key, "10.0.0.1"):
                self.assertNotIn(forbidden, text)
            self.assertRegex(body, r"Time: \d{4}-\d\d-\d\d \d\d:\d\d UTC")
            self.assertTrue(all(re.fullmatch(r"[a-z_]+: \d+|Time: .*|", line) or line == body.splitlines()[0]
                                for line in body.splitlines()), body)

    def test_each_event_is_logged_with_counts_only(self):
        guard, _, _ = make_guard(global_turns_per_hour=1)
        with patch("sys.stderr") as err:
            guard.admit_hosted_turn("secret-client-hash")
            guard.admit_hosted_turn("secret-client-hash")
        logged = "".join(str(c.args[0]) for c in err.write.call_args_list)
        self.assertIn("event=hourly_cap", logged)
        self.assertNotIn("secret-client-hash", logged)


class TestHardening(unittest.TestCase):
    def test_espeak_argv_has_double_dash_before_the_sentence(self):
        from pipeline import speak

        run = MagicMock()
        with tempfile.TemporaryDirectory() as tmp, \
             patch("sys.platform", "linux"), \
             patch("pipeline.speak._get_espeak_cli", return_value="/usr/bin/espeak-ng"), \
             patch("subprocess.run", run):
            speak._synthesize_file("--stdout hello", Path(tmp) / "out.wav", None)
        argv = run.call_args.args[0]
        self.assertEqual(argv[-2:], ["--", "--stdout hello"])

    def test_the_gradio_monitoring_dashboard_is_off_in_both_entry_points(self):
        root = Path(__file__).resolve().parent.parent
        for name in ("app.py", "webapp.py"):
            self.assertIn("enable_monitoring=False", (root / name).read_text(encoding="utf-8"), name)

    def test_driving_note_no_longer_offers_to_pass_a_message_on(self):
        from pipeline import orchestrator

        note = orchestrator.DRIVING_CONTINUATION_NOTE.format(caregiver="Sarah")
        self.assertNotIn("shall I let", note)
        self.assertIn("Could you ask Sarah for a lift instead?", note)
        self.assertIn("rule 26", note)

    def test_the_module_ships_to_the_space(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "deploy_hf_space", Path(__file__).resolve().parent.parent / "scripts" / "deploy_hf_space.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIn("guardrails.py", module.STAGE_FILES)

    def test_every_guardrail_variable_is_documented(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "guardrails.py").read_text(encoding="utf-8")
        names = set(re.findall(r"\bFY_[A-Z0-9_]+\b", source)) - {"FY_OWNER_ALERT_SMTP_"}
        self.assertIn("FY_MAX_INPUT_CHARS", names)
        for doc in (".env.example", "README.md"):
            text = (root / doc).read_text(encoding="utf-8")
            for name in sorted(names):
                self.assertTrue(name in text, f"{name} is not documented in {doc}")


if __name__ == "__main__":
    unittest.main()
