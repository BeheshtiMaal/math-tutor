"""Terminal input/display; compiled LangGraph owns all routing."""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import importlib.util
import json
import sys
from uuid import uuid4
from typing import Sequence

from langchain_core.messages import AIMessage
from langgraph.types import Command
from langsmith import tracing_context
from pydantic import ValidationError
from agent import AppConfig, ConfigurationError, OpenAIModelClient, Preferences, Request, build_graph, load_config, new_request_state

REQUIRED_PACKAGES = ("langgraph", "langchain", "langchain-openai", "sympy", "pydantic", "python-dotenv", "numpy", "httpx")


def check_configuration() -> tuple[dict, bool]:
    config, credentials = load_config()
    versions = {}
    for package in REQUIRED_PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return {
        "phase": 7, "graph_available": True, "learn_available": True,
        "search_enabled": config.search_enabled, "search_backend": config.search_backend,
        "search_key_present": credentials.search_api_key is not None,
        "model_base_url": config.model_base_url,
        "search_url": config.search_url,
        "step_available": True,
        "topic_notes_present": (config.sources_dir / "topics").is_dir(),
        "example_bank_present": (config.sources_dir / "examples" / "paul").is_dir(),
        "teaching_rules_present": (config.sources_dir / "teaching_bestpractices.md").is_file(),
        "semantic_enabled": config.semantic_enabled,
        "embedding_model": config.embedding_model,
        "embedding_revision": config.embedding_revision,
        "embedding_package_present": importlib.util.find_spec("sentence_transformers") is not None,
        "embedding_cache_present": (config.embedding_cache_dir / "sources.npz").is_file(),
        "provider": config.provider, "model_configured": config.model is not None,
        "credentials_configured": credentials.openai_api_key is not None,
        "preferences": config.preferences.model_dump(), "limits": config.limits.model_dump(),
        "package_versions": versions,
        "note": "Exact graph with full/step learning available; prepared local evidence and SymPy may be missing. No model request was made by this check.",
    }, all(versions.values())


HELP = """Answer and full/step learning. Commands: /help, /mode answer|learn,
/delivery full|step, /level beginner|intermediate|advanced,
/language fa|en, /reset, /debug on|off, /exit.
Lesson replies: next / بعدی / ادامه / اوکی; simplify / نفهمیدم;
full / کامل بگو; a follow-up question; done / تمام.
Only next advances a step. Full explains the remaining lesson.
Settings apply to the next request; /delivery full also finishes an active lesson's remainder.
Local calculation examples:
  2x+5=17
  diff x^3
  integrate x^2 from 0 to 1
  limit sin(x)/x at 0 both
  matrix inverse [[1,2],[3,4]]
  simplify x/x
Use 'wrt y' to select a variable. JSON problem payloads are also accepted.
During clarification, reply with the complete request or use /reset to cancel.
"""


