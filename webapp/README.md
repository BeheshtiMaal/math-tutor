# Generative UI backend — W5

The tutor's existing `write_explanation` node may request `function_graph` and
`step_reveal` components on the web channel. Answer mode and CLI output remain
text-only. No graph nodes, edges or state keys were added. Optional requests are
carried by the existing lesson plan and writer response; they are validated when
their explanation is emitted, including step resume and simplification.

`ui_blocks.py` defines separate closed proposal and enriched output unions.
The model supplies mathematical intent, titles and fallback text. It cannot
supply IDs, versions, provider names, plotted y values, samples or verification
labels. `ui_pipeline.py` validates each proposal, checks safety, calls the provider
and validates the complete output. At most two model repair calls are shared
across the reply (also respecting `TUTOR_WRITER_REPAIRS`). Exhaustion, timeout,
malformed input or unavailable services drop the component and retain lesson
text. Every emitted block's standalone fallback is also appended to text segments,
so the lesson remains readable even when a component cannot render. The W6
frontend now renders the two version 1 components.

## Limits and execution

- Two blocks per reply; each raw proposal/repair is at most 16 KiB.
- Graphs: 1–3 expressions, 0–4 unique sliders, 0–5 highlighted x values,
  50–2000 samples per expression (default 400).
- All input coordinates/parameters are finite and bounded to ±1,000,000.
  Domains must increase and span at most 200. Slider defaults must lie in their
  ranges, and steps must be positive and no larger than the range.
- Algebra blocks: 2–12 rows; unique row IDs, at most 1024 characters per state,
  and 300 per justification. Titles/fallbacks are bounded plain text.
- Existing scalar AST node/depth, literal magnitude and power limits apply.
  Variable `x` is the only v1 variable; slider symbols must exactly match the
  other free symbols. Two-argument `log(x,b)` is supported by the existing parser.
- At most four UI math workers execute concurrently. Each is a fresh interpreter
  with JSON IPC, bounded results and the existing math deadline setting
  (`TUTOR_MATH_TIMEOUT_SECONDS`, default 5 seconds). Timeout and cancellation kill
  and reap the child. Longer Windows cold-start budgets can be configured up to
  the existing 60-second limit; acceptance used 30 seconds for spawned workers.

Sampling preserves intermediate domain restrictions, including removable holes.
SymPy computes real continuous domains and excludes singularities, including
ones between grid points. Finite samples and explicit `gaps` are returned; clients
must break the curve at every gap instead of connecting points across it.
Overflow creates `out_of_range` gaps. Undefined highlights are omitted with a
warning; defined highlights include a series index for multi-curve graphs.
Periodic arguments are limited to affine arguments with slope magnitude at most
100 to bound singularity enumeration. Unsupported domain analysis drops a block
or returns a safe sampling failure rather than drawing an unverified curve.

Step states accept safe scalar expressions/equations or a small literal LaTeX
subset (log bases, simple fractions/radicals, powers and elementary functions).
They are converted to the same AST; no general LaTeX parser or `sympify` evaluates
model text. The backend generates displayed LaTeX from SymPy expressions. Initial
and final envelope states must match the first/last rows. Equation transformations
are checked by comparing real solution sets with each state's domain; expression
transformations require identical domains and symbolic equality. A known false
transformation rejects the whole block. Unsupported formal notation receives
`unsupported`; unresolved symbolic decisions receive `unknown`. These statuses
must be visibly labelled by W6. Verification applies to mathematical states,
not to the prose justification. More complex notation/assumptions are not silently
interpreted.

