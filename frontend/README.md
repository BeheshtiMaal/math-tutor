# MathTutor web frontend

Next.js 16.4, React 19.3, TypeScript, Tailwind 4, shadcn/ui and AI Elements. Persian-first, with local Vazirmatn font assets and safe Markdown/KaTeX rendering. Provider credentials belong exclusively to the Python backend.

From the repository root, start the actual tutor service:

```powershell
.\.venv\Scripts\python.exe -m webapp
```

In another terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. The server-side frontend proxy defaults to `http://127.0.0.1:8765`; change `TUTOR_BACKEND_URL` in `frontend/.env.local` when needed. No `NEXT_PUBLIC` provider key is needed. Restart the frontend after changing its environment.

## Local chat data

IndexedDB database `mathtutor`, version 1, holds chat transcripts, pending request identities, session settings and theme. Deleting a chat deletes its local record; it does not erase the Python checkpointer before its normal eviction. JSON export includes schema version and transcripts. When a server thread expires or the backend restarts, the transcript stays visible; the explicit recovery action creates a new thread with a bounded summary and labels it as a new session.

Streaming retries preserve `X-Request-ID`. The backend caches the latest turn's safe events and replays them, so a reconnect does not repeat a `next` action. Older replay identities are evicted as new turns begin. Stopping receipt detaches the browser; the bounded backend turn finishes once and can be recovered. Backend restart loses replay/checkpoint data and is handled through the new-session recovery flow.

The HTTP event vocabulary is `status`, `text`, `block`, `error`, `turn_end`. W5 supplies validated backend blocks; W6 renders version 1 graphs and algebra steps in the chat. Unknown versions/types and invalid or broken blocks show their escaped fallback text. See [backend contracts](../webapp/README.md). Text deltas stream **after structured writer validation**, rather than forwarding unvalidated provider JSON tokens. Step mode pauses on the graph's actual interrupt and resumes through `Command`.

## Interactive components — W6

The renderer registry validates every payload against the closed client schema.
Graphs draw only backend samples; the browser never evaluates expressions. Curves
break at every undefined/discontinuous gap, including a pole between samples.
Sliders use keyboard arrows/Home/End, Latin mathematical values and a 250 ms
debounce. Changing a value cancels the old request and ignores a stale response.
The server-only `/api/ui/sample` proxy forwards to the bounded SymPy endpoint;
no model call or lesson advancement is involved. Loading, invalid-base, network,
expired-definition and retry states are localized. Old curves are hidden when
they do not represent the selected parameter values. Text alternatives include
resolved highlights, domains, gaps and a bounded table of calculated points.

Step reveal shows one checked transformation at a time, with previous/next
controls and a highlight on the changed equation sides. Unsupported/unknown
steps are visibly labelled as not machine-checked. Motion respects the system's
reduced-motion preference. "این مرحله را نفهمیدم" prepares an explicit question
about the current step in the composer; the user can review and send it. Structured
component events and their tutor reactions are W7, not automatically sent by W6.

Blocks, slider positions and completed sample data, and the current reveal index
are stored with each message. These are additive optional fields in IndexedDB
schema version 1, so existing text chats need no migration. The sidebar reports
when a chat write is pending; wait for it to finish before reloading. Exports
include block data/state. An error boundary isolates each block from its neighbors.

For all W4/W6 browser tests, use `scripts/serve_w6_fixture.py` instead of the W4
fixture in the commands below. It retains W4 scenarios and adds logarithm graph
and equation lessons, using the real eleven-node graph and actual SymPy workers
with deterministic model/retrieval replacements. Start it on port 8766, then run
`npm run test:e2e`. Results go to `test-results/browser-results.json`. The additional
agent-operated Windows visual checklist is `node scripts/w6-browser-review.mjs`.

## Checks and offline browser acceptance

```powershell
npm run typecheck
npm run test
npm run build
```

