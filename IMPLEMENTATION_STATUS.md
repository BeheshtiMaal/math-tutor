# Implementation status

Current work: AvalAI embedding migration completed. Earlier phase entries are historical; the latest entry records current behavior and tests.

## Phase 0 — Complete reference acquisition and organization

Status: **incomplete; preparation tooling implemented, originals awaited**.

Authority: version 2.5 of `specs/math_tutor_spec (1).md` and `specs/math_tutor_implementation_prompt (1).md`. The user subsequently explicitly directed ignoring Phase 0 and implementing Phase 1. Phase 0 remains incomplete and is outside the current task.

Changed files:

- `scripts/acquire_references.py`: repeatable optional downloads, local PDF/HTML conversion, validation, SHA-256, hash-bound review gates and measured reports.
- `requirements-acquisition.txt`: acquisition dependencies only.
- `sources/manifests/references.json`: 42 required unique references, exact expected local paths, provenance and usage fields.
- `sources/manifests/DOWNLOAD_CHECKLIST.md`: all 14 OpenStax books, 25 Paul lessons and three teaching references.
- `sources/manifests/acquisition_report.md` and `disk_usage.json`: measured inventory and gaps.
- `.gitignore`: prevents automatic publication of raw and converted corpora.
- `README.md`: Windows PowerShell download/conversion/review instructions and limitations.
- `tests/test_acquisition.py`: offline checks using synthetic inputs and mocked transfers.

Actual checks:

- Python 3.10.5; Beautiful Soup 4.13.3 available locally. pypdf not installed; real PDF conversion not exercised.
- `python scripts\acquire_references.py`: exit 2 as expected; 0/42 acquired/complete. Raw bytes: 0. Extracted text bytes: 0. Full measured totals are in `disk_usage.json`.
- `python -m unittest discover -s tests -v`: six tests passed. Tests cover required reference counts, paths escaping the workspace, invalid/missing originals, hidden solutions/TeX/MathML, changed-source review invalidation, and incomplete-transfer detection.
- Direct HTTP attempts in the prior acquisition work and the current turn failed with Windows socket error 10013. No original was downloaded. User offered to download originals; further bulk network attempts were not made.

Outstanding:

- User downloads the originals to checklist paths and records actual retrieval date, resolved URLs, edition and exact-source terms.
- Install pypdf locally, convert and inspect every reference, including formula fidelity and complete coverage.
- The current converter handles individual HTML documents. If a PDF is unavailable, complete multi-page HTML book acquisition/assembly needs an explicit section inventory; a preface is insufficient.
- Source permission for later tutor/product/AI ingestion is not cleared. Paul terms restrict product incorporation; current OpenStax notices restrict generative AI ingestion. These remain separate from private acquisition and conversion status.

User-supplied PDFs appeared under `files/` and have been preserved; no acquisition/conversion was run in the Phase 1 turn.

## Phase 1 — Workspace, configuration and contracts

Status: **implementation complete; environment exit check incomplete because SymPy is missing**.

User authorization: "ignore phase 0 and implement phase 1." Phase 2 was subsequently explicitly authorized; its current status is below.

Changed files:

- `agent.py`: typed state/reducers, routing/request/math/evidence schemas, expression AST validation and configurable limits, fresh request state, separate secret credentials, explicit one-time dotenv loading, async provider/search/retrieval protocols and lazy OpenAI integration.
- `cli.py`: offline configuration/dependency diagnostics and explicit Phase 1-only startup behavior.
- `requirements.txt`: dependency versions; `.env.example`: empty-value settings template.
- `tests/fakes.py` and `tests/test_contracts.py`: injectable offline services and configuration/schema/state/import checks.
- `.gitignore`: local environment/cache, secrets and user-supplied PDFs excluded.
- `README.md`: exact PowerShell commands, module boundaries, graph node/edge/barrier contracts, three teaching levels, full/step progression and actual dependency limitation. Phase 0 guidance retained.

Environment created with `python -m venv --system-site-packages .venv`, preserving and reusing globally installed libraries. Tested versions: Python 3.10.5, LangGraph 1.2.12, LangChain 1.4.2, langchain-openai 1.6.4, Pydantic 2.13.5, python-dotenv 1.2.3. SymPy 1.14.0 is required/pinned but not installed or tested. The provider was inferred from the presence of OPENAI_API_KEY, without inspecting or printing its value. TUTOR_MODEL is intentionally unset; no model ID/account capability was assumed.

Actual checks:

- Application imports passed inside `.venv`. A subprocess also patched socket connection functions to fail and successfully imported both modules and constructed the provider with a fake key, proving those checked paths make no network requests.
- Contract/configuration checks passed: blank template defaults, environment precedence, safe errors, explicit single dotenv load, credentials excluded from serialization/repr/state, supported problem payloads, hostile/malformed structures, input/depth/node/matrix limits, bounded history and fresh request resets, exact level/delivery enums, evidence provenance/status/verification rules and async injected service failures.
- Full offline test suite initially passed 20 tests (including the six retained acquisition checks). After adding math-result status consistency validation, `python -m unittest discover -s tests -p test_contracts.py -v` passed all 15 Phase 1 tests. The six acquisition tests passed in the earlier full run; no acquisition code changed in this phase.
- `cli.py --check` reports missing SymPy and returns 2; regular `cli.py` exits 0 with an explicit contracts-only notice.
- Two pip installation attempts could not resolve SymPy. `uv pip install --python .venv\Scripts\python.exe --cache-dir .cache\uv sympy==1.14.0` failed with Windows socket error 10013. No package download succeeded and the global installation was not modified.
- No live model/search requests, resource downloads, embeddings, database setup or tutor graph runs were performed.

