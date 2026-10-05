---
trigger: always_on
description: Testing and verification requirements.
---

# Testing Requirements

Every new feature must include appropriate tests.

Before completing a task:

- Run the test suite.
- Run the build.
- Run linting if available.
- Test important edge cases.

Never remove or weaken a test simply because it fails.

When fixing a bug:
1. Reproduce the bug.
2. Create a failing test.
3. Fix the implementation.
4. Confirm the test passes.
5. Run regression tests.
