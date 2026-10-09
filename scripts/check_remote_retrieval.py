"""Explicit AvalAI cache-reuse and actual-corpus bilingual retrieval smoke."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import EvidenceRequest, load_config, run_math_worker
from retrieval import SemanticRetrievalClient


def main():
    config, credentials = load_config()
    if config.embedding_backend != "avalai":
        print("Configure TUTOR_EMBEDDING_BACKEND=avalai first.")
        return 2
    client = SemanticRetrievalClient(config, run_math_worker, credentials=credentials)
    indexes = client.build_indexes()
    if any(row["status"] != "success" for row in indexes.values()):
        print(json.dumps(indexes, ensure_ascii=True, indent=2))
        return 2
    reused_without_api = client.embedder.requests == 0
    cases = []
    for language, query, expected in [
        ("en", "What is the instantaneous rate of change and the slope of a tangent?", "derivative"),
        ("fa", "نرخ تغییر لحظه‌ای و شیب خط مماس تابع چیست؟", "derivative"),
        ("en", "How do the discriminant and quadratic formula give the roots of an equation?", "algebra"),
        ("fa", "چگونه با دلتا و فرمول معادله درجه دوم ریشه‌ها را پیدا کنیم؟", "algebra"),
    ]:
        # Deliberately allow all starter topics: metadata does not force the
        # expected topic to win these semantic-ranking checks.
        request = EvidenceRequest(query=query, topic="mathematics", language=language, learner_level="advanced", max_records=1)
        result = client.retrieve(request, "sources")
        found = result.records[0].topic if result.records else None
        cases.append(dict(language=language, expected_topic=expected, actual_topic=found, method=result.retrieval_method,
                          status="passed" if found == expected and result.retrieval_method == "semantic" else "failed"))
    report = dict(backend=config.embedding_backend, model=config.embedding_model, dimensions=config.embedding_dimension,
                  cache_reuse=indexes, cache_reuse_without_api_requests=reused_without_api, cases=cases,
                  smoke_api_requests=client.embedder.requests, smoke_prompt_tokens=client.embedder.prompt_tokens,
                  local_embedding_model_loaded=False, chat_or_search_called=False)
    destination = config.embedding_cache_dir / "retrieval-smoke.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if reused_without_api and all(row["status"] == "passed" for row in cases) else 2


if __name__ == "__main__":
    raise SystemExit(main())