Remaining exit-gate blocker: install the pinned SymPy dependency from a network-enabled terminal (or an offline wheel) and verify `cli.py --check` succeeds. Phase 1 code imports and schema checks work without it, but the required dependency environment is not complete. A configured model ID is only required when live provider use begins.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe cli.py --check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Next phase: Phase 2 — working concise answer path, only after explicit user continuation. Stop here.

## Phase 2 — Working answer path

Status: **incomplete exit gate: graph/CLI/worker implementation is present; actual math acceptance is blocked by missing SymPy**.

User authorization: "now implement phase 2." Phase 0 remains skipped/incomplete. No Phase 3 implementation, corpus conversion or download was performed.

Changed files:

- `agent.py`: compiled real four-node answer graph with START/END; validated classify routing; checkpointed essential clarification in existing nodes; durable extraction tasks to avoid replaying provider calls; one malformed-output repair; safe local math grammar and allowlisted SymPy constructors; spawned JSON-only workers with deadlines/kill/reap; domain/exclusion/unevaluated-result handling and concise deterministic answers.
- `cli.py`: repeated input, same-thread Command resume, fresh request/reset threads, help/mode/language/debug/exit commands, EOF/Ctrl+C, Unicode and one-shot/offline modes; inherited network tracing disabled in CLI execution.
- `.env.example`: numeric/power/output limits; `requirements.txt`: current-phase documentation, unchanged pinned versions.
- `tests/test_answer_graph.py`: actual compiled graph topology/routes/interrupts, injected service failures/repair/deadlines, parser and CLI cases, actual worker timeout and missing-dependency behavior; seven real SymPy acceptance tests defined but skipped.
- `tests/test_contracts.py`: replaces the obsolete Phase 1 unimplemented-graph assertion with the authorized Phase 2 partial topology check.
- `README.md`: current runnable behavior, exact commands, incomplete math status, syntax/operations, supported limits, final versus current graph distinction and actual checks.

Actual results:

- Full suite: 41 collected, 34 passed, seven real math tests skipped. After adding malformed-routing/nontext input handling and preserving clarification counters, the final focused Phase 2 run collected 21 tests: 14 passed, seven real math tests skipped.
- Tests invoke the real compiled LangGraph, inspect exactly classify/answer/math_tool/write_answer plus sentinels, exercise answer and explicitly unavailable learn routes, resume interrupts on the same thread, and confirm END has no pending next node.
- Concise x=6 was checked with an injected math result; **SymPy did not calculate x=6 here**. Provider clarification caching was verified with a fake client called exactly once across resume. Malformed output repair, provider error redaction and deadlines passed.
- CLI repeated-input, commands during clarification, reset, Persian digits, invalid preferences, EOF and inherited tracing disable checks passed. Offline CLI/worker smoke for `2x+5=17` returned the readable missing-SymPy message. `--check` reports graph available, learn unavailable and SymPy missing.
- Actual spawned worker timeout/kill/reap behavior passed without SymPy. Imports/client construction were also checked with sockets forbidden in the retained contracts suite.
- SymPy 1.14.0 remains absent. A fresh uv install attempt failed with Windows socket error 10013. Actual derivative, indefinite/definite integral, one/two-sided limit, equation roots, matrix/singular inverse and simplification-exclusion checks have **not run**. Their tests remain explicitly skipped until installation; Phase 2 cannot be called complete.
- Python 3.10.5, LangGraph 1.2.12, LangChain 1.4.2, langchain-openai 1.6.4, Pydantic 2.13.5, python-dotenv 1.2.3. Live provider smoke: not exercised (model ID unset); live search/embedding: outside Phase 2.
- Initial graph verification exposed Python 3.10 runnable-context propagation and inherited LangSmith telemetry attempts. Explicit runnable context fixed task/interrupt execution; CLI and offline tests now disable network tracing. Initial telemetry attempts failed under network restrictions; no successful live provider/service request occurred.

Runnable inspection:

```powershell
.\.venv\Scripts\python.exe cli.py --check
.\.venv\Scripts\python.exe cli.py --offline
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_answer_graph.py -v
```

To remove the blocker, use a network-enabled terminal or an offline wheel:

```powershell
.\.venv\Scripts\python.exe -m pip install sympy==1.14.0
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe cli.py --offline --query "2x+5=17"
```

Limitations: learn mode explicitly unavailable until Phase 4; no prepared corpus/runtime example bank; math implementation not yet validated against real SymPy; local syntax defaults to variable x, free-text assumptions/compound power exponents/symbolic integration bounds unsupported; full teaching CLI remains future work. Missing dependency and failed exit checks must be resolved and accurately recorded before declaring Phase 2 complete.

Next phase: Phase 3 — curated example bank and teaching preparation, only on explicit user continuation. Stop here.

## Phase 4 — Exact parallel learning graph

Status: **graph implementation and offline acceptance checks pass; real-corpus exit gate remains incomplete**.

