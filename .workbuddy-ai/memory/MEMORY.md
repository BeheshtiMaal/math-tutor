# MathTutor — project conventions

## Workflow rules (from `math_tutor_web_roadmap.md` and spec v3.0 §21)

- **One phase at a time.** Finish the current phase and its exit gates, update `IMPLEMENTATION_STATUS.md` with *actual* results, report, then **stop and wait for explicit user go-ahead**. Never start the next phase automatically.
- **Report only what was actually run.** Do not claim success for anything not executed. Mark incomplete items as incomplete.
- **Keep the existing regression tests passing.** Baseline after W2/W3: **206 tests, 204 passed, 2 skipped, 0 failures** (~150–250 s). W2 added 31 (`tests/test_web_refactors.py`); pre-W2 baseline was 175; W3 added none. The 2 skips are pre-existing: missing-SymPy (`test_answer_graph.py:190`) and optional local-E5 (`test_semantic_retrieval.py:338`). Record exactly which tests changed and why. Run it with `.venv/Scripts/python.exe -m unittest discover -s tests` — **pytest is not installed**.
- The roadmap file lives outside the repo (`C:\Users\Alireza\Downloads\math_tutor_web_roadmap.md`); it is user-supplied, not stored in the workspace.
- Phase progress: W0–W7 implemented; **W7 checked** (sources/manifests/phase_w7_report.md). Latest regression: 273 run, 271 passed, 2 skips; frontend 29 passed; Chromium 8/8 and Firefox 8/8; typecheck/build passed. Component state, sequence and pending replay identity persist in IndexedDB. W3 historical quality/content-verification limits remain in w3_completion.md. Next is **W8** — do not start without explicit go-ahead.

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
- W7 `ui_event` is implemented: matching typed envelope and empty message required; issued step/slider binding, same-thread Command resume, checkpointed ID/sequence ordering and five-events/five-seconds limits. Informational actions stay local. See sources/manifests/phase_w7_report.md.
- Remaining placeholders: `level_suggestion` is `null` until W8; `usage` values are `null` until W9. Blocks use the validated component union; W7 event replies expose accepted/duplicate/stale status.
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


## Learner-facing language/GenUI policy (2026-10-14)

- Select useful visuals automatically; the learner must not need to name components. Use source-grounded defaults when model blocks are absent/invalid, retaining real backend samples and checks.
- Persian conversations and worked-example prose stay Persian; math/function names alone never switch the language. Preserve exact source math during translation. Intentional language changes remain supported.
- Do not display citations, source IDs/equation references, or Paul/source coverage notices. Retain evidence provenance and retrieval/verification diagnostics internally.
- W6 user-chat fixes checked with 249 Python tests (247 pass, 2 skips), actual model HTTP turns and Chrome SSE. Full details: sources/manifests/lesson_fixes_report.md. Original user history was read through an authorized copied snapshot and not modified. W7 remains unstarted.


- Visual-frequency preference (2026-10-14): do not generate a new chart for every learner message. Existing chart content is checkpointed and reused across follow-ups, simplification and continuation. Only different function/derivation content warrants a new visual. Preserve automatic first-lesson selection. Verified with 65 targeted tests and four actual model turns; see sources/manifests/visual_frequency_report.md.


- Example UI preference (2026-10-14): when the learner requests an example, prioritize step_reveal for that exact sourced example while preserving full text and current lesson index. English/Persian natural requests infer learn mode unless explicitly overridden. Topic-note examples can fill a missing bank. Fixed log examples are checked; formal named-function/derivative notation displays as unsupported, never falsely verified. Generic graphs are not added on ordinary follow-ups after an example reveal. Verified with 74 targeted tests, actual Persian logarithm/derivative requests and ten KaTeX formula renders; sources/manifests/example_ui_report.md.

- Geometry canvas (2026-10-14): geometry_canvas:1 supports unit circle, triangle and vectors; bounded numerical backend geometry drives every drawn measurement. Natural topic requests select it; existing scenes are reused. Drag/keyboard/sliders/reset and saved scene/results work without new tutor turns. Degenerate/zero-vector angles stay undefined; no proof claim. Backend 265 pass/2 skip, frontend 24 pass, typecheck/build and both browser engines pass; actual Persian circle/normal update proxy checked. See sources/manifests/geometry_canvas_report.md. W7 unstarted; real servers on 3000/8765.

- Latest phase: W7 complete (2026-10-14), W8 unstarted. Component confusion/current graph/text recovery reach the tutor without advancing or repeated retrieval/components; transparent messages and saved identity. Eleven nodes/edges unchanged; contracted ui_event state field populated. Backend 271 pass/2 skip, frontend 29 pass, typecheck/build, Chromium 8/8 and Firefox 8/8. Actual Persian event reactions checked; initial planner fallback remains disclosed. Updated bilingual fixtures; optional replay headers now forwarded correctly. See sources/manifests/phase_w7_report.md. Real servers 3000/8765 left running; wait for explicit W8 go-ahead.

- Math rendering correction (2026-10-14): MathText uses lib/math-markdown.ts. Never use a replacement string containing $$ to normalize display math: JS collapses it to a single dollar. Preserve code/URLs, explicit inline/display modes and numerical notation. Latest copied Chrome chat went from 4 math/1 error to 14 math/0 errors; frontend 34 tests/typecheck and runtime checks passed. Saved originals untouched; refresh renders the fix. See sources/manifests/latex_rendering_fix_report.md. W8 remains unstarted.

- Latest phase: W8 complete (2026-10-14); W9 unstarted. Header «حافظه یادگیری» manages bounded IndexedDB topic levels/weak points and local reset. Conservative bilingual automatic estimates are not proficiency assessments; session/stored manual choices win. Simplify/step confusion influences subsequent explanations; cached steps adapt after correction. HTTP profiles are ephemeral LearnerRuntime context, never checkpoint/config/cache state; legacy learner_profile key is null on web. Reset scrubs pending profiles and prevents old turns restoring memory, preserving chats/explicit session settings. Derived level_suggestion/plan_level added; eleven-node topology/Tavily-disabled preference unchanged. Backend 277 pass/2 skip, final affected 6+9+26 pass; frontend 40, typecheck/build; Chrome 10/10 and Firefox 10/10. Actual Persian levels/review checked, earlier planner fallbacks disclosed. See sources/manifests/phase_w8_report.md. Real servers 3000/8765 restored, fixture stopped, no commit requested. Stop before W9.

- Conversational examples (2026-10-14): «یه مثال برام میزنی» already matches intent. On bank translation failure use localized worked notes; optional UI conversion can use safe source derivative endpoints. Never truncate unsupported math into a prefix or claim formal differentiation verified. Only explicit example requests can repeat step_reveal; automatic charts and ordinary follow-ups stay deduplicated. Exact live phrase twice rendered reveals with unchanged step and no extra chart/KaTeX/page error. Final 54 actual graph/SymPy in-process checks and 13 normal-worker example/history checks pass; early OS worker delays disclosed. Report sources/manifests/colloquial_example_report.md. Original Chrome history read through isolated copy only; frontend/schema/topology unchanged, real servers running, W9 unstarted.
