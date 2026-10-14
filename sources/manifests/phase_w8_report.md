# Phase W8 — learning memory and level adaptation

Completed 2026-10-14. Automatic English/Persian wording heuristics choose lesson
depth; the UI explicitly describes the estimate as approximate, not a proficiency
assessment. Session manual choices and stored manual topic corrections win over
inference. Suggestions remain separate response metadata. Correcting a level
mid-lesson adapts the subsequent cached step without restarting progression.

The «حافظه یادگیری» header control lists topic levels, manual/inferred source,
last review and confusion concepts/counts. Learners can correct levels or clear
memory. The existing IndexedDB version stores the bounded profile: at most 50
topics, 10 confusion spots per topic, 20 recent topics, and 16 KiB UTF-8. Outgoing
profiles trim to 15,000 bytes, prioritize the active topic and normalize dates.

Simplify, selected-step confusion and recognized natural confusion record weak
points once per successful turn. The next relevant explanation receives up to
three weak points as data and is asked to review them before building on them.
If planning fails, matching actual mathematical excerpts are prioritized;
writer directions are excluded from fallback text. Fallback is not equivalent
to a tailored explanation and retains internal diagnostic warnings.

Raw HTTP profiles travel only in per-invocation LangGraph Runtime context. They
never enter graph state, checkpoint configuration, service storage or replay
caches. The legacy CLI state key remains compatible; HTTP initializes it to
null. Only derived level suggestion and cached-plan level are additional state
fields. Eleven graph nodes/edges remain unchanged.

Reset clears the profile and deduplication markers, scrubs saved pending profile
snapshots, and prevents older pending replies from restoring cleared memory.
It preserves chat transcripts and explicit session settings. Request replay
fingerprints omit the profile so a scrubbed request replays the original events
without executing the graph again. Reset does not erase historical tutor
messages. The external model receives relevant weak concepts for generation;
the non-retention guarantee tested here concerns this application backend.

## Actual verification

- Backend regression: 279 run, 277 passed, 2 existing skips, zero failures/errors,
  167.002 seconds. Optional local E5 acceptance was explicitly skipped after its
  transformer import stalled; the existing environment-dependent check remains
  skipped. No embedding implementation changed.
- Final affected checks after prompt/fallback adjustments: learner memory 6,
  presentation 9 and step teaching 26 passed. Checkpoint-history/raw-storage and
  stream-cache tests use unique private markers to verify profile non-retention.
  Same-topic novice/fluent, confusion adaptation, reset and manual precedence
  are exercised through the actual graph/HTTP path.
- Frontend: all 40 tests across 7 files passed with one worker. Initial default
  parallel run had 33 passes and a geometry worker startup timeout; it was not
  counted as a complete pass. Typecheck and isolated production build passed.
- Chromium 10/10 and Firefox 10/10 passed separately, including existing W4–W7
  flows and the two W8 scenarios. The real graph and SymPy execute against
  deterministic external services in `scripts/serve_w8_fixture.py`.
- Agent browser: memory component React props/state/callbacks inspected; light
  and dark dialog screenshots reviewed at 375px. No horizontal overflow or
  KaTeX errors; keyboard focus stayed in the dialog. No new axe scan claimed.
- Actual model Persian logarithm requests selected beginner versus advanced.
  Final remembered-condition request reviewed positive base / base not equal
  to one in its first explanation. Some earlier live requests used planning
  fallbacks; no broad live-model quality certification is claimed. These
  synthetic requests do not include private user chat history.

Initial backend failures were obsolete test-double signatures lacking the new
Runtime context argument; the corrected module and full regression passed.
Initial browser runs encountered cold compilation/startup delays and an invalid
test assumption that a short review always contains a reveal. The test now
requests a worked example before testing selected-step confusion. No failed
or unexecuted check is counted as passing. Internal Paul coverage warnings remain
diagnostics and are not displayed in learner messages.

Artifacts: `phase_w8_regression.json`, `phase_w8_browser_tests.json`,
`phase_w8_live_checks.json`, and `phase_w8_runtime_checks.json`. Private browser
captures and intermediate failure logs remain ignored under `.cache/`.
Spec/status were backed up before editing. Prior W3–W7/geometry/LaTeX work and
saved chats are preserved. Tavily stays disabled; no commit requested.
Temporary QA fixture stopped; real backend 8765 and frontend 3000 are restored.
W9 has not started.