User authorization: "implement phase 4." This explicitly bypasses Phase 3 preparation. No reference download, PDF conversion, runtime corpus creation, bank import, embedding or live search was performed. Existing supplied PDFs were preserved.

Changed files:

- `agent.py`: exactly eleven compiled nodes plus START/END, validated answer/learn routes, four independent resource edges from learn, one `add_edge(list(RESOURCE_NODES), "write_explanation")` barrier, writer/user_input loop and conditional done to END. Typed lesson objective, shared evidence request, emission version, selected example and new-topic boundary fields reset for each request. URL serializers retain validation while making provenance checkpoint-compatible. Existing answer behavior is retained.
- `learning.py`: bounded local Markdown/JSON passage retrieval with required provenance, compact JSONL Paul example retrieval, level/subtopic filters, deduplication and three-per-pool cap, rule reading, supported symbolic example comparisons, seven learning node bodies, level-specific full synthesis with bounded schema/citation repairs, honest passage fallback, deterministic citations and one rotating example, checkpointed follow-up/done. Resource service injection permits controlled fake workers; graph scheduling remains entirely LangGraph.
- `cli.py`: reports Phase 4/full-learning availability and missing corpus, displays explanations before pauses exactly once, same-thread resume/done, fresh-request boundary for explicitly requested different topics. Existing commands remain; advanced step controls are not implemented.
- `tests/test_learning_graph.py`: real topology/barrier/concurrency/interrupt/CLI/file-evidence checks. Existing contracts and answer tests now inspect the complete graph and honest missing-evidence learn route.
- `README.md`: current graph, service interfaces, local evidence formats, scope, commands and limitations. `requirements.txt`: phase comment only; pins unchanged.

Actual checks/results:

- Final full offline suite: **59 tests collected; 51 passed; eight skipped** because SymPy is absent. Phase 4 focused suite: 17 collected, 16 passed, one real symbolic equivalence check skipped. The other seven skipped tests are retained Phase 2 actual-math checks. No skipped check is counted as passed.
- The actual compiled graph's complete node and rendered edge sets match the specification. Its builder has exactly one waiting edge containing all four resource predecessors; there are no extra coordinator/validator/clarification nodes or resource-to-resource edges.
- Event-controlled fake workers all start before any finishes. Releasing three leaves the writer uncalled; releasing the fourth yields exactly one writer invocation. The same run includes a failed guidance branch and skipped web branch, preserves the successful evidence, and reaches the real checkpointed user_input interrupt.
- Temporary **synthetic** local notes, metadata, JSONL examples and rules feed the actual file adapter and actual graph. Tests preserve formulas, URL/author/section/retrieval date/terms, show one level-matching example, exclude rejected/malformed records, enforce compact counts/deduplication and avoid repeating the last example.
- Fake model checks verify distinct beginner/intermediate/advanced prompts, source-ID validation and bounded repair/fallback. These check application behavior, not live model factuality or genuine corpus coverage.
- Follow-ups preserve the lesson objective and recent explanation, invoke only the writer and keep the initial three retrieval calls unchanged. Same-thread done/تمام reaches END without another writer/model call. CLI help during pause does not repeat output; each explanation version prints once. An explicit different-topic teaching request ends the old checkpoint and starts a fresh request.
- Timeout/wrong-record resource failures still reach the barrier/writer. Missing notes/examples/rules remain explicit empty results; no model call is made to fabricate absent lesson evidence. Live web search remains skipped even when enabled in configuration; the injected search backend is never called.
- Stored computational verification assertions are not trusted automatically. Injected symbolic workers check zero/nonzero differences and antiderivatives by differentiation, retaining domain assumptions. Missing/unresolved workers leave unknown status; unsupported equation/matrix result representations remain unsupported. **Actual SymPy equivalence was not exercised**.
- `cli.py --check` reports Phase 4, exact graph/full learning available, step unavailable, all three prepared-corpus presence flags false, model unconfigured and SymPy missing. Offline learn one-shot displays the honest missing-corpus explanation and checkpoint prompt, without network calls; its application return code is 2 for the pending interaction.
- Tested environment unchanged: Python 3.10.5, LangGraph 1.2.12, LangChain 1.4.2, langchain-openai 1.6.4, Pydantic 2.13.5, python-dotenv 1.2.3. No successful live provider/search request or new dependency installation was attempted in Phase 4.

Unresolved exit-gate blockers/limits:

- Prepared actual topic notes, curated Paul examples and original teaching rules are absent because Phase 3 was bypassed. Actual provenance-backed corpus acceptance cannot be declared passed using temporary test fixtures. PDFs alone are not runtime notes or a curated bank.
- SymPy 1.14.0 remains missing after earlier network socket error 10013. Real symbolic calculation/verification remains untested; install it from a network-enabled terminal or offline wheel and run the skipped checks.
- No model ID is configured. Offline display uses actual passages and level framing; tailored full explanation/follow-up quality needs a configured model and actual corpus. Live smoke is not claimed.
- Keyword/topic aliases are basic, not Phase 6 bilingual semantic retrieval. Oversized whole source passages are omitted with a notice rather than cutting formulas. Matrix/solution-set example verification needs additional dedicated checks before those claims can be called verified.
- Step-mode progression, next/simplify/full controls and the remaining robust teaching CLI are Phase 5. Live web search is Phase 7. No future phase has been implemented or advertised as complete.