The numerical/verification approach follows SymPy's explicit real-domain
[solveset](https://docs.sympy.org/latest/modules/solvers/solveset.html) and
[calculus domain](https://docs.sympy.org/latest/modules/calculus/index.html)
contracts. `lambdify` receives only SymPy expressions built from the allowlisted
AST, never raw model text.

## HTTP and stream contracts

JSON chat responses contain a typed `blocks` list. SSE sends
`event: block` with `{"block": <complete validated envelope>}` after the text and
before the terminal event. Replay reuses those events and block IDs. Graph data
is embedded in `params.samples`; this is a backend-only output field, rejected
in proposals. Algebra rows carry backend-only `verification` labels.

`POST /api/ui/sample` accepts:

```json
{
  "thread_id": "thr_00000000000000000000000000",
  "block_id": "blk_00000000000000000000000000",
  "expressions": [{"label": "y", "expression": "log(x,b)"}],
  "variable": "x",
  "domain": {"min": -1, "max": 9},
  "parameters": {"b": 0.5},
  "sample_count": 51,
  "highlight_points": [{"x": 8, "label": "x = 8"}]
}
```

Use actual IDs and the definition from a previously issued graph. Expressions,
domain and highlight definitions must match that graph; parameter names must
match its sliders and values must be inside their ranges. Sampling calls neither
the model nor LangGraph. Returned `series` contain finite `points` and `gaps`
(`from`, `to`, `reason`); highlight results include resolved y and `series_index`.
Invalid bases (`b <= 0` or `b = 1`) never produce samples. Base 0.5 is supported.

Rates are limited to 10 requests/second/thread with burst 20. Capacity/rate
exhaustion returns 429; unknown threads return 404; unknown/altered definitions
return 422; oversized/malformed request fields use the existing safe 400/413
mapping. Math deadline failures return 504. Other unsupported math returns
`status: invalid_expression` with a fixed warning. No input/provider exception or
stack trace is returned. Sampling does not change lesson step index.

Only the latest 32 issued graph definitions per thread are retained for sampling;
old sample arrays are not duplicated in this library. Registry eviction removes
definitions and rate buckets. Older definitions or a restarted backend require
the existing session recovery/error flow. The normal 256 KiB request limit and
localhost/CORS settings also apply to this endpoint.

## Offline checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_ui_*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The real compiled graph is used; only external model/retrieval services are
replaced. Representative SSE and direct sampling acceptance uses actual spawned
SymPy workers. Separate numerical unit tests call the calculation functions
directly; lifetime checks prove timeout/cancellation cleanup. No live provider
quality evaluation is implied. W6 component rendering is implemented in the
frontend; W7 component-event resume is implemented below.

## Geometry canvas

`geometry_canvas` version 1 supports closed `unit_circle`, `triangle`, and
`vectors` scenes. Initial and updated points, segments, arcs, and measurements
come from the bounded numerical geometry engine (`data_source: geometry_engine`).
These are floating-point measurements, not symbolic proofs. No generated SVG,
scripts, or expressions are accepted. Degenerate triangles and zero-vector
angles are explicitly undefined.

`POST /api/ui/geometry` accepts an issued scene's IDs and updated inputs:

```json
{
  "thread_id": "thr_00000000000000000000000000",
  "block_id": "blk_00000000000000000000000000",
  "scene": {"kind": "unit_circle", "angle_degrees": 90}
}
```

Use the actual thread/block IDs. Scene kind must match the issued block. Circle
angles are bounded to 0–360 degrees; triangle vertices and vector components to
−10–10. Triangle scenes require exactly three `{x,y}` vertices; vectors require
`u` and `v` points. Nonfinite inputs, extra fields, and unknown references are
rejected. Updates share the sampling rate/capacity limits and definition registry;
they do not call the model, resume the graph, or advance the lesson.

## W7 component interactions

Send `action: "ui_event"`, an empty `message`, and a closed `ui_event` envelope
to the existing chat/stream/resume endpoint. The envelope contains `event_id`
(`evt_` plus 26 Crockford characters), matching `thread_id`, issued `block_id`,
positive monotonic `seq`, UTC ISO `sent_at`, `type`, and typed `payload`:

- `step_confused`: `{ "step_id": "s1" }`; explain the issued row more simply.
- `graph_question`: `{ "params": { "b": 0.5 } }`; report SymPy-calculated curve
  values for these exact slider settings.
- `block_error`: `{ "code": "render_failed" }`; acknowledge and continue in text.

Definitions, step IDs and parameter ranges are bound to the issuing thread.
Client-supplied expressions, samples or algebra states are never trusted.
`Command(resume=...)` enters the existing `user_input` node and then
`write_explanation`; lesson position and cached retrieval remain intact. The
contracted `ui_event` state field carries only the current validated context.
The event ID/sequence ledger replaces one bounded checkpoint message and retains
the latest 128 IDs. Responses expose `event_status` (`accepted`, `duplicate`,
`stale`); ignored events have no new text or blocks. SSE request-ID replay remains
available independently of event deduplication.

At most five new tutor events per five seconds per thread are accepted. The
normal per-thread active-turn lock preserves order. Browser slider changes,
step navigation and viewing are informational and never resume the tutor.
Geometry supports text recovery; geometry manipulation continues to use its
numeric update endpoint rather than generating tutor turns. Unknown/restarted
threads use the existing `thread_not_found` recovery flow.

## W8 profile context

Requests may include a bounded version-1 `learner_profile`, `level`, and
`level_source`. Explicit session level, stored manual topic level, current
heuristic hint, stored inferred level, then beginner default determine depth.
Responses expose resolved `learner_level`/`level_source` and a separate
`level_suggestion`; this is a conservative heuristic, not a proficiency test.

Validated HTTP profiles exist only in per-invocation `LearnerRuntime` context.
They never enter graph state, checkpoint configuration, stream caches or service
storage. The compatibility state field remains null on the web. Confusion data
is sent to the writer as data for a relevant simpler review, not instructions.
The model service receives those concepts to generate the explanation.

The client owns correction/reset and sends a trimmed snapshot each fresh turn.
Invalid/oversized profiles are rejected in `profile_status` while the lesson
continues. Exact SSE replay excludes the profile from its fingerprint so reset
can scrub pending snapshots without executing the original turn twice.

## W9 hardening and usage

`usage` now contains provider-reported prompt/completion tokens (null when any
call lacks metadata) and `limit_reached`. Native adapter callbacks capture all
chat-model calls, including repairs, outside graph/checkpoint state. A bounded
metadata-only local JSONL log records each executed turn once, including partial
failures; exact stream replay does not charge or log twice. Per-chat admission
limits for turns, model calls and reported tokens are configured with
`TUTOR_WEB_SESSION_MAX_*`. They reset on idle eviction/server restart and are
not an account-wide monetary cap. Embedding/search billing is excluded.

`session_limit` is a safe 429 error; the frontend displays a localized recovery
message. `degraded` indicates the current reply used a model fallback or retained
local evidence after a resource failure, without exposing provider/coverage
diagnostics. Historical warning accumulation does not mislabel a new reply.

Actual/chunked body bytes and numeric JSON tokens are bounded before validation;
foreign/null-origin writes are rejected. The proxy also bounds bodies before
retaining them. FastAPI/Starlette and HTTP dependencies were upgraded for the
W9 security audit. Full Windows setup, acceptance and extensions are documented
in [DEVELOPMENT.md](../docs/DEVELOPMENT.md).
