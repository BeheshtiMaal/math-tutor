"""Cross-language retrieval checks with distractors, over the real curated corpus.

Phase W3 exit gate 2. Four families are measured, and they are not equivalent:

* ``end_to_end`` - the topic the live system would infer (``infer_topic``) is used,
  which is what a real turn does when the client sends no topic. This is the gate.
* ``distractor`` - topic is left unconstrained ("mathematics") so every curated chunk
  competes; the query must be won by the expected topic and not by a named confusable
  one. This is the gate.
* ``paired`` - the Persian and English phrasings of a topic must agree under the
  unconstrained setup. Recorded; a mismatch is a quality gap, not a silent pass.
* ``semantic`` - unconstrained ranking per query. Recorded as a diagnostic: this is
  the strictest reading and its misses are listed as gaps rather than hidden.

Writes ``sources/manifests/retrieval_cross_language.json``.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import EvidenceRequest, load_config, run_math_worker  # noqa: E402
from learning import infer_topic  # noqa: E402
from retrieval import SemanticRetrievalClient  # noqa: E402

# topic -> (Persian question, English question). Phrased as a learner would ask,
# not as a keyword list.
QUERIES = {
    "logarithms": ("لگاریتم چیست و چه نسبتی با توان دارد؟",
                   "What is a logarithm and how is it related to exponentiation?"),
    "exponentials": ("تابع نمایی چیست و چگونه رشد را مدل می‌کند؟",
                     "What is an exponential function and how does it model growth?"),
    "trigonometry": ("سینوس و کسینوس روی دایره واحد چگونه تعریف می‌شوند؟",
                     "How are sine and cosine defined on the unit circle?"),
    "algebra": ("معادله درجه دوم را چگونه حل کنم؟",
                "How do I solve a quadratic equation?"),
    "derivative": ("مشتق یک تابع چگونه محاسبه می‌شود؟",
                   "How is the derivative of a function computed?"),
    "integral": ("انتگرال معین را چگونه حساب کنم؟",
                 "How do I evaluate a definite integral?"),
    "limits": ("حد یک تابع به چه معناست؟",
               "What does the limit of a function mean?"),
    "matrix": ("ماتریس و دترمینان چه کاربردهایی دارند؟",
               "What are matrices and determinants used for?"),
    "probability": ("احتمال شرطی چگونه محاسبه می‌شود؟",
                    "How is conditional probability computed?"),
    "optimization": ("مسئله بهینه‌سازی را چگونه حل کنم؟",
                     "How do I solve an optimization problem?"),
}

# (query, expected topic, topic that must not win). Unconstrained, so distractors are live.
DISTRACTORS = [
    ("لگاریتم و پایه آن", "logarithms", "exponentials"),
    ("logarithm change of base", "logarithms", "exponentials"),
    ("مشتق تابع را چطور حساب کنم؟", "derivative", "integral"),
    ("derivative and tangent slope", "derivative", "integral"),
    ("انتگرال و پادمشتق", "integral", "derivative"),
    ("matrix determinant and elimination", "matrix", "algebra"),
    ("احتمال شرطی و بیز", "probability", "algebra"),
    ("unit circle and sine cosine", "trigonometry", "algebra"),
    ("حد و قضیه فشردگی", "limits", "derivative"),
]

GATE_FAMILIES = {"end_to_end", "distractor"}


def main():
    config, credentials = load_config()
    if config.embedding_backend != "avalai":
        print("TUTOR_EMBEDDING_BACKEND must be avalai.", file=sys.stderr)
        return 2
    client = SemanticRetrievalClient(config, run_math_worker, credentials=credentials)

    def top(query, language, topic):
        request = EvidenceRequest(query=query, topic=topic, language=language,
                                 learner_level="advanced", max_records=1)
        result = client.retrieve(request, "sources")
        record = result.records[0] if result.records else None
        return (record.topic if record else None), result.retrieval_method, result.warning

    end_to_end, semantic, paired = [], [], []
    for topic, (query_fa, query_en) in QUERIES.items():
        for language, query in (("fa", query_fa), ("en", query_en)):
            inferred = infer_topic(query)
            found, method, warning = top(query, language, inferred)
            end_to_end.append(dict(kind="end_to_end", language=language, expected_topic=topic,
                                   inferred_topic=inferred, actual_topic=found, method=method, query=query,
                                   status="passed" if found == topic else "failed", warning=warning))
            free, free_method, free_warning = top(query, language, "mathematics")
            semantic.append(dict(kind="semantic", language=language, expected_topic=topic, actual_topic=free,
                                 method=free_method, query=query,
                                 status="passed" if free == topic else "failed", warning=free_warning))
    for topic in QUERIES:
        fa = next(row for row in semantic if row["expected_topic"] == topic and row["language"] == "fa")
        en = next(row for row in semantic if row["expected_topic"] == topic and row["language"] == "en")
        paired.append(dict(kind="paired", topic=topic, fa_topic=fa["actual_topic"], en_topic=en["actual_topic"],
                           status="passed" if fa["actual_topic"] == en["actual_topic"] else "failed"))

    distractors = []
    for query, expected, forbidden in DISTRACTORS:
        language = "fa" if any("\u0600" <= ch <= "\u06FF" for ch in query) else "en"
        found, method, warning = top(query, language, "mathematics")
        distractors.append(dict(kind="distractor", language=language, query=query, expected_topic=expected,
                                forbidden_topic=forbidden, actual_topic=found, method=method,
                                status="passed" if found == expected and found != forbidden else "failed",
                                warning=warning))

    families = {"end_to_end": end_to_end, "semantic": semantic, "paired": paired, "distractor": distractors}
    all_cases = end_to_end + semantic + paired + distractors
    gate_failures = [row for name in GATE_FAMILIES for row in families[name] if row["status"] != "passed"]
    gaps = [f"{row['expected_topic']} ({row['language']}): got {row['actual_topic']}"
            for row in semantic if row["status"] != "passed"]
    gaps += [f"{row['topic']}: fa gave {row['fa_topic']} but en gave {row['en_topic']}"
             for row in paired if row["status"] != "passed"]

    payload = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        curation_phase="W3",
        model=config.embedding_model, dimension=config.embedding_dimension,
        design="end_to_end and distractor are the exit-gate families. semantic leaves the topic "
               "unconstrained so every curated chunk competes; its misses are listed as gaps.",
        gate_families=sorted(GATE_FAMILIES),
        gate=dict(passed=not gate_failures, failures=gate_failures),
        by_family={name: dict(cases=len(rows), passed=sum(1 for r in rows if r["status"] == "passed"))
                   for name, rows in families.items()},
        totals=dict(cases=len(all_cases), passed=sum(1 for r in all_cases if r["status"] == "passed")),
        semantic_quality_gaps=gaps,
        cases=all_cases,
        query_api_requests=client.embedder.requests,
    )
    (ROOT / "sources/manifests/retrieval_cross_language.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for name, stats in payload["by_family"].items():
        marker = " (gate)" if name in GATE_FAMILIES else ""
        print(f"{name}{marker}: {stats['passed']}/{stats['cases']} passed")
    for row in gate_failures:
        print(f"  GATE FAIL [{row['kind']}] expected {row.get('expected_topic')} got {row.get('actual_topic')} "
              f"({row.get('method')}): {row.get('query')}", file=sys.stderr)
    for gap in gaps:
        print(f"  semantic gap: {gap}", file=sys.stderr)
    print(f"query api requests: {client.embedder.requests}")
    return 2 if gate_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