Runnable checks:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_learning_graph.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe cli.py --check
.\.venv\Scripts\python.exe cli.py --offline
# In the CLI: /mode learn, then a question; follow up or reply done / تمام.
```

Next phase: Phase 5 — interactive step teaching and robust CLI, only after explicit user continuation. Stop here; Phase 4's actual-corpus/real-symbolic gaps remain recorded above.

## Phase 5 — Interactive step teaching and robust CLI

Status: **implementation and offline Phase 5 exit checks complete; real-corpus/live-model teaching remains unvalidated**.

User authorization: "implement phase 5." Earlier Phase 0/3 corpus and Phase 1/2/4 dependency/integration gaps remain unresolved. No downloads, PDF conversion, corpus preparation, semantic embeddings, live model requests or live search were performed. Phase 6/7 features were not implemented.

Changed files:

- `agent.py`: extends validated LessonStep with cached text and source IDs; typed current-step content/completion fields initialize cleanly at new-request boundaries. The compiled eleven-node graph, exact edges, checkpoint implementation and four-resource waiting barrier remain the architecture used by the new interaction path.
- `lesson_steps.py`: validated 2–3 sentence step/plan schemas; bounded typed resume replies; Persian/English next/simplify/full/done aliases; ambiguous acknowledgments remain follow-ups; offline source-excerpt chunking protects explicit TeX/code units and decimals. Oversized whole units produce a coverage notice rather than broken formula fragments.
- `learning.py`: step mode is implemented instead of forced to full. The writer caches a plan once, emits only the current step, advances once only for next, simplifies/answers at the same index, reveals only the remainder on full, delays one matching example to its final step unless explicitly requested, and preserves provenance/verification status. Completion does not invent further steps. User input interrupts validate bounded replies and re-prompt safely; repeated invalid replies end the lesson. No nodes/edges or resource reruns were added for follow-up.
- `cli.py`: adds delivery/level commands and Persian level labels; settings apply to the next request, with /delivery full also resuming an active learning lesson. Commands do not become math clarification replies. Reset clears pending interaction/history/emission cursors, EOF/Ctrl+C exit cleanly, emitted versions prevent repeated chunks, and debug prints only new safe node/status traces. Diagnostics now report Phase 5/full/step availability.
- `tests/test_step_teaching.py`: new focused interaction/CLI/schema acceptance checks against actual LangGraph. `tests/test_learning_graph.py`: replaces the obsolete unavailable-step assertion with a real Persian step pause. README and requirements phase comment updated; dependency pins unchanged.

Actual checks/results:

- Initial focused run: **19 Phase 5 tests passed**. After adding explicit-example, Persian-content and provider-timeout cases, the full suite collected **81 tests: 73 passed, eight skipped**. All **22 Phase 5 tests passed** in that full run. The skips are seven earlier real math cases and one real example-equivalence case, all blocked by absent SymPy; none counted as passed.
- Tests use the actual compiled LangGraph, its real in-memory checkpoints and same-thread Command resume. The existing complete topology/barrier/concurrency checks still pass. Fake clients supply synthetic evidence and provider responses; they never replace graph scheduling.
- First step emits two short sentences, provenance and a checkpoint prompt, with no future method or example. Resume does not replay planning. Each next/بعدی/اوکی advances one index and emits once; cached plan IDs/content stay stable. The sourced example is displayed once only at its final step, retaining provenance and unknown computational status.
- Confusion/simplification and ordinary questions keep step_index/last_emitted_step fixed, preserve objective/current explanation in the provider context, and do not rerun resource nodes. Ambiguous “Okay, but why?” does not advance. Explicit example requests show one source-backed example without moving the index; full later prefers another candidate.
- Full/کامل بگو explains only the undisplayed remainder, includes its final example once, sets full delivery/completion and preserves the checkpoint for follow-up/done. Next at completion does not create an endless plan. Early done/تمام reaches END without exposing future material or another provider call. Done after full does not reprint the explanation.
- Real CLI execution inside focused tests exercises all commands, bad enums/commands, blank input, Persian controls, help during pauses, stable output versions, no repeated debug history, /delivery full during learning versus math clarification, reset/new plan, EOF and Ctrl+C. One-shot step returns 2 after displaying exactly one chunk/pause. Reset starts at step zero with fresh retrieval/planning and retained preferences.
- Schema/source-ID repairs are bounded to two; malformed plans and step replies degrade to actual excerpts without exception/secret leakage. Planning timeout is recoverable. Direct malformed/empty/oversized resume payloads re-prompt without advancing or replaying model work; repeated invalid replies end safely.
- Missing corpus/model produces a short honest unavailable-evidence message. Offline simplification repeats the current source excerpt with an explicit tailored-simplification limitation. Formula preservation was checked with synthetic TeX/decimal source content. These are not claims about real downloaded book fidelity or actual live provider quality.
- Actual subprocess smoke: `cli.py --offline`, with mode learn, delivery step, level beginner, language en, question, simplify, full, done and exit, returned **0**, with empty stderr and readable missing-corpus messages. This exercises the actual CLI process; it does not constitute a real sourced mathematics lesson.
- `cli.py --check` reports Phase 5, full/step available, all prepared-corpus flags false, model unconfigured and SymPy missing; its application code remains 2 until dependencies are complete. Tested library/Python versions match Phase 4; no packages were installed.

Current limits and outstanding earlier-phase blockers:

- No actual topic notes, curated Paul bank or teaching guidance exist. No model ID is configured. Tailored teaching and mathematical explanation quality have only been checked with fake provider responses and synthetic source fixtures, not a live model/real corpus. Corpus preparation remains Phase 3 work.
- SymPy 1.14.0 remains absent; earlier symbolic acceptance and actual example verification are untested. The earlier socket error 10013 download blocker was not retried in this phase.
- Settings other than an active /delivery full apply at the next request boundary, as explained by CLI help. Offline excerpts cannot provide tailored simplification/answers; that limitation is reported explicitly. Source citations and complete example records are displayed separately from the short teaching body.
- The sentence helper is basic and bounded, not structural/semantic corpus ingestion. Ordinary follow-ups reuse cached evidence and must acknowledge insufficient coverage rather than invent an answer. No new retrieval node/route or semantic refresh backend was introduced.
- Live search remains explicitly skipped until Phase 7. Semantic bilingual retrieval and embedding/cache setup remain Phase 6. Project completion is not claimed.

Inspect the implementation:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_step_teaching.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe cli.py --offline
# Then: /mode learn, /delivery step, /level beginner, and a topic question.
# Replies: next / بعدی; simplify / نفهمیدم; full / کامل بگو; done / تمام.
```

