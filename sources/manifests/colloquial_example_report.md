# Conversational example requests

The saved MathTutor chat confirmed «یه مثال برام میزنی» produced a sourced
derivative as plain text. Intent recognition already accepted this phrase;
optional example-to-UI conversion could fail, and visual novelty could suppress
an explicitly requested repeat. A live browser probe also found an example
translation failure leaving no mathematical text to turn into a reveal.

The writer now falls back to an existing localized worked example in retrieved
topic notes when bank translation fails. Safe source function/derivative
endpoints can form a two-row `step_reveal` when optional conversion fails.
Complete example text remains alongside it. Unsupported/unsafe notation is not
truncated into a different expression. Formal differentiation retains the
provider's unsupported verification label, never a false equivalence claim.

Only explicit example requests may repeat `step_reveal`; ordinary follow-ups
still suppress duplicate visuals, including graphs. Repeats are deduplicated
within a single response. Lesson index and source mathematics are preserved.
No frontend/schema/graph-topology changes. Tavily remains disabled.

Regression and live-browser results are recorded in
`colloquial_example_regression.json` and `colloquial_example_live_checks.json`.
The actual-chat audit and unsuccessful intermediate browser captures stay in
ignored `.cache/example-request-audit/`; original user data was not modified.

Final focused regression: 54 passed, zero failures/errors/skips, 8.843 seconds,
with the real graph and actual SymPy validation in-process. This run does not
certify worker isolation; a separate normal-worker run passed all 13 example and
visual-history tests in 33.282 seconds, with zero failures/errors/skips. It is
recorded in the same artifact. Earlier runs hit Windows startup timeouts; an interrupted
broader run is not counted as passing. Initial endpoint assertions were corrected
to expect the provider's canonical LaTeX output rather than input syntax.

Live Chromium against the real backend/model: a Persian derivative lesson, then
the exact conversational example request twice. Each request rendered a reveal;
the original one chart remained one chart, lesson position stayed unchanged,
and there were zero page/KaTeX errors. The initial live attempts exposed the
translation fallback defect before final acceptance. Internal planner/writer
fallback warnings remain; successful component display is not a certification
of overall model explanation quality. Existing user conversations are not
rewritten, and backend restart uses the existing fresh-session recovery flow.
Next MCP reported no configuration, compilation or connected-page runtime
errors. No frontend tests or build rerun: frontend code did not change.
