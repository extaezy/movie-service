---
name: git-checkpoint
description: Identify a logical development checkpoint and prepare a clear Git commit for project progress.
---

When a logical implementation stage is complete:

1. Inspect changed files.
2. Group only related changes.
3. Do not include unrelated modifications.
4. Summarize what was implemented.
5. Suggest a concise commit message.

Prefer conventional commit style when appropriate:

feat:
fix:
test:
refactor:
docs:
chore:

Example:

feat(auth): add user registration endpoint

Do not create artificially tiny commits for every minor edit.

Prefer commits that represent understandable development stages.

If the current changes contain multiple unrelated features, recommend separating them.
