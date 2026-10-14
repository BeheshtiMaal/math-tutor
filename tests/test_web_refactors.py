"""Phase W2 acceptance: core refactors that remove CLI-era assumptions.

The real compiled graph is used throughout; only the external model, search and
retrieval services are replaced, exactly as the earlier phases do.
"""
import asyncio
import json
import os
import re
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from langgraph.types import Command
from pydantic import ValidationError

import agent
from fakes import FakeModelClient
from test_learning_graph import client
from test_step_teaching import plan
from webapp.main import create_app
from webapp.service import TutorService
from webapp.threads import ThreadRegistry, new_thread_id

PERSIAN = re.compile(r"[\u0600-\u06FF]")


def setUpModule():
    global tracing_env
    tracing_env = patch.dict(
        os.environ,
        {"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false", "LANGCHAIN_TRACING": "false"},
    )
    tracing_env.start()


def tearDownModule():
    tracing_env.stop()


def persian_plan():
    return {"steps": [
        {"objective": "فهم قاعده", "explanation": "توان n یک عدد صحیح مثبت است. قاعده توان، x را به آن توان مشتق می‌گیرد.", "source_ids": ["power-rule"]},
        {"objective": "به‌کارگیری روش", "kind": "method", "explanation": "در توان ضرب کن. توان را یکی کم کن تا n*x^(n-1) به دست آید.", "source_ids": ["power-rule"]},
        {"objective": "حفظ فرض‌ها", "kind": "check", "explanation": "این یادداشت قاعده را برای n صحیح مثبت بیان می‌کند. این فرض را نگه دار.", "source_ids": ["power-rule"]},
    ]}


def full_draft(explanation="The derivative measures an instantaneous rate of change.", **changes):
    draft = {"explanation": explanation, "source_ids": ["power-rule"]}
    draft.update(changes)
    return draft


def config_for(*, mode="learn", delivery="step", language=None, level=None, limits=None):
    return agent.AppConfig(
        limits=limits or agent.Limits(math_timeout_seconds=30.0, request_timeout_seconds=60.0),
        preferences=agent.Preferences(mode=mode, delivery_mode=delivery, language=language, learner_level=level),
    )


def make_app(*, config=None, model=None, retrieval=None, math_runner=None, channel="web"):
    config = config or config_for()
    options = {"channel": channel}
    if math_runner is not None:
        options["math_runner"] = math_runner
    if retrieval is not None:
        options["retrieval_client"] = retrieval
    graph = agent.build_graph(config, model, **options)
    service = TutorService(config=config, graph=graph, registry=ThreadRegistry())
    app = create_app(service=service, config=config, credentials=agent.Credentials())
    return app, service, graph


def latex_runner(record):
    def runner(problem, limits):
        record.append(problem)
        return agent.MathResult(status="solved", result="x=6", latex="x = 6")
    return runner


class ScriptDetectionChecks(unittest.TestCase):
    def test_dominant_script_wins_and_ambiguity_returns_none(self):
        self.assertEqual(agent.detect_language("مشتق را توضیح بده"), "fa")
        self.assertEqual(agent.detect_language("Explain the derivative rule"), "en")
        # No script-bearing characters, and a lone math variable, are ambiguous.
        self.assertIsNone(agent.detect_language("2x+5=17"))
        self.assertIsNone(agent.detect_language(""))
        self.assertIsNone(agent.detect_language("x"))
        # A near tie is ambiguous rather than a coin flip.
        self.assertIsNone(agent.detect_language("abc مشت"))
        self.assertEqual(agent.detect_language("مشتق derivative"), "en")

    def test_persian_digits_are_normalised_only_inside_math(self):
        self.assertEqual(agent.latinize_math_digits("مقدار $x=۱۲$ است"), "مقدار $x=12$ است")
        self.assertEqual(agent.latinize_math_digits("$$y=۳۴$$"), "$$y=34$$")
        # Chrome keeps Persian digits; only math regions are rewritten.
        self.assertEqual(agent.latinize_math_digits("مرحله ۱۲ از ۲۰"), "مرحله ۱۲ از ۲۰")