For browser checks, start the synthetic-service fixture from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\serve_w4_fixture.py
```

Start/restart the frontend in another terminal:

```powershell
Set-Location frontend
$env:TUTOR_BACKEND_URL = 'http://127.0.0.1:8766'
npm run dev
```

Then:

```powershell
npx playwright install firefox
npm run test:e2e
node scripts/browser-review.mjs
```

The Chromium project uses installed Google Chrome; Firefox uses Playwright's Firefox build. The fixture executes the real eleven-node graph with deterministic external-service replacements. It is for acceptance checks, not a live-model lesson-quality assessment. The agent-operated Windows visual/keyboard checklist is recorded separately from automated smoke results.

W5 backend blocks, W6 rendering and W7 component events are implemented.
W8 level inference and W9 usage accounting remain later phases. Tavily remains
disabled by the existing backend setting.

## Geometry canvas

The predefined `geometry_canvas:1` renderer is in
`components/blocks/geometry-canvas.tsx`, registered in `block-renderer.tsx`.
Natural requests such as «دایره واحد را توضیح بده», «زاویه‌های مثلث را توضیح بده»
or «جمع بردارها را توضیح بده» select a grounded scene automatically. Repeated
scenes remain in their original message rather than appearing every turn.

Drag points or focus them and use arrow keys. Sliders provide another keyboard
and single-pointer option. Measurements update through `/api/ui/geometry` without
a chat turn. Scene inputs and results persist with the message; reset restores
the issued scene. Labels follow the lesson language and math remains LTR.

For repeatable geometry browser checks, run
`scripts/serve_geometry_fixture.py` from the repository root, keeping the normal
frontend running. `npx playwright test e2e/geometry.spec.ts --project=chromium`
and then `--project=firefox` forward only the two relevant API routes to this
fixture on 8766. The real graph and numeric engine execute; external model
responses are deterministic. This does not certify general live-model quality.

An isolated production build can use
`$env:TUTOR_BUILD_DIST_DIR='.next-geometry-build'; npm run build` to preserve the
development cache. Restart `next dev` afterward to restore generated dev types.

## W7 interactivity

«این مرحله را نفهمیدم» sends the selected row to the tutor immediately.
«دربارهٔ این نمودار بپرس» sends the current successfully displayed parameters.
«ادامه با متن» reports a failed component and requests a text continuation.
Each explicit request appears as a readable chat message. Sliders and local
reveal navigation only update the component; they do not request a tutor reply.
Both scene state and a bounded local activity history persist in the existing
IndexedDB version. Event sequence and pending replay identity survive reload.
Five events per five seconds are allowed per thread; busy/expired/pending
sessions disable new component actions. A pending request retries its original
event and HTTP request IDs.

Use the updated `serve_w6_fixture.py` for W4–W7 acceptance. Its bilingual synthetic
lesson plans follow the current language policy. Run `lesson.spec.ts`,
`blocks.spec.ts`, and `ui-events.spec.ts` separately for Chromium and Firefox.
The new event scenario checks current graph values, selected-row explanation,
ordering, duplicate handling and restoration without advancing the lesson.

## W8 learning memory

The level selector defaults to automatic. Conservative English/Persian wording
heuristics suggest depth; explicit session or saved topic choices take priority.
The displayed estimate is not a proficiency assessment. Open «حافظه یادگیری»
to view and correct topic levels, inspect weak points, or clear the profile.
Clearing memory preserves conversations and explicit lesson settings.

The bounded profile stays in this browser's IndexedDB and a trimmed snapshot
accompanies tutor requests. Simplification and selected-step confusion record
concepts for a brief review in later explanations. Successful turn IDs prevent
replay from double counting; reset strips saved pending profile snapshots and
prevents older in-flight turns from restoring cleared memory.

Use `scripts/serve_w8_fixture.py` on 8766 for W4–W8 browser acceptance, with
`TUTOR_BACKEND_URL=http://127.0.0.1:8766` on the development frontend. Add
`learner-memory.spec.ts` to the W7 acceptance files, one browser engine at a time.
Return the frontend proxy to 8765 afterward. External services are deterministic
in this fixture; the actual graph and math providers execute.

## W9 acceptance

The final fixture `scripts/serve_w9_fixture.py` covers all component types and
the main journeys, including answer/full modes, service failure notices and
literal backend process restarts while paused or in flight. It uses synthetic
external services and the real graph/math. Run the full Playwright suite for
Chromium and Firefox separately, with the frontend proxy pointed to 8766.
Its `/__qa` routes are acceptance-only and never appear in the normal backend.

Proxy routes reject foreign origins/Host URLs and bound streamed request bodies.
KaTeX is patched to 0.18.2 across the Markdown dependencies, with trust disabled.
The app displays a generic Persian notice for a degraded reply and a session
limit message; it never displays provider secrets or Paul coverage diagnostics.
See [the clean-checkout guide](../docs/DEVELOPMENT.md) for setup and restoration.
# Agentation visual feedback (development)

Run `npm run dev` and open `http://127.0.0.1:3000` on desktop. The Agentation
toolbar appears in the bottom-right corner only in development. Activate it,
click an element, write a note, and add the annotation.

The toolbar syncs to `http://localhost:4747`. Codex is configured globally with
`codex mcp add agentation -- npx -y agentation-mcp server`; reload MCP servers or
restart Codex after configuration. Keep Codex connected while annotating, then
ask it to read pending Agentation feedback. For a standalone local server, run
`npx -y agentation-mcp server`. Check connectivity with
`npx -y agentation-mcp doctor`.
