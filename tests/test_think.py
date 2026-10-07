"""Tests for THINK prompt generation, sentence chunking, and memory extraction."""
import unittest

from pipeline import think


class TestExtractNewMemoryDispatch(unittest.TestCase):
    """Goes through extract_new_memory(), the entry point the orchestrator calls."""

    SUPERSEDE = "SUPERSEDE: His grandson is named Leo | His grandson is named Liam"
    DELETE = "DELETE: His grandson is named Leo"

    def _with_llm(self, llm_result, transcript):
        from unittest.mock import patch
        with patch("pipeline.think.extract_memory_llm", return_value=llm_result) as m:
            out = think.extract_new_memory(
                transcript, "", ["His grandson is named Leo"], use_llm=True
            )
        return out, m

    def test_llm_supersede_beats_family_marker(self):
        out, m = self._with_llm(self.SUPERSEDE, "Actually, my grandson's name is Liam, not Leo.")
        self.assertEqual(out, self.SUPERSEDE)
        m.assert_called_once()

    def test_llm_delete_beats_family_marker(self):
        out, _ = self._with_llm(self.DELETE, "Please forget my grandson's name.")
        self.assertEqual(out, self.DELETE)

    def test_llm_supersede_daughter_correction(self):
        cmd = "SUPERSEDE: His daughter is named Susan | His daughter is named Sarah"
        out, _ = self._with_llm(cmd, "Actually, my daughter is Sarah, not Susan.")
        self.assertEqual(out, cmd)

    def test_marker_fallback_only_when_llm_call_failed(self):
        out, _ = self._with_llm(think.LLM_CALL_FAILED, "My grandson will visit on Sunday")
        self.assertEqual(out, "ADD: My grandson will visit on Sunday")

    def test_no_fallback_when_llm_succeeds_with_nothing_to_extract(self):
        """Regression: a successful LLM verdict of 'nothing here' (plain
        None) must not be second-guessed by the marker heuristic, even when
        the transcript matches a DURABLE_MARKERS pattern."""
        out, _ = self._with_llm(None, "My grandson will visit on Sunday")
        self.assertIsNone(out)

    def test_marker_fallback_never_stores_a_question(self):
        for t in (
            "What's my grandson's name again?",
            "What's my grandson's name again? I can't remember.",
            "Is my grandson named Liam? Did I get that right?",
        ):
            out, _ = self._with_llm(think.LLM_CALL_FAILED, t)
            self.assertIsNone(out, t)

    def test_empty_completion_falls_back_not_treated_as_deliberate_none(self):
        """Regression (Codex review of #82): a truncated/empty completion
        (e.g. finish_reason="length") is a failed call, not a successful
        "nothing to extract" verdict, so the marker fallback must still run."""
        from unittest.mock import patch
        from types import SimpleNamespace

        for empty_content in ("", "   \n"):
            completion = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=empty_content))]
            )
            with patch("pipeline.think.get_client") as mock_client:
                mock_client.return_value.chat.completions.create.return_value = completion
                out = think.extract_new_memory("My grandson is named Leo", "That is lovely.", [])
            self.assertEqual(out, "ADD: My grandson is named Leo", repr(empty_content))

    def test_offline_never_stores_forget_or_correction_as_fact(self):
        for t in (
            "Please forget my grandson's name.",
            "Could you forget that my son lives in Ohio?",
            "Actually, my grandson's name is Liam, not Leo.",
            "Actually, my daughter is Sarah, not Susan.",
            "I was wrong, my wife is called Ann.",
        ):
            self.assertIsNone(think.extract_new_memory(t, "", [], use_llm=False), t)

    def test_offline_benign_facts_still_added(self):
        for t in (
            "My grandson will visit on Sunday",
            "My favorite flavor is strawberry",
            "I used to work as a teacher in Boston",
            "My daughter is Sarah and she lives in Ohio",
        ):
            self.assertEqual(think.extract_new_memory(t, "", [], use_llm=False), f"ADD: {t}")


