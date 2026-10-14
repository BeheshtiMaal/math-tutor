# Saved-chat math rendering correction — 2026-10-14

Inspected the latest MathTutor chat using a copy of only Chrome's IndexedDB for
`http://127.0.0.1:3000`. The original browser/profile and conversations were not
modified. Raw chat data, copied database and screenshots remain in ignored
`.cache/latex-audit`; no private transcript is included in this report.

The quadratic worked example contained a source `align*` environment inside
`\[...\]`. The old JavaScript replacement string contained `$$`, which
`String.replace` interprets as a literal single dollar. Thus intended display
math became inline math and KaTeX rejected the environment. Earlier replies
also contained plain polynomial notation without delimiters.

The new frontend notation normalizer preserves literal display delimiters,
separates display blocks properly, normalizes math digits and renders conservative
plain arithmetic expressions. It retains code, URLs, escaped currency, dates and
ordinary Markdown. Existing HTML/TeX trust restrictions remain. No expressions
are evaluated, sampled values changed or stored messages rewritten.

Actual checks:

- Before: the copied latest chat rendered four math expressions and one KaTeX
  error (`align*` used in inline mode). The two corresponding regression tests
  failed, with three other new checks passing.
- After: the complete copied chat rendered fourteen expressions, zero KaTeX
  errors and no unexpected code blocks in real Chrome. The isolated aligned
  excerpt rendered two display blocks with zero errors. React inspection
  confirmed MathText received the original source notation, and the screenshot
  showed the aligned equations and final answer.
- All 34 frontend tests passed, including five new checks for display mode,
  legacy polynomials/products, code/currency/dates, digits and untrusted content.
  Typecheck passed. Next MCP reported no compilation/config/browser errors.
- `git diff --check` passed. No backend, graph, W8, or retrieval change; no backend
  regression, production rebuild or full cross-browser suite was run for this
  frontend correction.

Refresh the existing chat to use the renderer fix; no new chat is required.
