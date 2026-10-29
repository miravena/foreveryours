"""SYSTEM_PROMPT rule 21: an open-ended invitation gets one briefed topic.

Live judge turn T04 ("What should we talk about this afternoon?") came back as
"How are you feeling today?" with jazz, Leo and Sarah's 4 PM groceries all in
the pre-brief. Two things were missing: nothing told the model to offer a
briefed item, and the CASUAL zero-memory gate handed THINK no facts at all for
that transcript. These tests cover both offline, with the hosted model stubbed.
"""
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from caregiver import CaregiverFlags
from memory.store import MemoryStore
from pipeline import think
from pipeline.intent import Intent, detect_intent, is_topic_invitation
from pipeline.nebius_client import NebiusNotConfigured
from pipeline.orchestrator import run_turn

RULE_21 = "21. OFFER A BRIEFED TOPIC"
RULE_19 = "19. NO-LISTENING HONESTY"
RULE_20 = "20. REMEMBERED FACTS ONLY, ATTRIBUTED CORRECTLY"
INVITATION = "What should we talk about this afternoon?"
PROFILE = ["Dad loves jazz", "His grandson is named Leo"]
UPDATES = ["Sarah is dropping off groceries at 4 PM today"]


def _notes_text(messages) -> str:
    """The <family_notes> data message (#280), or "" when there is none."""
    return next((m["content"] for m in messages
                 if m.get("role") == "user" and str(m.get("content", "")).startswith("<family_notes>")), "")


def _system_text(messages: list[dict]) -> str:
    return "\n".join(m["content"] for m in messages if m["role"] == "system")


class TestBuildPromptCarriesRule21(unittest.TestCase):
    def test_rule_and_seeded_facts_reach_the_prompt(self):
        messages = think.build_prompt(
            INVITATION, PROFILE, guardrails=["Avoid talking about driving"],
            caregiver_updates=UPDATES, intent=Intent.CASUAL.value,
        )
        system = _system_text(messages)
        self.assertIn(RULE_21, system)
        self.assertIn("Offer ONE item by name", system)
        notes = _notes_text(messages)  # #280: the brief is a data message
        for fact in PROFILE + UPDATES:
            self.assertIn(fact, notes)
            self.assertNotIn(f"- {fact}", system)  # rule 11 quotes "Dad loves jazz" itself
        self.assertEqual(messages[-1], {"role": "user", "content": INVITATION})

    def test_rule_21_follows_rules_19_and_20(self):
        system = _system_text(think.build_prompt(INVITATION, PROFILE))
        self.assertIn(RULE_19, system)
        self.assertIn(RULE_20, system)
        self.assertIn(RULE_21, system)
        self.assertLess(system.index(RULE_20), system.index(RULE_21))

    def test_rule_21_example_is_the_one_sentence_it_asks_for(self):
        # The rule asks for one sentence; its own example must not model two.
        rule = think.SYSTEM_PROMPT.split(RULE_21, 1)[1].split("\n", 1)[0]
        examples = re.findall(r'"([^"]+)"', rule)
        offer = [e for e in examples if "Sarah mentioned" in e]
        self.assertEqual(len(offer), 1, rule)
        self.assertIsNone(re.search(r"[.!?]\s+\S", offer[0]), offer[0])


class TestTopicInvitationDetector(unittest.TestCase):
    def test_invitations_are_detected(self):
        for text in (
            INVITATION,
            "What can we chat about?",
            "I've got nothing to talk about today.",
            "I don't know what to talk about.",
        ):
            with self.subTest(text=text):
                self.assertTrue(is_topic_invitation(text))
                self.assertEqual(detect_intent(text), Intent.CASUAL)

    def test_ordinary_turns_are_not_invitations(self):
        for text in ("What's two plus two?", "Hello there.", "Let's talk about Miles Davis", ""):
            with self.subTest(text=text):
                self.assertFalse(is_topic_invitation(text))


class _CapturingClient:
    """Stands in for the Nebius client: records the streamed THINK call's
    messages and streams back a canned reply. Non-streamed calls (AUDIT,
    memory extraction) behave as if no key is configured."""

    def __init__(self, reply: str):
        self.reply = reply
        self.messages = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        if not kwargs.get("stream"):
            raise NebiusNotConfigured("stubbed: no hosted call in this test")
        self.messages = kwargs["messages"]
        return iter([SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=self.reply))])])


def _speak_joined(sentences, audio_out_dir, on_chunk=None):
    return " ".join(sentences), [], 0.5


class TestOrchestratorHandsTheBriefToThink(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        (root / "data").mkdir()
        (root / "audio").mkdir()
        self.audio_dir = root / "audio"
        self.store = MemoryStore("test_dad", root / "data")
        self.flags = CaregiverFlags("test_dad", root / "data")
        # The live judge check's pre-brief, seeded as caregiver memos.
        self.store.add("Dad loves jazz", source="caregiver_memo")
        self.store.add("His grandson is named Leo", source="caregiver_memo")
        self.store.add("I'm dropping off groceries at 4 PM today", source="caregiver_memo")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run(self, transcript: str, reply: str = "Sarah mentioned you love jazz, shall we talk about that?"):
        client = _CapturingClient(reply)
        with patch("pipeline.think.get_client", return_value=client), \
             patch("pipeline.orchestrator._speak_turn", side_effect=_speak_joined):
            res = run_turn(
                transcript=transcript,
                memory_store=self.store,
                flags=self.flags,
                audio_out_dir=self.audio_dir,
                caregiver_name="Sarah",
            )
        if res.background_thread:
            res.background_thread.join(timeout=10)
        return client, res

    def test_invitation_messages_carry_rule_21_and_the_brief(self):
        client, res = self._run(INVITATION)
        self.assertIsNotNone(client.messages, "THINK was never called")
        system = _system_text(client.messages)
        self.assertIn(RULE_21, system)
        notes = _notes_text(client.messages)  # #280: the brief is a data message
        self.assertIn("- Dad loves jazz", notes)  # the seeded fact, not rule 20's example
        self.assertIn("groceries at 4 PM", notes)
        self.assertEqual(client.messages[-1]["content"], INVITATION)
        self.assertRegex(res.reply_text.lower(), r"jazz|\bleo\b|sarah|grocer")

    def test_invitation_gets_one_anchor_not_the_whole_profile(self):
        client, _ = self._run(INVITATION)
        notes = _notes_text(client.messages)
        anchors = notes.split("Profile:\n", 1)[1].split("\nUpdates:", 1)[0]
        self.assertEqual(len([ln for ln in anchors.splitlines() if ln.startswith("- ")]), 1)

    def test_plain_casual_turn_still_gets_zero_memories(self):
        client, _ = self._run("What's two plus two?", reply="Two plus two is four.")
        system = _system_text(client.messages)
        self.assertNotIn("- Dad loves jazz", system)
        self.assertNotIn("groceries at 4 PM", system)


if __name__ == "__main__":
    unittest.main()
