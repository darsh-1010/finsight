@AGENTS.md

## Claude Code

- **Enforcement vs. guidance**: `AGENTS.md` above is context, not a hard gate — Claude tries to follow
  it but can drift on vague or conflicting instructions. Don't just assert compliance with §2/§9 (e.g.
  "ruff clean") — actually run `ruff check` / `pylint --rcfile=...` and show the result before calling
  a change done.
- **Planning**: use plan mode for anything matching §1's "non-trivial change" bar instead of writing
  the plan straight into chat. Track §0's atomic sub-tasks with the todo list tool rather than a
  hand-maintained `task.md`.
- **Research**: use `WebSearch`/`WebFetch` for §1's research step.
- **Skills**: if a skill in the current skill list already covers the task (lint review, PDF/xlsx/docx
  work, etc.), use it instead of re-deriving the same steps inline.
- **graphify**: only follow the graphify section if those tools are actually present in this session —
  don't invent a `graphify` shell invocation that isn't installed.

Keep this file and `AGENTS.md` each under ~200 lines — both load in full every session regardless of
the `@import` split, so trim content rather than relocating it.
