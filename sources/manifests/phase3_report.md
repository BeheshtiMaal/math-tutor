# Phase 3 — limited source preparation

Status: **implemented; exit incomplete**. Downloads and readable prose extraction finished. Original starter notes, selective example bank, schema/importer and teaching rules are prepared. Formula fidelity remains incomplete; level gaps are explicit. No subsequent phase implementation was started.

| Book | PDF bytes | Pages | Download | Extraction |
|---|---:|---:|---|---|
| Calculus Volume 1 | 52,104,540 | 769 | downloaded | incomplete |
| Calculus Volume 2 | 47,350,759 | 737 | downloaded | incomplete |
| College Algebra 2e | 84,220,165 | 1073 | downloaded | incomplete |
| Introductory Statistics 2e | 23,503,369 | 847 | downloaded | incomplete |

Total completed PDFs: **207,178,833 bytes (197.58 MiB)**. Partial-transfer bytes: **0**. Extracted text: **5,397,578 bytes**, across **3,426 pages**. No additional textbooks, alternate editions, full website or complete Paul collection was downloaded. All four licenses resolved from current official CMS metadata are **Creative Commons Attribution-NonCommercial-ShareAlike 4.0**; original copyright pages and exact notices remain in the PDFs. Manifest preserves actual authors, source/PDF/license URLs, retrieval times, local paths and hashes.

Download failures: **none**. Extraction page exceptions: **0**. Mathematical fidelity problems: **all four books remain incomplete**. Calculus Volume 1 PDF page 226 omits the image-based power rule and derivative proof from text; Volume 2 page 14 omits sigma notation and bounds; College Algebra page 727 omits matrix entries and brackets; Statistics page 180 loses fraction layout. Sparse-page counts are 25, 29, 12 and 16 respectively; these include front matter and blank pages and are diagnostic flags, not an assertion that every sparse page is an error. Each original page was rendered and visually compared with its extracted text. Reviews are bound to the original PDF hashes. This is a spot check, not whole-book certification. Raw extracts have no retrieval metadata and are never loaded as teaching evidence.

Seven original MathTutor starter notes (28 heading records) cover derivatives, integrals, limits, equations, matrices, probability and optimization, with bilingual names, actual reference sections and explicit project authorship. They are not OpenStax transcripts or full-book coverage. Calculus Volume 2 is acquired but no direct book transcript is indexed. Teaching guidance contains exactly 15 original rules, five per level, with an IES practice-guide reference.

Exactly **51** distinct Paul problems were selected from **eight** existing linked lesson pages. Each retains its original statement, complete selected solution and shared discussion where needed, TeX, visible example/part label, Paul Dawkins attribution, retrieval date, source URL and terms. Diagram source links and descriptive alt text are retained; no diagram files were downloaded. Copyright notices are retained; the private bank, originals and raw extracts are excluded from Git. No external publishing or permission request was made.

| Topic / atomic subtopic | Beginner | Intermediate | Advanced | Missing |
|---|---:|---:|---:|---:|
| algebra / linear equations | 2 | 2 | 2 | 3 |
| algebra / quadratic equations | 3 | 3 | 3 | 0 |
| derivative / power rule | 3 | 3 | 3 | 0 |
| integral / antiderivatives | 3 | 3 | 3 | 0 |
| matrix / augmented systems | 3 | 2 | 0 | 4 |
| limits / evaluating limits | 3 | 3 | 1 | 2 |
| optimization / constrained optimization | 2 | 2 | 2 | 3 |
| probability / basic probability | 0 | 0 | 0 | 9 |

Target remains three selected examples per atomic topic/subtopic/level; **21 slots missing**. These gaps describe this finite reviewed selection, not a claim that no additional suitable problem exists anywhere on Paul. No selected problem was reused under several levels. Difficulty is project judgment and its rationale is in the selection manifest.

Supported mathematical results: **27 verified**, **23 unsupported**, **1 unknown**, **0 rejected**. Exact finite equation solution sets are compared against a domain-aware solveset result, including denominator exclusions and empty sets; root substitution alone is insufficient. Antiderivative candidates are differentiated directly, avoiding a redundant integration timeout, and their derivatives are compared symbolically with the original integrand. The logarithmic primitive in `CalcI/ComputingIndefiniteIntegrals`, Example 1 (f), remains unknown because its absolute-value comparison was inconclusive. Irrational/fractional exponent representations, piecewise existence proofs, row-reduction systems and multistage optimization/application claims lack complete supported checks. Verification concerns the stated result, not every prose transition or teaching claim. No numerical samples are treated as proofs.

Checks actually run: the final full regression run collected **119**, with **118 passed and one skipped** (the deliberate missing-SymPy scenario when SymPy is installed). After the final comparison-budget/test-deadline and repeat-inventory changes, **19 learning-graph tests and seven preparation tests passed**. Validated repeat import retained **51** unique records. Actual-file hashes/sizes, all seven notes, 15 teaching rules, six Persian/English keyword cases and a real LangGraph local lesson with exactly one matching example plus `done` resume passed. This smoke uses no model/search calls or semantic index construction. Regression tests also exercise the existing semantic implementation with fixtures; this does not certify full-book cross-language coverage.

Initial full regression found one fixture that assumed the project's source directory was empty; it now uses a temporary empty directory and keyword retrieval. The initial corpus smoke inherited tracing and received HTTP 403 from LangSmith; tracing is now explicitly disabled in the check script. A subsequent smoke exceeded its 20-second resource deadline while running multiple Windows workers concurrently; its check configuration now uses a 60-second request deadline and the clean final smoke passed. No live AvalAI request was made or key value printed in this phase.

Installed preparation versions: BeautifulSoup 4.13.3, pypdf 6.20.0, PyMuPDF 1.28.2; symbolic verification uses the existing SymPy 1.14.0. PDFs and text extracts are local artifacts, not generated success placeholders.

Changed files: `scripts/prepare_core_sources.py`, `prepare_paul_examples.py`, `prepare_topic_notes.py`, `review_core_sources.py`, `check_phase3.py`, `report_phase3.py`; retired bulk CLI in `scripts/acquire_references.py`; `learning.py` verification helper; `tests/test_phase3_preparation.py`, `test_learning_graph.py`, `test_answer_graph.py`, `test_acquisition.py`; `requirements-acquisition.txt`, `.gitignore`, README, implementation status and the four canonical specs. Generated: four PDFs/extracts, seven notes and seven metadata sidecars, `sources/teaching_bestpractices.md`, `sources/examples/schema.json`, private Paul JSONL, and manifests `openstax_core.json`, `formula_reviews.json`, `topic_registry.json`, `paul_selection.json`, `phase3_checks.json` and this report. Temporary probe scripts were removed; user originals and historical manifests were preserved.

Inspect now: `.\.venv\Scripts\python.exe scripts\check_phase3.py`. Reproduce preparation using the commands in README. Core acquisition returns exit 2 while formula review remains incomplete; successful PDF transfers do not override that gate. Render reviewed original pages with `scripts/review_core_sources.py --render`.

Remaining work before the Phase 3 exit: reviewed transcription or reliable math-aware extraction of missing formulas, notation/layout checks, and suitable selected examples for the recorded level gaps. Do not index unreviewed raw book text. The numbered next phase is Phase 4; wait for explicit continuation. STOP at Phase 3.