class TestOfflineRevisionMarkers(unittest.TestCase):
    """PR #69 review: markers must drop corrections/forgets, never plain facts."""

    def test_plain_facts_with_revision_lookalikes_are_added(self):
        for t in (
            "I actually like jazz",
            "My favorite color is blue, not red",
            "My daughter, not my son, lives in Ohio",
            "No, I never liked broccoli but my wife does",
        ):
            self.assertEqual(think.extract_new_memory(t, "", [], use_llm=False), f"ADD: {t}", t)

    def test_unpunctuated_correction_not_stored(self):
        self.assertIsNone(think.extract_new_memory("My daughter is Sarah not Susan", "", [], use_llm=False))

    def test_do_not_remember_not_stored(self):
        for t in (
            "Do not remember my daughter's address",
            "Don't remember my daughter's address",
        ):
            self.assertIsNone(think.extract_new_memory(t, "", [], use_llm=False), t)

    def test_existing_passes_hold(self):
        for t in (
            "Actually, my grandson's name is Liam, not Leo",
            "Please forget my grandson's name",
        ):
            self.assertIsNone(think.extract_new_memory(t, "", [], use_llm=False), t)
        self.assertEqual(
            think.extract_new_memory("My grandson Leo loves trains", "", [], use_llm=False),
            "ADD: My grandson Leo loves trains",
        )


