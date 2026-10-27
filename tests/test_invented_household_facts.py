"""#245: the companion must not invent household facts.

Live sessions with the sample household briefed heard "Leo is doing well in
school and has a soccer game on Saturday" and "your granddaughter Maya will
bring lunch" -- none of it in any memo. Two layers, both offline here:

- THINK rule 25 (prompt): household facts only from the briefed memory or
  what the senior said this session, with a right/wrong example.
- A deterministic guard in the orchestrator: a sentence that introduces a
  relative nobody briefed ("your granddaughter Maya") is dropped before it is
  spoken, and so is a statement about a briefed one that no memo and nothing
  the senior said grounds ("Leo is doing great at school"); a warm no-news
  line takes its place.

Plus the grounding fix: a schedule question that also asks about a relative
("What's on for today? And how is my grandson doing?") reaches THINK with that
relative's briefed facts instead of none.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from caregiver import DEMO_MEMO, SAMPLE_FAMILY, CaregiverFlags, split_memo_facts
from memory.store import MemoryStore, PrivacyLevel
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
        # No worked wrong answer: the live model spoke rule 25's old WRONG
        # example word for word ("Leo is doing well in school and has a game
        # on Saturday") in 5 of 30 replies.
        self.assertNotIn("WRONG:", prompt)
        self.assertNotIn("game on Saturday", prompt)

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
        "Your dear grandson Max is coming over.",          # an adjective does not hide the name
        "Your grandson is Max.",                           # copular forms
        "Your grandson is named Max.",
        "Your grandson's name is Max.",
        "Your grandson named Max will bring lunch.",
        "Your grandson called Max is coming today.",
        "I can't wait for your granddaughter to bring lunch.",          # a negation, but no "no news"
        "It won't be long until your granddaughter brings lunch.",
    ]
    SHOULD_KEEP = [
        "Sarah told me about your grandson Leo, but I don't have any news about how he's doing.",
        "Your grandson Leo would love to hear your stories.",
        "Your grandson is Leo.",
        "Your grandson is named Leo, and he is nine.",
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

    def test_a_negated_relation_vouches_for_nothing(self):
        corpus = _judge_corpus("I do not have a granddaughter, you know.")
        self.assertTrue(unbriefed_relative("Your granddaughter will bring lunch.", corpus))
        corpus = _judge_corpus("I have no granddaughter, but my sister has one.")
        self.assertTrue(unbriefed_relative("Your granddaughter will bring lunch.", corpus))
        corpus = _judge_corpus("I do not have a granddaughter named Maya.")
        self.assertTrue(unbriefed_relative("Your granddaughter Maya will bring lunch.", corpus))
        # The denial covers that relative's own name only, never a briefed one.
        corpus = _judge_corpus("I have no granddaughter and my grandson Leo is visiting.")
        self.assertFalse(unbriefed_relative("Your grandson Leo is visiting.", corpus))

    def test_an_unrelated_negation_does_not_hide_a_briefed_relation(self):
        corpus = household_corpus(["Dad does not drive and his son Tom gives him lifts"], "Hello", None, "Sarah")
        self.assertFalse(unbriefed_relative("Your son Tom gives you lifts.", corpus))

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

    def test_a_senior_asking_whether_he_has_a_relative_vouches_for_none(self):
        corpus = _judge_corpus("Do I have a granddaughter named Maya?")
        self.assertTrue(unbriefed_relative("Your granddaughter Maya will bring lunch.", corpus))
        corpus = _judge_corpus("Is my granddaughter Maya coming today?")  # he says he has one
        self.assertFalse(unbriefed_relative("Your granddaughter Maya is a lovely name.", corpus))

    def test_a_sentence_opener_is_not_a_name(self):
        for s in ("Well, your grandson is Leo.", "Yes, your grandson is Leo.", "Actually, your grandson is Leo.",
                  "Sorry, your grandson is named Leo.",
                  "Unfortunately, your grandson, Leo, cannot visit today.",
                  "Sadly, your grandson cannot visit.",
                  "Alas, your grandson, Leo, cannot visit today.",
                  "Oh, your daughter Sarah is coming at 4 PM."):
            with self.subTest(sentence=s):
                self.assertFalse(unbriefed_relative(s, _judge_corpus()), s)
        self.assertTrue(unbriefed_relative("Maya, your granddaughter, is coming at noon.", _judge_corpus()))

    def test_a_question_tag_does_not_make_a_statement_a_question(self):
        corpus = _judge_corpus()
        self.assertTrue(unbriefed_relative("Your granddaughter will call later, won't she?", corpus))
        self.assertFalse(unbriefed_relative("How is your wife these days?", corpus))

    def test_a_relation_bound_to_a_briefed_name_passes(self):
        corpus = household_corpus(["Dad is married to Mary."], "Hello", None, "Sarah")
        self.assertFalse(unbriefed_relative("Your wife Mary sounds lovely.", corpus))
        self.assertTrue(unbriefed_relative("Your wife sounds lovely.", corpus))  # no name, no wife briefed

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

    def test_a_pronoun_follow_up_to_a_dropped_relative_goes_too(self):
        res, _ = self.turn("Tell me some family news.",
                           "Your granddaughter Maya is visiting today. She is bringing soup for lunch. "
                           "Sarah is dropping off groceries at 4 PM.")
        self.assertEqual(res.reply_text, "Sarah is dropping off groceries at 4 PM.")

    def test_a_dropped_stranger_named_again_goes_too(self):
        res, _ = self.turn("Tell me some family news.",
                           "Your granddaughter Maya is visiting today. Sarah is dropping off groceries at 4 PM. "
                           "Maya is bringing soup for lunch.")
        self.assertEqual(res.reply_text, "Sarah is dropping off groceries at 4 PM.")

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


    def test_a_safety_turn_drops_nothing_for_naming_a_relative(self):
        res, _ = self.turn("I fell and hurt my neck.", "Don't move your neck; ask your daughter to stay with you.")
        self.assertIn("ask your daughter to stay with you", res.reply_text)

    def test_driving_plan_turn_keeps_its_lift_offer_when_all_was_dropped(self):
        res, _ = self.turn("I think I'll drive down to the shop myself this afternoon.",
                           "Your son can drive you instead.")
        self.assertNotIn("son", res.reply_text.lower().split())
        self.assertIn("lift", res.reply_text)
        self.assertNotIn("family news", res.reply_text)


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


class TestInventedFamilyDetail(unittest.TestCase):
    """A statement about a briefed family member must be grounded in a memo
    or in what the senior said (the 3-in-20 live sample and T23 on #245)."""

    MEMOS = split_memo_facts(DEMO_MEMO) + ["Dad has a check-up with Dr. Tan on Thursday at 10 AM."]

    def grounding(self, transcript="What's on for today?", history=None):
        return orchestrator.family_grounding(self.MEMOS, transcript, history, "Sarah")

    def reads(self, reply, transcript="What's on for today?", history=None):
        """Which sentences of `reply` the guard drops, as the stream sees them."""
        g, family, relative, dropped = self.grounding(transcript, history), False, False, []
        for s in orchestrator._SENTENCE_SPLIT_RE.split(reply):
            if orchestrator.invented_family_detail(s, g, family, relative):
                dropped.append(s)
            family, relative = orchestrator.family_thread(s, g, "Sarah", family, relative)
        return dropped

    def test_the_live_inventions_are_dropped(self):
        for reply, bad in [
            ("Sarah is dropping off groceries at 4 PM today. She'll also bring your favorite jazz record for you "
             "to enjoy.", "She'll also bring your favorite jazz record for you to enjoy."),
            ("As for Leo, Sarah mentioned he's doing well and enjoying school, but I don't have any new details.",
             "As for Leo, Sarah mentioned he's doing well and enjoying school, but I don't have any new details."),
            ("Sarah is dropping off groceries at 4 PM today. Leo is doing great at school and has a soccer game "
             "on Saturday.", "Leo is doing great at school and has a soccer game on Saturday."),
            ("That's wonderful to hear\u2014Leo must be so proud of his game this weekend.",
             "That's wonderful to hear\u2014Leo must be so proud of his game this weekend."),
            ("Sarah mentioned Leo is doing well in school and has a game on Saturday.",
             "Sarah mentioned Leo is doing well in school and has a game on Saturday."),
        ]:
            with self.subTest(reply=reply):
                self.assertEqual(self.reads(reply), [bad])

    def test_a_statement_with_a_question_tag_is_still_a_statement(self):
        for reply in ["Leo is doing well, isn't he?", "Leo is doing well in school, did you know?",
                      "Leo isn\u2019t feeling well.", "I'm sure he's doing well, Leo.",
                      "Leo is doing well in school, isn\u2019t he?", "Leo can't see well these days."]:
            with self.subTest(reply=reply):
                self.assertEqual(self.reads(reply), [reply])

    def test_grounded_and_honest_replies_are_kept(self):
        for reply in [
            "Sarah is dropping off groceries at 4 PM today.",
            "Sarah is stopping by this afternoon with your groceries.",
            "Today the family has plans to drop off groceries at 4 PM. That's the main family update for now.",
            "Sarah mentioned you love jazz, so maybe you'll enjoy some music later.",
            "Sarah mentioned your grandson Leo, but I don't have any news about how he's doing. "
            "Have you heard from him lately?",
            "Leo is your grandson.",
            "I hope Leo is doing well. Does he play any sport?",
            "No, Sarah isn\u2019t listening to our conversation. She only sees safety flags.",
            "I won\u2019t tell Sarah\u2014your secret is safe with me.",
            "Sarah can't read your messages.", "Sarah can\u2019t watch or listen to what we say.",
            "I've let Sarah know about the fall so she can check on you.",
            "Your appointment with Dr. Tan is on Thursday at 10 AM, so bring your list of questions.",
            "Ella Fitzgerald was a wonderful singer. She recorded so many great songs.",
            "I'm glad Sarah can help you with the ride.",
        ]:
            with self.subTest(reply=reply):
                self.assertEqual(self.reads(reply), [])

    def test_a_hyphenated_family_name_is_still_family(self):
        g = orchestrator.family_grounding(["His grandson is named Jean-Luc"], "How is Jean-Luc?", None, "Sarah")
        reply = "Jean-Luc has a soccer game on Saturday."
        self.assertTrue(orchestrator.invented_family_detail(reply, g))
        self.assertFalse(orchestrator.invented_family_detail("Jean-Luc is your grandson.", g))

    def test_the_companions_own_act_does_not_clear_a_family_claim(self):
        for reply in ["Your grandson Leo has a soccer game on Saturday, so I'll let Sarah know you asked.",
                      "Leo has a soccer game on Saturday so I\u2019ll tell Sarah."]:
            with self.subTest(reply=reply):
                self.assertEqual(self.reads(reply), [reply])
        for reply in ["I let Sarah know, and she's making sure someone can check on you.",
                      "I'll keep it just between us\u2014I won't tell Sarah about the biscuits."]:
            with self.subTest(reply=reply):
                self.assertEqual(self.reads(reply), [])

    def test_what_the_senior_said_grounds_it(self):
        reply = "Leo has a soccer game on Saturday\u2014how lovely."
        self.assertEqual(self.reads(reply), [reply])
        self.assertEqual(self.reads(reply, "Leo has a soccer game on Saturday."), [])
        history = [{"role": "user", "content": "Leo has a soccer game on Saturday."},
                   {"role": "assistant", "content": "How lovely."}]
        self.assertEqual(self.reads(reply, "What's on today?", history), [])

    def test_a_hope_or_no_news_clears_only_what_follows_it(self):
        for reply in ["Leo has cancer and I hope he feels better soon.",
                      "Leo has a soccer game and I don't know when it is."]:
            with self.subTest(reply=reply):
                self.assertEqual(self.reads(reply), [reply])

    def test_a_follow_up_with_no_subject_is_still_about_the_relative(self):
        self.assertEqual(self.reads("Leo is your grandson. Soccer practice is on Saturday."),
                         ["Soccer practice is on Saturday."])
        self.assertEqual(self.reads("Sarah is dropping off groceries at 4 PM. Jazz always lifts the spirits."), [])
        self.assertEqual(self.reads("Leo is your grandson. That must make you proud."), [])

    def test_each_name_is_bound_to_its_own_relation(self):
        g = orchestrator.family_grounding(["His grandson is named Leo and his granddaughter is named Maya"],
                                          "", None, "Sarah")
        self.assertEqual(orchestrator.asked_relatives("How is my granddaughter doing?", g, "Sarah"), ["Maya"])
        self.assertEqual(orchestrator.asked_relatives("How is my grandson doing?", g, "Sarah"), ["Leo"])

    def test_a_suggestion_to_call_the_family_is_kept(self):
        for reply in ["Please call Sarah now.", "Stay with your family until help arrives.",
                      "I know Sarah would love to hear your voice today too. Why don't you give her a call later?",
                      "You could ring Sarah this evening."]:
            with self.subTest(reply=reply):
                self.assertEqual(self.reads(reply), [])
        self.assertEqual(self.reads("Leo has a soccer game, so you could call him."),
                         ["Leo has a soccer game, so you could call him."])

    def test_a_common_word_bound_as_a_name_is_still_family(self):
        g = orchestrator.family_grounding(["His grandson is named Will"], "", None, "Sarah")
        self.assertTrue(orchestrator.invented_family_detail("Will has cancer.", g))
        self.assertFalse(orchestrator.invented_family_detail("I will play some jazz for you.", g))
        self.assertEqual(orchestrator.asked_relatives("How is my grandson doing?", g, "Sarah"), ["Will"])

    def test_they_opening_a_sentence_after_the_family_is_the_family(self):
        reply = "Sarah is dropping off groceries at 4 PM. They have booked a holiday in Spain."
        self.assertEqual(self.reads(reply), ["They have booked a holiday in Spain."])

    def test_how_the_caregiver_hears_about_safety_is_kept(self):
        g = orchestrator.family_grounding(["His grandson is named Leo"], "Is Sarah listening to us?", None, "Sarah")
        for s in ("She only gets a message if there's a safety concern.",
                  "She only receives safety alerts, nothing else.",
                  "Only safety flags reach her.",
                  "She'll only be notified if there's a safety concern."):
            self.assertFalse(orchestrator.invented_family_detail(s, g, follows_family=True), s)
        self.assertTrue(orchestrator.invented_family_detail("Sarah has an emergency at work.", g))
        for s in ("She only learns about it if there's a safety issue.",
                  "She's only told about safety matters, like a fall.",
                  "She only receives a note if I'm concerned for your safety."):
            self.assertFalse(orchestrator.invented_family_detail(s, g, follows_family=True), s)
        self.assertTrue(orchestrator.invented_family_detail("Leo has cancer and Sarah has been notified.", g))
        self.assertTrue(orchestrator.invented_family_detail("Leo only had a fall at school.", g))

    def test_a_referral_to_the_caregiver_is_kept(self):
        g = orchestrator.family_grounding(["His grandson is named Leo"], "Can I take two aspirin?", None, "Sarah")
        for s in ("Sarah or your doctor can check that with you.", "Sarah can help you with that."):
            self.assertFalse(orchestrator.invented_family_detail(s, g), s)
        self.assertTrue(orchestrator.invented_family_detail("Leo has cancer, but Sarah can help.", g))

    def test_how_is_a_name_is_a_family_question(self):
        for q in ("How is Leo?", "How\u2019s Leo?", "how's Leo"):
            self.assertTrue(orchestrator.asks_about_family(q), q)
        self.assertFalse(orchestrator.asks_about_family("How is Monday looking for the doctor?"))

    def test_a_caregiver_with_a_surname_is_family(self):
        g = orchestrator.family_grounding(["His grandson is named Leo"], "", None, "Sarah Jones")
        self.assertTrue(orchestrator.invented_family_detail("Sarah Jones has cancer.", g))
        self.assertEqual(orchestrator.family_people_in("Sarah Jones and Leo", g, "Sarah Jones"), ["Leo"])

    def test_rule_19s_own_wording_is_kept(self):
        self.assertEqual(self.reads("Sarah cannot hear our conversation."), [])

    def test_a_named_outsider_ends_the_family_thread(self):
        self.assertEqual(self.reads("Leo is your grandson. Ella Fitzgerald was a wonderful singer. "
                                    "She recorded so many great songs."), [])

    def test_a_lowercase_memo_name_is_still_family(self):
        g = orchestrator.family_grounding(["His grandson is named leo"], "How is my grandson?", None, "Sarah")
        self.assertTrue(orchestrator.invented_family_detail("Leo has cancer.", g))
        self.assertEqual(orchestrator.asked_relatives("How is my grandson doing?", g, "Sarah"), ["Leo"])

    def test_only_the_bound_name_is_the_relative(self):
        g = orchestrator.family_grounding(["His grandson Leo visits Dr. Tan on Thursday"], "", None, "Sarah")
        self.assertEqual(orchestrator.asked_relatives("How is my grandson doing?", g, "Sarah"), ["Leo"])
        for memo in ["Leo, his grandson, lives in Leeds", "Leo is his grandson", "His grandson's name is Leo"]:
            with self.subTest(memo=memo):
                g = orchestrator.family_grounding([memo], "", None, "Sarah")
                self.assertEqual(orchestrator.asked_relatives("How is my grandson doing?", g, "Sarah"), ["Leo"])

    def test_a_question_the_senior_asks_grounds_nothing(self):
        self.assertEqual(self.reads("Leo has cancer.", "Does Leo have cancer?"), ["Leo has cancer."])
        self.assertEqual(self.reads("Leo has a soccer game on Saturday.",
                                    "Is that right? Leo has a soccer game on Saturday."), [])

    def test_the_companion_never_grounds_itself(self):
        reply = "Leo has a soccer game on Saturday."
        history = [{"role": "assistant", "content": reply}]
        self.assertEqual(self.reads(reply, "Tell me more.", history), [reply])

    def test_family_questions_are_recognised(self):
        for t in ["How is my grandson doing?", "What's on for today? And how is my grandson doing?",
                  "What's happening today? I'd love to hear about the family.", "How's Leo doing?",
                  "Any news from my grandson?", "What has Leo been up to?"]:
            with self.subTest(t=t):
                self.assertTrue(orchestrator.asks_about_family(t))
        for t in ["What's on for today?", "How is the weather?", "What kind of music do I like?",
                  "What's my grandson's name?"]:
            with self.subTest(t=t):
                self.assertFalse(orchestrator.asks_about_family(t))

    def test_asked_relative_is_the_briefed_name(self):
        g = self.grounding()
        self.assertEqual(orchestrator.asked_relatives("How is my grandson doing?", g, "Sarah"), ["Leo"])
        self.assertEqual(orchestrator.asked_relatives("How's Leo doing?", g, "Sarah"), ["Leo"])
        self.assertEqual(orchestrator.asked_relatives("How is Sarah doing?", g, "Sarah"), [])
        self.assertEqual(orchestrator.asked_relatives("How is my grandson's name?", g, "Sarah"), [])


class TestDetailGuardInRunTurn(_TurnBase):
    def test_invented_detail_becomes_an_honest_no_news_line(self):
        res, _ = self.turn("What's on for today? And how is my grandson doing?",
                           "Sarah is dropping off groceries at 4 PM today. Leo is doing great at school and has a "
                           "soccer game on Saturday. Have you heard from him lately?")
        self.assertEqual(res.reply_text, "Sarah is dropping off groceries at 4 PM today. I don't have any news about "
                                         "how Leo is doing, but I'd love to hear if you have. Have you heard from "
                                         "him lately?")

    def test_the_no_news_line_is_said_once(self):
        res, _ = self.turn("How is my grandson doing?",
                           "That's wonderful to hear\u2014Leo must be so proud of his game this weekend. "
                           "I know Sarah mentioned he's been excited about it.")
        self.assertEqual(res.reply_text, orchestrator._NO_NEWS_LINE.format(name="Leo"))

    def test_a_later_no_news_sentence_is_not_said_twice(self):
        res, _ = self.turn("What's on for today? And how is my grandson doing?",
                           "Leo is doing great at school. I don't have any other news about him. "
                           "Have you heard from Leo lately?")
        self.assertEqual(res.reply_text, orchestrator._NO_NEWS_LINE.format(name="Leo")
                         + " Have you heard from Leo lately?")

    def test_invented_detail_about_the_caregiver_is_dropped_without_a_no_news_line(self):
        res, _ = self.turn("What's happening today? I'd love to hear about the family.",
                           "Sarah is dropping off groceries at 4 PM today. She'll also bring your favorite jazz "
                           "record for you to enjoy.")
        self.assertEqual(res.reply_text, "Sarah is dropping off groceries at 4 PM today.")

    def test_a_reply_that_skips_the_asked_relative_gets_the_no_news_line(self):
        res, _ = self.turn("How is my grandson doing?", "Sarah mentioned you love jazz, shall we talk about that?")
        self.assertIn("Leo", res.reply_text)
        self.assertTrue(res.reply_text.endswith(orchestrator._NO_NEWS_LINE.format(name="Leo")))

    def test_an_answer_naming_the_relation_gets_no_contradicting_line(self):
        self.store.add("Leo is recovering from surgery", source="caregiver_memo", supersede=False)
        res, _ = self.turn("How is my grandson doing?", "Your grandson is recovering from surgery.")
        self.assertEqual(res.reply_text, "Your grandson is recovering from surgery.")

    def test_a_pronoun_answer_is_about_the_asked_relative(self):
        res, _ = self.turn("How is my grandson doing?", "He's doing great at school and has a soccer game on Saturday.")
        self.assertEqual(res.reply_text, orchestrator._NO_NEWS_LINE.format(name="Leo"))
        self.store.add("Leo is recovering from surgery", source="caregiver_memo", supersede=False)
        res, _ = self.turn("How is my grandson doing?", "He's recovering from surgery.")
        self.assertEqual(res.reply_text, "He's recovering from surgery.")
        res, _ = self.turn("What's on for today? And how is my grandson doing?",
                           "Today's schedule is light. Sarah is dropping off groceries at 4 PM. "
                           "I don't have any news about Leo.")
        self.assertTrue(res.reply_text.startswith("Today's schedule is light."))

    def test_a_repeated_no_news_keeps_what_follows_its_but(self):
        res, _ = self.turn("What's on for today? And how is my grandson doing?",
                           "Leo has a soccer game on Saturday. I don't have any other news about Leo, "
                           "but Sarah is dropping off groceries at 4 PM.")
        self.assertNotIn("soccer", res.reply_text)
        self.assertIn("Sarah is dropping off groceries at 4 PM.", res.reply_text)
        self.assertEqual(res.reply_text.count("news about"), 1)

    def test_the_privacy_answer_about_the_caregiver_is_kept_in_any_words(self):
        for q, reply in (("Is Sarah listening to us?",
                          "Sarah can't hear our conversation. She'd only be contacted if your wellbeing was at risk."),
                         ("Can Sarah hear what I tell you?",
                          "She can't hear our chat. She only gets word if something urgent comes up.")):
            res, _ = self.turn(q, reply)
            self.assertEqual(res.reply_text, reply)

    def test_the_caregiver_is_checked_when_dad_asks_about_the_family_or_the_day(self):
        for q in ("Have you heard any news about my family?", "What's happening today?"):
            res, _ = self.turn(q, "Sarah has cancer.")
            self.assertNotIn("cancer", res.reply_text, q)

    def test_the_fall_follow_up_about_the_caregiver_is_kept(self):
        reply = ("I\u2019m sorry I can\u2019t reach Sarah directly, but I have let her know you fell and that "
                 "you\u2019re feeling scared. She\u2019ll be in touch soon to check on you.")
        res, _ = self.turn("Did you tell Sarah about my fall?", reply)
        self.assertEqual(res.reply_text, reply)

    def test_live_replies_that_were_dropped_though_true(self):
        mem = ["Dad loves jazz", "His grandson is named Leo", "I'm dropping off groceries at 4 PM today",
               "Dad has a check-up with Dr. Tan on Thursday at 10 AM"]
        for q, s in (("Do I have any appointments this week?",
                      "You have a check\u2011up with Dr.\u202fTan on Thursday at 10\u202fa.m. Sarah is dropping off "
                      "groceries for you today at 4\u202fp.m. Let me know if there\u2019s anything else you\u2019d like "
                      "to talk about."),
                     ("Alright, I'll wait for Sarah then.", "Great\u2014waiting for Sarah sounds like a good plan."),
                     ("Did you tell Sarah about my fall?",
                      "I\u2019ve let your family know what happened, and Sarah will be reaching out to you soon.")):
            g = orchestrator.family_grounding(mem, q, None, "Sarah")
            self.assertFalse(orchestrator.invented_family_detail(s, g), s)
        g = orchestrator.family_grounding(mem, "", None, "Sarah")
        for s in ("Leo is doing great at school.", "I've let Sarah know, and Leo has cancer.",
                  "I told Sarah, and she has a new job."):
            self.assertTrue(orchestrator.invented_family_detail(s, g), s)

    def test_the_caregiver_passing_on_the_seniors_plans_is_kept(self):
        mem = ["His grandson is named Leo", "Dad has a check-up with Dr. Tan on Thursday at 10 AM"]
        g = orchestrator.family_grounding(mem, "Do I have any appointments this week?", None, "Sarah")
        for s in ("Sarah mentioned you have an appointment with Dr.", "Sarah noted that you're scheduled to see Dr.",
                  "According to Sarah, you have a doctor's appointment with Dr.",
                  "Your daughter Sarah mentioned you've got a check-up with Dr Tan on Thursday at 10:00 a.m.",
                  "Yes, Sarah let me know you have a check-up booked with Dr."):
            self.assertFalse(orchestrator.invented_family_detail(s, g), s)
        self.assertFalse(orchestrator.invented_family_detail("Tan is on Thursday at 10:00 a.m.", g, True, False))
        for s in ("Sarah mentioned you and Leo are going fishing.", "Leo said you are his hero.",
                  "Sarah mentioned she has a new job."):
            self.assertTrue(orchestrator.invented_family_detail(s, g), s)

    def test_a_statement_with_any_tag_is_still_checked(self):
        g = orchestrator.family_grounding(["His grandson is named Leo"], "", None, "Sarah")
        for s in ("Leo has a soccer game on Saturday, remember?", "Leo has cancer, okay?",
                  "Leo has cancer, you see?", "Leo has a new puppy, as you know?"):
            self.assertTrue(orchestrator.invented_family_detail(s, g), s)
        self.assertFalse(orchestrator.invented_family_detail("Has Leo got a new puppy?", g))

    def test_what_follows_a_denial_is_still_checked(self):
        g = orchestrator.family_grounding(["His grandson is named Leo"], "", None, "Sarah")
        self.assertTrue(orchestrator.invented_family_detail("Sarah can't hear us and Leo has cancer.", g))
        self.assertFalse(orchestrator.invented_family_detail("Sarah can't hear us, and I'm always here.", g))
        self.assertFalse(orchestrator.invented_family_detail(
            "I don't have any news about Leo, but I'd love to hear if you have.", g))

    def test_the_privacy_answer_in_new_words_is_kept(self):
        reply = "No, Sarah can't hear us. She only sees brief safety alerts if something needs attention."
        res, _ = self.turn("Can Sarah hear what I tell you?", reply)
        self.assertEqual(res.reply_text, reply)

    def test_a_time_in_words_matches_the_memo(self):
        res, _ = self.turn("What's happening today?", "Sarah is dropping off groceries at four\u202fp.m. today.")
        self.assertIn("groceries", res.reply_text)

    def test_a_relative_on_a_privacy_turn_is_still_checked(self):
        res, _ = self.turn("Is Sarah listening to us?",
                           "Sarah can't hear us. Leo has a soccer game on Saturday.")
        self.assertNotIn("soccer", res.reply_text)

    def test_a_relative_the_senior_denies_is_not_family(self):
        history = [{"role": "user", "content": "I don't have a granddaughter named Maya."},
                   {"role": "assistant", "content": "Thanks for telling me."}]
        res, _ = self.turn("How is my granddaughter doing?", "I'm not sure, tell me about her!", history=history)
        self.assertNotIn("Maya", res.reply_text)

    def test_a_fact_the_senior_told_answers_the_question(self):
        history = [{"role": "user", "content": "Leo is recovering from surgery."},
                   {"role": "assistant", "content": "I'm sorry to hear that."}]
        res, _ = self.turn("How is my grandson doing?", "Recovering from surgery, as you told me.", history=history)
        self.assertNotIn("don't have any news", res.reply_text)

    def test_a_subjectless_invented_answer_is_dropped(self):
        res, _ = self.turn("How is my grandson doing?", "Recovering from cancer treatment.")
        self.assertNotIn("cancer", res.reply_text)
        self.assertIn("news about how Leo", res.reply_text)
        res, _ = self.turn("What's on for today? And how is my grandson doing?", "Today's schedule is light.")
        self.assertIn("Today's schedule is light.", res.reply_text)

    def test_a_briefed_fact_with_no_name_answers_the_question(self):
        self.store.add("Leo is recovering from surgery", source="caregiver_memo", supersede=False)
        res, _ = self.turn("How is my grandson doing?", "Recovering from surgery, according to the notes.")
        self.assertNotIn("don't have any news", res.reply_text)

    def test_a_question_without_a_question_mark_grounds_nothing(self):
        for q in ("Does Leo have cancer", "does leo have cancer", "Leo is fine. Does he have cancer"):
            g = orchestrator.family_grounding(["His grandson is named Leo"], q, None, "Sarah")
            self.assertTrue(orchestrator.invented_family_detail("Leo has cancer.", g), q)
        g = orchestrator.family_grounding(["His grandson is named Leo"], "Leo has a cold.", None, "Sarah")
        self.assertFalse(orchestrator.invented_family_detail("Leo has a cold.", g))

    def test_is_sarah_okay_is_a_family_question(self):
        for q in ("Is Sarah okay?", "Is my grandson feeling better?", "Has Leo been well?"):
            self.assertTrue(orchestrator.asks_about_family(q), q)
        self.assertFalse(orchestrator.asks_about_family("Is Sarah listening to us?"))
        res, _ = self.turn("Is Sarah okay?", "Sarah has cancer.")
        self.assertNotIn("cancer", res.reply_text)

    def test_the_word_emergency_does_not_exempt_family_news(self):
        res, _ = self.turn("How is my grandson doing?", "Leo had emergency surgery yesterday.")
        self.assertNotIn("surgery", res.reply_text)

    def test_a_typed_lowercase_name_is_a_family_question(self):
        res, _ = self.turn("how is leo doing?", "He's doing great at school and has a soccer game on Saturday.")
        self.assertNotIn("soccer", res.reply_text)
        g = orchestrator.family_grounding(["His grandson is named Will"], "", None, "Sarah")
        self.assertEqual(orchestrator.asked_relatives("how will I know how it is going?", g, "Sarah"), [])

    def test_how_is_leo_drops_an_invented_reply(self):
        res, _ = self.turn("How is Leo?", "He's doing great at school and has a soccer game on Saturday.")
        self.assertNotIn("soccer", res.reply_text)

    def test_a_pronoun_about_the_caregiver_does_not_answer_for_the_relative(self):
        res, _ = self.turn("How is my grandson doing?", "Sarah said she is dropping off groceries at 4 PM.")
        self.assertTrue(res.reply_text.endswith(orchestrator._NO_NEWS_LINE.format(name="Leo")))

    def test_family_question_reaches_think_with_the_relative_and_the_note(self):
        _res, stream = self.turn("How is my grandson doing?",
                                 "Sarah mentioned your grandson Leo, but I don't have any news about how he's doing.")
        self.assertEqual(stream.call_args.args[1][0], "His grandson is named Leo")
        self.assertIn(orchestrator._FAMILY_QUESTION_NOTE, stream.call_args.args[0])

    def test_family_news_question_gets_the_family_facts(self):
        _res, stream = self.turn("What's happening today? I'd love to hear about the family.",
                                 "Sarah is dropping off groceries at 4 PM today.")
        self.assertIn("His grandson is named Leo", stream.call_args.args[1])

    def test_a_caregiver_only_note_never_reaches_the_no_news_line(self):
        self.store.add("His granddaughter is named Maya", source="caregiver_memo", supersede=False,
                       privacy=PrivacyLevel.CAREGIVER_ONLY.value)
        res, _ = self.turn("How is my granddaughter doing?", "I don't have any news about that. How are you today?")
        self.assertNotIn("Maya", res.reply_text)

    def test_lift_offer_on_a_driving_turn_is_kept(self):
        res, _ = self.turn("I think I'll drive down to the shop myself this afternoon.",
                           "Sarah or one of the family could give you a lift instead.")
        self.assertIn("Sarah or one of the family could give you a lift instead.", res.reply_text)

    def test_plain_question_gets_no_family_note(self):
        _res, stream = self.turn("What's on for today?", "Sarah is dropping off groceries at 4 PM.")
        self.assertNotIn(orchestrator._FAMILY_QUESTION_NOTE, stream.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
