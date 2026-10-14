# Worked example requests use step reveal — 2026-10-14

User requirement: when the learner asks for an example, give the example through
the predefined step_reveal component. Recognize English example/examples and
Persian مثال/نمونه requests, including an initial request without a mode toggle.
Explicit answer mode remains authoritative.

Example requests now attach the selected sourced example, prioritize its step
reveal over a chart, and preserve the complete example text. A requested example
in step delivery does not advance the lesson. If the separate example bank is
empty, the writer can use a worked-example unit from the supplied topic notes.
The introductory logarithm example uses a fixed sourced derivation checked by
SymPy. Other examples use a typed, bounded example-specific model proposal and
the existing validation/provider pipeline. Envelope endpoints become actual
first/last rows. Domain restrictions that cannot be a scalar state remain in
the complete example text. Unsafe or unsupported-to-render proposals degrade
to that text rather than invented steps.

The step provider now preserves a single source variable such as z or t instead
of requiring x. Named function/derivative notation such as R'(z), and bounded
formal definitions separated by quad, are safe display-only mathematical
notation. They are explicitly unsupported by the transformation checker and
never executed or certified. Plain scalar transformations retain actual SymPy
checks. Code-like input and unapproved LaTeX commands remain rejected. Source
function and derivative are never falsely treated as equivalent expressions.

Visual novelty still suppresses repeats. Once an example has introduced a step
visual, ordinary follow-ups do not add a generic topic graph. No new graph
nodes, state keys, API contracts or frontend renderer types were introduced.
Tavily remains disabled; W7 remains unstarted; prior uncommitted work preserved.

Validation: 74 targeted tests passed, no failures/errors/skips (56.257 seconds).
Seven new tests cover natural intent, source-specific reveal generation,
Persian note examples without a bank, fixed-log verification, text fallback,
non-x variables, safe formal derivative notation, honest verification labels,
endpoint normalization, and no duplicate charts on later messages. Existing
teaching intent, visual frequency, block, backend, lesson, and streaming checks
also passed. Early live checks exposed dropped model proposals and restrictive
source notation; both paths were corrected before final acceptance.

Final actual model checks passed: a direct Persian logarithm example request
returned step_reveal; a Persian derivative example requested mid-lesson returned
step_reveal and kept the lesson index unchanged. Both included Persian text.
All ten formulas in those actual reveal payloads rendered through the installed
KaTeX without errors. These are actual HTTP/model checks plus formula-rendering
checks; no new browser interaction suite was run for this backend-only change.
Details: example_ui_regression.json and example_ui_live_checks.json. Private
diagnostic source text stays in ignored .cache. Backend restarted and healthy
on 8765; frontend remains on 3000. Existing saved messages were not modified.
