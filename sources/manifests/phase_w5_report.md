# Phase W5 completion — 2026-10-13

Status: implemented and checked. W6 has not started. Tavily remains disabled.
No nodes, edges or state keys changed; the graph still has the authorized eleven
nodes. UI generation is internal to the existing write_explanation node.

## Implemented

- Separate closed Pydantic proposal and enriched block unions for function_graph
  and step_reveal. Strict bounds on blocks, strings, samples, sliders, steps,
  finite numeric inputs and domain size. Computed values/verification are rejected
  in model proposals; IDs, provider names and version are assigned by the backend.
- Writer prompting/integration for full lessons, planned step emission, remaining
  material on full-switch, and step follow-up/simplification. Answer mode and CLI
  remain text-only. Text and blocks remain separate. Validated block fallback
  text is also present in the normal text segments for the W4 shell.
- Safe scalar parsing extended to two-argument log(x,b); the numerical worker
  constructs SymPy expressions from the AST without evaluating model source.
  Real-domain sampling preserves cancelled denominator holes, undefined regions,
  poles between grid points and overflow gaps. Undefined highlights are omitted.
- Algebra state normalization to a bounded notation subset, SymPy-generated
  LaTeX, real solution-set/identity comparison with domain restrictions, and honest
  verified/unsupported/unknown labels. Known false steps reject the whole block.
- Bounded per-reply block repairs (at most two, respecting configuration), text
  fallback on any validation/provider failure, async killable workers with timeout
  and cancellation cleanup, and a maximum of four UI math workers.
- POST /api/ui/sample for issued graph definitions, bounded slider values, no
  graph/model call, token bucket 10/s/thread with burst 20, safe errors and cleanup.
  The latest 32 definitions per thread are retained without duplicating sample
  arrays. Requests cannot change expressions/domain/highlights to a different plot.
- Typed JSON responses and complete validated SSE block events using the W0
  payload {"block": ...}. Request-ID replay preserves block IDs and computations.

## Actual checks

Final full offline run: **240 tests run, 238 passed, 2 skipped, zero failures and
errors**, 77.110 seconds. Counts: phase_w5_regression.json; detailed local log:
.cache/w5-regression-direct.log. The skips are the existing missing-SymPy-environment
test (SymPy is installed) and optional unavailable local E5 model test.

New tests: 17 in test_ui_blocks.py and 5 in test_ui_backend.py. The focused 22-test
run passed; the final full run includes subsequent endpoint-retention/end-state
hardening. Existing test_web_refactors.py's placeholder W2 test was updated to
use the actual strict graph request and assert W5 emission/provider data plus
fallback text. No tests were removed or skipped for W5. Its 31-test run passed.

Acceptance observes actual spawned SymPy workers behind the real compiled graph:
log base 2 at x=8 gives y=3, non-positive x is a gap, base 0.5 gives y=-3, and base
1 produces no samples. Numerical checks reject zero/negative bases. A logarithm
equation log(x,2)=3 -> x=2^3 -> x=8 has verified transformations. Wrong roots,
squaring that introduces a root and lost domain restrictions are rejected.
Unsupported notation and unresolved decisions are not marked verified.

Tests also cover hostile syntax, model-supplied y/verification data, schema bounds,
removable singularities and tangent poles, overflow, unbound symbols, repair
exhaustion, repair success alongside a valid neighbor, text preservation, child
timeout/cancellation cleanup, step resume, JSON/SSE schemas, stable replay,
definition binding, rate burst/refill and eviction cleanup. Existing topology,
checkpoint, CLI and W4 streaming checks pass in the full run. git diff --check
passed. No frontend source or dependency changed; W4 browser/build results remain
historical and were not rerun for this backend-only phase.

Runtime versions measured: Python 3.10.5, FastAPI 0.121.2, SymPy 1.14.0,
Pydantic 2.13.5, LangGraph 1.2.12. No dependency upgrade was needed.

## Limits and next phase

No live model/search/embedding request or lesson-quality evaluation was run.
Model/retrieval services in acceptance are deterministic fixtures; LangGraph is
real and representative UI calculations use spawned SymPy. Existing W3 evidence
limits remain unchanged. The scalar v1 implementation accepts x and a small
notation subset; unsupported domain/notation complexity degrades safely. Periodic
arguments are restricted to affine arguments with slope magnitude at most 100.
Transform verification applies to the mathematical state, not justification prose.
Workers use the existing configured math deadline (default 5 seconds; acceptance
spawn checks use 30 seconds to accommodate Windows cold starts).

The W4 shell currently displays the standalone block fallback text. Interactive
plots and step-reveal renderers are W6; UI events are W7. No W6 implementation was
started. Backend contract, examples and limits: webapp/README.md. All prior W3/W4
edits remain preserved on the existing branch; no new Git commit was requested.
