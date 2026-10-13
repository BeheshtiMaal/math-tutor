# MathTutor — project conventions

## Workflow rules (from `math_tutor_web_roadmap.md` and spec v3.0 §21)

- **One phase at a time.** Finish the current phase and its exit gates, update `IMPLEMENTATION_STATUS.md` with *actual* results, report, then **stop and wait for explicit user go-ahead**. Never start the next phase automatically.
- **Report only what was actually run.** Do not claim success for anything not executed. Mark incomplete items as incomplete.
- **Keep the existing regression tests passing.** Baseline after W2/W3: **206 tests, 204 passed, 2 skipped, 0 failures** (~150–250 s). W2 added 31 (`tests/test_web_refactors.py`); pre-W2 baseline was 175; W3 added none. The 2 skips are pre-existing: missing-SymPy (`test_answer_graph.py:190`) and optional local-E5 (`test_semantic_retrieval.py:338`). Record exactly which tests changed and why. Run it with `.venv/Scripts/python.exe -m unittest discover -s tests` — **pytest is not installed**.
- The roadmap file lives outside the repo (`C:\Users\Alireza\Downloads\math_tutor_web_roadmap.md`); it is user-supplied, not stored in the workspace.
- Phase progress: W0 done, W1 done, W2 done, W3 done (content). Next is **W4 (streaming)** — do not start without explicit go-ahead.

## Curated core content (phase W3, `sources/topics/`)

- **Latest derivative follow-up:** bank now has 87 examples from 14 pages; derivatives have 45 across seven subtopics (14 beginner / 17 intermediate / 14 advanced). The unused-reserve counts below describe the pre-expansion inventory. Definition, product/quotient, chain, implicit, higher-order and linear-approximation pages are now imported. Full bank verification: 39 verified, 46 unsupported, 2 unknown; no rejected results. Example index rebuilt: 36 added, 51 reused. Natural English/Persian teaching intent chooses learn when `Request.mode` is absent; explicit mode still wins. Exact “hey explain me logarithm” and two derivative probes succeeded live, with no writer fallback. Regression: 208 tests, 206 passed, 2 skipped. Full 80-run evaluation remains pending; W4 not started.

