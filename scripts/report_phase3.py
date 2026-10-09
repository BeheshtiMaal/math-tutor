"""Summarize measured Phase 3 preparation and synchronize execution-status docs."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read_log(path):
    raw = path.read_bytes()
    return raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8")


def section(path, marker, body):
    original = path.read_text(encoding="utf-8")
    if marker in original:
        original = original.split(marker, 1)[0].rstrip()
    path.write_text(original.rstrip() + "\n\n" + marker + "\n\n" + body.strip() + "\n", encoding="utf-8")


def main():
    directory = ROOT / "sources/manifests"
    core = json.loads((directory / "openstax_core.json").read_text(encoding="utf-8"))
    paul = json.loads((directory / "paul_selection.json").read_text(encoding="utf-8"))
    checks = json.loads((directory / "phase3_checks.json").read_text(encoding="utf-8"))
    log = read_log(ROOT / ".cache/phase3/tests-final.log")
    focused = read_log(ROOT / ".cache/phase3/learning-final.log")
    assert re.search(r"Ran 119 tests.*?OK \(skipped=1\)", log, re.S)
    assert re.search(r"Ran 19 tests.*?\bOK\b", focused, re.S)
    assert checks["actual_langgraph_local_lesson"].startswith("passed")
    total = sum(b["actual_file_size_bytes"] for b in core["books"] if b["download_status"] == "downloaded")
    assert total == core["total_actual_download_bytes"] == checks["actual_pdf_size_bytes"]
    assert paul["verification_counts"] == checks["verification_counts"]
    coverage = {}
    for row in paul["coverage"]:
        coverage.setdefault((row["topic"], row["subtopic"]), {})[row["learner_level"]] = row["selected"]
    missing = sum(row["missing"] for row in paul["coverage"])
    table = "| Book | PDF bytes | Pages | Download | Extraction |\n|---|---:|---:|---|---|\n" + "\n".join(
        f"| {b['title']} | {b['actual_file_size_bytes']:,} | {b['page_count']} | {b['download_status']} | {b['extraction_status']} |" for b in core["books"])
    count_table = "| Topic / atomic subtopic | Beginner | Intermediate | Advanced | Missing |\n|---|---:|---:|---:|---:|\n" + "\n".join(
        f"| {topic} / {subtopic} | {levels.get('beginner', 0)} | {levels.get('intermediate', 0)} | {levels.get('advanced', 0)} | {9-sum(levels.values())} |" for (topic, subtopic), levels in coverage.items())
    report = f"""# Phase 3 — limited source preparation

Status: **implemented; exit incomplete**. Downloads and readable prose extraction finished. Original starter notes, selective example bank, schema/importer and teaching rules are prepared. Formula fidelity remains incomplete; level gaps are explicit. No subsequent phase implementation was started.

{table}

Total completed PDFs: **{total:,} bytes ({total/1048576:.2f} MiB)**. Partial-transfer bytes: **{core['total_partial_transfer_bytes']}**. Extracted text: **{core['total_extracted_text_bytes']:,} bytes**, across **{sum(b['page_count'] for b in core['books']):,} pages**. No additional textbooks, alternate editions, full website or complete Paul collection was downloaded. All four licenses resolved from current official CMS metadata are **Creative Commons Attribution-NonCommercial-ShareAlike 4.0**; original copyright pages and exact notices remain in the PDFs. Manifest preserves actual authors, source/PDF/license URLs, retrieval times, local paths and hashes.

Download failures: **none**. Extraction page exceptions: **0**. Mathematical fidelity problems: **all four books remain incomplete**. Calculus Volume 1 PDF page 226 omits the image-based power rule and derivative proof from text; Volume 2 page 14 omits sigma notation and bounds; College Algebra page 727 omits matrix entries and brackets; Statistics page 180 loses fraction layout. Sparse-page counts are 25, 29, 12 and 16 respectively; these include front matter and blank pages and are diagnostic flags, not an assertion that every sparse page is an error. Each original page was rendered and visually compared with its extracted text. Reviews are bound to the original PDF hashes. This is a spot check, not whole-book certification. Raw extracts have no retrieval metadata and are never loaded as teaching evidence.