Next phase: Phase 6 — bilingual local semantic retrieval, only after explicit user continuation. Stop here.

## Phase 6 — Bilingual local semantic retrieval

Status: **code and offline infrastructure checks complete; real-model and real-corpus exit checks incomplete**.

User authorization: "implement phase 6." Earlier skipped Phase 0/3 corpus preparation remains incomplete. No source documents were acquired, converted or manufactured. Phase 7 live search remains skipped.

Changed files and runnable behavior:

- `retrieval.py`: lazy local-only multilingual E5 adapter, coherent heading/paragraph chunks protecting math/code fences and repeating explicit assumptions for linked children; example statement/solution remains one complete logical record with unchanged quota. Atomic NumPy caches store vectors, stable IDs, content hashes, full logical records/provenance and model/settings identity. Cosine ranking filters eligible source/example chunks; compatible broader source coverage is reported. Missing model, incompatible cache or invalid vectors produces a labelled keyword fallback, never a semantic success claim. Changed/new chunks alone are embedded; unchanged vectors are reused and deleted records removed.
- `agent.py`: embedding configuration and typed source parent/adjacent references; default retrieval is the semantic adapter, with injectable embedding service. Exact eleven real LangGraph nodes, edges, fan-out and all-four predecessor barrier remain unchanged.
- `learning.py`: separates full corpus loaders from request filtering and verification, preserving bank IDs/three-example limits. Resource-node sanitation retains retrieval labels and explicitly broader source evidence. Computational verification remains independent of relevance ranking; absent SymPy leaves unknown status.
- `cli.py`: Phase 6 diagnostics, `--index` and explicit `--index --rebuild-index`, without provider calls/downloads. Empty banks report empty, not successful ingestion. `.env.example` lists model/cache settings.
- `requirements.txt`: tested NumPy 2.2.1. `requirements-embeddings.txt`: optional sentence-transformers range, **not installed/tested here**. `scripts/download_embedding_model.py`: explicit pinned download helper with local model identity marker; successful network transfer has not been tested. Runtime never invokes it automatically.
- `tests/test_semantic_retrieval.py`: fixed English/Persian queries against synthetic English passages and distractors, cache reuse/change/removal/mismatch/corruption, linked mathematical chunks, complete examples, level/quota/provenance, real graph and local-only adapter/prefix behavior. README documents setup, formats and limitations.

Actual checks/results:

- Final full suite: **99 collected, 90 passed, nine skipped**, in 12.219 seconds. Eight skips require absent SymPy; one requires actual sentence-transformers/model weights. All earlier graph/barrier/CLI checks still pass. Focused retrieval suite: **18 collected, 17 passed, one skipped**.
- Earlier full run collected 97 checks and hit a 60-second subprocess timeout in the existing offline import/provider-construction check. The focused contracts rerun passed all 15; after the two additional cache/adapter tests, the final full run passed as reported above. No network access was permitted in the offline-construction check.
- Fixed injected embeddings exercise fa/en paraphrases and distractor ranking with actual returned text/provenance; they are service fixtures, **not evidence of multilingual E5 accuracy**. Real-model acceptance remains skipped rather than counted as passed. Missing embeddings fall back to labelled bilingual keyword/metadata matching.
- Repeat ingestion/restart embeds no unchanged documents. Modifying one source embeds only its changed chunk; removing records drops them. Revision/dimension/normalization/preprocessing mismatch, corrupt cache and zero/nonfinite vectors are rejected. Explicit rebuild permits the intended new model/settings.
- Assumptions and multi-line display formulas, including blank lines inside align/$$ environments, remain intact. Indivisible oversized formulas are omitted with coverage warnings. Oversized example child chunks preserve one logical ID, complete original solution/label/provenance and adjacent links without increasing the example quota. Whole-record evidence budgets yield explicit empty coverage rather than truncation.
- Actual subprocess diagnostics and index commands return **2**, with empty stderr, missing package/cache/corpus flags and two empty banks. An actual offline CLI step/done/exit smoke returns **0**, with empty stderr and missing-evidence messages. This does not establish real sourced teaching quality.
- Actual package attempt: `pip install --disable-pip-version-check --retries 0 --timeout 5 'sentence-transformers>=3,<6'` failed with no matching distribution available from the accessible index. A model config HEAD request failed with Windows socket error **10013**. No embedding package or model weights were installed; no cache/model or corpus success is claimed.

