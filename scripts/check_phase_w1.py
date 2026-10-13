"""Phase W1 exit gate: a scripted HTTP client drives the service over a real socket.

What is real here:

* the compiled eleven-node LangGraph, built once and reused;
* LangGraph's own in-memory checkpointer (no other persistence layer);
* the SymPy math worker, which produces ``x=6`` for ``2x+5=17``;
* uvicorn listening on loopback and an httpx client speaking HTTP to it.

What is replaced: the external model, search and retrieval services, exactly as
the earlier phases do in their offline runs. The graph engine is never faked.

Run:  ./.venv/Scripts/python.exe scripts/check_phase_w1.py
"""
from __future__ import annotations

import json
import os
import socket
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
# The first SymPy call pays a cold spawn on Windows (~15s at the time of
# writing); the 5s default would report a timeout for a correct answer.
LIMITS = agent.Limits(math_timeout_seconds=30.0, request_timeout_seconds=60.0)


class Report:
    """Collect every check so one failure never hides the others."""

    def __init__(self) -> None:
        self.checks: list[dict] = []

    def check(self, name: str, passed: bool, **detail) -> bool:
        self.checks.append({"check": name, "passed": bool(passed), **detail})
        print(f"{'PASS' if passed else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
        return bool(passed)

    @property
    def passed(self) -> bool:
        return all(item["passed"] for item in self.checks)


def build_app():
    config = agent.AppConfig(
        limits=LIMITS,
        preferences=agent.Preferences(mode="learn", delivery_mode="step", language="en", learner_level="beginner"),
    )
    model = FakeModelClient([plan()])
    retrieval = retrieval_client()
    graph = agent.build_graph(config, model, retrieval_client=retrieval)
    service = TutorService(
        config=config,
        graph=graph,
        registry=ThreadRegistry(max_threads=8, idle_seconds=3600.0),
    )
    app = create_app(service=service, config=config, credentials=agent.Credentials())
    return app, service, model, retrieval


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def start_server(app, port: int):
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    )
    thread = threading.Thread(target=server.run, name="uvicorn-check", daemon=True)
    thread.start()
    deadline = time.time() + 30
    while time.time() < deadline:
        if server.started:
            return server, thread
        time.sleep(0.05)
    raise RuntimeError("uvicorn did not report startup within 30 seconds")


