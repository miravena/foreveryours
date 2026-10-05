---
name: review-feature
description: Reviews completed changes against requirements, architecture, security and testing standards.
---

# Feature Review

Read:

- intent.md
- spec.md
- plan.md
- AGENTS.md

Review the implementation for:

## Correctness
- Does it satisfy the requirements?
- Are edge cases handled?

## Architecture
- Does it follow existing architecture?
- Is unnecessary complexity introduced?

## Security
- Authentication
- Authorization
- Input validation
- Sensitive data exposure
- Secrets

## Testing
- Are important cases tested?
- Are regression tests present?

## Maintainability
- Is the code understandable?
- Is there duplicated logic?

## Plan Compliance
- Does the implementation match plan.md?
- If not, explain every deviation.

Do not modify code.

Produce a review report.
