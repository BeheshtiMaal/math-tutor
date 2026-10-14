"""Run the fixed W3 evaluation set against the real compiled tutor and record the results.

Phase W3 task 8 and exit gate 3. Every item is sent through the actual eleven-node
graph with the real model, retrieval and web-search services, in learn mode with full
delivery, in the language of the prompt. Nothing is faked.

Concept matching is deliberately coarse: it is a presence check to make a human read
faster, not an automatic correctness judgement. Results are written after every item so
a long run can be inspected or resumed, and the gaps are listed rather than hidden.

Runs are concurrent (bounded), because a sequential pass costs ~19 s per lesson.

Each row also records whether the reply was **provider-degraded**: the writer fell back
to displaying the local passages because the model call failed. A degraded row is not
evidence about content coverage, so degraded and non-degraded rows are counted
separately and never merged into one "quality gap" list.

Usage:
    python scripts/run_evaluation.py                 # full set
    python scripts/run_evaluation.py --limit 2       # smoke run
    python scripts/run_evaluation.py --concurrency 8
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import OpenAIModelClient, Request, build_graph, load_config, new_request_state  # noqa: E402
from langsmith import tracing_context  # noqa: E402
from web_search import TavilySearchClient  # noqa: E402

STRIP = ("$", "\\(", "\\)", "\\[", "\\]", "\\left", "\\right", "\\text", "\\,", "\\;", "\\!",
         "\\", "{", "}", "_", "*", "`")

# Bounded editorial alternatives for the concepts missed solely by wording.
# These are coverage hints, not mathematical correctness or negation proofs.
CONCEPT_ALTERNATIVES = {
    "multiply": ("multiplying", "product"),
    "sum formula": ("addition formula", "sine addition identity"),
    "two-sided": ("both the left and the right", "left and right must agree"),
    "نادرست": ("درست نیست", "برقرار نیست", "کافی نیست", "نیست", "خطا"),
    "هیچ‌کدام": ("نه بیشینه", "نه کمینه"),
    "پایه یکسان": ("پایه‌ها یکی", "پایه‌ها با هم مساوی", "پایه برابر"),
    "ریشه ناخواسته": ("ریشه‌های ناخواسته", "جواب‌های اضافی"),
    "لزومی ندارد": ("لازم نیست", "ضروری نیست"),
    "علامت‌دار": ("تجمع علامت", "با علامت منفی", "مقدار انتگرال منفی"),
    "تجزیه": ("(x - 1)(x + 1)",),
    "2/3": (r"\frac{2}{3}",),
}


def normalize(text):
    text = text.lower().replace("\u200c", "")
    text = text.replace("ي", "ی").replace("ك", "ک")
    text = text.replace(r"\cdot", "*").replace(r"\times", "*")
    text = re.sub(r"\^\{([^{}]+)\}", r"^(\1)", text)
    text = re.sub(r"\^([a-z0-9]+)", r"^(\1)", text)
    for token in STRIP:
        text = text.replace(token, "")
    return re.sub(r"\s+", " ", text).strip()


def concept_found(concept, answer_norm, answer_compact):
    for candidate in (concept, *CONCEPT_ALTERNATIVES.get(concept, ())):
        value = normalize(candidate)
        if value in answer_norm or value.replace(" ", "") in answer_compact:
            return True
    return False


async def run_item(graph, config, record, language):
    request = Request(query=record["prompt"][language], topic=record["topic"], mode="learn",
                      language=language, learner_level=record["learner_level"], delivery_mode="full")
    state = new_request_state(request, config)
    thread = {"configurable": {"thread_id": str(uuid4())}}
    started = time.monotonic()
    with tracing_context(enabled=False):
        result = await graph.ainvoke(state, thread)
    elapsed = round(time.monotonic() - started, 1)

    answer = result.get("explanation") or result.get("answer") or ""
    # Score the lesson itself, not appended bank examples or service warnings.
    segments = result.get("explanation_segments") or []
    lesson_text = segments[0].text if segments else answer
    answer_norm, answer_compact = normalize(lesson_text), normalize(lesson_text).replace(" ", "")
    expected = record["expected_concepts"][language]
    found = [term for term in expected if concept_found(term, answer_norm, answer_compact)]
    missing = [term for term in expected if term not in found]
    status = "complete" if not missing else ("partial" if found else "missed")
    warnings = list(result.get("warnings") or ())
    # A provider failure makes the writer display the local passages verbatim. That is
    # an infrastructure outcome, not a statement about the curated notes, so it is
    # flagged and counted apart from genuine content gaps.
    degraded = any("Explanation synthesis failed" in warning for warning in warnings)
    return dict(
        id=record["id"], topic=record["topic"], learner_level=record["learner_level"],
        kind=record["kind"], language=language, status=status, elapsed_seconds=elapsed,
        degraded=degraded, expected=expected, found=found, missing=missing,
        answer_chars=len(answer), answer=answer, warnings=warnings,
        scoring_version="w3-concept-alternatives-v2", scored_text="first explanation segment",
        nodes=[getattr(event, "node", None) if not isinstance(event, dict) else event.get("node")
               for event in (result.get("execution_trace") or ())],
        topic_kind=result.get("topic_kind"),
    )


def failed_jobs(dataset, previous):
    """Select exact item/language pairs, including partial coverage failures."""
    records = {record["id"]: record for record in dataset["records"]}
    rows = previous.get("non_complete_runs", previous.get("results", []))
    selected, seen = [], set()
    for row in rows:
        if row.get("status") not in {"partial", "missed", "error"}:
            continue
        key = (row["id"], row["language"])
        if key[0] not in records or key[1] not in {"fa", "en"}:
            raise ValueError(f"Unknown evaluation item/language: {key}")
        if key not in seen:
            selected.append((records[key[0]], key[1]))
            seen.add(key)
    if not selected:
        raise ValueError("No partial, missed or error runs found in the supplied artifact")
    return selected


def unrun_jobs(dataset, previous):
    """Select unfinished pairs; reject ambiguous reconstructed aggregate coverage."""
    all_jobs = [(record, language) for record in dataset["records"] for language in ("fa", "en")]
    known = {(record["id"], language) for record, language in all_jobs}
    if "selected_pairs" in previous:
        selected = {(row["id"], row["language"]) for row in previous["selected_pairs"]}
        if not selected <= known or len(selected) != previous["planned_runs"]:
            raise ValueError("Prior selected pairs do not match the dataset/planned count")
        all_jobs = [(record, language) for record, language in all_jobs
                    if (record["id"], language) in selected]
        known = selected
    if "results" in previous:
        completed = {(row["id"], row["language"]) for row in previous["results"]}
        if not completed <= known or len(completed) != previous["runs"]:
            raise ValueError("Prior completed rows do not match the evaluation dataset/count")
    else:
        # The lost 42-row run retained counts by topic, level and language.
        # Five whole topics are known, and only integral is partially completed.
        # Level counts uniquely identify the integral intermediate pair.
        completed = set()
        topic_counts = {topic: sum(count for status, count in scores.items()
                                   if status in {"complete", "partial", "missed", "error"})
                        for topic, scores in previous["by_topic"].items()}
        partial_topics = []
        for topic, count in topic_counts.items():
            jobs = [(record, language) for record, language in all_jobs if record["topic"] == topic]
            if count == len(jobs):
                completed.update((record["id"], language) for record, language in jobs)
            elif count:
                partial_topics.append(topic)
        if len(partial_topics) > 1:
            raise ValueError("Multiple partial topics make aggregate reconstruction ambiguous")
        for level, scores in previous["by_level"].items():
            full_count = sum((record["id"], language) in completed
                             for record, language in all_jobs if record["learner_level"] == level)
            remaining = scores["n"] - full_count
            candidates = [(record, language) for record, language in all_jobs
                          if record["topic"] in partial_topics and record["learner_level"] == level]
            if remaining not in {0, len(candidates)}:
                raise ValueError("Partial level/language coverage cannot be recovered from aggregates")
            if remaining:
                completed.update((record["id"], language) for record, language in candidates)
        if len(completed) != previous["runs"]:
            raise ValueError("Reconstructed completed count differs from saved run count")
        for language, scores in previous["by_language"].items():
            if sum(pair[1] == language for pair in completed) != sum(scores.values()):
                raise ValueError("Reconstructed language counts differ from saved aggregates")
        for topic, count in topic_counts.items():
            if sum((record["id"], language) in completed for record, language in all_jobs
                   if record["topic"] == topic) != count:
                raise ValueError("Reconstructed topic counts differ from saved aggregates")
    jobs = [(record, language) for record, language in all_jobs
            if (record["id"], language) not in completed]
    if not jobs:
        raise ValueError("No unfinished evaluation pairs remain")
    return jobs


async def main(limit, concurrency, output, force, rerun_failed=None, run_unfinished=None, phase='W3'):
    config, credentials = load_config()
    dataset = json.loads((ROOT / "sources/manifests/evaluation_set.json").read_text(encoding="utf-8"))
    records = dataset["records"][:limit] if limit else dataset["records"]
    selection_source = rerun_failed or run_unfinished
    if selection_source:
        if limit:
            raise ValueError("--limit cannot be combined with a prior-run selection")
        prior_path = ROOT / selection_source
        if (ROOT / output).resolve() == prior_path.resolve():
            raise ValueError("Failure reruns must use a separate --output artifact")
        previous = json.loads(prior_path.read_text(encoding="utf-8"))
        jobs = (failed_jobs if rerun_failed else unrun_jobs)(dataset, previous)
        records = list({record["id"]: record for record, _ in jobs}.values())
    else:
        jobs = [(record, language) for record in records for language in ("fa", "en")]

    # Wire the same live services the CLI and web entry points use: a real provider
    # model, a real search client and the real embedding backend.
    model = OpenAIModelClient(config, credentials) if config.model else None
    search_client = TavilySearchClient(config, credentials)
    graph = build_graph(config, model=model, search_client=search_client, channel="web",
                        embedding_credentials=credentials)
    destination = (ROOT / output) if not Path(output).is_absolute() else Path(output)

    # A short smoke run once overwrote a long aborted run and its raw rows were lost.
    # Refuse to clobber an aborted artifact unless the caller says so explicitly.
    if destination.exists() and not force:
        try:
            previous = json.loads(destination.read_text(encoding="utf-8"))
        except Exception:
            previous = {}
        if previous.get("run_status") == "aborted":
            print(f"{destination} holds an aborted run ({previous.get('runs')}/"
                  f"{previous.get('planned_runs')}). Pass --force to overwrite, or --output elsewhere.",
                  file=sys.stderr)
            return 2

    results, failures, lock = [], [], asyncio.Lock()
    gate = asyncio.Semaphore(max(1, concurrency))

    def summarise():
        degraded = [row for row in results if row.get("degraded")]
        clean = [row for row in results if not row.get("degraded")]
        return dict(
            generated_at=datetime.now(timezone.utc).isoformat(),
            curation_phase=phase, channel="web", model=config.model,
            provider=config.provider, search_backend=config.search_backend,
            search_enabled=config.search_enabled,
            concurrency=concurrency,
            # An interrupted run must not read as a finished one, and a smoke run must
            # not read as a full pass.
            scope=f"failed-only({len(jobs)} item/language pairs)" if rerun_failed else
                  (f"unfinished-only({len(jobs)} item/language pairs)" if run_unfinished else
                   ("full" if not limit else f"smoke({len(records)} items)")),
            rerun_of=selection_source,
            selection_basis=("reconstructed from topic/level/language aggregates; raw rows lost"
                             if run_unfinished and "results" not in previous else "explicit item/language pairs"),
            selected_pairs=[dict(id=record["id"], language=language) for record, language in jobs],
            run_status="complete" if len(results) == len(jobs) else "aborted",
            items=len(records), runs=len(results), planned_runs=len(jobs),
            scoring="Concept terms are a coarse presence check for a human read, not automatic correctness.",
            totals={name: sum(1 for r in results if r["status"] == name)
                    for name in ("complete", "partial", "missed", "error")},
            degraded_runs=len(degraded),
            clean_runs=len(clean),
            # Split deliberately: a provider-degraded row says nothing about the notes.
            degraded_totals={name: sum(1 for r in degraded if r["status"] == name)
                             for name in ("complete", "partial", "missed", "error")},
            clean_totals={name: sum(1 for r in clean if r["status"] == name)
                          for name in ("complete", "partial", "missed", "error")},
            by_topic={topic: {name: sum(1 for r in results if r["topic"] == topic and r["status"] == name)
                              for name in ("complete", "partial", "missed", "error")}
                      for topic in sorted({r["topic"] for r in results})},
            quality_gaps=sorted(set(failures)),
            results=results,
        )

    async def worker(record, language):
        try:
            row = await run_item(graph, config, record, language)
        except Exception as error:  # a raised error is recorded, never a silent pass
            row = dict(id=record["id"], topic=record["topic"], learner_level=record["learner_level"],
                       kind=record["kind"], language=language, status="error", degraded=None,
                       error=f"{type(error).__name__}: {error}")
        async with lock:
            results.append(row)
            if row.get("status") in {"partial", "missed", "error"} and not row.get("degraded"):
                failures.append(f"{row['id']}/{language}: {row.get('status')} missing={row.get('missing')}")
            destination.write_text(json.dumps(summarise(), ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
            flag = " [degraded]" if row.get("degraded") else ""
            print(f"({len(results)}/{len(jobs)}) {row['id']}/{language}: {row['status']}{flag} "
                  f"({row.get('elapsed_seconds')}s, {row.get('answer_chars')} chars) "
                  f"missing={row.get('missing')}", flush=True)

    async def guarded(record, language):
        async with gate:
            await worker(record, language)

    # Python 3.10 has no asyncio.TaskGroup; gather is the portable bounded fan-out.
    await asyncio.gather(*(guarded(record, language) for record, language in jobs))

    final = summarise()
    print("\ntotals:", final["totals"])
    print(f"degraded by provider fallback: {final['degraded_runs']}/{final['runs']} "
          f"(clean {final['clean_runs']})")
    return 0


if __name__ == "__main__":
    # Windows redirected consoles may default to cp1252; missing terms include Persian.
    sys.stdout.reconfigure(encoding="utf-8")
    cli = argparse.ArgumentParser()
    cli.add_argument("--limit", type=int, default=0)
    cli.add_argument("--concurrency", type=int, default=6)
    cli.add_argument("--output", default="sources/manifests/evaluation_run.json")
    cli.add_argument("--phase", choices=['W3','W9'], default='W3')
    cli.add_argument("--force", action="store_true",
                     help="overwrite an existing aborted run artifact")
    selection = cli.add_mutually_exclusive_group()
    selection.add_argument("--rerun-failed", help="prior artifact: rerun only its partial/missed/error item-language pairs")
    selection.add_argument("--run-unfinished", help="prior artifact: run only its unfinished item-language pairs")
    arguments = cli.parse_args()
    raise SystemExit(asyncio.run(main(arguments.limit, arguments.concurrency,
                                      arguments.output, arguments.force, arguments.rerun_failed, arguments.run_unfinished,arguments.phase)))