class PerMessageLanguageChecks(unittest.IsolatedAsyncioTestCase):
    def state(self, query, config, **changes):
        return agent.new_request_state(agent.Request(query=query, mode="learn", delivery_mode="step", **changes), config)

    async def run_lesson(self, graph, thread, query, config, **changes):
        result = await graph.ainvoke(self.state(query, config, **changes), thread)
        await graph.ainvoke(Command(resume="done"), thread)
        return result

    async def test_two_languages_in_one_thread_resolve_independently(self):
        config = config_for()
        graph = agent.build_graph(config, FakeModelClient([persian_plan(), plan()]), retrieval_client=client())
        thread = {"configurable": {"thread_id": "w2-language"}}
        first = await self.run_lesson(graph, thread, "مشتق را توضیح بده", config)
        self.assertEqual(first["language"], "fa")
        self.assertEqual(first["language_source"], "detected")
        self.assertTrue(PERSIAN.search(first["explanation"]))
        second = await self.run_lesson(graph, thread, "Explain derivatives", config)
        self.assertEqual(second["language"], "en")
        self.assertEqual(second["language_source"], "detected")
        self.assertTrue(second["explanation"].startswith("Step 1/"))

    async def test_ambiguous_message_falls_back_to_the_previous_language_then_fa(self):
        config = config_for()
        graph = agent.build_graph(config, FakeModelClient([persian_plan(), plan()]), retrieval_client=client())
        thread = {"configurable": {"thread_id": "w2-fallback"}}
        # A fresh thread with no previous message falls back to fa.
        fresh = await graph.ainvoke(self.state("2x+5=17", config), {"configurable": {"thread_id": "w2-fresh"}})
        self.assertEqual(fresh["language"], "fa")
        await self.run_lesson(graph, thread, "Explain derivatives", config)
        # The next ambiguous message inherits the thread's previous language.
        inherited = await graph.ainvoke(self.state("2x+5=17", config), thread)
        self.assertEqual(inherited["language"], "en")
        self.assertEqual(inherited["language_source"], "detected")

    async def test_session_override_wins_over_detection(self):
        config = config_for(language="fa")
        graph = agent.build_graph(config, FakeModelClient([persian_plan()]), retrieval_client=client())
        result = await graph.ainvoke(self.state("Explain derivatives", config), {"configurable": {"thread_id": "w2-override"}})
        self.assertEqual(result["language"], "fa")
        self.assertEqual(result["language_source"], "override")

    async def test_followup_question_switches_language_mid_lesson(self):
        config = config_for()
        graph = agent.build_graph(config, FakeModelClient([persian_plan()]), retrieval_client=client())
        thread = {"configurable": {"thread_id": "w2-followup"}}
        first = await graph.ainvoke(self.state("مشتق را توضیح بده", config), thread)
        self.assertEqual(first["language"], "fa")
        switched = await graph.ainvoke(Command(resume="Why does this rule hold?"), thread)
        self.assertEqual(switched["language"], "en")
        self.assertEqual(switched["language_source"], "detected")
        # The session override still wins on a resumed turn.
        overridden = agent.build_graph(config_for(language="fa"), FakeModelClient([persian_plan()]), retrieval_client=client())
        over_thread = {"configurable": {"thread_id": "w2-followup-override"}}
        await overridden.ainvoke(self.state("مشتق را توضیح بده", config_for(language="fa")), over_thread)
        still_fa = await overridden.ainvoke(Command(resume="Why does this rule hold?"), over_thread)
        self.assertEqual(still_fa["language"], "fa")
        self.assertEqual(still_fa["language_source"], "override")