async def run_cli(config: AppConfig, model=None, *, query=None, graph=None, read=input, display=print, search_client=None) -> int:
    graph = graph or build_graph(config, model=model, search_client=search_client)
    thread = {"configurable": {"thread_id": str(uuid4())}}
    pending = False
    pending_kind = None
    history = []
    debug = False
    emitted_version = 0
    queued_request = None
    emitted_traces = 0
    display("MathTutor Phase 7 — answer and full/step learning. /help for syntax; /exit to quit.")
    while True:
        try:
            line = queued_request if queued_request is not None else query if query is not None else read("reply> " if pending else "> ")
            queued_request = None
        except (EOFError, KeyboardInterrupt):
            display("Goodbye.")
            return 0
        line = line.strip()
        if not line:
            if query is not None:
                display("Enter a mathematical request.")
                return 2
            continue
        if line.startswith("/"):
            resume_command = False
            parts = line.split()
            command = parts[0]
            if command == "/exit" and len(parts) == 1:
                return 0
            if command == "/help" and len(parts) == 1:
                display(HELP)
            elif command == "/reset" and len(parts) == 1:
                thread = {"configurable": {"thread_id": str(uuid4())}}
                pending, history, emitted_version = False, [], 0
                pending_kind, queued_request, emitted_traces = None, None, 0
                display("Session reset.")
            elif command in {"/mode", "/language", "/delivery", "/level"} and len(parts) == 2:
                field = {"/mode": "mode", "/language": "language", "/delivery": "delivery_mode", "/level": "learner_level"}[command]
                try:
                    value = {"مبتدی": "beginner", "متوسط": "intermediate", "پیشرفته": "advanced"}.get(parts[1], parts[1]) if field == "learner_level" else parts[1]
                    config.preferences = Preferences.model_validate({**config.preferences.model_dump(), field: value})
                    display("Preference saved for the next request.")
                    if field == "delivery_mode" and value == "full" and pending_kind == "lesson":
                        line, resume_command = "full", True
                except ValidationError:
                    display("Invalid preference. Use /help.")
            elif command == "/debug" and len(parts) == 2 and parts[1] in {"on", "off"}:
                debug = parts[1] == "on"
                display("Debug " + parts[1] + ".")
            else:
                display("Unknown or malformed command. Use /help.")
            if query is not None:
                return 0
            if not resume_command:
                continue
        try:
            if pending:
                with tracing_context(enabled=False):
                    result = await graph.ainvoke(Command(resume=line), thread)
            else:
                thread = {"configurable": {"thread_id": str(uuid4())}}
                emitted_version = 0
                emitted_traces = 0
                state = new_request_state(Request(query=line), config, history)
                with tracing_context(enabled=False):
                    result = await graph.ainvoke(state, thread)
            interruptions = result.get("__interrupt__", ())
            pending = bool(interruptions)
            pending_kind = interruptions[0].value.get("kind") if pending else None
            if result.get("explanation_version", 0) > emitted_version:
                display(result["explanation"])
                emitted_version = result["explanation_version"]
            if pending:
                for pause in interruptions:
                    display(pause.value["prompt"])
            else:
                if result.get("mode") != "learn":
                    display(result.get("final_answer") or "No answer was produced.")
                elif result.get("final_answer"):
                    display(result["final_answer"])
                history = list(result.get("messages", [])) + [AIMessage(content=result.get("final_answer") or result.get("explanation", ""))]
                queued_request = result.get("new_topic_query")
            if debug:
                for event in result.get("execution_trace", [])[emitted_traces:]:
                    display(f"[{event.node}: {event.status}]")
            emitted_traces = len(result.get("execution_trace", []))
            if query is not None:
                return 2 if pending or getattr(result.get("math_result"), "status", None) in {"error", "timeout", "unsupported", "unevaluated"} else 0
        except KeyboardInterrupt:
            display("Request cancelled.")
            thread = {"configurable": {"thread_id": str(uuid4())}}
            pending = False
            pending_kind, emitted_version, emitted_traces = None, 0, 0
        except (ValidationError, ValueError):
            display("Invalid request or configuration; use /help for supported syntax.")
            if query is not None:
                return 2
            display("Use /reset to cancel any pending interaction.")
        except Exception:
            display("Request failed safely. Use /reset and try again.")
            pending = False
            pending_kind, emitted_version, emitted_traces, queued_request = None, 0, 0, None
            thread = {"configurable": {"thread_id": str(uuid4())}}
            if query is not None:
                return 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate config and report installed dependencies without network activity")
    parser.add_argument("--offline", action="store_true", help="Never call the language model or web search; local embeddings remain available")
    parser.add_argument("--query", help="Process one request; return nonzero for clarification or calculation failure")
    parser.add_argument("--index", action="store_true", help="Build/update local embedding caches; never download a model")
    parser.add_argument("--rebuild-index", action="store_true", help="Explicitly rebuild caches after model/settings changes (with --index)")
    args = parser.parse_args(argv)
    try:
        if args.check:
            report, complete = check_configuration()
            print(json.dumps(report, indent=2, ensure_ascii=True))
            return 0 if complete else 2
        config, credentials = load_config()
        if args.rebuild_index and not args.index:
            parser.error("--rebuild-index requires --index")
        if args.index:
            from agent import run_math_worker
            from retrieval import SemanticRetrievalClient
            reports = SemanticRetrievalClient(config, run_math_worker).build_indexes(rebuild=args.rebuild_index)
            print(json.dumps(reports, indent=2, ensure_ascii=True))
            return 0 if any(report["status"] == "success" for report in reports.values()) and all(report["status"] != "error" for report in reports.values()) else 2
        model = OpenAIModelClient(config, credentials) if config.model and not args.offline else None
        from web_search import TavilySearchClient
        if args.offline:
            config.search_enabled = False
        search_client = TavilySearchClient(config, credentials)
    except ConfigurationError as exc:
        print(str(exc))
        return 2
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        return asyncio.run(run_cli(config, model, query=args.query, search_client=search_client))
    except KeyboardInterrupt:
        print("Goodbye.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