def main() -> int:
    report = Report()
    app, service, model, retrieval = build_app()
    port = free_port()
    server, thread = start_server(app, port)
    base = f"http://127.0.0.1:{port}"
    answer_thread = new_thread_id()
    lesson_thread = new_thread_id()

    try:
        # trust_env=False is required: this environment exports HTTP_PROXY with no
        # NO_PROXY, and httpx honours it by default, which would send loopback
        # traffic through a proxy instead of to the service under test.
        with httpx.Client(base_url=base, timeout=180.0, trust_env=False) as client:
            # ------------------------------------------------------- health
            health = client.get("/health")
            body = health.json()
            report.check(
                "health returns 200 and version 3.0",
                health.status_code == 200 and body["version"] == "3.0",
                status=health.status_code,
            )
            report.check(
                "health reports the frozen eleven-node graph",
                body["graph_nodes"] == list(agent.NODE_NAMES) and len(body["graph_nodes"]) == 11,
                nodes=len(body["graph_nodes"]),
            )
            report.check(
                "health reports configuration presence, never a credential value",
                body["services"]["model"] == "missing" and body["known_threads"] == 0,
                services=body["services"],
            )
            report.check(
                "CORS is limited to the configured frontend origin",
                client.get("/health", headers={"Origin": FRONTEND_ORIGIN}).headers.get(
                    "access-control-allow-origin"
                )
                == FRONTEND_ORIGIN,
            )

            # ------------------------------------- gate 1: answer mode (real SymPy)
            started = time.time()
            answer = client.post(
                "/api/chat/turn",
                json={"thread_id": answer_thread, "message": "2x+5=17", "action": "new_lesson", "mode": "answer"},
            )
            answer_body = answer.json()
            report.check(
                "answer mode: 2x+5=17 solves to x=6 via the real SymPy worker",
                answer.status_code == 200
                and answer_body["status"] == "ok"
                and answer_body["mode"] == "answer"
                and answer_body["segments"] == [{"kind": "answer", "text": "x=6"}],
                segments=answer_body.get("segments"),
                seconds=round(time.time() - started, 2),
                http=answer.status_code,
            )
            report.check(
                "answer mode reaches no external model",
                len(model.calls) == 0,
                model_calls=len(model.calls),
            )

            # ------------------------------------- gate 1: learn mode + next + done
            first = client.post(
                "/api/chat/turn",
                json={"thread_id": lesson_thread, "message": "Explain derivatives", "action": "new_lesson"},
            ).json()
            report.check(
                "learn mode: first step is delivered and the graph pauses",
                first["status"] == "ok"
                and first["mode"] == "learn"
                and first["delivery"] == "step"
                and first["lesson"]["awaiting_user"] is True
                and first["lesson"]["step_index"] == 0
                and first["lesson"]["total_steps"] == 4
                and first["interrupt"]["kind"] == "lesson",
                lesson=first.get("lesson"),
            )
            report.check(
                "learn mode: the topic is classified against the prepared corpus",
                first["topic"] == "derivative" and first["topic_kind"] in {"core", "open"},
                topic=first.get("topic"),
                topic_kind=first.get("topic_kind"),
            )

            nxt = client.post("/api/chat/resume", json={"thread_id": lesson_thread, "action": "next"}).json()
            report.check(
                "next resume advances exactly one step and re-pauses",
                nxt["status"] == "ok"
                and nxt["lesson"]["step_index"] == 1
                and nxt["lesson"]["awaiting_user"] is True,
                lesson=nxt.get("lesson"),
            )

            done = client.post("/api/chat/resume", json={"thread_id": lesson_thread, "action": "done"}).json()
            report.check(
                "done resume ends the lesson with no pending interrupt",
                done["status"] == "ok"
                and done["interrupt"] is None
                and done["lesson"]["awaiting_user"] is False,
                lesson=done.get("lesson"),
            )
            report.check(
                "the lesson plan is cached: one planning call and three retrievals",
                len(model.calls) == 1 and len(retrieval.calls) == 3,
                model_calls=len(model.calls),
                retrieval_calls=len(retrieval.calls),
            )

            # ------------------------------------- gate 2: unknown / expired thread
            unknown = new_thread_id()
            for action in ["next", "full", "done"]:
                response = client.post("/api/chat/resume", json={"thread_id": unknown, "action": action})
                payload = response.json()
                report.check(
                    f"resuming an unknown thread with '{action}' is a status, not an error",
                    response.status_code == 200 and payload["status"] == "thread_not_found",
                    status=response.status_code,
                    body_status=payload.get("status"),
                )
            report.check(
                "a rejected resume never creates the thread",
                service.registry.known(unknown) is False,
            )

            # ------------------------------------- transport limits and error shape
            oversized = client.post(
                "/api/chat/turn",
                json={"thread_id": new_thread_id(), "message": "x" * 300_000, "action": "new_lesson"},
            )
            report.check(
                "an oversized body is rejected with 413 before the handler",
                oversized.status_code == 413
                and oversized.json()["error"]["code"] == "payload_too_large",
                status=oversized.status_code,
            )
            bad_id = client.post("/api/chat/turn", json={"thread_id": "thr_short", "message": "hi"})
            report.check(
                "a malformed thread id is a 400 without echoing the value",
                bad_id.status_code == 400
                and "thr_short" not in bad_id.text
                and bad_id.json()["error"]["code"] == "bad_request",
                status=bad_id.status_code,
            )
            ui_event = client.post(
                "/api/chat/turn",
                json={"thread_id": lesson_thread, "action": "ui_event"},
            )
            report.check(
                "ui_event is explicitly refused until phase W7",
                ui_event.status_code == 400
                and ui_event.json()["error"]["message_key"] == "error.action_not_supported",
                status=ui_event.status_code,
            )

            # ------------------------------------- gate 3: idle cleanup
            live = client.get("/health").json()
            report.check(
                "both scripted threads are tracked and none are active",
                live["known_threads"] == 2 and live["active_threads"] == 0,
                known=live["known_threads"],
                active=live["active_threads"],
            )
            service.registry.idle_seconds = -1.0
            evicted = service.sweep()
            report.check(
                "sweeping idle threads evicts them and drops their checkpoints",
                set(evicted) == {answer_thread, lesson_thread}
                and service.registry.stats()["known_threads"] == 0,
                evicted=evicted,
            )
            after = client.post("/api/chat/resume", json={"thread_id": lesson_thread, "action": "next"}).json()
            report.check(
                "an evicted thread reports thread_not_found rather than resuming",
                after["status"] == "thread_not_found",
                status=after.get("status"),
            )
    finally:
        server.should_exit = True
        thread.join(timeout=15)

    payload = {
        "phase": "W1",
        "transport": f"uvicorn on 127.0.0.1:{port} + httpx over a real socket",
        "graph": "real compiled LangGraph, 11 nodes, LangGraph in-memory checkpointer",
        "real_services": ["sympy math worker", "langgraph checkpointer", "uvicorn", "httpx client"],
        "replaced_services": ["model", "search", "retrieval"],
        "checks": report.checks,
        "passed": report.passed,
    }
    manifest = ROOT / "sources" / "manifests" / "phase_w1_checks.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{sum(c['passed'] for c in report.checks)}/{len(report.checks)} checks passed -> {manifest}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