class TopicKindChecks(unittest.TestCase):
    def test_core_topics_are_the_ones_with_prepared_notes(self):
        core = agent.load_core_topics(agent.PROJECT_ROOT / "sources")
        self.assertIn("derivative", core)
        self.assertIn("مشتق", core)
        self.assertNotIn("topology", core)
        self.assertEqual(agent.topic_kind_of("derivative", core), "core")
        self.assertEqual(agent.topic_kind_of("Topology", core), "open")
        self.assertEqual(agent.topic_kind_of(None, core), "open")

    def test_a_core_topic_reports_core_and_an_open_topic_reports_open(self):
        config = config_for()
        graph = agent.build_graph(config, FakeModelClient([plan()]), retrieval_client=client())
        core_state = agent.new_request_state(agent.Request(query="Explain derivatives", topic="derivative", mode="learn"), config)
        core = asyncio_run(graph, core_state, "w2-core")
        self.assertEqual(core["topic"], "derivative")
        self.assertEqual(core["topic_kind"], "core")
        open_state = agent.new_request_state(agent.Request(query="Explain topology", topic="topology", mode="learn"), config)
        open_result = asyncio_run(graph, open_state, "w2-open")
        self.assertEqual(open_result["topic"], "topology")
        self.assertEqual(open_result["topic_kind"], "open")
        # Both complete a lesson and reach the waiting interrupt.
        self.assertTrue(core["__interrupt__"])
        self.assertTrue(open_result["__interrupt__"])


def asyncio_run(graph, state, thread_id):
    return asyncio.run(graph.ainvoke(state, {"configurable": {"thread_id": thread_id}}))


class ProfileContractChecks(unittest.TestCase):
    def test_unknown_fields_are_ignored_and_bounds_are_enforced(self):
        profile = agent.LearnerProfile.model_validate({
            "version": 1,
            "topics": {"derivative": {"level": "advanced", "level_source": "manual", "colour": "ignored"}},
            "recent_topics": ["derivative"],
            "updated_at": "2026-10-13T11:20:00Z",
            "future_field": "ignored",
        })
        self.assertEqual(profile.level_for("derivative"), "advanced")
        self.assertIsNone(profile.level_for("integral"))

    def test_oversized_and_malformed_profiles_are_rejected(self):
        with self.assertRaises(ValidationError):
            agent.LearnerProfile.model_validate({"topics": {f"topic-{index}": {"level": "beginner"} for index in range(51)}})
        with self.assertRaises(ValidationError):
            agent.LearnerProfile.model_validate({"topics": {"derivative": {"level": "expert"}}})
        with self.assertRaises(ValidationError):
            agent.LearnerProfile.model_validate({"topics": {"derivative": {"level": "beginner", "confusion_spots": [{"concept": "c"}] * 11}}})
        with self.assertRaises(ValidationError):
            agent.LearnerProfile.model_validate({"recent_topics": ["t" * 121]})
        with self.assertRaises(ValidationError):
            agent.LearnerProfile.model_validate({"topics": {f"t{index}": {"level": "beginner", "confusion_spots": [{"concept": "x" * 120}] * 10} for index in range(50)}})

    def test_a_future_timestamp_is_clamped_rather_than_rejected(self):
        from datetime import datetime, timedelta, timezone

        future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        profile = agent.LearnerProfile.model_validate({"updated_at": future})
        self.assertLess(profile.updated_at, datetime.now(timezone.utc) + timedelta(minutes=1))

    def test_profile_level_applies_only_when_no_session_level_is_set(self):
        profile = agent.LearnerProfile.model_validate({"topics": {"derivative": {"level": "advanced", "level_source": "manual"}}})
        self.assertEqual(profile.level_for("derivative"), "advanced")
        # An inferred stored level is a suggestion, not a manual setting.
        inferred = agent.LearnerProfile.model_validate({"topics": {"derivative": {"level": "advanced", "level_source": "inferred"}}})
        self.assertIsNone(inferred.level_for("derivative"))


