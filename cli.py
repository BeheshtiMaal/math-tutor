"""Terminal input/display; compiled LangGraph owns all routing."""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import importlib.util
import json
import os
import re
import sys
from uuid import uuid4
from typing import Sequence

from langchain_core.messages import AIMessage
from langgraph.types import Command
from langsmith import tracing_context
from pydantic import ValidationError
from agent import AppConfig, ConfigurationError, OpenAIModelClient, Preferences, Request, build_graph, load_config, new_request_state
from terminal_display import render_terminal

REQUIRED_PACKAGES = ("langgraph", "langchain", "langchain-openai", "sympy", "pydantic", "python-dotenv", "numpy", "httpx", "tiktoken", "arabic-reshaper", "python-bidi")


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
        "embedding_backend": config.embedding_backend,
        "embedding_base_url": config.embedding_base_url,
        "embedding_key_present": credentials.embedding_api_key is not None,
        "embedding_model": config.embedding_model,
        "embedding_revision": config.embedding_revision,
        "embedding_package_present": importlib.util.find_spec("tiktoken" if config.embedding_backend == "avalai" else "sentence_transformers") is not None,
        "embedding_cache_present": (config.embedding_cache_dir / "sources.npz").is_file(),
        "provider": config.provider, "model_configured": config.model is not None,
        "credentials_configured": credentials.openai_api_key is not None,
        "preferences": config.preferences.model_dump(), "limits": config.limits.model_dump(),
        "package_versions": versions,
        "note": "Exact graph with full/step learning available; prepared local evidence and SymPy may be missing. No model request was made by this check.",
    }, all(versions.values())


HELP = """
math-tutor / help
-----------------

GET STARTED
  Solve:    2x+5=17
  Learn:    Can you help me with x^2 - 5x + 6 = 0 step-by-step?

SETTINGS
  /mode answer|learn                  Quick answer or a lesson
  /delivery full|step                 Whole lesson or one step at a time
  /level beginner|intermediate|advanced
  /language fa|en                     Persian or English

DURING A LESSON
  next      Advance one step          (بعدی)
  simplify  Explain this step simply  (نفهمیدم)
  full      Show all remaining steps  (کامل بگو)
  done      End the lesson            (تمام)
  You can also ask a follow-up question.
  A complete new math problem starts a fresh lesson at step 1.

MORE MATH EXAMPLES
  diff x^3
  integrate x^2 from 0 to 1
  limit sin(x)/x at 0 both
  matrix inverse [[1,2],[3,4]]
  simplify x/x
  Add 'wrt y' to select a different variable.

SESSION
  /help           Show this guide
  /reset          Start a fresh conversation
  /debug on|off   Show or hide execution details
  /exit           Quit

Settings apply to your next request. /delivery full also finishes
the remaining steps of an active lesson. Only 'next' advances a step.
During clarification, enter the complete request or use /reset.
"""


def terminal_text(text: str) -> str:
    """Render common TeX wrappers as readable text, preserving unsupported math."""
    text = re.sub(r"\\(?:left|right)\b", "", text)
    text = re.sub(r"\\(?:\(|\)|\[|\])", "", text)
    text = text.replace("$$", "").replace("$", "")
    # Repeated passes handle nested braces without evaluating any expression.
    for _ in range(16):
        previous = text
        text = re.sub(r"\\(?:dfrac|tfrac|frac)\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", text)
        text = re.sub(r"\\sqrt\{([^{}]*)\}", r"sqrt(\1)", text)
        text = re.sub(r"\\(?:boxed|text|mathrm|mathbf)\{([^{}]*)\}", r"\1", text)
        text = re.sub(r"([_^])\{([^{}]*)\}", r"\1(\2)", text)
        if text == previous:
            break
    replacements = {r"\times": "*", r"\cdot": "*", r"\pm": "+/-", r"\neq": "!=",
                    r"\leq": "<=", r"\geq": ">=", r"\infty": "infinity"}
    for command, replacement in replacements.items():
        text = re.sub(re.escape(command) + r"\b", lambda match: replacement, text)
    text = text.translate(str.maketrans({"−": "-", "×": "*", "÷": "/", "±": "+/-", "√": "sqrt",
                                       "²": "^2", "³": "^3", "≤": "<=", "≥": ">=", "≠": "!="}))
    return text.strip()


def configure_terminal() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if os.name == "nt" and sys.stdout.isatty():
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.windll.kernel32
        kernel.SetConsoleTitleW("math-tutor")
        kernel.SetConsoleCP(65001)
        kernel.SetConsoleOutputCP(65001)
        # Courier New includes Persian glyphs absent from some console fonts.
        class ConsoleFont(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.ULONG), ("nFont", wintypes.DWORD),
                        ("dwFontSize", wintypes._COORD), ("FontFamily", wintypes.UINT),
                        ("FontWeight", wintypes.UINT), ("FaceName", wintypes.WCHAR * 32)]
        font = ConsoleFont()
        font.cbSize = ctypes.sizeof(font)
        font.dwFontSize.Y = 20
        font.FontFamily = 54
        font.FontWeight = 400
        font.FaceName = "Courier New"
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.SetCurrentConsoleFontEx.argtypes = [wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(ConsoleFont)]
        kernel.SetCurrentConsoleFontEx(kernel.GetStdHandle(-11), False, ctypes.byref(font))


async def run_cli(config: AppConfig, model=None, *, query=None, graph=None, read=input, display=print, search_client=None, embedding_credentials=None) -> int:
    raw_display = display
    def display(text):
        rendered = terminal_text(text)
        raw_display("\n" + render_terminal(rendered) + "\n" if raw_display is print else rendered)
    graph = graph or build_graph(config, model=model, search_client=search_client, embedding_credentials=embedding_credentials)
    thread = {"configurable": {"thread_id": str(uuid4())}}
    pending = False
    pending_kind = None
    history = []
    debug = False
    emitted_version = 0
    queued_request = None
    emitted_traces = 0
    display("math-tutor\n----------\nAsk a math question to begin. /help for commands; /exit to quit.")
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
    configure_terminal()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate config and report installed dependencies without network activity")
    parser.add_argument("--offline", action="store_true", help="Disable model, search and remote embeddings; local embeddings remain available")
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
        if args.offline and config.embedding_backend == "avalai":
            if args.index:
                parser.error("AvalAI index construction requires network access; omit --offline")
            config.semantic_enabled = False
        if args.rebuild_index and not args.index:
            parser.error("--rebuild-index requires --index")
        if args.index:
            from agent import run_math_worker
            from retrieval import SemanticRetrievalClient
            retrieval = SemanticRetrievalClient(config, run_math_worker, credentials=credentials)
            reports = retrieval.build_indexes(rebuild=args.rebuild_index)
            if config.embedding_backend == "avalai":
                reports["api_usage"] = {"requests": retrieval.embedder.requests, "prompt_tokens": retrieval.embedder.prompt_tokens}
            print(json.dumps(reports, indent=2, ensure_ascii=True))
            banks = [reports[kind] for kind in ["sources", "examples"]]
            return 0 if any(report["status"] == "success" for report in banks) and all(report["status"] != "error" for report in banks) else 2
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
        return asyncio.run(run_cli(config, model, query=args.query, search_client=search_client, embedding_credentials=credentials))
    except KeyboardInterrupt:
        print("Goodbye.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
