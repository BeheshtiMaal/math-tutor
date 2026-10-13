"""Validate curated core notes and regenerate sidecars, the topic registry and the teaching rules.

Phase W3 changed the contract of this script. The note bodies are now authored
directly in ``sources/topics/<topic>.md`` and are the source of truth; they are
rich bilingual documents (three levels, four structural units per level) and are
deliberately *not* regenerated from a Python literal. This script:

1. validates every curated note against the structural contract;
2. writes the ``<topic>.metadata.json`` sidecars the evidence loader reads;
3. regenerates ``sources/manifests/topic_registry.json``, which defines the core list;
4. keeps ``sources/teaching_bestpractices.md`` in sync with the rule list.

It fails loudly: on any structural defect it prints every problem and exits
non-zero *without writing anything*, so a bad edit can never silently shrink the
core list or ship a half-bilingual note.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The core list is fixed here and must stay in sync with the notes on disk.
# topic -> (book key, reference sections, level objectives)
TOPICS = {
    "derivative": (
        "calculus-volume-1",
        "3.3 Differentiation Rules",
        "beginner: rate of change; intermediate: power rules; advanced: domain and local definition",
    ),
    "integral": (
        "calculus-volume-1",
        "5.3 The Fundamental Theorem of Calculus; 5.4 Integration Formulas",
        "beginner: primitive; intermediate: rewriting; advanced: convergence and conditions",
    ),
    "limits": (
        "calculus-volume-1",
        "2.2 The Limit of a Function; 2.3 The Limit Laws",
        "beginner: approach; intermediate: one-sided comparison; advanced: squeeze and existence",
    ),
    "algebra": (
        "college-algebra-2e",
        "1.5 Factoring Polynomials; 2.2 Linear Equations in One Variable; 2.5 Quadratic Equations",
        "beginner: inverse operations; intermediate: method choice; advanced: excluded and repeated roots",
    ),
    "matrix": (
        "college-algebra-2e",
        "7.5 Matrices and Matrix Operations; 7.6 Solving Systems with Gaussian Elimination",
        "beginner: entries and rows; intermediate: elimination; advanced: rank and solution families",
    ),
    "probability": (
        "introductory-statistics-2e",
        "3.1 Terminology; 3.3 Two Basic Rules of Probability",
        "beginner: outcomes; intermediate: conditional probability; advanced: independence assumptions",
    ),
    "optimization": (
        "calculus-volume-1",
        "4.7 Applied Optimization Problems",
        "beginner: objective; intermediate: constraint; advanced: global extremum and endpoints",
    ),
    "logarithms": (
        "college-algebra-2e",
        "6.3 Logarithmic Functions; 6.4 Graphs of Logarithmic Functions; "
        "6.5 Logarithmic Properties; 6.6 Exponential and Logarithmic Equations",
        "beginner: exponent question; intermediate: product/quotient/power rules and change of base; "
        "advanced: domain and inverse-function conditions",
    ),
    "exponentials": (
        "college-algebra-2e",
        "6.1 Exponential Functions; 6.2 Graphs of Exponential Functions; "
        "6.7 Exponential and Logarithmic Models",
        "beginner: repeated growth; intermediate: compound and continuous models; "
        "advanced: base conditions and model limits",
    ),
    "trigonometry": (
        "calculus-volume-1",
        "1.3 Trigonometric Functions; 3.5 Derivatives of Trigonometric Functions",
        "beginner: right-triangle ratios; intermediate: unit circle and identities; "
        "advanced: periodicity, domain and inverse branches",
    ),
}

# Ordered structural contract for every note.
LEVELS = (("Beginner", "مبتدی"), ("Intermediate", "متوسط"), ("Advanced", "پیشرفته"))
UNITS = (
    ("Definition", "تعریف"),
    ("Rule and conditions", "قاعده و شرطها"),
    ("Worked example", "مثال حل‌شده"),
    ("Common mistakes", "اشتباه‌های رایج"),
)

# Roadmap W3 item 3 names the coverage logarithms must have. Checked case-insensitively.
REQUIRED_TERMS = {
    "logarithms": (
        "inverse",
        "base",
        "change of base",
        "product rule",
        "quotient rule",
        "power rule",
        "domain",
        "graph",
        "natural logarithm",
        "common mistakes",
    ),
}

PERSIAN = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")

RULES = [
    "[beginner] Ask about one prerequisite and define every new symbol before using it.",
    "[beginner] Connect a concrete quantity to its expression before giving a general rule.",
    "[beginner] Use short steps and explain the purpose of the current operation.",
    "[beginner] Pair a described diagram with words and equations when it clarifies the idea.",
    "[beginner] Show one complete worked example, then invite a small independent attempt.",
    "[intermediate] Explain why the chosen method fits the expression or domain.",
    "[intermediate] Ask the learner to explain one transition before revealing the next step.",
    "[intermediate] Interleave a worked solution with a related retrieval question.",
    "[intermediate] Revisit a prior concept after a delay instead of relying only on repetition now.",
    "[intermediate] Diagnose a specific misconception and correct it with a reason.",
    "[advanced] State domain restrictions and the hypotheses required by each theorem.",
    "[advanced] Separate a calculation, a proof of existence and a proof of completeness.",
    "[advanced] Discuss a boundary or counterexample that tests the claim's scope.",
    "[advanced] Preserve uncertainty and identify exactly which claims SymPy checked.",
    "[advanced] Invite an explanatory argument, then verify assumptions and special cases.",
]


def split_sections(text, level):
    """Split ``text`` into (heading, body) blocks whose heading has exactly ``level`` hashes."""
    pattern = re.compile(r"(?m)^#{%d}(?!#) " % level)
    pieces, marks = [], [match.start() for match in pattern.finditer(text)]
    for index, start in enumerate(marks):
        end = marks[index + 1] if index + 1 < len(marks) else len(text)
        block = text[start:end]
        heading, _, body = block.partition("\n")
        pieces.append((heading.strip(), body))
    return pieces


def paragraphs(body):
    """One paragraph per non-empty line: the notes put the English line then its Persian line."""
    return [line.strip() for line in body.splitlines() if line.strip()]


def bilingual_unit(body):
    """Return (has_english, has_persian) for a unit body."""
    paras = paragraphs(body)
    english = any(not PERSIAN.search(para) and re.search(r"[A-Za-z]", para) for para in paras)
    persian = any(PERSIAN.search(para) for para in paras)
    return english, persian


def validate(topic, text, problems):
    """Append a human-readable problem for every structural defect found in one note."""
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        problems.append(f"{topic}: missing a level-1 title line")
        return None
    title = lines[0][2:].strip()
    parts = title.split(" / ")
    if len(parts) != 2 or not all(part.strip() for part in parts):
        problems.append(f"{topic}: title must be '# English / Persian', got {title!r}")
        return None
    english_title, persian_title = (part.strip() for part in parts)
    if not PERSIAN.search(persian_title):
        problems.append(f"{topic}: Persian half of the title has no Persian letters: {persian_title!r}")

    levels = split_sections(text, 2)
    expected_levels = [f"## {en} / {fa}" for en, fa in LEVELS]
    got_levels = [heading for heading, _ in levels]
    if got_levels != expected_levels:
        problems.append(f"{topic}: level headings must be {expected_levels}, got {got_levels}")

    for (level_english, _), (heading, body) in zip(LEVELS, levels):
        label = f"{topic}/{level_english}"
        intro = body.split("###", 1)[0]
        if paragraphs(intro):
            problems.append(f"{label}: the level heading must carry no prose; "
                            f"fold any framing sentence into the Definition unit")

        units = split_sections(body, 3)
        expected_units = [f"### {en} / {fa}" for en, fa in UNITS]
        got_units = [unit_heading for unit_heading, _ in units]
        if got_units != expected_units:
            problems.append(f"{label}: unit headings must be {expected_units}, got {got_units}")
            continue

        for (unit_english, _), (_, unit_body) in zip(UNITS, units):
            has_en, has_fa = bilingual_unit(unit_body)
            if not has_en:
                problems.append(f"{label}/{unit_english}: no English paragraph")
            if not has_fa:
                problems.append(f"{label}/{unit_english}: no Persian paragraph")

    for term in REQUIRED_TERMS.get(topic, ()):
        if term.lower() not in text.lower():
            problems.append(f"{topic}: required coverage term missing: {term!r}")

    return dict(english=english_title, persian=persian_title)


def verify_reference(book_key, book, section, topic, problems, warnings):
    """Check the reference is not fabricated: the book must be local and each section must exist in it."""
    text_path = ROOT / "sources/text/openstax" / f"{book_key}.md"
    if not text_path.exists():
        warnings.append(f"{topic}: extracted text for {book_key} is unavailable, section check skipped")
        return
    text = text_path.read_text(encoding="utf-8", errors="ignore")
    for number in re.findall(r"\b\d+\.\d+\b", section):
        if not re.search(r"(?m)^" + re.escape(number) + r"\s", text):
            problems.append(f"{topic}: reference section {number} is not a heading in {book['title']}")


def main():
    manifest = json.loads((ROOT / "sources/manifests/openstax_core.json").read_text(encoding="utf-8"))
    books = {Path(book["raw_path"]).stem: book for book in manifest["books"]}
    directory = ROOT / "sources/topics"
    directory.mkdir(parents=True, exist_ok=True)

    problems, warnings, notes, missing = [], [], {}, []
    for topic, (book_key, section, _) in TOPICS.items():
        path = directory / (topic + ".md")
        if not path.exists():
            missing.append(f"{topic}: no note file at {path.relative_to(ROOT).as_posix()}")
            continue
        text = path.read_text(encoding="utf-8")
        titles = validate(topic, text, problems)
        if titles:
            notes[topic] = (path, titles)
        if book_key not in books:
            problems.append(f"{topic}: unknown reference book key {book_key!r}")
        else:
            verify_reference(book_key, books[book_key], section, topic, problems, warnings)

    problems.extend(missing)
    extra = sorted(p.stem for p in directory.glob("*.md") if p.stem not in TOPICS)
    if extra:
        problems.append(f"note files present but not in the core list: {extra}")

    if problems:
        print(f"Refusing to write: {len(problems)} structural problem(s).", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    registry = []
    for topic, (book_key, section, levels) in TOPICS.items():
        path, titles = notes[topic]
        record = books[book_key]
        metadata = dict(
            topic=topic,
            provenance=dict(
                source_url=record["source_url"],
                section_title=section,
                source_author="MathTutor project (original exposition), referencing " + record["title"],
                retrieved_at=record["retrieved_at"],
                usage_terms_url=record["license_url"],
                usage_terms="Original project exposition; reference textbook license observed: "
                + record["license"]
                + ". Raw extracted text has not been cleared for formula fidelity or embedding use.",
            ),
        )
        # No learner_level key: every record matches every level, because the note
        # carries all three levels and the loader must not filter two thirds of it.
        path.with_suffix(".metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        registry.append(
            dict(
                topic=topic,
                english=titles["english"],
                persian=titles["persian"],
                path=path.relative_to(ROOT).as_posix(),
                reference_book=record["title"],
                reference_section=section,
                level_objectives=levels,
                note_origin="original_project_exposition",
                textbook_transcript=False,
            )
        )

    (ROOT / "sources/manifests/topic_registry.json").write_text(
        json.dumps(
            dict(
                phase=3,
                curation_phase="W3",
                topics=registry,
                raw_book_retrieval_enabled=False,
                limitation="Curated notes cover the ten core topics at three levels. They do not "
                "establish whole-book coverage: Calculus Volume 2 is acquired but no direct "
                "transcript is indexed, and four core topics (probability, logarithms, "
                "exponentials, trigonometry) have no source example in the selected example bank. "
                "See sources/manifests/example_gap_report.json.",
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    header = (
        "# Original teaching guidance\n\nProject-authored rules: five per level. Rules about spacing, "
        "worked examples, explanatory questions and connecting representations are informed by the IES "
        "practice guide [Organizing Instruction and Study to Improve Student Learning]"
        "(https://ies.ed.gov/ncee/wwc/PracticeGuide/1). Other rules implement the tutor's own domain, "
        "verification and interaction policy. These are adaptations, not quoted rules or a claim of "
        "experimentally proven tutoring quality.\n\n"
    )
    (ROOT / "sources/teaching_bestpractices.md").write_text(
        header + "\n".join(f"{i}. {rule}" for i, rule in enumerate(RULES, 1)) + "\n", encoding="utf-8"
    )

    print(f"Validated {len(registry)} curated core topic notes (3 levels x 4 units each) and wrote sidecars, "
          f"topic_registry.json and {len(RULES)} level-specific teaching rules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