class ProfileInGraphChecks(unittest.IsolatedAsyncioTestCase):
    async def test_profile_reaches_the_state_and_sets_the_level_without_a_session_level(self):
        config = config_for(level=None)
        profile = agent.LearnerProfile.model_validate({"topics": {"derivative": {"level": "advanced", "level_source": "manual"}}})
        graph = agent.build_graph(config, FakeModelClient([plan()]), retrieval_client=client())
        state = agent.new_request_state(agent.Request(query="Explain derivatives", topic="derivative", mode="learn", learner_profile=profile), config)
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "w2-profile"}})
        self.assertEqual(result["learner_level"], "advanced")
        self.assertEqual(result["level_source"], "manual")
        self.assertIsInstance(result["learner_profile"], agent.LearnerProfile)

    async def test_session_level_wins_over_the_stored_profile_level(self):
        config = config_for(level="beginner")
        profile = agent.LearnerProfile.model_validate({"topics": {"derivative": {"level": "advanced", "level_source": "manual"}}})
        graph = agent.build_graph(config, FakeModelClient([plan()]), retrieval_client=client())
        state = agent.new_request_state(agent.Request(query="Explain derivatives", topic="derivative", mode="learn", learner_profile=profile), config)
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "w2-profile-precedence"}})
        self.assertEqual(result["learner_level"], "beginner")
        self.assertEqual(result["level_source"], "manual")

    async def test_default_level_is_reported_as_default(self):
        config = config_for(level=None)
        graph = agent.build_graph(config, FakeModelClient([plan()]), retrieval_client=client())
        state = agent.new_request_state(agent.Request(query="Explain derivatives", topic="derivative", mode="learn"), config)
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "w2-profile-default"}})
        self.assertEqual(result["learner_level"], "beginner")
        self.assertEqual(result["level_source"], "default")


class WriterSchemaChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.retrieval = client()

    async def run_full(self, responses, *, channel="web", thread="w2-writer"):
        config = config_for(delivery="full")
        graph = agent.build_graph(config, FakeModelClient(responses), retrieval_client=self.retrieval, channel=channel)
        state = agent.new_request_state(agent.Request(query="Explain derivatives", topic="derivative", mode="learn", language="en"), config)
        return await graph.ainvoke(state, {"configurable": {"thread_id": thread}})

    async def test_typed_output_separates_segments_from_blocks(self):
        result = await self.run_full([full_draft()], thread="w2-typed")
        self.assertIn("explanation", result)
        self.assertIn("explanation_segments", result)
        self.assertIn("block_requests", result)
        self.assertIn("ui_blocks", result)
        self.assertTrue(all(isinstance(item, agent.TextSegment) for item in result["explanation_segments"]))
        self.assertEqual(result["ui_blocks"], [])
        # Text and blocks are never merged into one field.
        self.assertNotIn("block_requests", result["explanation"])

    async def test_a_valid_block_request_is_validated_and_emitted_in_w5(self):
        request = {"type": "function_graph", "title": "Power rule", "params": {
            "expressions": [{"label": "y", "expression": "x^2"}],
            "domain": {"min": -2, "max": 2}, "sample_count": 50}, "fallback_text": "A graph of x squared."}
        result = await self.run_full([full_draft(block_requests=[request])], thread="w2-block-valid")
        self.assertEqual(len(result["block_requests"]), 1)
        self.assertIsInstance(result["block_requests"][0], agent.BlockRequest)
        self.assertEqual(len(result["ui_blocks"]), 1)
        self.assertEqual(result["ui_blocks"][0]["data_source"], "sympy_graph_sampler")
        self.assertIn("A graph of x squared.", result["explanation"])

    async def test_a_malformed_block_request_is_dropped_and_the_text_survives(self):
        bad = {"type": "hologram", "title": "Nope", "fallback_text": "x"}
        result = await self.run_full([full_draft(block_requests=[bad])], thread="w2-block-bad")
        self.assertEqual(result["block_requests"], [])
        self.assertTrue(result["explanation"].strip())
        self.assertTrue(any("dropped" in warning for warning in result["warnings"]))

    async def test_too_many_block_requests_are_repaired_not_accepted(self):
        from learning import LessonDraft

        request = {"type": "function_graph", "title": "T", "fallback_text": "F"}
        # At most two blocks per reply (spec section 9.1); a third fails the
        # schema, which routes the draft through the writer repair loop.
        with self.assertRaises(ValidationError):
            LessonDraft.model_validate({"explanation": "Two sentences here. And another.", "source_ids": ["power-rule"],
                                        "block_requests": [request, request, request]})
        accepted = LessonDraft.model_validate({"explanation": "Two sentences here. And another.", "source_ids": ["power-rule"],
                                               "block_requests": [request, request]})
        self.assertEqual(len(accepted.block_requests), 2)

    async def test_malformed_text_is_repaired_through_the_writer_loop(self):
        # First attempt cites an unknown source; the repair message then yields a
        # valid draft. The loop, not the caller, performs the repair.
        result = await self.run_full([
            {"explanation": "A first attempt.", "source_ids": ["not-a-source"]},
            full_draft("The derivative measures an instantaneous rate of change."),
        ], thread="w2-repair")
        self.assertIn("instantaneous rate of change", result["explanation"])
        self.assertNotIn("A first attempt.", result["explanation"])

    async def test_answer_mode_never_requests_a_block(self):
        config = config_for(mode="answer", delivery="full")
        calls = []
        graph = agent.build_graph(config, FakeModelClient([]), retrieval_client=self.retrieval, channel="web", math_runner=latex_runner(calls))
        state = agent.new_request_state(agent.Request(query="2x+5=17", mode="answer", language="en"), config)
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "w2-answer-blocks"}})
        self.assertEqual(result["block_requests"], [])
        self.assertEqual(result["ui_blocks"], [])
        self.assertEqual(len(result["explanation_segments"]), 1)
        self.assertEqual(result["explanation_segments"][0].kind, "answer")