- **The authored `sources/topics/*.md` files are the source of truth.** `scripts/prepare_topic_notes.py` is a **validator + registry generator** — it refuses to write anything (exit 1) on a structural defect. Never regenerate notes over an edit.
- **10 core topics** (fixed with the user): derivative, integral, limits, algebra, matrix, probability, optimization, logarithms, exponentials, trigonometry. Each note is **57 lines**: bilingual title, reference line, then 3 `## <Level>` sections × 4 `### <Unit>` units (Definition, Rule and conditions, Worked example, Common mistakes). Each unit is **one English line then one Persian line** (no blank line between).
- **`learner_level` comes from the `## <Level>` heading, not the sidecar.** Sidecars carry only `topic`/`provenance`. A level heading must carry **no prose** — fold framing sentences into the Definition unit, or the loader turns them into near-contentless chunks that outrank real content. The loader **drops heading-only sections** for the same reason.
- `ALIASES` in `learning.py` must list the three new topics **before** `algebra`; `infer_topic` returns the first match and "معادله نمایی" is an exponential question.
- `scripts/verify_curated_notes.py` checks every note formula SymPy can reach (**137 claims; 129 verified, 0 rejected, 0 unknown, 8 unsupported**). Verification strategies are **chained** (`simplify` → `expand_log` → …), not applied independently.
- `scripts/check_cross_language_retrieval.py` gates on `end_to_end` and `distractor` only (`semantic`/`paired` are diagnostics). Currently **20/20 and 9/9**; the recorded non-gate gap is the Persian `limits` query losing to `derivative`.
- **Anti-fabrication:** every cited section is resolved against the local extracted book text; a section that is not a real heading aborts the run. `trigonometry` originally cited a book this project does not own — that class of error is now caught.
- **Example-bank source inventory (Paul's Online Math Notes, `scripts/prepare_paul_examples.py`).** The bank is **Paul-HTML only** — every record hardcodes `source_author="Paul Dawkins"` plus the Paul usage notice, and the extractor parses `div.example`. Quota is **max 3 per (topic, subtopic, level)**, so new coverage must come from **new subtopics**, not more of the same one. The bank draws 51 examples from only **8** of the ~25 linked pages, which leaves large unused reserves: **integral 25 unused** (`ComputingDefiniteIntegrals` 6, `SubstitutionRuleIndefinite` 4, `CalcII/IntegrationByParts` 9, `CalcII/PartialFractions` 6), **derivative 23 unused** (`DefnOfDerivative` 4, `ProductQuotientRule` 3, `ChainRule` 5, `ImplicitDIff` 6, `HigherOrderDerivatives` 3, `LinearApproximations` 2), **limits 15 unused** (`TheLimit` 5, `OneSidedLimits` 4, `LimitsAtInfinityI` 6), **algebra 4 unused** (`SystemsTwoVrble`). **Truly exhausted:** matrix (`AugmentedMatrix` has only 2 examples, both used) and optimization (`Optimization` has 6, all used). **probability has no Paul page at all.** `CalcIII/*` (LagrangeMultipliers, DirectionalDeriv, PartialDerivatives) is linked but outside the acquired curriculum. The only probability reference is OpenStax *Introductory Statistics 2e* §3.1/§3.3, already extracted locally, but importing it needs a **new OpenStax extractor** and different provenance/licence handling. `tutorial.math.lamar.edu` is reachable from this machine.
- **Derivative is the *best*-sourced topic but was the worst in the W3 eval (3/2/3).** Cause: all 9 derivative examples come from `DiffFormulas` alone ("differentiate this expression"), so nothing covers the definition / rate of change, product-quotient, chain, implicit or higher-order rules — which is exactly what the eval probes missed (`12*x^2 - 2`, `46`, "rate of change", `n*x^(n-1)`). The fix is new subtopics from `DefnOfDerivative` / `ChainRule` / `ImplicitDIff`, not more sources.


## Web service (phase W1, `webapp/`)

- The compiled graph is built **once** in the FastAPI lifespan and reused. `service.py` only invokes/resumes; it never inspects `mode` to pick a branch.
- Resume mirrors `cli.py`: `Command(resume=<text>)` on the same thread; the graph's own `user_input` node interprets the text.
- The in-memory checkpointer is the **only** graph-state store. A restart loses lessons; the client gets `thread_not_found` and starts fresh from its saved transcript.
- `ui_event` returns `400 bad_request` / `error.action_not_supported` until W7 — by design.
- Contract placeholders that must not change shape in later phases: `blocks` always `[]` (W5), `level_suggestion` always `null` (W8), `usage` values always `null` (W9).
- `fastapi.sse` / `EventSourceResponse` / `app.frontend()` do **not** exist in FastAPI 0.121.2 + Starlette 0.49.3. W4 must use `StreamingResponse`.

## Core refactors (phase W2, `agent.py` / `learning.py`)

- **Channel is a build parameter, never state.** `Channel = Literal["web","cli"]` goes into `build_graph(..., channel=)` and `learning_nodes(..., channel=, core_topics=)`. It must stay out of the state contract (spec §5 table) and must not change the 11-node set. `webapp/main.py` builds `web`, `cli.py` builds `cli`.
- **"Only an override counts" for language.** A checkpointed thread inherits `language`, so `classify` honours `route.language` **only** when `state["language_source"] == "override"`; otherwise `detect_language` + thread fallback decide. `new_request_state` must write `language_source = "detected"` when no override is supplied, or a cleared CLI override pins itself forever. `language`/`language_source` have no state initializer on purpose.
- **LaTeX must be built from solution objects, never from the finished display string.** `sp.latex("x=6")` quotes it → `\mathtt{\text{x=6}}`. Render `sp.latex(variable)` / `sp.latex(root)` in the solve branch.
- **Level precedence:** session `learner_level` → profile manual level (`level_for`) → `beginner`/`default`. Profile contracts live in the core because the graph state carries them; never stored server-side.
- **Web segments drop UI chrome** (e.g. `"Step i/n"`) that the CLI `explanation` keeps; the client renders step numbers from `lesson` metadata (§11.3). Blocks are typed but `ui_blocks` stays `[]` until W5.

## Environment hazards

- **FIXED (W3) — the learn-mode writer used to never synthesise against AvalAI.** `write_explanation` failed on every learn-mode turn (`Explanation synthesis failed; displaying actual local passages instead.`). Cause was **not** an outage and **not** prompt size: `LessonDraft.block_requests: list[Any]` serialises to `"items": {}`, an untyped array item, which AvalAI rejects (400 `invalid_request` / 503 `service_unavailable` interchangeably). The real schema failed even with a 45-character prompt; a trivial `{ok: bool}` schema succeeded with a 19,615-character prompt. **Applied fix: `agent.py:780` `OpenAIModelClient.structured` uses `with_structured_output(schema, method="function_calling")`.** Verified: `RoutingOutput` still routes, `LessonDraft` succeeds repeatedly, a live learn lesson went `degraded 4/4` → `0/4`, regression still 206/204/2/0. Re-typing the field as all-optional `str | None` does **not** work (the `anyOf` item is rejected too). Evidence: `sources/manifests/writer_provider_diagnosis.json`.
- **`scripts/run_evaluation.py` refuses to overwrite an `aborted` artifact** unless `--force` is passed — a smoke run once destroyed a 42-run record's raw rows. Use `--output` to direct a run elsewhere, and check `scope` (`full` vs `smoke(n items)`) before trusting an artifact as a full pass.
- **AvalAI returns 429 `insufficient credit`** sometimes — check the account balance before any long live run.
- **`HTTP_PROXY` is set to `http://127.0.0.1:56933` with no `NO_PROXY`.** `httpx` honours it by default, so loopback requests get proxied and fail (seen as a bogus `404`). Use `trust_env=False` in httpx, and bypass the proxy for `127.0.0.1` in any Node/Python client. This will matter for W4.
- The first real SymPy call pays a cold spawn on Windows (~15 s); the 5 s default `math_timeout_seconds` reports a false timeout. Use ≥30 s for one-shot acceptance runs.
- **Python is 3.10 — `asyncio.TaskGroup` does not exist.** Use `asyncio.gather` with a semaphore for bounded concurrency.
- **A sequential live evaluation costs ~19 s per lesson.** Always run the harness concurrently (`scripts/run_evaluation.py --concurrency 8`).
- LangSmith tracing is configured but the key is forbidden (403); wrap live runs in `tracing_context(enabled=False)` (as `cli.py` does) or the logs fill with ingest errors.


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
