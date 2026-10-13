# MathTutor — project conventions

## Workflow rules (from `math_tutor_web_roadmap.md` and spec v3.0 §21)

- **One phase at a time.** Finish the current phase and its exit gates, update `IMPLEMENTATION_STATUS.md` with *actual* results, report, then **stop and wait for explicit user go-ahead**. Never start the next phase automatically.
- **Report only what was actually run.** Do not claim success for anything not executed. Mark incomplete items as incomplete.
- **Keep the existing regression tests passing.** Baseline after W1: **175 tests, 2 skipped**. W1 added 29 (`tests/test_web_service.py`); pre-W1 baseline was 146. Record exactly which tests changed and why.
- The roadmap file lives outside the repo (`C:\Users\Alireza\Downloads\math_tutor_web_roadmap.md`); it is user-supplied, not stored in the workspace.
- Phase progress: W0 done, W1 done. Next is **W2 (core refactors)** — do not start without explicit go-ahead.

## Web service (phase W1, `webapp/`)

- The compiled graph is built **once** in the FastAPI lifespan and reused. `service.py` only invokes/resumes; it never inspects `mode` to pick a branch.
- Resume mirrors `cli.py`: `Command(resume=<text>)` on the same thread; the graph's own `user_input` node interprets the text.
- The in-memory checkpointer is the **only** graph-state store. A restart loses lessons; the client gets `thread_not_found` and starts fresh from its saved transcript.
- `ui_event` returns `400 bad_request` / `error.action_not_supported` until W7 — by design.
- Contract placeholders that must not change shape in later phases: `blocks` always `[]` (W5), `level_suggestion` always `null` (W8), `usage` values always `null` (W9).
- `fastapi.sse` / `EventSourceResponse` / `app.frontend()` do **not** exist in FastAPI 0.121.2 + Starlette 0.49.3. W4 must use `StreamingResponse`.

## Environment hazards

- **`HTTP_PROXY` is set to `http://127.0.0.1:56933` with no `NO_PROXY`.** `httpx` honours it by default, so loopback requests get proxied and fail (seen as a bogus `404`). Use `trust_env=False` in httpx, and bypass the proxy for `127.0.0.1` in any Node/Python client. This will matter for W4.
- The first real SymPy call pays a cold spawn on Windows (~15 s); the 5 s default `math_timeout_seconds` reports a false timeout. Use ≥30 s for one-shot acceptance runs.

## Hard invariants

- **The LangGraph node set is frozen at 11**: `classify`, `answer`, `math_tool`, `write_answer`, `learn`, `read_source`, `verified_examples`, `teaching_bestpractices`, `web_search`, `write_explanation`, `user_input`. Adding/removing/renaming a node requires explicit written approval.
- **LangGraph is the only orchestration engine.** FastAPI handlers may invoke/stream/resume the compiled graph but must never decide routes. Same for the CLI loop.
- **The LLM never emits executable content** and never supplies a number that is drawn. All displayed numbers come from SymPy or validated deterministic code.
- **Credentials stay out of** state, logs, the frontend and test output.
- Tests hitting live services are opt-in and labelled; default runs use fakes. The real compiled graph is never faked.

## Repo gotchas

- `specs/` and `IMPLEMENTATION_STATUS.md` are in `.gitignore` and untracked. **Back up before overwriting** — git history will not save them. Spec archives go in `specs/archive/`.
- `sources/raw/`, `sources/text/`, `sources/examples/paul/`, `files/`, `.cache/` are gitignored local-only corpora.
- Active embedding backend is AvalAI `text-embedding-3-large` (3072-dim), endpoint `https://api.avalai.ir/v1`. No local embedding model is loaded for this backend.
- Display policy: answers and lessons contain **no citations/source names/URLs**. Provenance stays in evidence records and manifests.
- Persian digits in UI chrome only; Latin digits inside all math. Web channel uses LaTeX (KaTeX); CLI uses plain text.