class ChannelNotationChecks(unittest.IsolatedAsyncioTestCase):
    async def run_answer(self, channel):
        config = config_for(mode="answer", delivery="full")
        calls = []
        graph = agent.build_graph(config, None, channel=channel, math_runner=latex_runner(calls))
        state = agent.new_request_state(agent.Request(query="2x+5=17", mode="answer", language="en"), config)
        return await graph.ainvoke(state, {"configurable": {"thread_id": f"w2-notation-{channel}"}})

    async def test_web_channel_renders_sympy_latex_and_cli_keeps_plain_text(self):
        web = await self.run_answer("web")
        self.assertEqual(web["final_answer"], "$$x = 6$$")
        self.assertEqual(web["explanation_segments"][0].text, "$$x = 6$$")
        cli = await self.run_answer("cli")
        self.assertEqual(cli["final_answer"], "x=6")

    async def test_web_channel_without_sympy_latex_falls_back_to_plain_text(self):
        config = config_for(mode="answer", delivery="full")

        def plain_runner(problem, limits):
            return agent.MathResult(status="solved", result="x=6")

        graph = agent.build_graph(config, None, channel="web", math_runner=plain_runner)
        state = agent.new_request_state(agent.Request(query="2x+5=17", mode="answer", language="en"), config)
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "w2-notation-plain"}})
        self.assertEqual(result["final_answer"], "x=6")

    def test_the_writer_prompt_asks_for_the_channel_notation(self):
        from learning import notation_rule

        self.assertIn("$", notation_rule("web"))
        self.assertIn("LaTeX", notation_rule("web"))
        self.assertIn("plain-text", notation_rule("cli"))
        self.assertNotIn("LaTeX commands or Unicode math symbols. Never", notation_rule("web"))

    async def test_step_segments_drop_the_ui_chrome_header(self):
        config = config_for()
        graph = agent.build_graph(config, FakeModelClient([plan()]), retrieval_client=client(), channel="web")
        state = agent.new_request_state(agent.Request(query="Explain derivatives", topic="derivative", mode="learn", delivery_mode="step", language="en"), config)
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "w2-chrome"}})
        # explanation keeps the CLI header; the web segments do not carry chrome.
        self.assertTrue(result["explanation"].startswith("Step 1/"))
        self.assertFalse(any(segment.text.startswith("Step ") for segment in result["explanation_segments"]))
        self.assertTrue(result["explanation_segments"])


