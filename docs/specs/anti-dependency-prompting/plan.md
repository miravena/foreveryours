# Plan: Anti-Dependency Prompting (Priority 2)

## Goal
Ensure the AI acts as a bridge to human connection rather than a replacement for it. If the senior expresses dependency (e.g., "You're all I need", "I don't need to talk to my family"), the system must warmly redirect them to reach out to real people.

## Findings
We currently have a basic "Anti-Parasocial" rule (Rule #17) in `pipeline/think.py` that tells the AI to "remind them of their family's love." However, it does not instruct the AI to *actively encourage the senior to call or contact* their family. We need to upgrade this from a passive reminder to an active human-connection bridge.

## Proposed Changes

### 1. `pipeline/think.py`
Update Rule #17 in the `SYSTEM_PROMPT` to explicitly mandate encouraging human contact.

### 2. `tests/test_mature_benchmarks.py`
- Add a new **Benchmark 7: Anti-Dependency & Human Connection Compliance** to formally test that the prompt enforces this active redirection to family.
- Update the existing Benchmark 6 to remove the old "anti-parasocial" check (since it's now covered by Benchmark 7).