Seven original MathTutor starter notes (28 heading records) cover derivatives, integrals, limits, equations, matrices, probability and optimization, with bilingual names, actual reference sections and explicit project authorship. They are not OpenStax transcripts or full-book coverage. Calculus Volume 2 is acquired but no direct book transcript is indexed. Teaching guidance contains exactly 15 original rules, five per level, with an IES practice-guide reference.

Exactly **{paul['selected_count']}** distinct Paul problems were selected from **eight** existing linked lesson pages. Each retains its original statement, complete selected solution and shared discussion where needed, TeX, visible example/part label, Paul Dawkins attribution, retrieval date, source URL and terms. Diagram source links and descriptive alt text are retained; no diagram files were downloaded. Copyright notices are retained; the private bank, originals and raw extracts are excluded from Git. No external publishing or permission request was made.

{count_table}

Target remains three selected examples per atomic topic/subtopic/level; **{missing} slots missing**. These gaps describe this finite reviewed selection, not a claim that no additional suitable problem exists anywhere on Paul. No selected problem was reused under several levels. Difficulty is project judgment and its rationale is in the selection manifest.

Supported mathematical results: **27 verified**, **23 unsupported**, **1 unknown**, **0 rejected**. Exact finite equation solution sets are compared against a domain-aware solveset result, including denominator exclusions and empty sets; root substitution alone is insufficient. Antiderivative candidates are differentiated directly, avoiding a redundant integration timeout, and their derivatives are compared symbolically with the original integrand. The logarithmic primitive in `CalcI/ComputingIndefiniteIntegrals`, Example 1 (f), remains unknown because its absolute-value comparison was inconclusive. Irrational/fractional exponent representations, piecewise existence proofs, row-reduction systems and multistage optimization/application claims lack complete supported checks. Verification concerns the stated result, not every prose transition or teaching claim. No numerical samples are treated as proofs.

Checks actually run: the final full regression run collected **119**, with **118 passed and one skipped** (the deliberate missing-SymPy scenario when SymPy is installed). After the final comparison-budget/test-deadline and repeat-inventory changes, **19 learning-graph tests and seven preparation tests passed**. Validated repeat import retained **51** unique records. Actual-file hashes/sizes, all seven notes, 15 teaching rules, six Persian/English keyword cases and a real LangGraph local lesson with exactly one matching example plus `done` resume passed. This smoke uses no model/search calls or semantic index construction. Regression tests also exercise the existing semantic implementation with fixtures; this does not certify full-book cross-language coverage.

Initial full regression found one fixture that assumed the project's source directory was empty; it now uses a temporary empty directory and keyword retrieval. The initial corpus smoke inherited tracing and received HTTP 403 from LangSmith; tracing is now explicitly disabled in the check script. A subsequent smoke exceeded its 20-second resource deadline while running multiple Windows workers concurrently; its check configuration now uses a 60-second request deadline and the clean final smoke passed. No live AvalAI request was made or key value printed in this phase.

Installed preparation versions: BeautifulSoup 4.13.3, pypdf 6.20.0, PyMuPDF 1.28.2; symbolic verification uses the existing SymPy 1.14.0. PDFs and text extracts are local artifacts, not generated success placeholders.

Changed files: `scripts/prepare_core_sources.py`, `prepare_paul_examples.py`, `prepare_topic_notes.py`, `review_core_sources.py`, `check_phase3.py`, `report_phase3.py`; retired bulk CLI in `scripts/acquire_references.py`; `learning.py` verification helper; `tests/test_phase3_preparation.py`, `test_learning_graph.py`, `test_answer_graph.py`, `test_acquisition.py`; `requirements-acquisition.txt`, `.gitignore`, README, implementation status and the four canonical specs. Generated: four PDFs/extracts, seven notes and seven metadata sidecars, `sources/teaching_bestpractices.md`, `sources/examples/schema.json`, private Paul JSONL, and manifests `openstax_core.json`, `formula_reviews.json`, `topic_registry.json`, `paul_selection.json`, `phase3_checks.json` and this report. Temporary probe scripts were removed; user originals and historical manifests were preserved.

