# Phase W4 completion — 2026-10-13

Status: implemented and checked. W5 has not started. The eleven-node graph, edges and state contract are unchanged. Tavily remains disabled by the existing configuration.

The FastAPI SSE endpoint streams actual graph updates and resumes actual interrupts. It emits the agreed status/text/error/turn_end vocabulary, heartbeats and safe errors; turn_end is last. Text deltas are emitted after structured writer validation, rather than raw provider tokens. W4 emits no UI blocks. Optional X-Request-ID replay prevents retries from repeating a next action. Replay storage retains the latest completed turn per registered thread; unknown threads do not allocate replay records. A disconnected subscriber detaches while the bounded turn finishes once. Shutdown cancels remaining tasks. The non-streaming service also now keeps interrupt detection local to each request.

The Next.js frontend provides Persian RTL layout, local Vazirmatn assets, safe Markdown/KaTeX with isolated LTR mathematics and Latin math digits, manual levels, learn/answer and step/full modes, and next/simplify/full/done controls. Its right sidebar supports IndexedDB chat restore, search, rename, delete and versioned JSON export. Theme, keyboard handling, responsive layout, error/retry and explicit new-session recovery after server-thread expiry are implemented. Provider credentials remain in Python; the Next route proxies requests server-side.

## Actual checks

| Check | Result |
| --- | --- |
| Full offline Python regression | 218 run; 216 passed, 2 pre-existing skips; zero failures/errors |
| Focused SSE checks after final progress-only change | 5 passed |
| Frontend component/parser checks | 6 passed |
| TypeScript | Passed |
| Next.js production build | Passed |
| Chromium browser scenarios on Windows | 3 passed |
| Firefox browser scenarios on Windows | 3 passed |
| Chrome axe accessibility scan, light and dark | Zero violations/incomplete results; 37 passes each |
| Next dev MCP compilation/runtime errors | None |

Browser scenarios cover a complete step lesson and mixed Persian/math, next/resume, reload, rename/search/export/delete, terminal-loss replay without duplicate turns, and explicit recovery of an unknown thread with saved history. Chromium and Firefox passed in separate final runs. Firefox submission required reusing one IndexedDB connection; the initial repeated-connection issue was fixed before its final pass. The full Python run used a direct runner after earlier PowerShell output-handling attempts were interrupted; only its completed result is reported above.

The Windows visual/keyboard checklist checked light/dark, 375px layout, focus, reduced motion and page errors in both engines. It was agent-operated, not a human sign-off. Screenshots remain locally in .cache/w4-browser-review. Browser versions and observations are in phase_w4_browser_review.json; regression counts are in phase_w4_regression.json.

Acceptance uses the real compiled graph with deterministic replacement external services (scripts/serve_w4_fixture.py), not live LLM or search calls. These checks establish transport, interaction and persistence behavior; they do not certify live-model lesson quality or rescore historical W3 evaluations. W3 content-verification and historical evidence limits remain in w3_completion.md. Visual blocks, component events, inferred levels and usage accounting belong to later phases.

Run the actual backend and frontend using frontend/README.md. Temporary QA servers were shut down after verification. No W4 Git commit was requested; existing W3 edits are preserved.