Model selection and outstanding limits:

- Selected `intfloat/multilingual-e5-small`, pinned revision `fd1525a9fd15316a2d503bf26ab031a61d056e98`, 384 dimensions, L2/cosine, maximum 512 tokens and passage/query prefixes. Selection follows the [model card](https://huggingface.co/intfloat/multilingual-e5-small) and [local-only adapter API](https://sbert.net/docs/package_reference/sentence_transformer/model.html). The pinned revision is an identity, not a claim that it is the latest. Real Persian/English retrieval quality still requires actual weights and acceptance execution.
- Prepared topic text, curated Paul bank and teaching guidance remain absent. Source sidecars must supply reviewed provenance/topic mappings; embedding does not establish formula fidelity, permissions or correctness. Actual corpus coverage and real model acceptance remain required to complete this phase's exit gate.
- SymPy 1.14.0 remains absent. No actual supported symbolic verification or live language-model/search request ran. Follow-ups reuse evidence without rerunning resource graph nodes. No Phase 7 functionality was implemented.

Inspect/setup from the project directory:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_semantic_retrieval.py -v
.\.venv\Scripts\python.exe cli.py --check
# On a network-enabled terminal:
.\.venv\Scripts\python.exe -m pip install -r requirements-embeddings.txt
.\.venv\Scripts\python.exe scripts\download_embedding_model.py
$env:TUTOR_EMBEDDING_MODEL_DIR = 'E:\Agentic\MathTutor\.cache\models\multilingual-e5-small'
# After supplying the separately prepared corpus:
.\.venv\Scripts\python.exe cli.py --index
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Next phase: Phase 7 — live web search and final integration, only after explicit user continuation. Stop here; the Phase 6 real-model/corpus blockers remain recorded above.

## Phase 7 — Live web search and final integration

Status: **implementation and offline integration checks complete; real mathematical/corpus/live-service acceptance incomplete**. Project completion is not claimed.

User authorization: "implement phase 7." No additional graph nodes, routes, corpus generation, dependency downloads or third-party messages were introduced. Earlier Phase 0/3 preparation and missing SymPy/embedding dependencies remain unresolved.

Changed files and behavior:

- `web_search.py`: asynchronous Tavily HTTPS adapter using installed HTTPX 0.28.1, independently called from the existing web branch. Requests basic search, at most five results, no generated answer/raw-page content/images. Streamed responses are limited to one megabyte; types/URLs are validated, duplicate URLs removed, and actual whole snippets bounded before reaching writers. Deadlines cancel pending work. Missing keys/disabled configuration skip; authentication/rate/network/malformed/oversized failures return safe status records without credentials or response bodies.
- `agent.py`: explicit Tavily backend setting and source-origin metadata; passes the injected search client into the existing learning nodes. Keys stay outside state/checkpoints. The actual eleven-node LangGraph, answer chain, four independent resource branches, all-four predecessor barrier and writer/user-input loop remain exact.
- `learning.py`: web snippets join bounded local evidence for full/step planning, response and deterministic citations. Stable URL-derived IDs retain title, URL and retrieval time; unestablished authors/source terms are honestly marked. Snippets are supplementary rather than a Paul-bank replacement or complete reviewed page. Local text takes priority in the combined context budget. Follow-ups use cached evidence with no resource replay. Writer checks reject duplicate/unknown source IDs and explicit unsupported tool-verification claims, with at most two repairs and honest excerpt fallback; they do not formally prove mathematics.
- `cli.py`: constructs the configured backend at explicit startup, reports Phase 7/search presence flags and HTTPX version; `--offline` disables both provider and search calls, permitting only local embedding loading. Full/step, reset, one-time output and answer-only behavior remain intact.
- `.env.example`, `requirements.txt`, `README.md`: search setup, tested HTTPX pin, offline/live commands and limitations. No Tavily SDK installation is required; integration follows the [official REST documentation](https://docs.tavily.com/documentation/api-reference/endpoint/search).
- `scripts/check_live_services.py`: opt-in status-only provider/search/local-embedding smoke for configured and available services. Reports passed/failed/not_exercised independently; exit 2 means at least one check did not pass. Never invents availability or downloads missing weights. Provider coverage is one structured response, search one request, embedding one Persian query against two English synthetic passages.
- `tests/test_final_integration.py`: nine new checks against real HTTPX/LangGraph with synthetic service responses. The earlier search-disabled fixture is updated to explicitly disable search, matching its intent after this phase.

Actual checks/results:

- Full suite: **108 collected, 99 passed, nine skipped**, 19.020 seconds. The eight real symbolic checks remain skipped for absent SymPy; the actual embedding acceptance case remains skipped for absent embedding package/model. All nine new Phase 7 tests passed; exact topology/barrier/event-controlled overlap, one-example selection, concise answer routing, full/step controls and CLI failure recovery remain covered by the passing prior suite.
- Focused Phase 7 run: **nine tests passed**. Real asynchronous HTTP mocks exercise payload/prefix auth without secret output, deduplication/provenance, invalid URLs, whole-record budgets, empty results, 401/429/500, malformed JSON, oversized response, connection error and actual cancellation at a short deadline. Graph tests exercise full/step web citations, cached follow-ups, local lesson preservation on search failure, one sourced example, bounded repair exhaustion and CLI finish/reset/exit.
- The initial full run exposed citation formatting accessing source-origin metadata on ExampleRecord. It was corrected to default non-source records to ordinary sourced citations; the final full suite above passes. No failure was counted as a successful acceptance check.
- Actual subprocess smoke: offline CLI performs full lesson/done, then step/full/done/exit; returns **0** with empty stderr. The corpus is absent, so this validates honest missing-evidence interaction rather than real source-backed teaching quality.
- Actual diagnostics return **2**, with empty stderr: Phase 7 available, search disabled, search key absent, provider model unset, all prepared-bank flags false, embedding package/cache absent and SymPy null. Credential presence alone does not establish provider availability; no values are printed.
- Actual live-service checker returns **2**, empty stderr, with all three services **not_exercised**: provider model unconfigured, search disabled/key absent, embedding package unavailable. No successful live model/search/embedding request is claimed. This phase did not retry the prior socket error 10013 download blocker or install packages.

Remaining acceptance blockers:

- Prepare/review the actual corpus, provenance/topic mappings, three-example-per-pool Paul bank and teaching guidance from earlier phases; validate formula fidelity and actual coverage.
- Install SymPy 1.14.0 and execute actual mathematical/example verification acceptance. Unsupported verification representations remain honestly unsupported/unknown; text consistency checks are not mathematical certification.
- Install the optional embedding package and pinned model, build the actual indexes and pass real fa/en retrieval acceptance. Current bilingual ranking checks use artificial service fixtures, not model accuracy evidence.
- Configure an available provider model and Tavily key, then execute live checks on a network-enabled machine. Live output quality, external connectivity and real-corpus teaching remain unvalidated.

Inspect the result:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe cli.py --check
.\.venv\Scripts\python.exe cli.py --offline
.\.venv\Scripts\python.exe scripts\check_live_services.py
```

For live search set `TUTOR_SEARCH_ENABLED=true`, `TUTOR_SEARCH_BACKEND=tavily`, and `TUTOR_SEARCH_API_KEY` in the local `.env`; configure `TUTOR_MODEL` for provider synthesis. README records model-download/index setup and acquisition instructions. No phase follows Phase 7 in the governing plan. Stop here; resolve the listed acceptance blockers before claiming project completion.

## Follow-up verification — Installed dependencies and AvalAI configuration

User reports completing setup and requests checks/next steps, then clarifies that both service keys are AvalAI-issued and the model base URL is `https://api.avalai.ir/v1`.

- Confirmed SymPy **1.14.0**, sentence-transformers **5.7.0**, Torch **2.14.1**, Transformers **5.19.0**, and pinned multilingual E5 files/identity marker are installed locally. These supersede historical missing-package notes above.
- Added validated `TUTOR_MODEL_BASE_URL`, `TUTOR_SEARCH_URL` and `avalai_tavily` backend. Chat uses the configured base URL; AvalAI Tavily uses `/v1/search/tavily-search`, its documented request parameters and `snippet` response field, while direct Tavily retains its own route/content field. Sources: [AvalAI quick start](https://docs.avalai.ir/en/quickstart), [Tavily API](https://docs.avalai.org/en/providers/tavily).
- Preserved local keys while correcting `.env` endpoints and adding 20-second math/60-second request deadlines. A five-second calculation initially timed out; actual `cli.py --offline --query '2x+5=17'` subsequently returned **x=6**, exit 0.
- Both OpenAI and AvalAI key variables were inherited with different values from the local file. Added dedicated `AVALAI_API_KEY` selection and explicit opt-in `TUTOR_KEYS_FROM_DOTENV=true`; only nonempty file credential values override inherited credentials when enabled. The local chat key was moved to its dedicated field without printing it. Verified effective model/search keys now match the local file; no credential values appear in reports or graph state. Default environment precedence remains unchanged when the opt-in is false.
- Initial installed-dependency run: 108 checks, two timeout failures (real derivative worker and old local-file graph fixture), two skips. Updated the Phase 4 file fixture to explicitly test keyword retrieval independently of model loading, and actual E5 acceptance to load the configured local model directory. The focused answer/math suite then passed **20 of 21**, skipping only the missing-SymPy case because SymPy is installed.
- Full verification with installed math/model and endpoint tests: **110 collected, 109 passed, one skipped**, 117.353 seconds. Real differentiation/integration/limits/roots/matrices/simplification and actual Persian/English E5 retrieval acceptance passed. After the additional credential-preference test/change, reran the affected suites: **12 final-integration tests passed**, **15 configuration/contract tests passed**. No repeat of the full suite after that small credential change is claimed.
- Embedding smoke passed: actual Persian query ranked the derivative passage over an English matrix distractor. This is synthetic fixed-case model acceptance, not actual corpus coverage.
- Live AvalAI chat/search requests failed to connect. A separate key-free endpoint connectivity check traced **PermissionError errno 13 / Windows error 10013**. This execution environment therefore cannot validate remote key authorization, credits, model access or live search; failures must not be interpreted as invalid keys. Run `scripts/check_live_services.py` from the user's network-enabled terminal.
- `cli.py --index` reports **both banks empty**. `sources` contains manifests only: prepared topic notes, Paul example bank and teaching guidance remain absent. No index/model re-download is needed until actual prepared evidence is supplied. Real sourced teaching and corpus acceptance remain incomplete.

Next required work: complete the skipped reference review/Phase 3 preparation, then build local indexes. Verify AvalAI from the user's terminal and run the interactive tutor. Existing PDFs remain preserved; no corpus records or source attribution were manufactured during these checks.

## Scope revision — four-book Phase 3 acquisition

Documentation-only work authorized. Version 2.6 removes the preliminary acquisition phase, retaining phases 1–7 with limited downloading/text extraction inside Phase 3. Required books are Calculus Volumes 1 and 2, College Algebra 2e and Introductory Statistics 2e. LangGraph-only execution, bilingual structural/semantic retrieval and the compact Paul selection policy remain unchanged. Canonical spec/prompt filenames now exist; the `(1)` files are redirects.

Phase 3 is not currently authorized: the most recent authorized implementation was Phase 7, followed by verification. Downloading/extraction and current PDF URL/license resolution remain scheduled for explicit Phase 3 execution. Books downloaded in this revision: none. Total actual download size this revision: **0 bytes**. Download/extraction failures: none, because no attempt was made. Old broad-acquisition manifests/reports/scripts remain historical and are not authority for the revised four-book plan. No implementation or future-phase downloads ran.

Validation: preserved Phase 1/2/4/5/7 prompt bodies verbatim; preserved sole LangGraph orchestration, bilingual retrieval and compact-example policy sections verbatim; preserved every existing Paul reference URL; both source lists contain exactly the four required OpenStax book-page URLs. Stop at the end of this documentation revision.

## Phase 3 execution — 2026-10-09

Phase 3 was explicitly authorized and executed on 2026-10-09. Exactly four official PDFs were resolved and downloaded: **207,178,833 actual bytes**, zero partial transfers; readable extracts total **5,397,578 bytes**. Actual PDF/license URLs, author metadata, paths, hashes, page diagnostics and statuses are in [the core manifest](sources/manifests/openstax_core.json).

The Phase 3 exit is **incomplete**: visually reviewed pages show missing formula images or flattened notation in all four extracts, which remain excluded from retrieval. Seven clearly attributed original starter notes, 15 original level-specific teaching rules, a schema/deduplicating importer and 51 distinct selected Paul examples are prepared. Mathematical result checks: 27 verified, 23 unsupported, one unknown; 21 topic/level slots remain missing. The three-per-topic-per-level policy is unchanged. No additional books, full-site crawling or entire example collection was downloaded; LangGraph-only execution and bilingual retrieval remain unchanged. No later phase was implemented in this run.

See [the Phase 3 report](sources/manifests/phase3_report.md), [selected-example counts/rationales](sources/manifests/paul_selection.json) and [topic registry](sources/manifests/topic_registry.json) for actual results and remaining work. Earlier acquisition reports are historical.

Final full regression: 119 collected, 118 passed, one expected skip. Final affected learning suite: 19 passed. Actual-corpus keyword/real-LangGraph smoke and idempotent 51-record import passed. Phase 3 formula exit remains incomplete; no later implementation phase started. See the report for initial failures and corrections.

## AvalAI embedding migration — 2026-10-09

Initialized local Git on `main` and committed the existing implementation/docs as `370a876` before migration. API keys, environment, generated caches and private source originals remain excluded; no remote repository/push was configured.

Added a bounded, validated AvalAI embedding adapter, credential injection outside graph state, backend-specific defaults/cache metadata, safe failures and an offline network guard. Active `.env` now uses `text-embedding-3-large`, 3,072 dimensions and a separate `.cache/retrieval/avalai/text-embedding-3-large` cache. Existing chat/search keys and endpoints were preserved. API calls use the user's AvalAI key; no local model is loaded in this backend. Graph topology is unchanged.

Actual preparation: 28 source-note passages + 51 complete selected examples = 79 vectors, in three requests / 33,893 reported prompt tokens. A repeat build reused every document vector without another document request. Both English and Persian derivative/equation cases passed across unrestricted topic ranking. `text-embedding-3-small` missed both Persian cases; the larger model was selected using the same cases and unchanged notes. Raw PDF extracts remain excluded and their Phase 3 formula status is unchanged.

Regression before final model selection: 133 collected, 131 passed, two skipped (missing-SymPy scenario and optional compatible local-E5 acceptance under the remote configuration). After selecting the larger model/defaults: eight remote-adapter tests and 15 contract tests passed; actual large-model index/reuse/bilingual smoke passed. See [the migration record](sources/manifests/avalai_embeddings.json). The first small-model semantic smoke failed two Persian cases; this was corrected by selecting/testing the larger model, not hidden or relabelled as success.

Run `.\.venv\Scripts\python.exe cli.py`; `cli.py --index` reuses cached documents and `scripts/check_remote_retrieval.py` explicitly tests the remote backend. `--offline` disables remote embeddings. Local generated cache files are present but ignored by Git; no secret value was committed or printed.
