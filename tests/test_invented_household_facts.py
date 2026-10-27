"""#245: the companion must not invent household facts.

Live sessions with the sample household briefed heard "Leo is doing well in
school and has a soccer game on Saturday" and "your granddaughter Maya will
bring lunch" -- none of it in any memo. Two layers, both offline here:

- THINK rule 25 (prompt): household facts only from the briefed memory or
  what the senior said this session, with a right/wrong example.
- A deterministic guard in the orchestrator: a sentence that introduces a
  relative nobody briefed ("your granddaughter Maya") is dropped before it is
  spoken. Invented detail about a KNOWN person is left to rule 25.

Plus the grounding fix: a schedule question that also asks about a relative
("What's on for today? And how is my grandson doing?") reaches THINK with that
relative's briefed facts instead of none.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from caregiver import DEMO_MEMO, SAMPLE_FAMILY, CaregiverFlags, split_memo_facts
from memory.store import MemoryStore
from pipeline import orchestrator, think
from pipeline.orchestrator import household_corpus, unbriefed_relative, run_turn


class TestRule25InPrompt(unittest.TestCase):
    def test_rule_25_is_in_the_system_prompt_with_an_example(self):
        prompt = think.SYSTEM_PROMPT
        self.assertIn("25. HOUSEHOLD FACTS ONLY FROM THE NOTES OR THIS CONVERSATION", prompt)
        self.assertIn("Never name a person who is not in them", prompt)
        self.assertIn("never add a relative", prompt)
        self.assertIn("say plainly that you have no news about that, and ask the senior", prompt)
        self.assertIn("Small talk, feelings and general chat are still welcome", prompt)
        self.assertIn("RIGHT:", prompt)
        self.assertIn("WRONG: \"Leo is doing well in school", prompt)

    def test_rule_25_reaches_the_model_on_every_turn(self):
        msgs = think.build_prompt("How is my grandson doing?", ["His grandson is named Leo"])
        self.assertIn("HOUSEHOLD FACTS ONLY FROM THE NOTES", msgs[0]["content"])

    def test_logistical_guidance_adds_nothing_unlisted(self):
        msgs = think.build_prompt("What's on today?", [], caregiver_updates=["x"], intent="LOGISTICAL")
        self.assertIn("add no plan, visit or family news that is not listed (rule 25)", msgs[0]["content"])
        self.assertNotIn("Provide relevant family updates", msgs[0]["content"])

    def test_prompt_seeds_no_relative_outside_the_sample_household(self):
        # Rule 11's old example named a son "John" that no household has.
        self.assertNotIn("John", think.SYSTEM_PROMPT)


def _judge_corpus(transcript="How is my grandson doing?", history=None):
    return household_corpus(split_memo_facts(DEMO_MEMO), transcript, history, "Sarah")


class TestUnbriefedRelative(unittest.TestCase):
    """The deterministic guard on the judge-check household (DEMO_MEMO:
    jazz, grandson Leo, no driving, Sarah's groceries)."""

    SHOULD_DROP = [
        "Your granddaughter Maya will bring lunch.",
        "Maya, your granddaughter, is coming at noon.",
        "Your grandson Max has a soccer game on Saturday.",
        "Your granddaughter will bring over some soup.",
        "Your wife would have loved this song.",
        "Your brother called this morning.",
        "Is your granddaughter Maya coming today?",       # a named stranger, even in a question
        "Your son Tom can give you a lift.",
        "Your son will bring lunch.",                      # no son briefed; Sarah is not proof of one
        "Your daughter is coming by with groceries.",      # nor of a daughter, unless named as her
        "I don't know, but your granddaughter will call.",  # the negation is in another clause
        "I have no news about your granddaughter Maya.",   # a named stranger, even when negated
    ]
    SHOULD_KEEP = [
        "Sarah told me about your grandson Leo, but I don't have any news about how he's doing.",
        "Your grandson Leo would love to hear your stories.",
        "Your daughter Sarah is dropping off groceries at 4 PM.",
        "Sarah, your daughter, is coming by at 4 PM.",
        "I don't have any news about your wife.",           # honest, not an invention
        "There is nothing noted about your brother, Dad.",
        "Your grandchildren must keep you busy.",            # a grandson is briefed
        "Your grandson's visits sound lovely.",
        "Do you have a granddaughter too?",                  # asking is fine
        "How is your family doing today?",
        "I'm always glad to chat with you.",
        "Would you like to put on some Ella Fitzgerald?",   # small talk, no relation claimed
        "Sarah mentioned you love jazz.",
    ]

    def test_invented_relatives_are_caught(self):
        corpus = _judge_corpus()
        for s in self.SHOULD_DROP:
            with self.subTest(sentence=s):
                self.assertTrue(unbriefed_relative(s, corpus), s)

    def test_briefed_relatives_and_small_talk_pass(self):
        corpus = _judge_corpus()
        for s in self.SHOULD_KEEP:
            with self.subTest(sentence=s):
                self.assertFalse(unbriefed_relative(s, corpus), s)

    def test_what_the_senior_said_this_session_vouches(self):
        history = [{"role": "user", "content": "My granddaughter Maya is visiting next week."},
                   {"role": "assistant", "content": "How lovely."}]
        corpus = _judge_corpus("Will she bring the baby?", history)
        self.assertFalse(unbriefed_relative("Your granddaughter Maya sounds wonderful.", corpus))

    def test_a_name_the_senior_typed_in_lowercase_vouches(self):
        corpus = _judge_corpus("my granddaughter maya is visiting next week")
        self.assertFalse(unbriefed_relative("How lovely that your granddaughter Maya is visiting.", corpus))

    def test_the_companion_never_vouches_for_itself(self):
        history = [{"role": "user", "content": "Hello there."},
                   {"role": "assistant", "content": "Your granddaughter Maya says hello."}]
        corpus = _judge_corpus("Who?", history)
        self.assertTrue(unbriefed_relative("Your granddaughter Maya says hello.", corpus))

    def test_sample_family_names_are_known(self):
        texts = [t for _g, t, _p in SAMPLE_FAMILY["items"]]
        corpus = household_corpus(texts, "Hello", None, "Sarah")
        self.assertFalse(unbriefed_relative("Your grandson Leo visits on Saturday at 3 PM.", corpus))
        self.assertTrue(unbriefed_relative("Your granddaughter Maya will bring lunch.", corpus))

    def test_whole_names_are_compared(self):
        # Review findings: a hyphenated briefed name is known in full, and an
        # ordinary lowercase word ("will") never vouches for a name ("Will").
        corpus = household_corpus(["His grandson is named Jean-Luc", "Sarah will bring groceries"],
                                  "Hello", None, "Sarah")
        self.assertFalse(unbriefed_relative("Your grandson Jean-Luc loves music.", corpus))
        self.assertTrue(unbriefed_relative("Your grandson Will is coming by.", corpus))
        self.assertTrue(unbriefed_relative("Your grandson Jean is coming by.", corpus))
        corpus = household_corpus(["His granddaughter is Niamh O'Brien"], "Hello", None, "Sarah")
        self.assertFalse(unbriefed_relative("Your granddaughter O\u2019Brien called.", corpus))

    def test_lowercase_memo_names_vouch_but_function_words_do_not(self):
        corpus = household_corpus(["his grandson is named leo", "Sarah will bring groceries"], "Hello", None, "Sarah")
        self.assertFalse(unbriefed_relative("Your grandson Leo is named in the notes.", corpus))
        self.assertTrue(unbriefed_relative("Your grandson Will is coming by.", corpus))
        corpus = household_corpus(["His grandson is named Will"], "Hello", None, "Sarah")
        self.assertFalse(unbriefed_relative("Your grandson Will is named in the notes.", corpus))

    def test_possessive_names_match(self):
        corpus = _judge_corpus()
        self.assertFalse(unbriefed_relative("Your grandson Leo's name is in my notes.", corpus))
        self.assertFalse(unbriefed_relative("Your grandson Leo\u2019s stories are lovely.", corpus))
        self.assertTrue(unbriefed_relative("Your granddaughter Maya's lunch is at noon.", corpus))

    def test_addressing_the_senior_is_not_naming_a_relative(self):
        self.assertFalse(unbriefed_relative("Your grandson, Dad, sounds lovely.", _judge_corpus()))

    def test_a_question_tag_does_not_make_a_statement_a_question(self):
        corpus = _judge_corpus()
        self.assertTrue(unbriefed_relative("Your granddaughter will call later, won't she?", corpus))
        self.assertFalse(unbriefed_relative("How is your wife these days?", corpus))

    def test_no_caregiver_means_no_assumed_children(self):
        corpus = household_corpus(["Dad loves jazz"], "Hello", None, "")
        self.assertTrue(unbriefed_relative("Your daughter Sarah is coming by.", corpus))

    def test_a_briefed_daughter_vouches_for_your_daughter(self):
        corpus = household_corpus(["Sarah is his daughter and primary caregiver."], "Hello", None, "Sarah")
        self.assertFalse(unbriefed_relative("Your daughter is coming by with groceries.", corpus))
        self.assertTrue(unbriefed_relative("Your son is coming by with groceries.", corpus))


class _TurnBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.store = MemoryStore("dad", root / "data")
        for line in split_memo_facts(DEMO_MEMO):
            self.store.add(line, source="caregiver_memo", supersede=False)
        self.flags = CaregiverFlags("dad", root / "data")
        self.audio = root / "audio"
        self.audio.mkdir()
        fake_speak = lambda sentences, out: ((s, out / f"{i}.wav") for i, s in enumerate(sentences))  # noqa: E731
        for p in (patch.object(orchestrator.speak, "speak_sentences", fake_speak),
                  patch.object(orchestrator.audit, "audit_reply", return_value=("SAFE", "stub")),
                  patch.object(orchestrator.think, "extract_new_memory", return_value=None)):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def turn(self, transcript, reply, history=None):
        with patch.object(orchestrator.think, "stream_reply", return_value=iter([reply])) as stream:
            res = run_turn(transcript, self.store, self.flags, self.audio, caregiver_name="Sarah",
                           history=history, simulated_hour=10)
            if res.background_thread:
                res.background_thread.join(timeout=10)
        return res, stream


class TestGuardInRunTurn(_TurnBase):
    def test_sentence_naming_an_unbriefed_relative_is_not_spoken(self):
        res, _ = self.turn("What's happening today?",
                           "Sarah is dropping off groceries at 4 PM. Your granddaughter Maya will bring lunch.")
        self.assertIn("Sarah is dropping off groceries at 4 PM.", res.reply_text)
        self.assertNotIn("Maya", res.reply_text)
        self.assertFalse(res.is_fallback)

    def test_briefed_relative_is_spoken(self):
        reply = "Sarah told me about your grandson Leo, but I don't have any news about how he's doing."
        res, _ = self.turn("How is my grandson doing?", reply)
        self.assertEqual(res.reply_text, reply)

    def test_reply_that_was_only_invention_says_so_honestly(self):
        res, _ = self.turn("Tell me some family news.", "Your granddaughter Maya is coming with soup.")
        self.assertEqual(res.reply_text, orchestrator._UNBRIEFED_EMPTY_REPLY)
        self.assertIn("family news", res.reply_text)
        self.assertFalse(res.is_fallback)

    def test_safety_advice_is_never_dropped_for_naming_a_relative(self):
        res, _ = self.turn("Who should I ring if I feel unwell tonight?",
                           "If you feel very unwell, call 911, and your brother can help too.")
        self.assertIn("911", res.reply_text)


class TestGrounding(_TurnBase):
    def test_schedule_question_about_the_grandson_hands_think_his_fact(self):
        _res, stream = self.turn("What's on for today? And how is my grandson doing?",
                                 "Sarah is dropping off groceries at 4 PM.")
        kwargs = stream.call_args.kwargs
        self.assertEqual(kwargs["intent"], "LOGISTICAL")
        self.assertIn("His grandson is named Leo", stream.call_args.args[1])
        self.assertTrue(any("groceries" in u for u in kwargs["caregiver_updates"]))

    def test_plain_schedule_question_still_gets_no_unrelated_profile_facts(self):
        _res, stream = self.turn("What's on for today?", "Sarah is dropping off groceries at 4 PM.")
        self.assertEqual(stream.call_args.args[1], [])


if __name__ == "__main__":
    unittest.main()