class TestThink(unittest.TestCase):
    def test_build_prompt_structure(self):
        transcript = "Can you play some music?"
        facts = ["Loves Miles Davis", "Grandson is Leo"]
        guardrails = ["Avoid talking about driving"]
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hello, good to hear from you."},
        ]

        messages = think.build_prompt(transcript, facts, guardrails, history)
        self.assertEqual(messages[0]["role"], "system")
        system_content = messages[0]["content"]
        self.assertIn("SENIOR PROFILE & BELOVED ANCHORS", system_content)
        self.assertIn("- Loves Miles Davis", system_content)
        self.assertIn("- Grandson is Leo", system_content)
        self.assertIn("DO NOT RAISE (Safety Guardrails)", system_content)
        self.assertIn("- Avoid talking about driving", system_content)
        self.assertEqual(messages[1], history[0])
        self.assertEqual(messages[2], history[1])
        self.assertEqual(messages[3]["role"], "user")
        self.assertEqual(messages[3]["content"], transcript)

    def test_build_prompt_with_intent_and_caregiver_updates(self):
        transcript = "hello i feel so sad recently"
        facts = ["Dad loves jazz"]
        updates = ["Family member (Leo) is dropping off groceries at 4 PM today"]
        guardrails = ["Avoid talking about driving"]

        messages = think.build_prompt(
            transcript,
            facts,
            guardrails=guardrails,
            caregiver_updates=updates,
            intent="EMOTIONAL_SUPPORT",
        )
        system_content = messages[0]["content"]
        self.assertIn("CURRENT CONVERSATIONAL INTENT: EMOTIONAL_SUPPORT", system_content)
        self.assertIn("Validate their feelings first with warmth", system_content)
        self.assertIn("TODAY'S FAMILY / CAREGIVER UPDATES", system_content)
        self.assertIn("Family member (Leo) is dropping off groceries", system_content)
        self.assertIn("RELEVANCE DOES NOT IMPLY INSERTION", system_content)
        self.assertIn("DO NOT PRETEND TO HAVE A PHYSICAL BODY", system_content)

    def test_sentence_chunks_standard_punctuation(self):
        tokens = ["Hello ", "there! ", "How ", "are ", "you ", "doing ", "today? ", "I am well."]
        chunks = list(think.sentence_chunks(iter(tokens)))
        self.assertEqual(chunks, ["Hello there!", "How are you doing today?", "I am well."])

    def test_sentence_chunks_abbreviation_awareness(self):
        # "Dr. Smith" and "4 p.m." must NOT split mid-title or mid-time
        tokens = [
            "We have an appointment with Dr. ",
            "Smith at 4 ",
            "p.m. today. ",
            "Please bring your notes.",
        ]
        chunks = list(think.sentence_chunks(iter(tokens)))
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0], "We have an appointment with Dr. Smith at 4 p.m. today.")
        self.assertEqual(chunks[1], "Please bring your notes.")

    def test_durable_memory_extraction_rules(self):
        # Valid markers
        self.assertEqual(
            think.extract_new_memory("My favorite flavor is strawberry", "", use_llm=False),
            "ADD: My favorite flavor is strawberry",
        )
        self.assertEqual(
            think.extract_new_memory("I used to work as a teacher in Boston", "", use_llm=False),
            "ADD: I used to work as a teacher in Boston",
        )
        self.assertEqual(
            think.extract_new_memory("I love jazz so much", "", use_llm=False),
            "ADD: I love jazz so much",
        )
        self.assertEqual(
            think.extract_new_memory("My grandson will visit on Sunday", "", use_llm=False),
            "ADD: My grandson will visit on Sunday",
        )

        # Word boundary tests: should NOT trigger on partial substrings
        self.assertIsNone(think.extract_new_memory("This is my song playing", "", use_llm=False))
        self.assertIsNone(think.extract_new_memory("I likely will go to bed soon", "", use_llm=False))
        self.assertIsNone(think.extract_new_memory("How are you today?", "", use_llm=False))

    def test_system_prompt_rules_trivia_and_hallucination(self):
        prompt = think.SYSTEM_PROMPT
        self.assertIn("TRIVIA & UNKNOWN FACTS", prompt)
        self.assertIn("NO FABRICATED MEMORIES", prompt)
        self.assertIn("Do NOT offer to contact, call, or alert family or caregivers over basic trivia", prompt)
        self.assertIn("Only reference memories explicitly listed in the profile facts", prompt)

    def test_system_prompt_rules_family_perspective_and_redirection(self):
        prompt = think.SYSTEM_PROMPT
        self.assertIn("FAMILY PERSPECTIVE & IDENTITY", prompt)
        self.assertIn("GRACEFUL GUARDRAIL REDIRECTION", prompt)
        self.assertIn("NEVER say \"the music your dad loved\"", prompt)
        self.assertIn("Never address the senior by their child's name", prompt)
        self.assertIn("Do NOT invert family relationships", think.EXTRACTION_SYSTEM_PROMPT)

    def test_stream_reply_token_budget_headroom(self):
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        with patch("pipeline.think.get_client", return_value=mock_client):
            list(think.stream_reply("Hello", []))
            _, kwargs = mock_client.chat.completions.create.call_args
            self.assertEqual(kwargs.get("max_tokens"), 1024)

    def test_stream_reply_disables_thinking_by_default(self):
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        with patch("pipeline.think.get_client", return_value=mock_client), \
             patch("pipeline.think.THINK_ENABLE_REASONING", False):
            list(think.stream_reply("Hello", []))
            _, kwargs = mock_client.chat.completions.create.call_args
            extra_body = kwargs.get("extra_body", {})
            self.assertEqual(extra_body.get("chat_template_kwargs"), {"enable_thinking": False})

    def test_stream_reply_enables_thinking_when_configured(self):
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        with patch("pipeline.think.get_client", return_value=mock_client), \
             patch("pipeline.think.THINK_ENABLE_REASONING", True):
            list(think.stream_reply("Hello", []))
            _, kwargs = mock_client.chat.completions.create.call_args
            self.assertNotIn("extra_body", kwargs)

    def test_system_prompt_rules_zero_memory_uncertainty_and_privacy(self):
        prompt = think.SYSTEM_PROMPT
        self.assertIn("ZERO-MEMORY DEFAULT", prompt)
        self.assertIn("UNCERTAINTY & HONEST LIMITS", prompt)
        self.assertIn("CAREGIVER PRIVACY FIREWALL", prompt)
        self.assertIn("RESPECT SENIOR AGENCY & AUTONOMY", prompt)
        self.assertIn("prefer using ZERO memories", prompt)
        self.assertIn("I don't have a confirmed time for that", prompt)

    def test_system_prompt_rules_clinical_and_anti_dependency(self):
        prompt = think.SYSTEM_PROMPT
        self.assertIn("NO MEDICAL DIAGNOSIS OR MEDICATION ADVICE", prompt)
        self.assertIn("DO NOT PRETEND TO HAVE A PHYSICAL BODY OR PERFORM IN-PERSON ACTIONS", prompt)
        self.assertIn("ANTI-DEPENDENCY & HUMAN CONNECTION", prompt)
        self.assertIn("Never diagnose medical symptoms, recommend pill dosages", prompt)
        self.assertIn("ForeverYours must complement human relationships, never replace them", prompt)


if __name__ == "__main__":
    unittest.main()

    def test_circadian_prompts_sundowning(self):
        prompt = think.build_prompt("Hello", [], intent="CASUAL", current_hour=18)
        self.assertTrue(any("SUNDOWNING SYNDROME ACTIVE" in b for b in prompt))

    def test_circadian_prompts_night(self):
        prompt = think.build_prompt("Hello", [], intent="CASUAL", current_hour=23)
        self.assertTrue(any("NIGHT MODE" in b for b in prompt))
