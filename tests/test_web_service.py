"""Phase W1 acceptance: FastAPI wraps the real compiled LangGraph.

The graph engine is never faked here. Only external services (model, search,
retrieval) are replaced, exactly as the earlier phases do. Stub graphs appear
only where the test is deliberately exercising the transport layer's own error
mapping, never to stand in for LangGraph behaviour.
"""
import asyncio
import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

import agent
from fakes import FakeModelClient
from test_learning_graph import client, evidence
from test_step_teaching import plan
from webapp.errors import ApiError, ErrorCode
from webapp.main import build_service, create_app, service_status
from webapp.schemas import ChatTurnRequest, LearnerProfile
from webapp.service import TutorService
from webapp.settings import ServerSettings, ServerSettingsError
from webapp.threads import ThreadRegistry, new_thread_id, valid_thread_id


def setUpModule():
    global tracing_env
    tracing_env = patch.dict(
        os.environ,
        {"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false", "LANGCHAIN_TRACING": "false"},
    )
    tracing_env.start()


def tearDownModule():
    tracing_env.stop()


def make_config(*, mode="learn", delivery="step", language="en", level="beginner"):
    return agent.AppConfig(
        preferences=agent.Preferences(mode=mode, delivery_mode=delivery, language=language, learner_level=level)
    )


def make_app(*, config=None, model=None, retrieval=None, math_runner=None, max_threads=8, idle_seconds=3600.0):
    config = config or make_config()
    options = {}
    if math_runner is not None:
        options["math_runner"] = math_runner
    if retrieval is not None:
        options["retrieval_client"] = retrieval
    graph = agent.build_graph(config, model, **options)
    registry = ThreadRegistry(max_threads=max_threads, idle_seconds=idle_seconds)
    service = TutorService(config=config, graph=graph, registry=registry)
    app = create_app(service=service, config=config, credentials=agent.Credentials())
    return app, service, graph


def solve_runner(record):
    def runner(problem, limits):
        record.append(problem)
        return agent.MathResult(status="solved", result="x=6")
    return runner


class StubGraph:
    """Transport-layer stub. Never used to assert graph behaviour."""

    def __init__(self, *, error=None, delay=0.0, checkpointer=None):
        self.error = error
        self.delay = delay
        self.checkpointer = checkpointer
        self.threads = []

    async def ainvoke(self, payload, config):
        self.threads.append(config["configurable"]["thread_id"])
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return {"mode": "answer", "final_answer": "stub", "warnings": [], "execution_trace": []}


