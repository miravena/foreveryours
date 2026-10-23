"""ForeverYours test suite."""
import os

# The warm Piper server (#207) is a real second process that loads a 64 MB voice.
# Only the tests about it start one (tests/test_speak.py, TestPiperServer*, which
# set this back to "1"); every other test sees the engine tiers as they were, whether
# or not a developer has fetched a voice into models/piper/.
os.environ["TTS_PIPER_SERVER"] = "0"
# Likewise the per-sentence `piper` CLI: with a fetched voice it costs ~2 s per sentence,
# so the suite would take minutes on one machine and seconds on another. The Piper tests
# set TTS_BACKEND back to "auto" themselves.
os.environ["TTS_BACKEND"] = "espeak"
