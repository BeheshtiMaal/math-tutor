"""Explicit smoke checks for configured/available services; safe status-only output."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import tracing_context
from agent import load_config, OpenAIModelClient, RoutingOutput, EvidenceRequest
from retrieval import LocalE5, EmbeddingUnavailable
from remote_embeddings import AvalAIEmbeddings
from web_search import TavilySearchClient


async def check():
    config, credentials = load_config()
    results = {}
    if config.model and credentials.openai_api_key:
        try:
            with tracing_context(enabled=False):
                await asyncio.wait_for(OpenAIModelClient(config, credentials).structured([
                    SystemMessage(content="Classify as answer mode, algebra topic, en language, beginner learner level, full delivery."),
                    HumanMessage(content="Solve 2x+5=17")], RoutingOutput), config.limits.request_timeout_seconds)
            results["provider"] = {"status": "passed", "coverage": "Structured output only; not mathematical correctness"}
        except Exception:
            results["provider"] = {"status": "failed", "reason": "Provider request failed or timed out"}
    else:
        results["provider"] = {"status": "not_exercised", "reason": "Model or provider key unconfigured"}
    if config.search_enabled and credentials.search_api_key:
        result = await TavilySearchClient(config, credentials).search(EvidenceRequest(
            query="definition of derivative tangent slope", topic="derivative", language="en", learner_level="beginner", max_records=2))
        results["search"] = {"status": "passed" if result.status == "success" else "failed",
                             "evidence_status": result.status, "records": len(result.records)}
    else:
        results["search"] = {"status": "not_exercised", "reason": "Search disabled or key unconfigured"}
    if config.embedding_backend == "avalai":
        try:
            embedder = AvalAIEmbeddings(config, credentials.embedding_api_key)
            documents = await asyncio.to_thread(embedder.encode, ["The derivative gives the instantaneous rate of change and tangent slope.", "A matrix is a rectangular array of numbers."])
            query = await asyncio.to_thread(embedder.encode, ["شیب لحظه‌ای تابع چیست؟"], query=True)
            results["embedding"] = {"status": "passed" if int((documents @ query[0]).argmax()) == 0 else "failed",
                                    "backend": "avalai", "coverage": "One Persian query against two English synthetic passages"}
        except Exception:
            results["embedding"] = {"status": "failed", "reason": "AvalAI embedding request failed or returned invalid vectors"}
    elif not importlib.util.find_spec("sentence_transformers"):
        results["embedding"] = {"status": "not_exercised", "reason": "Embedding package unavailable"}
    else:
        try:
            embedder = LocalE5(config)
            embedder.load()
        except EmbeddingUnavailable:
            results["embedding"] = {"status": "not_exercised", "reason": "Compatible local model unavailable"}
        else:
            try:
                documents = await asyncio.to_thread(embedder.encode, ["The derivative gives the instantaneous rate of change and tangent slope.", "A matrix is a rectangular array of numbers."])
                query = await asyncio.to_thread(embedder.encode, ["شیب لحظه‌ای تابع چیست؟"], query=True)
                results["embedding"] = {"status": "passed" if int((documents @ query[0]).argmax()) == 0 else "failed",
                                        "coverage": "One Persian query against two English synthetic passages"}
            except Exception:
                results["embedding"] = {"status": "failed", "reason": "Local embedding check failed"}
    print(json.dumps(results, indent=2))
    return 0 if all(row["status"] == "passed" for row in results.values()) else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(check()))
