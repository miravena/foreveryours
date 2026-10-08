# Feature Review: Test Integrity (Issue 63)

## Feature Overview
Benchmark 9 now executes offline. It uses a mock `get_client()` fixture to verify that the `stream_reply` method properly embeds "NIGHT MODE" rules when `current_hour=23`, and properly processes a streaming mock response to assert conversational vocabulary. The blanket `except Exception:` block has been eradicated.

## What Was Fixed
- Switched Benchmark 9 from a live API integration test to an offline unit test.
- Eliminated the dangerous `try/except Exception: self.skipTest(...)` loophole that was masking Python runtime errors.

## Honest Gap Analysis (Loopholes & Downfalls)
- By mocking the LLM response in Benchmark 9, we are no longer verifying if the *actual* live Nemotron 30B model obeys the Night Mode prompt. We are only verifying that the Python code correctly formats the prompt and correctly parses our hardcoded mock string. If the real LLM suddenly starts ignoring the "NIGHT MODE" instruction, this test will pass anyway because we control the mock. To truly ensure LLM obedience, we would need a dedicated, periodic live-evaluation suite that explicitly runs against production API keys without blanket exceptions.