class HealthAndTopologyChecks(unittest.TestCase):
    def test_health_reports_the_eleven_nodes_and_configuration_presence(self):
        app, _, _ = make_app()
        with TestClient(app) as client_:
            response = client_.get("/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["version"], "3.0")
        self.assertEqual(body["graph_nodes"], list(agent.NODE_NAMES))
        self.assertEqual(len(body["graph_nodes"]), 11)
        self.assertFalse(body["offline"])
        self.assertEqual(body["services"], {"model": "missing", "search": "missing", "embedding": "missing"})
        self.assertEqual(body["known_threads"], 0)
        self.assertEqual(body["active_threads"], 0)

    def test_offline_server_reports_disabled_services(self):
        config = make_config()
        config.search_enabled = True
        config.semantic_enabled = True
        status = service_status(config, agent.Credentials(search_api_key="k", embedding_api_key="k"), offline=True)
        self.assertEqual(status.model_dump(), {"model": "disabled", "search": "disabled", "embedding": "disabled"})

    def test_compiled_graph_node_and_edge_set_is_unchanged(self):
        _, service, graph = make_app()
        view = graph.get_graph()
        self.assertEqual(set(view.nodes), {"__start__", "__end__", *agent.NODE_NAMES})
        expected = set(agent.FIXED_EDGES)
        expected.update(
            (node, target)
            for node, routes in agent.CONDITIONAL_EDGES.items()
            for target in routes.values()
        )
        # The resource barrier is an edge-list edge, not a FIXED_EDGES entry:
        # every resource node feeds write_explanation exactly once.
        sources, sink = agent.RESOURCE_BARRIER
        expected.update((node, sink) for node in sources)
        self.assertEqual({(edge.source, edge.target) for edge in view.edges}, expected)
        # The barrier is intact: four resources feed the writer once.
        self.assertEqual(agent.RESOURCE_BARRIER[1], "write_explanation")
        self.assertEqual(len(agent.RESOURCE_BARRIER[0]), 4)
        self.assertIsNotNone(service.graph)

    def test_health_never_reports_a_credential_value(self):
        config = make_config()
        config.model = "fixture-model"
        config.search_enabled = True
        credentials = agent.Credentials(
            openai_api_key="private-fixture-key",
            search_api_key="private-search-key",
            embedding_api_key="private-embedding-key",
        )
        graph = agent.build_graph(config)
        service = TutorService(config=config, graph=graph, registry=ThreadRegistry())
        app = create_app(service=service, config=config, credentials=credentials)
        with TestClient(app) as client_:
            text = client_.get("/health").text
        self.assertNotIn("private-fixture-key", text)
        self.assertNotIn("private-search-key", text)
        self.assertNotIn("private-embedding-key", text)
        self.assertEqual(json.loads(text)["services"]["model"], "configured")


class AnswerAndLessonChecks(unittest.TestCase):
    def test_answer_mode_request_returns_x_equals_six(self):
        calls = []
        app, _, _ = make_app(
            config=make_config(mode="answer", delivery="full"),
            math_runner=solve_runner(calls),
        )
        thread_id = new_thread_id()
        with TestClient(app) as client_:
            response = client_.post(
                "/api/chat/turn",
                json={"thread_id": thread_id, "message": "2x+5=17", "action": "new_lesson", "mode": "answer"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["mode"], "answer")
        self.assertEqual(body["segments"], [{"kind": "answer", "text": "x=6"}])
        self.assertEqual(body["blocks"], [])
        self.assertIsNone(body["interrupt"])
        self.assertFalse(body["lesson"]["awaiting_user"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].operation, "solve")

    def test_learn_mode_step_lesson_next_resume_and_done(self):
        retrieval = client()
        model = FakeModelClient([plan()])
        app, _, _ = make_app(model=model, retrieval=retrieval)
        thread_id = new_thread_id()
        with TestClient(app) as client_:
            first = client_.post(
                "/api/chat/turn",
                json={"thread_id": thread_id, "message": "Explain derivatives", "action": "new_lesson"},
            ).json()
            self.assertEqual(first["status"], "ok")
            self.assertEqual(first["mode"], "learn")
            self.assertEqual(first["delivery"], "step")
            self.assertTrue(first["lesson"]["awaiting_user"])
            self.assertTrue(first["lesson"]["can_continue"])
            self.assertEqual(first["lesson"]["step_index"], 0)
            self.assertEqual(first["lesson"]["total_steps"], 4)
            self.assertEqual(first["interrupt"]["kind"], "lesson")
            self.assertTrue(first["interrupt"]["prompt"])
            self.assertEqual(len(first["segments"]), 1)
            self.assertEqual(first["segments"][0]["kind"], "text")

            second = client_.post(
                "/api/chat/resume",
                json={"thread_id": thread_id, "action": "next"},
            ).json()
            self.assertEqual(second["status"], "ok")
            self.assertEqual(second["lesson"]["step_index"], 1)
            self.assertTrue(second["lesson"]["awaiting_user"])

            third = client_.post(
                "/api/chat/resume",
                json={"thread_id": thread_id, "action": "done"},
            ).json()
            self.assertEqual(third["status"], "ok")
            self.assertIsNone(third["interrupt"])
            self.assertFalse(third["lesson"]["awaiting_user"])
        # The plan is cached: one planning call and no repeated retrieval.
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(len(retrieval.calls), 3)

    def test_threads_are_isolated_from_each_other(self):
        model = FakeModelClient([plan(), plan()])
        app, service, _ = make_app(model=model, retrieval=client())
        first_id, second_id = new_thread_id(), new_thread_id()
        with TestClient(app) as client_:
            client_.post("/api/chat/turn", json={"thread_id": first_id, "message": "Explain derivatives"})
            client_.post("/api/chat/turn", json={"thread_id": second_id, "message": "Explain derivatives"})
            advanced = client_.post("/api/chat/resume", json={"thread_id": first_id, "action": "next"}).json()
            untouched = client_.post("/api/chat/resume", json={"thread_id": second_id, "action": "next"}).json()
        self.assertEqual(advanced["lesson"]["step_index"], 1)
        self.assertEqual(untouched["lesson"]["step_index"], 1)
        self.assertTrue(service.registry.known(first_id))
        self.assertTrue(service.registry.known(second_id))
        self.assertEqual(service.registry.stats()["known_threads"], 2)

    def test_resume_on_an_unknown_thread_is_a_status_not_an_error(self):
        app, service, _ = make_app(model=FakeModelClient([plan()]), retrieval=client())
        unknown = new_thread_id()
        with TestClient(app) as client_:
            for action in ["next", "full", "done"]:
                response = client_.post("/api/chat/resume", json={"thread_id": unknown, "action": action})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "thread_not_found")
                self.assertEqual(response.json()["thread_id"], unknown)
                self.assertEqual(response.json()["segments"], [])
                self.assertIsNone(response.json()["lesson"])
            followup = client_.post(
                "/api/chat/resume",
                json={"thread_id": unknown, "action": "followup", "message": "why?"},
            )
            self.assertEqual(followup.json()["status"], "thread_not_found")
        # A rejected resume must never create the thread.
        self.assertFalse(service.registry.known(unknown))

    def test_restart_mid_lesson_yields_thread_not_found_and_a_fresh_lesson_still_works(self):
        thread_id = new_thread_id()
        first_app, _, _ = make_app(model=FakeModelClient([plan()]), retrieval=client())
        with TestClient(first_app) as client_:
            started = client_.post(
                "/api/chat/turn",
                json={"thread_id": thread_id, "message": "Explain derivatives"},
            ).json()
            self.assertTrue(started["lesson"]["awaiting_user"])

        # A restart discards both the registry and the in-memory checkpoints.
        second_app, _, _ = make_app(model=FakeModelClient([plan()]), retrieval=client())
        with TestClient(second_app) as client_:
            resumed = client_.post("/api/chat/resume", json={"thread_id": thread_id, "action": "next"})
            self.assertEqual(resumed.status_code, 200)
            self.assertEqual(resumed.json()["status"], "thread_not_found")
            # The client then starts a fresh lesson from the saved transcript.
            fresh_id = new_thread_id()
            fresh = client_.post(
                "/api/chat/turn",
                json={"thread_id": fresh_id, "message": "Explain derivatives"},
            ).json()
            self.assertEqual(fresh["status"], "ok")
            self.assertEqual(fresh["lesson"]["step_index"], 0)
            self.assertTrue(fresh["lesson"]["awaiting_user"])

    def test_ui_event_is_rejected_until_phase_w7(self):
        app, _, _ = make_app(model=FakeModelClient([plan()]), retrieval=client())
        with TestClient(app) as client_:
            response = client_.post("/api/chat/turn", json={"thread_id": new_thread_id(), "action": "ui_event"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "bad_request")
        self.assertIn("W7", response.json()["error"]["detail"])


class ErrorMappingChecks(unittest.TestCase):
    def test_invalid_request_fields_are_named_without_echoing_values(self):
        app, _, _ = make_app()
        with TestClient(app) as client_:
            response = client_.post(
                "/api/chat/turn",
                json={"thread_id": "not-a-thread", "message": "hi", "secret_extra": "private-value"},
            )
        self.assertEqual(response.status_code, 400)
        body = response.json()["error"]
        self.assertEqual(body["code"], "bad_request")
        self.assertNotIn("private-value", json.dumps(body))

    def test_oversized_body_is_rejected_before_the_handler(self):
        app, _, _ = make_app()
        with TestClient(app) as client_:
            response = client_.post(
                "/api/chat/turn",
                json={"thread_id": new_thread_id(), "message": "x" * 300_000},
            )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"], "payload_too_large")

    def test_internal_failure_never_leaks_the_exception_message(self):
        config = make_config(mode="answer", delivery="full")
        service = TutorService(
            config=config,
            graph=StubGraph(error=RuntimeError("private-fixture-key leaked here")),
            registry=ThreadRegistry(),
        )
        app = create_app(service=service, config=config, credentials=agent.Credentials())
        with TestClient(app, raise_server_exceptions=False) as client_:
            response = client_.post(
                "/api/chat/turn",
                json={"thread_id": new_thread_id(), "message": "2x+5=17", "action": "new_lesson"},
            )
        self.assertEqual(response.status_code, 500)
        body = response.json()["error"]
        self.assertEqual(body["code"], "internal_error")
        self.assertNotIn("private-fixture-key", json.dumps(body))
        self.assertNotIn("Traceback", json.dumps(body))

    def test_cors_is_limited_to_the_configured_frontend_origin(self):
        app, _, _ = make_app()
        with TestClient(app) as client_:
            allowed = client_.options(
                "/api/chat/turn",
                headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
            )
            blocked = client_.options(
                "/api/chat/turn",
                headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
            )
        self.assertEqual(allowed.headers.get("access-control-allow-origin"), "http://localhost:3000")
        self.assertNotIn("access-control-allow-origin", blocked.headers)

    def test_oversized_body_still_carries_cors_headers(self):
        app, _, _ = make_app()
        with TestClient(app) as client_:
            response = client_.post(
                "/api/chat/turn",
                headers={"Origin": "http://localhost:3000"},
                json={"thread_id": new_thread_id(), "message": "x" * 300_000},
            )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:3000")


class ProfileAndSettingsChecks(unittest.TestCase):
    def test_profile_is_validated_accepted_and_never_persisted(self):
        app, service, _ = make_app(
            config=make_config(mode="answer", delivery="full"),
            math_runner=solve_runner([]),
        )
        profile = {
            "version": 1,
            "topics": {"algebra": {"level": "intermediate", "level_source": "manual", "unknown": "ignored"}},
            "recent_topics": ["algebra"],
        }
        with TestClient(app) as client_:
            response = client_.post(
                "/api/chat/turn",
                json={
                    "thread_id": new_thread_id(),
                    "message": "2x+5=17",
                    "action": "new_lesson",
                    "mode": "answer",
                    "learner_profile": profile,
                },
            ).json()
        self.assertEqual(response["profile_status"], "accepted")
        # The service holds no profile attribute at all.
        self.assertFalse(any("profile" in name for name in vars(service)))

    def test_an_unusable_profile_is_dropped_without_failing_the_turn(self):
        app, _, _ = make_app(config=make_config(mode="answer", delivery="full"), math_runner=solve_runner([]))
        for bad in [
            {"version": 1, "topics": {"algebra": {"level": "expert"}}},
            {"version": 1, "topics": {f"topic-{index}": {"level": "beginner"} for index in range(60)}},
            {"version": 1, "recent_topics": [f"topic-{index}" for index in range(40)]},
        ]:
            with TestClient(app) as client_:
                response = client_.post(
                    "/api/chat/turn",
                    json={
                        "thread_id": new_thread_id(),
                        "message": "2x+5=17",
                        "action": "new_lesson",
                        "mode": "answer",
                        "learner_profile": bad,
                    },
                )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ok")
            self.assertEqual(response.json()["profile_status"], "rejected")

    def test_profile_model_bounds_and_unknown_field_tolerance(self):
        profile = LearnerProfile.model_validate(
            {"version": 1, "topics": {"algebra": {"level": "beginner", "extra": 1}}, "unknown": True}
        )
        self.assertEqual(profile.topics["algebra"].level, "beginner")
        with self.assertRaises(ValidationError):
            LearnerProfile.model_validate({"version": 1, "topics": {f"t{index}": {"level": "beginner"} for index in range(60)}})
        with self.assertRaises(ValidationError):
            LearnerProfile.model_validate({"version": 1, "topics": {"a": {"level": "beginner", "confusion_spots": [
                {"concept": "c"} for _ in range(11)
            ]}}})

    def test_server_settings_refuse_a_non_loopback_bind_by_default(self):
        with self.assertRaises(ValidationError):
            ServerSettings(host="0.0.0.0")
        self.assertEqual(ServerSettings(host="0.0.0.0", allow_nonlocal_bind=True).host, "0.0.0.0")
        self.assertEqual(ServerSettings().host, "127.0.0.1")
        with self.assertRaises(ServerSettingsError):
            ServerSettings.from_env({"TUTOR_WEB_PORT": "not-a-port"})
        parsed = ServerSettings.from_env(
            {"TUTOR_WEB_PORT": "9000", "TUTOR_WEB_OFFLINE": "true", "TUTOR_WEB_FRONTEND_ORIGINS": "http://localhost:5173"}
        )
        self.assertEqual(parsed.port, 9000)
        self.assertTrue(parsed.offline)
        self.assertEqual(parsed.frontend_origins, ("http://localhost:5173",))

    def test_thread_ids_are_validated_and_normalized(self):
        thread_id = new_thread_id()
        self.assertTrue(valid_thread_id(thread_id))
        self.assertEqual(ChatTurnRequest(thread_id=thread_id.lower(), message="hi").thread_id, thread_id)
        for bad in ["thr_" + "0" * 25, "thr_" + "0" * 27, "nope", "thr_" + "U" * 26]:
            with self.assertRaises(ValidationError):
                ChatTurnRequest(thread_id=bad, message="hi")


class ThreadRegistryChecks(unittest.TestCase):
    def test_idle_threads_are_evicted_and_active_threads_are_not(self):
        now = [1000.0]
        registry = ThreadRegistry(max_threads=10, idle_seconds=60.0, clock=lambda: now[0])
        idle_id, active_id = new_thread_id(), new_thread_id()
        registry.register(idle_id)
        registry.begin_turn(active_id)
        now[0] += 120.0
        evicted = registry.evict_idle()
        self.assertEqual(evicted, [idle_id])
        self.assertFalse(registry.known(idle_id))
        self.assertTrue(registry.known(active_id))
        self.assertEqual(registry.get(active_id).active, True)

    def test_registry_enforces_the_size_bound_without_evicting_active_threads(self):
        now = [0.0]
        registry = ThreadRegistry(max_threads=3, idle_seconds=10_000.0, clock=lambda: now[0])
        active_id = new_thread_id()
        registry.begin_turn(active_id)
        for _ in range(5):
            now[0] += 1.0
            registry.register(new_thread_id())
        evicted = registry.evict_idle()
        self.assertLessEqual(registry.stats()["known_threads"], 3)
        self.assertTrue(registry.known(active_id))
        self.assertTrue(evicted)

    def test_begin_turn_reports_a_second_concurrent_turn(self):
        registry = ThreadRegistry()
        thread_id = new_thread_id()
        self.assertIsNotNone(registry.begin_turn(thread_id))
        self.assertIsNone(registry.begin_turn(thread_id))
        registry.end_turn(thread_id, awaiting_user=True)
        self.assertIsNotNone(registry.begin_turn(thread_id))
        self.assertTrue(registry.get(thread_id).awaiting_user)


class ServiceConcurrencyChecks(unittest.IsolatedAsyncioTestCase):
    async def test_a_second_concurrent_turn_on_one_thread_is_rejected(self):
        config = make_config(mode="answer", delivery="full")
        graph = StubGraph(delay=0.05)
        service = TutorService(config=config, graph=graph, registry=ThreadRegistry())
        thread_id = new_thread_id()
        first = asyncio.create_task(
            service.turn(ChatTurnRequest(thread_id=thread_id, message="2x+5=17", action="new_lesson", mode="answer"))
        )
        await asyncio.sleep(0.01)
        with self.assertRaises(ApiError) as caught:
            await service.turn(ChatTurnRequest(thread_id=thread_id, action="next"))
        self.assertEqual(caught.exception.code, ErrorCode.TURN_IN_PROGRESS)
        result = await first
        self.assertEqual(result.status, "ok")
        self.assertFalse(service.registry.get(thread_id).active)

    async def test_a_turn_that_exceeds_its_deadline_is_reported_safely(self):
        config = make_config(mode="answer", delivery="full")
        service = TutorService(
            config=config,
            graph=StubGraph(delay=5.0),
            registry=ThreadRegistry(),
            turn_timeout_seconds=0.05,
        )
        thread_id = new_thread_id()
        with self.assertRaises(ApiError) as caught:
            await service.turn(ChatTurnRequest(thread_id=thread_id, message="2x+5=17", action="new_lesson", mode="answer"))
        self.assertEqual(caught.exception.code, ErrorCode.TURN_TIMEOUT)
        self.assertEqual(caught.exception.http_status, 504)
        # The thread must not be left marked active after a timeout.
        self.assertFalse(service.registry.get(thread_id).active)

    async def test_sweep_removes_the_thread_and_its_checkpoint(self):
        config = make_config()
        graph = agent.build_graph(config, FakeModelClient([plan()]), retrieval_client=client())
        now = [0.0]
        registry = ThreadRegistry(max_threads=8, idle_seconds=10.0, clock=lambda: now[0])
        service = TutorService(config=config, graph=graph, registry=registry)
        thread_id = new_thread_id()
        await service.turn(ChatTurnRequest(thread_id=thread_id, message="Explain derivatives", action="new_lesson"))
        self.assertIsNotNone(graph.get_state({"configurable": {"thread_id": thread_id}}).values)
        now[0] += 60.0
        evicted = service.sweep()
        self.assertEqual(evicted, [thread_id])
        self.assertFalse(registry.known(thread_id))
        self.assertEqual(graph.get_state({"configurable": {"thread_id": thread_id}}).values, {})

    async def test_build_service_wraps_an_injected_graph(self):
        config = make_config()
        graph = StubGraph()
        service = build_service(
            settings=ServerSettings(offline=True),
            config=config,
            credentials=agent.Credentials(),
            graph=graph,
        )
        self.assertIs(service.graph, graph)
        self.assertEqual(service.turn_timeout_seconds, 120.0)


class TopicKindChecks(unittest.TestCase):
    def test_core_topics_come_from_prepared_notes_and_everything_else_is_open(self):
        _, service, _ = make_app()
        self.assertEqual(service.topic_kind("derivative"), "core")
        self.assertEqual(service.topic_kind("limits"), "core")
        # Phase W3 promoted logarithms into the curated core list.
        self.assertEqual(service.topic_kind("logarithms"), "core")
        self.assertEqual(service.topic_kind(None), "open")

    def test_answer_mode_reports_the_topic_kind_in_the_response(self):
        app, _, _ = make_app(config=make_config(mode="answer", delivery="full"), math_runner=solve_runner([]))
        with TestClient(app) as client_:
            body = client_.post(
                "/api/chat/turn",
                json={"thread_id": new_thread_id(), "message": "2x+5=17", "action": "new_lesson", "mode": "answer"},
            ).json()
        self.assertIn(body["topic_kind"], {"core", "open"})
        self.assertEqual(body["topic"], "mathematics")
        self.assertEqual(body["topic_kind"], "open")


if __name__ == "__main__":
    unittest.main()
