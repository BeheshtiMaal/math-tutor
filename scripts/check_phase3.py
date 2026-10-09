"""Inspect actual Phase 3 files and bilingual keyword retrieval without APIs/indexing."""
from __future__ import annotations
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
# Match the CLI's offline privacy behavior even when inherited tracing is on.
for variable in ["LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING"]:
    os.environ[variable] = "false"
sys.path.insert(0, str(ROOT))
from agent import AppConfig, EvidenceRequest, Limits, run_math_worker
from learning import LocalRetrievalClient
from prepare_core_sources import sha


async def check():
    manifest = json.loads((ROOT / "sources/manifests/openstax_core.json").read_text(encoding="utf-8"))
    assert len(manifest["books"]) == 4
    for book in manifest["books"]:
        pdf, text = ROOT / book["raw_path"], ROOT / book["text_path"]
        assert pdf.stat().st_size == book["actual_file_size_bytes"]
        assert sha(pdf) == book["raw_sha256"]
        assert sha(text) == book["text_sha256"]
    client = LocalRetrievalClient(AppConfig(semantic_enabled=False, limits=Limits(math_timeout_seconds=30, request_timeout_seconds=60)), run_math_worker)
    sources, source_warning = client.load_sources()
    examples, example_warning = client.load_examples()
    assert sources and not source_warning
    assert len(examples) == 51 and not example_warning
    assert len({r.example_id for r in examples}) == len(examples)
    checks = []
    for topic in ["derivative", "مشتق", "matrix", "ماتریس", "probability", "احتمال"]:
        request = EvidenceRequest(query=topic, topic=topic, learner_level="beginner", language="fa" if not topic.isascii() else "en")
        evidence = await client.read_source(request)
        assert evidence.status == "success"
        checks.append(dict(topic=topic, status=evidence.status, retrieval_method=evidence.retrieval_method))
    for level in ["beginner", "intermediate", "advanced"]:
        request = EvidenceRequest(query="derivative", topic="derivative", learner_level=level, language="en")
        guidance = await client.teaching_bestpractices(request)
        assert len(guidance.records) == 5
    # Real LangGraph invocation with original local notes and one matching Paul
    # record. No model, semantic index, search request or subsequent phase work.
    from agent import build_graph, new_request_state, Request
    from langgraph.types import Command
    config = client.config
    graph = build_graph(config, retrieval_client=client)
    thread = {"configurable": {"thread_id": "phase3-actual-corpus"}}
    state = new_request_state(Request(query="Explain derivatives", topic="derivative", mode="learn", language="en", learner_level="beginner"), config)
    result = await graph.ainvoke(state, thread)
    assert result["source"].status == "success" and result["examples"].status == "success"
    assert result["selected_example_id"] in {r.example_id for r in examples}
    assert result["explanation"].count("Source example:") == 1
    assert result["__interrupt__"]
    await graph.ainvoke(Command(resume="done"), thread)
    report = dict(phase=3, actual_pdf_size_bytes=sum(b["actual_file_size_bytes"] for b in manifest["books"]),
        source_records=len(sources), unique_examples=len(examples), verification_counts=dict(Counter(r.verification_status for r in examples)),
        keyword_bilingual_cases=checks, teaching_rules=15, actual_langgraph_local_lesson="passed; one matching example and done resume",
        semantic_index_built=False, provider_or_search_calls=False, formula_exit_complete=False)
    (ROOT / "sources/manifests/phase3_checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    asyncio.run(check())
