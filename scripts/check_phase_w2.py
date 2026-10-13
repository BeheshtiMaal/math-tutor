"""Phase W2 exit gates: the core refactors, driven end to end.

Real here: the compiled eleven-node LangGraph, LangGraph's in-memory
checkpointer, the SymPy math worker, uvicorn on loopback and an httpx client
over a socket, plus the CLI in a subprocess for the debug-mode gate.

Replaced: the external model, search and retrieval services, as in every
offline run of the earlier phases. The graph engine is never faked.

Run:  ./.venv/Scripts/python.exe scripts/check_phase_w2.py
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
for variable in ["LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING"]:
    os.environ[variable] = "false"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TESTS))

import httpx  # noqa: E402
import uvicorn  # noqa: E402

import agent  # noqa: E402
from fakes import FakeModelClient  # noqa: E402
from test_learning_graph import client as retrieval_client  # noqa: E402
from test_step_teaching import plan  # noqa: E402
from webapp.main import create_app  # noqa: E402
from webapp.service import TutorService  # noqa: E402
from webapp.threads import ThreadRegistry, new_thread_id  # noqa: E402

FRONTEND_ORIGIN = "http://localhost:3000"
LIMITS = agent.Limits(math_timeout_seconds=30.0, request_timeout_seconds=60.0)
PERSIAN = "مشتق"


def persian_plan():
    return {"steps": [
        {"objective": "فهم قاعده", "explanation": "توان n یک عدد صحیح مثبت است. قاعده توان، x را به آن توان مشتق می‌گیرد.", "source_ids": ["power-rule"]},
        {"objective": "به‌کارگیری روش", "kind": "method", "explanation": "در توان ضرب کن. توان را یکی کم کن تا n*x^(n-1) به دست آید.", "source_ids": ["power-rule"]},
        {"objective": "حفظ فرض‌ها", "kind": "check", "explanation": "این یادداشت قاعده را برای n صحیح مثبت بیان می‌کند. این فرض را نگه دار.", "source_ids": ["power-rule"]},
    ]}


def full_draft(**changes):
    draft = {"explanation": "The derivative measures an instantaneous rate of change.", "source_ids": ["power-rule"]}
    draft.update(changes)
    return draft


class SchemaAwareModel(FakeModelClient):
    """Answers by schema shape so the scripted flow does not depend on call order."""

    async def structured(self, messages, schema):
        if not self.responses:
            from lesson_steps import LessonPlanDraft

            self.responses.append(plan() if schema is LessonPlanDraft else full_draft())
        return await super().structured(messages, schema)


class Report:
    def __init__(self):
        self.checks = []

    def check(self, name, passed, **detail):
        self.checks.append({"check": name, "passed": bool(passed), **detail})
        print(f"{'PASS' if passed else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
        return bool(passed)

    @property
    def passed(self):
        return all(item["passed"] for item in self.checks)


def build_app(channel="web", *, model=None, config=None):
    config = config or agent.AppConfig(
        limits=LIMITS,
        preferences=agent.Preferences(mode="learn", delivery_mode="step", language=None, learner_level=None),
    )
    graph = agent.build_graph(config, model, retrieval_client=retrieval_client(), channel=channel)
    service = TutorService(config=config, graph=graph, registry=ThreadRegistry(max_threads=16, idle_seconds=3600.0))
    app = create_app(service=service, config=config, credentials=agent.Credentials())
    return app, service, graph, config


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def start_server(app, port):
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False))
    thread = threading.Thread(target=server.run, name="uvicorn-w2", daemon=True)
    thread.start()
    deadline = time.time() + 30
    while time.time() < deadline:
        if server.started:
            return server, thread
        time.sleep(0.05)
    raise RuntimeError("uvicorn did not report startup within 30 seconds")


def has_persian(text: str) -> bool:
    return any("\u0600" <= character <= "\u06FF" for character in text)


def main() -> int:
    report = Report()
    # Only the Persian lesson needs a queued answer; everything else follows the
    # schema shape, so the checks stay independent of call order.
    model = SchemaAwareModel([persian_plan()])
    app, service, graph, config = build_app(model=model)
    port = free_port()
    server, thread = start_server(app, port)
    base = f"http://127.0.0.1:{port}"
    lesson_thread, topic_thread = new_thread_id(), new_thread_id()

    try:
        with httpx.Client(base_url=base, timeout=180.0, trust_env=False) as http:
            # ------------------------------------------- gate 1: per-message language
            fa = http.post("/api/chat/turn", json={
                "thread_id": lesson_thread, "message": "مشتق را توضیح بده", "action": "new_lesson", "mode": "learn",
            }).json()
            report.check(
                "a Persian message is detected as fa and answered in Persian",
                fa["status"] == "ok" and fa["language"] == "fa" and fa["language_source"] == "detected"
                and any(has_persian(segment["text"]) for segment in fa["segments"]),
                language=fa.get("language"), source=fa.get("language_source"),
            )
            http.post("/api/chat/resume", json={"thread_id": lesson_thread, "action": "done"})
            en = http.post("/api/chat/turn", json={
                "thread_id": lesson_thread, "message": "Explain derivatives", "action": "new_lesson", "mode": "learn",
            }).json()
            report.check(
                "an English message in the same thread is detected as en and answered in English",
                en["status"] == "ok" and en["language"] == "en" and en["language_source"] == "detected"
                and not any(has_persian(segment["text"]) for segment in en["segments"]),
                language=en.get("language"), source=en.get("language_source"),
            )
            http.post("/api/chat/resume", json={"thread_id": lesson_thread, "action": "done"})
            report.check(
                "the two turns in one thread used different languages",
                fa["language"] == "fa" and en["language"] == "en",
            )

            # A client override wins over detection.
            override = http.post("/api/chat/turn", json={
                "thread_id": new_thread_id(), "message": "Explain derivatives", "action": "new_lesson",
                "mode": "learn", "language_override": "fa",
            }).json()
            report.check(
                "a request language override wins over detection",
                override["language"] == "fa" and override["language_source"] == "override",
                language=override.get("language"), source=override.get("language_source"),
            )

            # An ambiguous message falls back to the thread's previous language.
            ambiguous = http.post("/api/chat/turn", json={
                "thread_id": lesson_thread, "message": "2x+5=17", "action": "new_lesson", "mode": "learn",
            }).json()
            report.check(
                "an ambiguous message falls back to the thread's previous language",
                ambiguous["language"] == "en" and ambiguous["language_source"] == "detected",
                language=ambiguous.get("language"),
            )

            # ------------------------------ gate 2: correct formulas per channel
            web_answer = http.post("/api/chat/turn", json={
                "thread_id": new_thread_id(), "message": "2x+5=17", "action": "new_lesson", "mode": "answer",
            }).json()
            report.check(
                "the web channel returns SymPy's own LaTeX for the formula",
                web_answer["status"] == "ok" and web_answer["segments"] == [{"kind": "answer", "text": "$$x = 6$$"}],
                segments=web_answer.get("segments"),
            )

            # ------------------------------------------- gate 3: core vs open topics
            core = http.post("/api/chat/turn", json={
                "thread_id": topic_thread, "message": "Explain derivatives", "action": "new_lesson", "mode": "learn",
            }).json()
            report.check(
                "a core topic completes a lesson and is labelled core",
                core["status"] == "ok" and core["topic"] == "derivative" and core["topic_kind"] == "core"
                and core["lesson"]["awaiting_user"] is True,
                topic=core.get("topic"), kind=core.get("topic_kind"),
            )
            open_state = agent.new_request_state(
                agent.Request(query="Explain topology", topic="topology", mode="learn", language="en"), config)
            open_result = run_graph(graph, open_state, "w2-open-topic")
            report.check(
                "an open topic completes a lesson and is labelled open",
                open_result["topic"] == "topology" and open_result["topic_kind"] == "open" and open_result["__interrupt__"],
                topic=open_result.get("topic"), kind=open_result.get("topic_kind"),
            )
            report.check(
                "the metadata distinguishes the two topic kinds",
                core["topic_kind"] == "core" and open_result["topic_kind"] == "open",
            )

            # ------------------------------------------- gate 4: profile validation
            good = {"version": 1, "topics": {"derivative": {"level": "advanced", "level_source": "manual"}}}
            accepted = http.post("/api/chat/turn", json={
                "thread_id": new_thread_id(), "message": "Explain derivatives", "action": "new_lesson",
                "mode": "learn", "learner_profile": good,
            }).json()
            report.check(
                "a valid profile is accepted and its level is applied",
                accepted["profile_status"] == "accepted" and accepted["learner_level"] == "advanced"
                and accepted["level_source"] == "manual",
                status=accepted.get("profile_status"), level=accepted.get("learner_level"),
            )
            oversized = {"topics": {f"topic-{index}": {"level": "beginner"} for index in range(60)}}
            rejected = http.post("/api/chat/turn", json={
                "thread_id": new_thread_id(), "message": "Explain derivatives", "action": "new_lesson",
                "mode": "learn", "learner_profile": oversized,
            }).json()
            report.check(
                "an oversized profile is rejected while the turn still succeeds",
                rejected["status"] == "ok" and rejected["profile_status"] == "rejected"
                and rejected["learner_level"] == "beginner",
                status=rejected.get("profile_status"),
            )
            malformed = {"topics": {"derivative": {"level": "expert"}}}
            broken = http.post("/api/chat/turn", json={
                "thread_id": new_thread_id(), "message": "Explain derivatives", "action": "new_lesson",
                "mode": "learn", "learner_profile": malformed,
            }).json()
            report.check(
                "a malformed profile is rejected while the turn still succeeds",
                broken["status"] == "ok" and broken["profile_status"] == "rejected",
                status=broken.get("profile_status"),
            )
            report.check(
                "the server keeps no copy of any profile",
                not hasattr(service, "learner_profile") and "learner_profile" not in json.dumps(accepted),
            )

            # ------------------------------------------- gate 5: writer output schema
            full = http.post("/api/chat/turn", json={
                "thread_id": new_thread_id(), "message": "Explain derivatives", "action": "new_lesson",
                "mode": "learn", "delivery": "full",
            }).json()
            report.check(
                "the writer returns ordered typed text segments and a separate empty block list",
                full["status"] == "ok" and full["blocks"] == []
                and full["segments"] and all(set(segment) == {"kind", "text"} for segment in full["segments"]),
                blocks=full.get("blocks"), segments=len(full.get("segments") or []),
            )
    finally:
        server.should_exit = True
        thread.join(timeout=15)

    # ------------------------------------------- gate 5 (cont.): schema and repair
    report.check(*schema_checks())

    # ------------------------------------------- gate 6: CLI debug mode
    cli = subprocess.run(
        [sys.executable, "cli.py", "--offline"],
        cwd=str(ROOT), input="/debug on\n2x+5=17\n/exit\n", capture_output=True, text=True, timeout=180, encoding="utf-8",
    )
    report.check(
        "the CLI still runs offline in debug mode and answers correctly",
        cli.returncode == 0 and "x=6" in cli.stdout and "[write_answer: success]" in cli.stdout,
        returncode=cli.returncode,
        debug_lines=cli.stdout.count("[") if cli.stdout else 0,
    )

    payload = {
        "phase": "W2",
        "transport": f"uvicorn on 127.0.0.1:{port} + httpx over a real socket",
        "graph": "real compiled LangGraph, 11 nodes, LangGraph in-memory checkpointer",
        "real_services": ["sympy math worker", "langgraph checkpointer", "uvicorn", "httpx client", "cli.py subprocess"],
        "replaced_services": ["model", "search", "retrieval"],
        "checks": report.checks,
        "passed": report.passed,
    }
    manifest = ROOT / "sources" / "manifests" / "phase_w2_checks.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{sum(c['passed'] for c in report.checks)}/{len(report.checks)} checks passed -> {manifest}")
    return 0 if report.passed else 1


def run_graph(graph, state, thread_id):
    import asyncio

    return asyncio.run(graph.ainvoke(state, {"configurable": {"thread_id": thread_id}}))


def schema_checks():
    """Writer schema and malformed-output repair, asserted directly."""
    from learning import LessonDraft

    request = {"type": "function_graph", "title": "Power rule", "params": {"expression": "x**2"}, "fallback_text": "A graph."}
    good = LessonDraft.model_validate({"explanation": "One sentence. Two sentences.", "source_ids": ["a"], "block_requests": [request]})
    accepted = len(good.block_requests) == 1
    try:
        LessonDraft.model_validate({"explanation": "One sentence. Two sentences.", "source_ids": ["a"], "block_requests": [request] * 3})
        capped = False
    except Exception:
        capped = True
    # A malformed block request is dropped by the node, not by the schema.
    from learning import accepted_blocks

    warnings = []
    dropped = accepted_blocks([{"type": "hologram", "title": "Nope", "fallback_text": "x"}], "web", warnings)
    name = "the writer schema accepts blocks, caps them at two, and drops malformed ones"
    return (name, accepted and capped and dropped == [] and bool(warnings))


if __name__ == "__main__":
    raise SystemExit(main())
