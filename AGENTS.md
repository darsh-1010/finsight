# Agent Instructions — FinSight

Mandatory instructions for all code generated or modified in this repo (`backend/` — FastAPI/Python,
`ml/` — Python, `frontend/` — TypeScript/React). Tool-agnostic: any coding agent reading this file
should follow it. Claude Code additionally reads `CLAUDE.md`, which imports this file — see that file
for Claude-specific workflow notes.

---

## 0. General Principles

- **Stability**: never break existing functionality; verify original behavior still works after a change.
- **Minimalist code**: smallest effective diff that solves the problem. No speculative abstractions,
  no config for values that never change, no unrequested scaffolding.
- **Atomic tasks**: break a complex request into sub-tasks and track them (e.g. a todo list) instead of
  one large undifferentiated change.
- **Root-cause fixes**: a bug report names a symptom, not a cause. Check every caller of the function
  you're about to touch before patching — fix it once where all callers route through, not once per
  symptom site.

## 1. Research & Planning

- For unfamiliar libraries, APIs, or architectural decisions, search for current best practice before
  writing code — don't guess at an API surface or a deprecated pattern from training data.
- For any non-trivial change (new endpoint, schema change, cross-service change), state the plan —
  files touched, approach, trade-offs — before editing, so it can be corrected before code is written.
- Match the existing architecture. A locally-consistent solution beats an objectively "better" pattern
  that fights the rest of the codebase.

## 2. Lint Compliance

The enforced gate is `make lint` → `ruff check` for `backend/` and `ml/`, `eslint` for `frontend/`
(see [Makefile](Makefile)). `backend/.pylintrc` and `ml/.pylintrc` define a stricter supplementary
bar for Python — run `pylint <file> --rcfile=backend/.pylintrc` (or `ml/.pylintrc`) on files you touch
there. There is no CI running any of this yet, so compliance is on the agent, not a safety net.

**Pylint hard limits** (from the `.pylintrc` files): line length 120 · function args 6 · locals/function 15
· return statements 6 · branches 12 · statements/function 50 · module lines 700 · class attributes 10.

**Forbidden**: `# pylint: disable=...` anywhere (fix the code instead) · wildcard imports ·
`print()` for logging (use `logging.getLogger(__name__)`) · `%`/`.format()` string formatting
(use f-strings) · `foo`/`bar`/`baz`/`tmp`/`test` as variable names.

**Always**: f-strings · `with` for context managers · dict/set comprehensions where clearer ·
4-space indent, no tabs. TypeScript/React code in `frontend/` follows the existing `eslint` config
instead of the above.

## 3. Code Clarity

- **Naming**: verb-first functions (`build_system_instruction`, not `sys_inst`); descriptive variables
  (`customer_phone`, not `cp`); booleans read as questions (`is_active`, `has_expired`); constants are
  `UPPER_SNAKE_CASE` with a comment on *why* that value, not just what it is. Short names OK only for
  loop counters (`i, j, k`), exceptions (`ex`), throwaway (`_`), and `pk`/`id`.
- **One function, one job.** If it doesn't fit on one screen (~40 lines), extract a helper.
- **File order**: docstring → imports (stdlib → third-party → local) → constants → helpers → core
  logic → `if __name__ == "__main__":`.
- **Comments explain *why*, not *what***: a threshold, a workaround, a protocol quirk — not a restated
  line of code. Code that needs heavy inline comments to be understood should be refactored instead.

## 4. Security

- **Secrets**: never hardcode API keys, passwords, tokens, or DB URIs — always `os.getenv(...)` /
  `.env`. Never commit `.env` (already covered by `.gitignore`).
- **Input validation**: validate every external input (API bodies, query params, file uploads) before
  use — types, ranges, lengths, formats. Use Pydantic models for FastAPI request bodies rather than
  ad-hoc checks.
- **Log sanitization**: never log secrets or PII in plain text — mask (e.g. `***{phone[-4:]}`) or omit.

## 5. Robustness & Error Handling

- Handle edge cases explicitly: empty input, `None`, zero-length data, missing dict keys (`.get()`
  with a default instead of bare `[...]` access).
- Catch specific exceptions and log them with context (request id, entity id) — never a bare `except:`.

## 6. Logging Standards

`logging.getLogger(__name__)` at module level. Format: `[ACTION] Key: value | Key: value`, e.g.
`logger.info(f"[USER_CREATED] User: {user_id} | Role: {role}")`. Levels: `DEBUG` internal traces ·
`INFO` lifecycle/success · `WARNING` recoverable/retries · `ERROR` functionality-affecting failures.
Never log secrets or PII (§4).

## 7. Documentation

- Update `README.md` when a module is added, setup steps change, or project structure changes
  significantly — it should reflect current state, not a past one.
- Document REST endpoints (method, path, request/response schema, status codes, example request)
  in the README or `docs/api.md`.
- Maintain `CHANGELOG.md` at the repo root (create it on first use) with `## [YYYY-MM-DD]` /
  `### Added` `### Changed` `### Fixed` sections for anything significant.

## 8. Output Quality

- Type hints on all function signatures. Docstrings on any function whose behavior isn't obvious from
  its name and signature.
- Guard clauses over deep nesting — return early instead of wrapping the rest of the function in `if`.
- No dead code: no commented-out code, unused imports, or obsolete functions left behind.

## 9. Pre-Submission Checklist

1. `ruff check` clean for touched Python files (§2); `pylint --rcfile=<backend|ml>/.pylintrc` clean too
2. No `# pylint: disable` comments
3. Type hints on touched functions; *why*-comments on non-obvious logic
4. No bare `except:`; no secrets/PII in code or logs; external inputs validated
5. `[ACTION] Key: value` logging format used
6. README / CHANGELOG updated if the change warrants it
7. Diff is the smallest one that solves the problem — no speculative extras
8. If the change is structural or alters a core workflow, update `.agents/temp_documentations/workflow.md`
   and `function.md` (see §10; create the directory on first use, don't pre-scaffold it)
9. No leftover scratch files, verification scripts, or temp test artifacts in the final diff

## 10. Continuous Documentation Updates

When a change adds/removes a module or alters an end-to-end workflow (RAG ingestion, intent
classification, a sequence between services), update `.agents/temp_documentations/workflow.md`
(flows/sequences) and `function.md` (high-level, plain-language purpose of each critical function —
big picture, not line-by-line). Create `.agents/temp_documentations/` the first time either file is
needed; don't create it speculatively.

---

## graphify

This project can maintain a persistent knowledge graph of the architecture at `graphify-out/`.
**If `graphify-out/GRAPH_REPORT.md` exists and looks current, read it before broad codebase
exploration** — it has core workflows, "god nodes", and community structure. If the `graphify` CLI/MCP
tool isn't available in your environment, or the report is missing/stale, fall back to normal
Grep/Glob exploration instead of blocking on it.

- **Discovery**: `graphify query "<question>"` / `graphify explain "<concept>"` to find relevant files
  and functions before reaching for a broad `grep`.
- **Navigation**: `graphify path "A" "B"` to trace data flow between two components.
- **Wiki**: if `graphify-out/wiki/index.md` exists, prefer it over raw source for a first read.
- **Maintenance**: after editing code, run `graphify update .` to refresh the graph (AST-only, no API
  cost). `graphify-out/` is generated output — gitignored, never commit it (see [.gitignore](.gitignore)).