class WebSurfaceChecks(unittest.TestCase):
    def test_language_and_topic_metadata_reach_the_http_response(self):
        app, _, _ = make_app(model=FakeModelClient([plan()]), retrieval=client())
        with TestClient(app) as http:
            body = http.post(
                "/api/chat/turn",
                json={"thread_id": new_thread_id(), "message": "Explain derivatives", "action": "new_lesson", "mode": "learn"},
            ).json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["language"], "en")
        self.assertEqual(body["language_source"], "detected")
        self.assertEqual(body["topic"], "derivative")
        self.assertEqual(body["topic_kind"], "core")
        self.assertEqual(body["blocks"], [])
        self.assertTrue(body["segments"])
        self.assertTrue(all(set(segment) == {"kind", "text"} for segment in body["segments"]))

    def test_a_persian_turn_is_answered_in_persian_through_the_api(self):
        app, _, _ = make_app(model=FakeModelClient([persian_plan()]), retrieval=client())
        with TestClient(app) as http:
            body = http.post(
                "/api/chat/turn",
                json={"thread_id": new_thread_id(), "message": "مشتق را توضیح بده", "action": "new_lesson", "mode": "learn"},
            ).json()
        self.assertEqual(body["language"], "fa")
        self.assertTrue(any(PERSIAN.search(segment["text"]) for segment in body["segments"]))

    def test_an_open_topic_is_labelled_open_and_still_completes_a_lesson(self):
        app, _, _ = make_app(model=FakeModelClient([plan()]), retrieval=client())
        with TestClient(app) as http:
            body = http.post(
                "/api/chat/turn",
                json={"thread_id": new_thread_id(), "message": "Explain topology", "action": "new_lesson", "mode": "learn"},
            ).json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["topic_kind"], "open")
        self.assertIsNotNone(body["lesson"])
        self.assertTrue(body["lesson"]["awaiting_user"])

    def test_an_oversized_profile_is_rejected_but_the_turn_still_succeeds(self):
        app, service, _ = make_app(model=FakeModelClient([plan()]), retrieval=client())
        thread_id = new_thread_id()
        oversized = {"topics": {f"topic-{index}": {"level": "beginner"} for index in range(60)}}
        with TestClient(app) as http:
            body = http.post(
                "/api/chat/turn",
                json={"thread_id": thread_id, "message": "Explain derivatives", "action": "new_lesson",
                      "learner_profile": oversized},
            ).json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["profile_status"], "rejected")
        # The rejected profile is not kept anywhere on the server.
        self.assertFalse(hasattr(service, "learner_profile"))

    def test_a_valid_profile_is_accepted_and_never_echoed_back(self):
        app, _, _ = make_app(model=FakeModelClient([plan()]), retrieval=client())
        profile = {"version": 1, "topics": {"derivative": {"level": "advanced", "level_source": "manual"}}}
        with TestClient(app) as http:
            body = http.post(
                "/api/chat/turn",
                json={"thread_id": new_thread_id(), "message": "Explain derivatives", "action": "new_lesson",
                      "learner_profile": profile},
            ).json()
        self.assertEqual(body["profile_status"], "accepted")
        self.assertEqual(body["learner_level"], "advanced")
        self.assertEqual(body["level_source"], "manual")
        self.assertNotIn("learner_profile", json.dumps(body))

    def test_a_request_language_override_is_reported_as_an_override(self):
        app, _, _ = make_app(model=FakeModelClient([plan()]), retrieval=client())
        with TestClient(app) as http:
            body = http.post(
                "/api/chat/turn",
                json={"thread_id": new_thread_id(), "message": "Explain derivatives", "action": "new_lesson",
                      "language_override": "fa"},
            ).json()
        self.assertEqual(body["language"], "fa")
        self.assertEqual(body["language_source"], "override")


if __name__ == "__main__":
    unittest.main()
