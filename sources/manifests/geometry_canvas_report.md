# Geometry canvas — 2026-10-14

Added the predefined `geometry_canvas:1` Gen UI component with unit-circle,
triangle, and planar-vector scenes. Natural English/Persian topic requests select
a scene from relevant retrieved evidence. New bilingual original project notes
cover these concepts. Supplied bounded coordinates and degree angles are retained
in automatic defaults. Circle follow-ups reuse the existing circle, including
when its angle changes. Ordinary follow-ups do not create another canvas.

The closed backend schemas reject expressions, scripts, extra fields, nonfinite
numbers and out-of-range coordinates. The numeric engine calculates all drawn
primitives and measurements. It reports undefined angles for degenerate triangles
and zero vectors. Measurements are numerical approximations, not symbolic proof.
The update endpoint checks issued thread/block/scene identity and shares existing
rate/capacity limits. Updates never call the model or advance lesson state.

The renderer supports pointer dragging, arrow keys, sliders, reset, text/coordinate
alternatives, Persian RTL/English labels, themes, cancellation and stale-response
protection. Validated inputs and results persist with each saved message. Existing
graph and step-reveal components, the eleven-node graph and its state keys remain
intact. Tavily is disabled. W7 has not started; no automatic tutor reaction to
component interaction is claimed.

## Validation

- Backend: 267 tests run, 265 passed, 2 skipped, zero failures/errors (127.213 s).
  The existing missing-SymPy environment check and optional local-E5 acceptance
  were skipped. E5 import had stalled during the earlier language-fix work; no
  embedding implementation changed. Eight new geometry tests cover math,
  hostile inputs, natural selection, thread/scene binding and lesson preservation.
  Exact counts: `geometry_canvas_regression.json`.
- Frontend: all 24 tests passed, including seven geometry tests. Typecheck passed.
  Production build passed with an isolated output directory, including the new
  route. Generated type imports were restored by restarting the owned dev server.
- Chromium and Firefox: one comprehensive geometry scenario passed in each,
  with the actual graph, API and geometry engine and deterministic external model.
  Verified all three scenes, keyboard changes, pointer drag, reset, saved-state
  restoration, no extra chat requests for interactions, no repeat canvas on an
  ordinary follow-up, no KaTeX/page errors and no horizontal overflow at 375px.
  The fixture forwards API requests directly to its backend; it does not by
  itself prove the Next proxy. Separate live checks below exercise that proxy.
- Actual model/Chrome: «دایره واحد را از ابتدا توضیح بده» automatically displayed
  a Persian unit-circle canvas over the normal SSE proxy. ArrowUp changed 45° to
  46° through the actual geometry proxy. The first update timed out while Next
  compiled this new route; retry succeeded and cleared the error. React DevTools
  inspection confirmed GeometryCanvas, issued IDs, Persian params and the pending
  scene; the final DOM showed 46° with no alert. This is a representative live
  integration check, not broad live-model geometry-quality evaluation.
- Next MCP: compilation issues, config errors and connected-browser session errors
  were empty; page metadata identified the active app route.

Earlier browser failures were check errors: the save-status selector assumed a
nonexistent accessible label, and the pointer start used the entire point group
bounding box without ensuring the actual hit circle was visible in the scroller.
Using the actual save indicator and visible hit-circle center resolved them;
no product change was needed for those failures. Mobile screenshots are stored
locally in ignored `.cache`; no user transcript or raw browser profile is shipped.

Prior W3–W6 work and existing saved conversations are preserved. Backend 8765
and frontend 3000 remain available. No new commit was requested.
