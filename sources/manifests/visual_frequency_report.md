# Visual frequency correction — 2026-10-14

User feedback: creating a new chart for every message is distracting. Visuals
should introduce useful ideas and remain available for subsequent discussion.

The writer now checkpoints visual identities in one replaceable internal
message, using the existing message state and reducer. Identity compares
functions or derivation states and ignores titles, domains, sampling counts
and cosmetic changes. Previously emitted content is suppressed before provider
sampling and again after repair/validation. Text-only replies do not erase that
history. A fresh lesson resets it. Generic topic graphs introduce a lesson
once; a writer can still request a different function or derivation later.
Previously rendered charts remain in their original messages and remain usable.
The model receives the existing visual identities and instructions to refer to
them during ordinary follow-ups, simplification and continuation.

Changed implementation: `webapp/ui_history.py`, `learning.py`, and
`webapp/ui_pipeline.py`. Graph topology, state keys, HTTP contracts and frontend
rendering are unchanged. Tavily stays disabled. No W7 work or git commit.

Validation: 65 targeted tests passed, zero failures/errors/skips (37.532s).
Three new regressions exercise repeated proposals, cosmetic changes, text-only
gaps, fresh lessons, full continuation, and genuinely different functions.
Provider-call assertions confirm repeated graphs are not sampled again while
new functions/derivations still run through the providers. Existing UI backend,
block, lesson presentation, step teaching and streaming checks also passed.

Actual live model check: a natural Persian logarithm request emitted a graph;
simplification, a Persian follow-up and full continuation emitted no new chart.
All four replies retained Persian and contained lesson text. See
`visual_frequency_regression.json` and `visual_frequency_live_checks.json`.
The real backend was restarted with the fix and remains on port 8765; the
frontend remains on port 3000. Existing saved messages were not modified.