Inspect now: `.\\.venv\\Scripts\\python.exe scripts\\check_phase3.py`. Reproduce preparation using the commands in README. Core acquisition returns exit 2 while formula review remains incomplete; successful PDF transfers do not override that gate. Render reviewed original pages with `scripts/review_core_sources.py --render`.

Remaining work before the Phase 3 exit: reviewed transcription or reliable math-aware extraction of missing formulas, notation/layout checks, and suitable selected examples for the recorded level gaps. Do not index unreviewed raw book text. The numbered next phase is Phase 4; wait for explicit continuation. STOP at Phase 3.
"""
    (directory / "phase3_report.md").write_text(report, encoding="utf-8")
    snapshot = f"""Phase 3 was explicitly authorized and executed on 2026-10-09. Exactly four official PDFs were resolved and downloaded: **{total:,} actual bytes**, zero partial transfers; readable extracts total **{core['total_extracted_text_bytes']:,} bytes**. Actual PDF/license URLs, author metadata, paths, hashes, page diagnostics and statuses are in [the core manifest](../sources/manifests/openstax_core.json).

The Phase 3 exit is **incomplete**: visually reviewed pages show missing formula images or flattened notation in all four extracts, which remain excluded from retrieval. Seven clearly attributed original starter notes, 15 original level-specific teaching rules, a schema/deduplicating importer and 51 distinct selected Paul examples are prepared. Mathematical result checks: 27 verified, 23 unsupported, one unknown; {missing} topic/level slots remain missing. The three-per-topic-per-level policy is unchanged. No additional books, full-site crawling or entire example collection was downloaded; LangGraph-only execution and bilingual retrieval remain unchanged. No later phase was implemented in this run.

See [the Phase 3 report](../sources/manifests/phase3_report.md), [selected-example counts/rationales](../sources/manifests/paul_selection.json) and [topic registry](../sources/manifests/topic_registry.json) for actual results and remaining work. Earlier acquisition reports are historical.
"""
    for name in ["math_tutor_spec.md", "math_tutor_implementation_prompt.md", "math_tutor_sources.md", "math_tutor_download_links.md"]:
        path = ROOT / "specs" / name
        text = path.read_text(encoding="utf-8")
        outdated = "Version 2.6 — four-book acquisition is scheduled for Phase 3. This is a selection/reference list, not a bulk download instruction. No PDF URL has been resolved and no download/extraction has been attempted in this documentation revision. Resolve current PDF URLs, licenses and actual byte sizes only when Phase 3 is authorized."
        if outdated in text:
            text = text.replace(outdated, "Version 2.6 — four-book acquisition belongs to Phase 3. This is a selection/reference list, not a bulk download instruction. Authorized Phase 3 execution has now downloaded the four books; the execution status below records actual results and remaining formula problems.")
            path.write_text(text, encoding="utf-8")
        section(path, "## Phase 3 execution status — 2026-10-09", snapshot)
    download_links = ROOT / "specs/math_tutor_download_links.md"
    current_urls = "| Book | Official resolved PDF URL | Actual PDF bytes | Observed license |\n|---|---|---:|---|\n" + "\n".join(
        f"| {b['title']} | {b['pdf_url']} | {b['actual_file_size_bytes']:,} | [BY-NC-SA 4.0]({b['license_url']}) |" for b in core["books"])
    section(download_links, "## Resolved PDF snapshot — 2026-10-09", current_urls + "\n\nResolve again from each official book page for future acquisition; these links are an observed snapshot, not a permanent guessed download pattern.")
    section(ROOT / "IMPLEMENTATION_STATUS.md", "## Phase 3 execution — 2026-10-09", snapshot.replace("../sources/", "sources/") +
        "\nFinal full regression: 119 collected, 118 passed, one expected skip. Final affected learning suite: 19 passed. Actual-corpus keyword/real-LangGraph smoke and idempotent 51-record import passed. Phase 3 formula exit remains incomplete; no later implementation phase started. See the report for initial failures and corrections.")
    print(f"Phase 3 report saved: four books, {total:,} PDF bytes, {paul['selected_count']} selected examples; exit incomplete.")


if __name__ == "__main__":
    main()
