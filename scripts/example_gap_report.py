"""Report the example-bank gap for the ten curated core topics, at topic x level.

Phase W3 task 4. The selected example bank is finite and drawn from linked pages
of Paul's Online Math Notes (Algebra and Calculus I). Where a core topic or level
has no source example, this script records the gap. It never fabricates a fill.

Writes ``sources/manifests/example_gap_report.json`` and ``sources/manifests/example_gap_report.md``.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ("beginner", "intermediate", "advanced")
# Three source examples per topic-level is the selection target the acquisition
# manifest already used; below it the slot is recorded as sparse, not as covered.
TARGET = 3


def classify(count):
    if count == 0:
        return "missing"
    if count < TARGET:
        return "sparse"
    return "covered"


def main():
    registry = json.loads((ROOT / "sources/manifests/topic_registry.json").read_text(encoding="utf-8"))
    topics = [entry["topic"] for entry in registry["topics"]]
    bank = [json.loads(line) for line in
            (ROOT / "sources/examples/paul/selected.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    grid = defaultdict(int)
    subtopics = defaultdict(set)
    for row in bank:
        grid[(row.get("topic"), row.get("learner_level"))] += 1
        if row.get("subtopic"):
            subtopics[row.get("topic")].add(row["subtopic"])

    slots, missing, sparse, covered = [], [], [], []
    for topic in topics:
        for level in LEVELS:
            count = grid.get((topic, level), 0)
            status = classify(count)
            record = dict(topic=topic, learner_level=level, selected=count, target=TARGET,
                          status=status, subtopics=sorted(subtopics.get(topic, ())))
            slots.append(record)
            {"missing": missing, "sparse": sparse, "covered": covered}[status].append(f"{topic}/{level}")

    bank_topics = sorted({row.get("topic") for row in bank})
    absent_topics = [topic for topic in topics if topic not in bank_topics]

    payload = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        curation_phase="W3",
        bank="sources/examples/paul/selected.jsonl",
        bank_size=len(bank),
        bank_origin=sorted({row.get("origin") for row in bank}),
        bank_courses=sorted({row.get("course") for row in bank}),
        bank_verification=dict(Counter(row.get("verification_status") for row in bank)),
        source_pages=json.loads((ROOT / "sources/manifests/paul_selection.json")
                                .read_text(encoding="utf-8"))["fetched_pages"],
        totals=dict(slots=len(slots), covered=len(covered), sparse=len(sparse), missing=len(missing)),
        topics_with_no_examples=absent_topics,
        covered_slots=covered,
        sparse_slots=sparse,
        missing_slots=missing,
        slots=slots,
        limitation="Coverage counts source examples only; 'covered' means three or more selected "
                   "examples exist, not that they are pedagogically sufficient. Every gap is recorded "
                   "rather than filled by invention, and unsupported examples remain source-backed but "
                   "not mathematically verified.",
    )
    (ROOT / "sources/manifests/example_gap_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Example-bank gap report (Phase W3)",
        "",
        f"Bank: `{payload['bank']}` - {len(bank)} selected examples from "
        f"{len(payload['source_pages'])} Paul's Online Math Notes pages ({', '.join(payload['bank_courses'])}).",
        "",
        f"Slots: {len(slots)} topic x level combinations. "
        f"Covered {len(covered)}, sparse {len(sparse)}, missing {len(missing)}.",
        "",
        f"Core topics with no selected example at any level: {', '.join(absent_topics) or 'none'}.",
        "",
        "| Topic | Beginner | Intermediate | Advanced |",
        "| --- | --- | --- | --- |",
    ]
    for topic in topics:
        cells = []
        for level in LEVELS:
            count = grid.get((topic, level), 0)
            cells.append(f"{classify(count)} ({count})")
        lines.append(f"| {topic} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Recorded gaps",
        "",
        f"* Missing: {', '.join(missing) or 'none'}",
        f"* Sparse (fewer than {TARGET}): {', '.join(sparse) or 'none'}",
        "",
        payload["limitation"],
        "",
    ]
    (ROOT / "sources/manifests/example_gap_report.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"slots {len(slots)}: covered {len(covered)}, sparse {len(sparse)}, missing {len(missing)}")
    print("topics with no examples:", ", ".join(absent_topics) or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
