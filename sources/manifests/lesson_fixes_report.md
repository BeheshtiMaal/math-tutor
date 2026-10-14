# Automatic lesson visuals and Persian presentation fixes — 2026-10-14

The authorized read-only inspection of Chrome's saved MathTutor chats confirmed
missing UI blocks, English fallback excerpts in Persian logarithm lessons,
English example prose appended to derivative lessons, and displayed source IDs.
The original browser database and saved conversations were not modified. Raw
history and diagnostic transcripts remain in the ignored local `.cache` folder.

The writer now selects useful visuals without requiring component instructions.
Grounded defaults for logarithms, derivatives, exponentials and trigonometry
cover missing or invalid model proposals; numeric samples and transformation
checks still use the existing bounded SymPy providers. Components are limited
to two per reply and never appear in concise-answer or CLI output. Logarithm
derivations are selected from the supplied example when that example is taught.
Other topics continue to use model-selected, backend-validated components.

Language detection excludes mathematical notation and function names. Writer
drafts and component prose must match the resolved language. Bilingual fallback
notes select the correct prose and preserve formulas. Examples translate prose
with source mathematics held fixed; changed, reordered or added mathematical
tokens are rejected with bounded retries. Intentional language changes update
the evidence request and adapt subsequent cached lesson steps.

Citations, source equation references and source-coverage diagnostics do not
appear in lesson text. Evidence IDs, provenance, verification results and
retrieval warnings remain internal. When the separate example bank has no
example, supplied curated-note examples can still be taught.

Validation: 249 Python tests run; 247 passed, two skipped; zero failures/errors
(91.502 seconds). Nine new presentation regressions cover automatic selection,
formula-only language continuity, bilingual fallback, citation removal, math
preservation during translation, and deliberate language changes. Existing
tests now assert that diagnostics remain internal and that a rejected proposal
can recover to a safe grounded visual. The missing-SymPy environment test is an
existing skip. Optional local E5 acceptance was explicitly skipped in this
fix's runner after its transformer import stalled; no embedding code changed.
Earlier interrupted attempts and expectation failures were corrected before
the final successful pass.

Four final live-model HTTP turns passed: a normal Persian logarithm request
returned a graph, its Persian follow-up retained Persian, full continuation
returned graph and step reveal, and a Persian derivative lesson returned a
graph and translated worked example. All displayed prose was Persian, without
citations or coverage notices. Initial logarithm and derivative replies took
16.7 and 29.3 seconds respectively. Invalid model visuals can still occur; the
final derivative reply recovered to the safe default instead of losing its
graph. Chrome at `http://127.0.0.1:3000` also displayed the automatic graph over
the actual SSE route, then displayed a graph and step reveal after the full
continuation control. The final inspected page had no displayed citations or
Paul notices. Next compilation reported no issues and the inspected
page had no KaTeX errors. No frontend rendering code changed in this fix.

Details: `lesson_fixes_regression.json`, `lesson_fixes_live_checks.json`.
Previous W6 renderer acceptance used deterministic block-emitting fixtures;
that established rendering but did not establish automatic live selection.
This fix adds that missing acceptance check. W7 has not started, graph topology
and state keys are unchanged, and Tavily remains disabled. Existing uncommitted
work was preserved; no commit was requested. The real servers remain available
on ports 3000 and 8765. Old replies are preserved; start a fresh chat to check
the corrected behavior after the backend restart.
