# W7 interactivity loop — implementation

Implemented the closed tutor-event envelope and the existing `ui_event` action.
Explicit step-confusion, graph-question and block-error actions resume the same
checkpoint through `Command(resume=...)`, `user_input`, and `write_explanation`.
All eleven nodes and edges remain unchanged. The already specified `ui_event`
state field now carries the current validated event/issued component context;
it is cleared after a response.

The server binds events to issued blocks and step IDs or slider ranges. A
checkpointed ledger stores the highest accepted sequence and latest 128 IDs,
so duplicates and stale events produce no new text, component, retrieval or
lesson advancement. The per-thread lock orders turns, and both client/server
limit new tutor events to five in five seconds. Existing request-ID SSE replay
preserves pending event identity across disconnect/reload.

Step confusion explains the selected algebra row and its predecessor using the
configured model, with a localized source-state fallback. Graph questions use
the actual bounded SymPy sampler for the current parameters and report computed
points/gaps rather than asking the model to invent curve facts. Component errors
acknowledge the failure and use available localized text. Geometry errors also
offer text recovery; geometry dragging remains numerical and client initiated.
Interactions do not produce another copy of the component.

The frontend shows a human-readable user message for each sent action. Slider,
view and reveal-navigation activity stays in a bounded local history; no tutor
turn is sent for it. Sequence, cached samples/reveal index and pending request
identity persist in the existing IndexedDB version. Busy, expired and pending
chats prevent additional component requests.

## Validation record

Six new backend acceptance tests cover selected-row context, unchanged cached
plan/retrieval/index, actual SymPy values with base 0.5 under full delivery, exact
stream replay, duplicate/stale handling, thread/block/payload binding, rate and
cleanup, and closed-envelope hostility. Two old placeholder tests now assert
that a missing envelope is rejected by request validation. Five new frontend
tests cover typed actions, local-only navigation, text fallback, ID/description
generation and per-thread rate limits.

The W4/W6 fixtures required correction: their mixed English/Persian plans were
rejected by the earlier language-continuity fixes. Initial acceptance had six
failures and two passes; fixture content now follows the requested language,
and the old Persian-lesson assertion expecting English was corrected. One new
test also initially assumed the wrong zero-based step ID. A subsequent duplicate
probe found an actual proxy defect: an omitted request-ID header was forwarded
as an invalid empty header. The proxy now omits absent IDs, preserving optional
request-ID semantics. These failures are not counted as successful validation.

Representative actual-model requests automatically produced a Persian example
reveal and a logarithm graph. Both event reactions returned Persian, no new
component, unchanged lesson index, and safe empty duplicate replies. The initial
live lesson planner fell back to source excerpts; retained diagnostic warnings
are internal. This is an event-integration check, not a new broad lesson-quality
evaluation or certification of the W3 quality limitations.

## Completion — 2026-10-14

- Full backend regression: 273 run, 271 passed, 2 skipped, zero failures/errors
  (190.091 seconds). The existing missing-SymPy check and optional local-E5
  acceptance are skipped; no embedding implementation changed. The six W7
  acceptance tests also passed separately after ISO-timestamp validation tightened.
  Counts: `phase_w7_regression.json`.
- Frontend: all 29 tests passed (five new); typecheck and final isolated production
  build passed. Production output used `.next-w7-build` to preserve the dev cache.
- Chromium: 8/8 passed (1.9 minutes); Firefox: 8/8 passed (3.0 minutes), run
  separately. All prior W4/W6 end-to-end scenarios and the W7 event scenario ran.
  Counts: `phase_w7_browser_tests.json`. These use the real graph and SymPy with
  deterministic external services, not general live-model quality evaluation.
- Actual live-model HTTP: Persian selected-step and current-graph reactions
  accepted; index unchanged, zero new blocks, duplicate safely ignored with empty
  text. Initial planning fallback and retained internal warnings are recorded in
  `phase_w7_live_checks.json`.
- Agent-operated Chrome check: selected reveal row remained at index 1 while
  lesson index remained 0; visible Persian request/response; no KaTeX error.
  React DevTools confirmed the typed callback and persisted row state. At 375px,
  light/dark controls were visually reviewed and neither document nor component
  footers overflowed. This is not human sign-off or a fresh axe audit.
- Restored runtime: Next MCP reports no compilation, config or connected-browser
  errors; real backend/frontend health is 200 and node count remains eleven.
  Details: `phase_w7_runtime_checks.json`. Final request summaries omit internal
  step IDs and isolate displayed parameter values as math.

W7 is complete. W8 is outside this change; Tavily remains disabled. Existing
saved conversations and earlier work are preserved. Temporary fixtures are
stopped; real backend 8765 and frontend 3000 remain available. No commit requested.
