"""Tests for safety fast-path triggers, invariants, and normalization."""
import unittest

from safety import fastpath


class TestFastPath(unittest.TestCase):
    def test_distress_triggers(self):
        cases = [
            "I fell down earlier and I'm scared",
            "Help me, I can't get up",
            "I have bad chest pain",
            "My chest hurts so much",
            "I'm dizzy and nauseous",
            "Call 911 right now",
            "I am bleeding from my hand",
            "Help me!",
            "Please help me",
            "Someone help me!",
            "Help me up",
            "Call for help",
            "Help, I'm scared",
            "help I am so scared",
            "Help! I'm terrified",
            # #51: the most natural way a senior says this, plus dash variants
            # that ASR/LLM punctuation produces
            "Help me, I'm scared",
            "help me I'm scared",
            "I'm lying on the floor and it hurts",
            "  help  ",
            "  can someone help me  ",
            "help me? I'm scared",
            "help—I'm frightened",
            "help - I'm frightened",
            "Help – I'm frightened",
            # #55 Criterion 1: "cannot" must fire like "can't"
            "I cannot get up",
            "I have fall",
            "I cannot breathe",
            # #55 Criterion 2 (option A): a bare plea that is the whole message
            "help",
            "Help!",
            "Help!!",
            # #55 Criterion 3: on/hit the floor + a distress co-token, either order
            "I'm on the floor and I can't move",
            "I'm stuck on the floor",
            "I hit the floor and can't get up",
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertTrue(res.triggered, f"Expected '{phrase}' to trigger fast-path")
                self.assertEqual(res.severity, "distress")
                self.assertIsNotNone(res.immediate_reply)
                self.assertIn("notifying their family", res.continuation_note)
                # Explicit falls carry the fall wording (TestFallReply below),
                # chest pain / breathing / bleeding / 911 the medical one;
                # every other distress phrase the generic one.
                self.assertIn(
                    res.caregiver_flag,
                    (fastpath.CAREGIVER_FLAG_TEXT["distress"], fastpath.CAREGIVER_FLAG_TEXT["fall"],
                     fastpath.CAREGIVER_FLAG_TEXT["medical"], fastpath.CAREGIVER_FLAG_TEXT["down_unable"]),
                )

    def test_physical_emergency_reply_says_911_not_988(self):
        # A medical emergency needs 911, not the 988 crisis line: a caregiver
        # flag is a notification, not a 911 call, so the senior is told to call.
        cases = [
            "I can't breathe",
            "I cannot breathe",
            "I have bad chest pain",
            "My chest hurts so much",
            "I am bleeding from my hand",
            "Call 911 right now",
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertTrue(res.triggered)
                self.assertEqual(res.severity, "distress")
                self.assertIn("911", res.immediate_reply)
                self.assertNotIn("988", res.immediate_reply)

    def test_mixed_crisis_and_physical_emergency_says_988_and_911(self):
        # Crisis wins the severity and the flag; the reply carries both numbers.
        for phrase in ("I want to die and I can't breathe. Call 911.",
                       "I can't breathe and I want to die."):
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertEqual(res.severity, "crisis")
                self.assertIn("988", res.immediate_reply)
                self.assertIn("911", res.immediate_reply)
                self.assertTrue(res.caregiver_flag.startswith("URGENT CRISIS:"))
        # A crisis-only report still names 988 alone.
        res = fastpath.check("I want to die")
        self.assertIn("988", res.immediate_reply)
        self.assertNotIn("911", res.immediate_reply)

    def test_conversational_help_requests_do_not_trigger(self):
        # Issue #15: conversational help requests must NOT trigger emergency distress
        cases = [
            "Can you help me remember my grandson's name?",
            "Help me understand what time Sarah is coming",
            "Help me find my reading glasses",
            "Help me choose what music to listen to",
            "Can you help me with this puzzle?",
            "Could you help me look for my coat?",
            "I think I'm falling asleep in front of the TV",
            "I'm scared of thunderstorms",
            "Does that help? I'm scared of the dark",
            "That helps, I'm scared less now",
            "Help me understand why I'm scared of storms",
            # #51 Criterion 3: allowing "me" must not make task- or
            # memory-requests look like distress
            "help me remember Leo's birthday",
            "Help me pay the electricity bill, please",
            # #55 Criterion 2 near-misses: embedded "help" must stay silent
            "that was a big help!",
            "I need help with the crossword",
            # #55 Criterion 3 near-misses: benign floor use must stay silent
            "I'm on the floor watching telly",
            "I'm sitting on the floor doing a puzzle",
            "the baby is on the floor",
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertFalse(res.triggered, f"Conversational request '{phrase}' should not trigger emergency distress")
                self.assertEqual(res.severity, "none")
                self.assertIsNone(res.caregiver_flag)

    def test_unicode_curly_quotes_normalization(self):
        # Curly apostrophes from phone keyboard or ASR
        res = fastpath.check("I’m dizzy")
        self.assertTrue(res.triggered)
        self.assertEqual(res.severity, "distress")

    def test_dashes_are_folded_before_matching(self):
        # #51: a dash between words is punctuation, not a word. Every dash
        # variant collapses to a space so no rule has to enumerate them.
        for dash in ("—", "–", "―", "‐", "‑", "−"):
            with self.subTest(dash=repr(dash)):
                self.assertEqual(fastpath._normalize(f"help{dash}I'm frightened"), "help i'm frightened")
        # ASCII hyphen and curly quotes still normalize as before
        self.assertEqual(fastpath._normalize("Help–I’m hurt"), "help i'm hurt")

    def test_confusion_triggers(self):
        cases = [
            "Where am I right now?",
            "I don't know where I am",
            "I don't know what day it is",
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertTrue(res.triggered, f"Expected '{phrase}' to trigger confusion")
                self.assertEqual(res.severity, "confusion")
                self.assertIn("You're safe", res.immediate_reply)
                self.assertIn("Possible confusion", res.caregiver_flag)

    def test_confusion_reply_discloses_family_sharing(self):
        # The orchestrator marks every fast-path flag disclosed_to_senior=True once
        # the reply is spoken, so the confusion reply must actually say the family
        # will be told -- otherwise the caregiver panel's "Dad was told" is false.
        cases = [
            "Where am I right now?",
            "I don't know where I am",
            "I don't know what day it is",
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertEqual(res.severity, "confusion")
                self.assertIn("family", res.immediate_reply.lower())
                self.assertIn("You're safe", res.immediate_reply)
                # THINK is told it already said so, so the continuation doesn't repeat it.
                self.assertIn("family", res.continuation_note.lower())
                self.assertIn("don't repeat", res.continuation_note.lower())

    def test_neutral_phrases_do_not_trigger(self):
        cases = [
            "I really love jazz music",
            "What is my grandson's name?",
            "It is sunny outside today",
            "Let's talk about Miles Davis",
            "I had a nice breakfast this morning",
            "I fell asleep in my chair earlier",
            "I'm exhausted after gardening",
            "I love the fall weather",
            "Today was an awful day",
            "I'm tired after a long walk",
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertFalse(res.triggered, f"Neutral phrase '{phrase}' should not trigger")
                self.assertEqual(res.severity, "none")
                self.assertIsNone(res.immediate_reply)
                self.assertIsNone(res.continuation_note)
                self.assertIsNone(res.caregiver_flag)

    def test_crisis_triggers(self):
        cases = [
            "I don't want to be here anymore",
            "I want to die",
            "Everyone would be better off without me",
            "I wish I was dead",
            "I wanna die",
            "I wish I were dead",
            "I'd be better off dead",
            "I want to kill myself",
            "I'm going to end my life",
            "I am suicidal",
            "I do not want to live",
            "I want to end it all",
            "I want to take my own life",
            "Life isn't worth living",
            "suicide is the only way",
            "I can't take this anymore, I just want it to be over. I want to die.",
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertTrue(res.triggered, f"Expected '{phrase}' to trigger crisis")
                self.assertEqual(res.severity, "crisis")
                self.assertIn("988", res.immediate_reply)
                self.assertIn("URGENT CRISIS:", res.caregiver_flag)

    def test_crisis_guard_phrases(self):
        # These should NOT trigger crisis because of the guard
        benign_cases = [
            "I'm so tired I could die",
            "That cake is to die for",
            "I was laughing so hard",
        ]
        for phrase in benign_cases:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertFalse(res.triggered, f"Expected '{phrase}' to NOT trigger crisis")
                
        # But if a real crisis phrase is in a separate clause, it MUST trigger
        mixed_cases = [
            "That cake is to die for. Honestly I want to die.",
            "I was laughing so hard! But seriously, I want to kill myself.",
            "I'm so tired I could die... I wish I was dead.",
            "That cake is to die for, and I want to die.",
            "I was laughing so hard, I want to kill myself.",
            "I'm so tired I could die: I wish I was dead.",
            "That cake is to die for\nand I want to die.",
        ]
        for phrase in mixed_cases:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertTrue(res.triggered, f"Expected '{phrase}' to trigger crisis despite the guard")
                self.assertEqual(res.severity, "crisis")

    def test_crisis_precedence_over_distress(self):
        # Issue #105: Crisis should take precedence if both are present
        phrase = "I fell down and I can't get up, I want to die"
        res = fastpath.check(phrase)
        self.assertTrue(res.triggered)
        self.assertEqual(res.severity, "crisis")

    def test_caregiver_flag_is_content_minimized(self):
        # The caregiver flag is a FIXED description of the trigger
        # category, never a copy of what the senior said. The panel is a
        # caregiver-visible surface, so a flag that quotes the utterance turns
        # it into a transcript leak ("I fell. Also please keep my bank PIN
        # 1234 private" -> both sentences on the caregiver's screen).
        # (severity, flag wording key, utterance): an explicit fall keeps
        # severity "distress" but has its own fixed wording.
        cases = [
            ("crisis", "crisis", "I want to die, and please keep my bank PIN 1234 private"),
            ("distress", "fall", "I fell. Also please keep my bank PIN 1234 private"),
            ("distress", "distress", "I can't get up. Also please keep my bank PIN 1234 private"),
            ("confusion", "confusion", "Where am I? My bank PIN is 1234"),
        ]
        for severity, wording, utterance in cases:
            with self.subTest(severity=severity):
                res = fastpath.check(utterance)
                self.assertTrue(res.triggered, f"Expected '{utterance}' to trigger")
                self.assertEqual(res.severity, severity)

                flag = res.caregiver_flag
                self.assertIsNotNone(flag)
                # The leak checks come FIRST so a regression fails on the leak
                # itself, not on a missing constant.
                self.assertNotIn("1234", flag)
                self.assertNotIn("PIN", flag)
                self.assertNotIn(utterance.strip(), flag)
                # ... and the flag is exactly the fixed text for this category.
                self.assertEqual(flag, fastpath.CAREGIVER_FLAG_TEXT[wording])



class TestFallReply(unittest.TestCase):
    """An explicit fall report gets its own reply (are you hurt, can you get up
    safely) and flag wording; ambiguous or non-fall distress keeps the generic
    reply. Severity stays "distress" either way."""

    FALLS = [
        "I fell down earlier and I'm scared",
        "I fell down",
        "I've had a fall",
        "I have fall",
        "I've fallen in the kitchen",
        "I'm falling",
        "I fell out of bed",
        "I fell forward onto the floor",
        "I had a nasty fall",
        "I took a bad fall",
    ]
    GENERIC = [
        "I can't get up",
        # Triggers, but does not establish that he fell himself.
        "My grandson fell off his bike",
        "I fell in love with jazz",
        "I fell out with my brother",
        "The vase is falling over",
        "I feel very unwell and I'm hurt",
        "Help me, I'm scared",
    ]
    GENERIC_REPLY = (
        "I hear you, and I'm taking this seriously. "
        "I'm letting your family know right now so someone can check on you. "
        "I'll only tell them if I'm worried about your safety."
    )

    def test_fall_reply_asks_hurt_and_get_up_safely(self):
        for phrase in self.FALLS:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertTrue(res.triggered)
                self.assertEqual(res.severity, "distress")
                reply = res.immediate_reply.lower()
                self.assertIn("are you hurt?", reply)
                self.assertIn("can you get up safely?", reply)
                self.assertIn("letting your family know right now", reply)
                self.assertIn("reported a fall", res.caregiver_flag.lower())
                self.assertEqual(res.caregiver_flag, fastpath.CAREGIVER_FLAG_TEXT["fall"])

    def test_untimed_fall_flag_makes_no_time_claim(self):
        res = fastpath.check("I fell down")
        self.assertNotIn("earlier", res.caregiver_flag.lower())
        self.assertNotIn("today", res.caregiver_flag.lower())

    def test_fall_continuation_quotes_the_utterance_and_follows_up_on_injury(self):
        res = fastpath.check("I fell down earlier and I'm scared")
        note = res.continuation_note
        # The THINK note carries the quoted utterance; the caregiver flag does not.
        self.assertIn('"I fell down earlier and I\'m scared"', note)
        self.assertNotIn("I fell down earlier", res.caregiver_flag)
        self.assertIn("already asked whether they are hurt", note)
        self.assertIn("don't repeat", note)
        self.assertIn("injury", note)
        self.assertIn("safe to get up", note)

    def test_non_fall_distress_keeps_the_generic_text(self):
        for phrase in self.GENERIC:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertTrue(res.triggered)
                self.assertEqual(res.severity, "distress")
                self.assertEqual(res.immediate_reply, self.GENERIC_REPLY)
                self.assertNotIn("hurt", res.immediate_reply.lower())
                self.assertNotIn("get up", res.immediate_reply.lower())
                self.assertEqual(res.caregiver_flag, fastpath.CAREGIVER_FLAG_TEXT["distress"])


class TestDownAndUnableToCall(unittest.TestCase):
    """#242: a senior who is down and cannot summon help is a physical
    emergency. The fast path answers it with the medical alert button and 911,
    raises the caregiver flag, and never names 988."""

    POSITIVES = [
        "I'm on the floor and can't reach the phone",
        "I’m on the floor and can’t reach the phone.",
        "I fell and I can't get to the phone",
        "I've been on the floor for hours",
        "I've been lying on the floor since last night",
        "I'm down here and I can't get up",
        "I fell down and I can't get up",
        "I hit the floor and can't get up",
        "I'm on the floor and I can't move",
        "I've fallen and I can't call anyone",
        "I had a fall and I cannot reach my phone",
        "I can't reach my phone, I'm on the floor",
        "I'm on the ground in the garden and can't call for help",
        "Help, I fell in the bathroom and I can't reach the telephone",
        # #244: stuck on the floor is the same situation as being unable to get up.
        "I'm stuck on the floor",
        "I am stuck on the floor",
        "I\u2019m stuck on the floor.",
        "I'm stuck on the floor again",
        "I'm really stuck on the floor",
        "I got stuck on the floor",
        "I've been stuck on the floor",
        "I'm stuck on the bathroom floor",
        "I'm stuck on the ground",
        "I'm trapped on the floor",
        "I'm stuck here on the floor",
        "Help, I'm stuck on the floor",
        "Stuck on the floor",
    ]
    NEGATIVES = [
        "I'm on the floor watching telly",
        "I'm sitting on the floor doing a puzzle",
        "I can't reach the phone charger from the sofa",
        "I can't reach the phone, it's on the top shelf",
        "I dropped my phone on the floor and can't reach it",
        "I fell asleep and can't find my phone",
        "I spent hours on the floor doing a puzzle with Leo",
    ]

    def test_positives_get_the_911_reply_and_flag_and_never_988(self):
        for phrase in self.POSITIVES:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertTrue(res.triggered)
                self.assertEqual(res.severity, "distress")
                self.assertTrue(res.calls_911)
                self.assertEqual(res.immediate_reply, fastpath.DOWN_UNABLE_REPLY)
                self.assertIn("911", res.immediate_reply)
                self.assertIn("medical alert", res.immediate_reply)
                self.assertIn("letting your family know right now", res.immediate_reply)
                self.assertNotIn("988", res.immediate_reply)
                self.assertNotIn("get up safely", res.immediate_reply)
                self.assertEqual(res.caregiver_flag, fastpath.CAREGIVER_FLAG_TEXT["down_unable"])
                self.assertNotIn("988", res.caregiver_flag)
                note = res.continuation_note
                self.assertIn("never mention 988", note)
                self.assertIn("don't repeat", note)

    # #244: not a person stuck on the ground. These may still trigger the
    # generic distress reply through older rules; they must not get the 911 one.
    STUCK_NEGATIVES = [
        "I'm stuck on the second floor",
        "I'm stuck on the ground floor",
        "I'm stuck on the top floor",
        "I'm stuck on the floor plan",
        "I'm stuck on the floor puzzle",
        "The drawer is stuck on the floor",
        "My grandson is stuck on the floor",
    ]

    def test_stuck_on_floor_negatives_do_not_get_the_911_reply(self):
        for phrase in self.STUCK_NEGATIVES:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertFalse(res.calls_911)
                self.assertNotEqual(res.immediate_reply, fastpath.DOWN_UNABLE_REPLY)

    def test_down_place_allows_a_room_word(self):
        # #280: a room word before "floor" is the same emergency.
        for phrase in ("I'm lying on the kitchen floor and I can't get up.",
                       "I'm on the bathroom floor, can't reach the phone.",
                       "I've been lying on the hallway floor since last night.",
                       "I can't get up off my bedroom floor, I'm on the bedroom floor."):
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertEqual(res.immediate_reply, fastpath.DOWN_UNABLE_REPLY)
                self.assertIn("911", res.immediate_reply)
                self.assertNotIn("988", res.immediate_reply)

    def test_a_room_floor_alone_is_still_a_near_miss(self):
        for phrase in ("I'm on the kitchen floor cleaning the tiles.",
                       "The cat is asleep on the bathroom floor."):
            with self.subTest(phrase=phrase):
                self.assertNotEqual(fastpath.check(phrase).immediate_reply, fastpath.DOWN_UNABLE_REPLY)

    def test_stuck_on_floor_is_not_the_generic_or_fall_reply(self):
        res = fastpath.check("I'm stuck on the floor")
        self.assertEqual(res.immediate_reply, fastpath.DOWN_UNABLE_REPLY)
        self.assertIn("911", res.immediate_reply)
        self.assertNotIn("988", res.immediate_reply)

    def test_judge_turns_keep_their_replies(self):
        # The generic fall reply stays for a past fall with no 911 cue.
        res = fastpath.check("I fell down earlier and I'm scared")
        self.assertIn("Are you hurt?", res.immediate_reply)
        self.assertFalse(res.calls_911)
        # The floor-and-phone reply stays.
        res = fastpath.check("I'm on the floor and can't reach the phone")
        self.assertEqual(res.immediate_reply, fastpath.DOWN_UNABLE_REPLY)

    def test_exact_issue_phrase(self):
        res = fastpath.check("I'm on the floor and can't reach the phone")
        self.assertTrue(res.triggered)
        self.assertIn("911", res.immediate_reply)
        self.assertNotIn("988", res.immediate_reply + res.continuation_note.replace("never mention 988", ""))

    def test_benign_near_misses_do_not_get_the_911_reply(self):
        for phrase in self.NEGATIVES:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertFalse(res.calls_911)
                self.assertNotEqual(res.immediate_reply, fastpath.DOWN_UNABLE_REPLY)
                self.assertFalse(res.triggered, phrase)

    def test_crisis_with_down_and_unable_keeps_988_and_adds_911(self):
        res = fastpath.check("I'm on the floor and can't reach the phone and I want to die")
        self.assertEqual(res.severity, "crisis")
        self.assertIn("988", res.immediate_reply)
        self.assertIn("911", res.immediate_reply)

    def test_flag_is_fixed_text(self):
        res = fastpath.check("I'm on the floor and can't reach the phone. My PIN is 1234")
        self.assertEqual(res.caregiver_flag, fastpath.CAREGIVER_FLAG_TEXT["down_unable"])
        self.assertNotIn("1234", res.caregiver_flag)

    def test_other_911_replies_are_marked_and_other_distress_is_not(self):
        self.assertTrue(fastpath.check("I have chest pain").calls_911)
        self.assertFalse(fastpath.check("I fell down earlier and I'm scared").calls_911)
        self.assertFalse(fastpath.check("I can't get up").calls_911)
        self.assertFalse(fastpath.check("I want to die").calls_911)


class TestPhysicalEmergencyNegatives(unittest.TestCase):
    """#211: figurative or unrelated uses of the emergency words never get the
    911 reply, and a mixed report names both numbers in either order."""

    NEGATIVES = [
        "My heart is full",
        "I could breathe easier now",
        "I like bleeding hearts in the garden",
        "Bleeding hearts",
        "I can breathe again",
        "He called 911 last year about the neighbour's fire",
    ]

    def test_negatives_do_not_get_the_911_reply(self):
        for phrase in self.NEGATIVES:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertFalse(res.calls_911)
                self.assertNotEqual(res.immediate_reply, fastpath.PHYSICAL_EMERGENCY_REPLY)

    def test_each_physical_phrase_says_911_and_never_988(self):
        for phrase in ("I can't breathe", "I have bad chest pain", "I am bleeding", "Call 911"):
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertEqual(res.severity, "distress")
                self.assertTrue(res.calls_911)
                self.assertIn("911", res.immediate_reply)
                self.assertNotIn("988", res.immediate_reply)
                self.assertEqual(res.caregiver_flag, fastpath.CAREGIVER_FLAG_TEXT["medical"])

    def test_mixed_report_in_either_order_names_988_and_911(self):
        for phrase in ("I want to die and I can't breathe",
                       "I can't breathe and I want to die",
                       "My chest hurts. I want to kill myself."):
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertEqual(res.severity, "crisis")
                self.assertIn("988", res.immediate_reply)
                self.assertIn("911", res.immediate_reply)


class TestCrisisContinuationNote(unittest.TestCase):
    def test_crisis_note_forbids_repeating_hotline_and_apology(self):
        res = fastpath.check("I want to die")
        self.assertEqual(res.severity, "crisis")
        # The canned reply keeps its hotline and apology ...
        self.assertIn("988", res.immediate_reply)
        self.assertIn("sorry", res.immediate_reply.lower())
        # ... and the THINK note says both were given and must not be repeated.
        note = res.continuation_note
        self.assertIn("Do NOT repeat the 988 number or any hotline", note)
        self.assertIn("do NOT apologize or say sorry again", note)


class TestFallLongTail(unittest.TestCase):
    """#198: falls phrased outside the canonical words. Each new pattern has a
    positive and a near-miss negative; benign idioms must stay quiet."""

    POSITIVES = [
        "I hit the floor",
        "I just hit the floor in the bathroom",
        "My legs just gave way on the stairs",
        "my knees gave out in the kitchen",
        "I went down in the garden and I can't put any weight on my ankle",
        "I went down on the stairs",
        "I went down in the kitchen",
        "I hit the floor",
    ]
    NEAR_MISSES = [
        "The price of tea hit the floor",
        "I hit the floor running with the cleaning this morning",
        "The ball hit the floor and rolled under the sofa",
        "The old table legs gave way to a newer set",
        "My patience gave out waiting for the post",
        "I went down to the shops this morning",
        "I went down the stairs to put the kettle on",
        "I went down to the garden to water the roses",
        "my knees gave out on that hike years ago",
        "my knees gave out when I was young",
        "my legs gave way to a nicer pair",
        "I went down in the basement to get the jam",
        "I went down on the bus to town",
        "I went down in the lift",
        "I went down in the world",
        "I hit the floor laughing",
        "I just hit the floor mat for the dog",
        "I went down in the garden to water the roses",
    ]

    def test_new_phrasings_trigger_distress(self):
        for phrase in self.POSITIVES:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertTrue(res.triggered)
                self.assertEqual(res.severity, "distress")

    def test_near_misses_do_not_trigger(self):
        for phrase in self.NEAR_MISSES:
            with self.subTest(phrase=phrase):
                self.assertFalse(fastpath.check(phrase).triggered)


class TestEveryBranchDiscloses(unittest.TestCase):
    """Invariant: every triggering fast-path branch tells the senior the family
    will be told. pipeline/orchestrator.py records each fast-path flag with
    disclosed_to_senior=True once the immediate reply is spoken, so a branch whose
    reply does not say so would make the caregiver panel claim "Dad was told"
    falsely. A new branch needs a representative phrase here."""

    # One representative phrase per triggering branch -> expected severity.
    BRANCH_PHRASES = {
        "crisis": ("I want to die", "crisis"),
        "fall": ("I fell down", "distress"),
        "distress": ("Help me, I'm scared", "distress"),
        "medical": ("I can't breathe", "distress"),
        "crisis_and_medical": ("I want to die and I can't breathe", "crisis"),
        "confusion": ("Where am I?", "confusion"),
    }

    def test_every_triggering_branch_discloses_family_sharing(self):
        for branch, (phrase, severity) in self.BRANCH_PHRASES.items():
            with self.subTest(branch=branch, phrase=phrase):
                res = fastpath.check(phrase)
                self.assertTrue(res.triggered, f"Expected '{phrase}' to trigger")
                self.assertEqual(res.severity, severity)
                self.assertIsNotNone(res.caregiver_flag)
                self.assertIn("family", res.immediate_reply.lower())

    def test_fall_phrase_takes_the_fall_branch(self):
        # Guards the table above: the fall phrase must hit the fall reply, not
        # the generic distress one, or the fall branch goes unchecked.
        res = fastpath.check(self.BRANCH_PHRASES["fall"][0])
        self.assertEqual(res.caregiver_flag, fastpath.CAREGIVER_FLAG_TEXT["fall"])

    def test_medical_phrase_takes_the_medical_branch(self):
        res = fastpath.check(self.BRANCH_PHRASES["medical"][0])
        self.assertEqual(res.caregiver_flag, fastpath.CAREGIVER_FLAG_TEXT["medical"])


class TestDrivingPlan(unittest.TestCase):
    """A senior's plan to drive himself is detected by the pure seam
    fastpath.driving_plan (the orchestrator gives THINK a lift-first note and
    records a disclosed low-severity note); a past mention is not a plan."""

    PLAN = "I think I'll drive down to the shop myself this afternoon"

    def test_plans_to_drive_are_detected(self):
        for t in (self.PLAN, "I think I will drive down to the shop myself this afternoon",
                  "I will drive", "I'll drive", "I\u2019ll drive",
                  "I think I\u2019ll drive down to the shop myself this afternoon",
                  "I'm going to drive to the bank", "I am driving to the shop this afternoon",
                  "I'm planning to drive to the shop this afternoon",
                  "I will happily drive myself to the shop",
                  "I am going to drive to the shop like I did years ago",
                  "I decided to drive to the shop", "I fancy driving to the shop this afternoon",
                  "Sarah offered to drive me, but I'll drive myself.",
                  "I'm going to drive to the shop and Sarah can drive me home",
                  "I'm going to go and drive to the shop",
                  "I'm not tired and I'll drive to the shop",
                  "I don't drive at night and I'll drive to the shop this afternoon"):
            self.assertTrue(fastpath.driving_plan(t), t)

    def test_past_negated_and_other_people_are_not(self):
        for t in ("I used to drive a bus", "I used to drive a bus for the council",
                  "I don't drive anymore, I gave it up.", "I never drive at night",
                  "Can Sarah drive to the shop for me?", "Alright, I'll wait for Sarah then.",
                  "Leo is learning to drive", "I remember driving to the shop with my dad.",
                  "I loved driving a bus when I was younger.", "I watched Sarah drive to the shop.",
                  "I drove to work for forty years", "I'm driving myself crazy with this crossword",
                  "I'm not driving today", "I want Sarah to drive me to the shop",
                  "I'll ask Sarah to drive me", "I don't think I'll drive today",
                  "I won't be driving to the shop", ""):
            self.assertFalse(fastpath.driving_plan(t), t)

    def test_driving_is_not_an_emergency(self):
        # No canned line, no alert: the fast path itself does not trigger.
        res = fastpath.check(self.PLAN)
        self.assertFalse(res.triggered)

    def test_note_is_low_severity_and_content_free(self):
        self.assertEqual(fastpath.DRIVING_FLAG_SEVERITY, "note")
        text = fastpath.CAREGIVER_FLAG_TEXT["driving"]
        self.assertIn("mentioned driving", text)
        self.assertNotIn("URGENT", text)
        self.assertNotIn("shop", text)  # never quotes the utterance


class TestIndirectGoodbyes(unittest.TestCase):
    """#199, ADR-013 amended: unambiguous indirect goodbyes get the canned 988
    reply and the disclosed CRISIS flag before the model speaks. Live, "I've said
    my goodbyes. I'm ready to go now." was answered with "take all the time you
    need" and no check-in until the AUDIT pass flagged it a turn late."""

    POSITIVES = [
        "I've said my goodbyes. I'm ready to go now.",
        "I have said my goodbyes.",
        "I've said all my goodbyes",
        "I made my final goodbyes.",
        "This is goodbye.",
        "This is my goodbye.",
        "this is my last goodbye",
        "I won't be here much longer.",
        "I won\u2019t be around much longer",
        "I will not be around much longer.",
        "I'm not going to be here much longer.",
        "I've put my affairs in order.",
        "I'm getting my affairs in order",
        "I'm giving my things away.",
        "I've been giving away all my stuff",
        "I'm ready to leave this world.",
        # "ready to go" beside a first-person goodbye or death context
        "I've had a good life. I'm ready to go.",
        "My time has come. I'm ready to go now.",
        "I'm dying, and I'm ready to go.",
    ]
    NEAR_MISSES = [
        "I'm ready to go to the shops.",
        "I'm ready to go to the shop now",
        "I'm ready to go home.",
        "I'm ready to go for a walk.",
        "I said goodbye to Sarah at the door.",
        "I said my goodbyes to Sarah at the door.",
        "My friend said her goodbyes at the funeral.",
        "My friend said her goodbyes at the funeral. I'm ready to go home.",
        "This is goodbye for now, see you tomorrow.",
        "The dog won't be here much longer, the vet takes him tomorrow.",
        "I'm giving my things to charity.",
        "I'm giving away my old books to the library.",
        # a bare "ready to go" is the ADR-013 backstop example, left to AUDIT
        "I'm ready to go now.",
    ]

    def test_indirect_goodbyes_trigger_the_crisis_reply(self):
        for phrase in self.POSITIVES:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertTrue(res.triggered)
                self.assertEqual(res.severity, "crisis")
                self.assertIn("988", res.immediate_reply)
                self.assertTrue(res.caregiver_flag.startswith("URGENT CRISIS:"))

    def test_near_misses_do_not_trigger(self):
        for phrase in self.NEAR_MISSES:
            with self.subTest(phrase=phrase):
                self.assertFalse(fastpath.check(phrase).triggered)

    def test_a_real_crisis_beside_a_benign_goodbye_still_fires(self):
        res = fastpath.check("I said my goodbyes to Sarah at the door. I want to die.")
        self.assertEqual(res.severity, "crisis")


if __name__ == "__main__":
    unittest.main()


class TestSoftFallsAndOverdoseIntent(unittest.TestCase):
    """Live probes on 2026-10-30: "I took a tumble earlier." reached only the AUDIT
    backstop, and a plan to take all one's pills had no crisis rule."""

    def test_softened_first_person_falls_get_the_fall_reply(self):
        for phrase in ("I took a tumble earlier.", "I've had a bit of a fall in the garden, nothing serious I think.",
                       "I had a wee tumble on the stairs.", "I had a small fall this morning."):
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertEqual(res.severity, "distress")
                self.assertIn("hurt", res.immediate_reply.lower())

    def test_tumble_near_misses_stay_calm(self):
        for phrase in ("I took a tumble dryer to the tip.", "The cat took a tumble off the sofa.",
                       "I watched a tumble dryer advert."):
            with self.subTest(phrase=phrase):
                self.assertEqual(fastpath.check(phrase).severity, "none")

    def test_overdose_intent_is_crisis(self):
        for phrase in ("I want to take all my pills.", "I'm thinking about taking all my sleeping pills.",
                       "I might just swallow all my tablets."):
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertEqual(res.severity, "crisis")
                self.assertIn("988", res.immediate_reply)

    def test_ordinary_medicine_talk_is_not_crisis(self):
        for phrase in ("Can I take all my pills tonight?", "I take all my pills with breakfast.",
                       "Sarah sorts all my pills into the box."):
            with self.subTest(phrase=phrase):
                self.assertNotEqual(fastpath.check(phrase).severity, "crisis")


class TestSlipsAndFootingAreFalls(unittest.TestCase):
    """The 10-30 Known-limitations examples ("I slipped in the bathroom", "I ended up on the
    rug") are first-person fall reports and get the fall reply; idioms stay calm."""

    def test_slips_and_footing_get_the_fall_reply(self):
        for phrase in ("I slipped in the bathroom this morning.", "I slipped on the ice.",
                       "I've slipped twice this week.", "I ended up on the rug.",
                       "I ended up on the kitchen floor.", "I lost my footing on the stairs.",
                       "I lost my balance in the hall."):
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertEqual(res.severity, "distress")
                self.assertIn("hurt", res.immediate_reply.lower())

    def test_slip_idioms_stay_calm(self):
        for phrase in ("It slipped my mind.", "I slipped out to the shop.", "I slipped on my coat and went out.",
                       "I slipped my shoes off.", "I slipped in quietly.", "I slipped up on the crossword.",
                       "Sarah slipped on the ice.", "I ended up on the bus."):
            with self.subTest(phrase=phrase):
                self.assertEqual(fastpath.check(phrase).severity, "none")
