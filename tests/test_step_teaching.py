"""Phase 5 acceptance invokes the actual compiled LangGraph and CLI."""
import asyncio
import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from langgraph.types import Command
import agent
import cli
from lesson_steps import StepDraft, LessonPlanDraft, parse_reply, sentences
from fakes import FakeModelClient, FakeRetrievalClient
from test_learning_graph import client, source, example, evidence


def setUpModule():
    global tracing_env
    tracing_env = patch.dict(os.environ, {"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false", "LANGCHAIN_TRACING": "false"})
    tracing_env.start()


def tearDownModule():
    tracing_env.stop()


def plan():
    return {"steps": [
        {"objective": "Understand the rule", "explanation": "The exponent n is a positive integer. The power rule differentiates x to that exponent.", "source_ids": ["power-rule"]},
        {"objective": "Apply the method", "kind": "method", "explanation": "Multiply by the exponent n. Reduce the exponent by one to obtain n*x^(n-1).", "source_ids": ["power-rule"]},
        {"objective": "Preserve assumptions", "kind": "check", "explanation": "This note states the rule for positive integer n. Keep that assumption when using the rule.", "source_ids": ["power-rule"]},
    ]}


class StepTeachingChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = agent.AppConfig(preferences=agent.Preferences(mode="learn", delivery_mode="step", language="en", learner_level="beginner"))
        self.retrieval = client()

    def state(self, **changes):
        return agent.new_request_state(agent.Request(query="Explain derivatives", **changes), self.config)

    async def start(self, responses=None, **options):
        model = FakeModelClient(responses if responses is not None else [plan()])
        graph = agent.build_graph(self.config, model, retrieval_client=self.retrieval, **options)
        thread = {"configurable": {"thread_id": self.id()}}
        first = await graph.ainvoke(self.state(), thread)
        return graph, thread, model, first

    async def test_first_short_chunk_pauses_no_future_step_or_example(self):
        graph, thread, model, first = await self.start()
        self.assertEqual(first["step_index"], 0)
        self.assertEqual(first["last_emitted_step"], 0)
        self.assertFalse(first["lesson_complete"])
        self.assertEqual(len(first["lesson_plan"]), 4)
        self.assertEqual(len(sentences(first["current_step_explanation"])), 2)
        self.assertIn("Step 1/4", first["explanation"])
        self.assertNotIn("Multiply by the exponent", first["explanation"])
        self.assertNotIn("Example:", first["explanation"])
        self.assertIsNone(first["selected_example_id"])
        self.assertEqual(graph.get_state(thread).next, ("user_input",))
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(len(self.retrieval.calls), 3)
        # Reading the checkpoint never advances or calls the model.
        self.assertEqual(graph.get_state(thread).values["step_index"], 0)
        self.assertEqual(len(model.calls), 1)

    async def test_next_advances_once_cached_plan_and_example_only_at_final_step(self):
        graph, thread, model, first = await self.start()
        saved = [step.model_dump() for step in first["lesson_plan"]]
        for index, reply in enumerate(["next", "بعدی", "اوکی"], 1):
            result = await graph.ainvoke(Command(resume=reply), thread)
            self.assertEqual(result["step_index"], index)
            self.assertEqual(result["last_emitted_step"], index)
            self.assertEqual([step.model_dump() for step in result["lesson_plan"]], saved)
            self.assertEqual(result["explanation_version"], index + 1)
            self.assertTrue(result["__interrupt__"])
            self.assertEqual(result["explanation"].count("Example:"), int(index == 3))
        self.assertTrue(result["lesson_complete"])
        self.assertIn("Verification: unknown", result["explanation"])
        self.assertEqual(len(self.retrieval.calls), 3)
        self.assertEqual(len(model.calls), 1)
        finished = await graph.ainvoke(Command(resume="next"), thread)
        self.assertEqual(finished["step_index"], 3)
        self.assertEqual(finished["last_emitted_step"], 3)
        self.assertIn("lesson is complete", finished["explanation"])
        self.assertNotIn("Example:", finished["explanation"])
        final = await graph.ainvoke(Command(resume="done"), thread)
        self.assertNotIn("__interrupt__", final)
        self.assertEqual(graph.get_state(thread).next, ())

    async def test_confusion_and_question_keep_position_context_then_next_advances(self):
        simplified = {"explanation": "The exponent is the multiplier in this rule. After multiplying, subtract one from the exponent.", "source_ids": ["power-rule"]}
        answer = {"explanation": "Here n denotes the positive integer exponent. This note keeps that assumption for the rule.", "source_ids": ["power-rule"]}
        graph, thread, model, first = await self.start([plan(), simplified, answer])
        second = await graph.ainvoke(Command(resume="next"), thread)
        saved = [step.model_dump() for step in second["lesson_plan"]]
        for reply, expected in [("نفهمیدم", simplified), ("What is n?", answer)]:
            result = await graph.ainvoke(Command(resume=reply), thread)
            self.assertEqual(result["step_index"], 1)
            self.assertEqual(result["last_emitted_step"], 1)
            self.assertEqual(result["current_step_explanation"], expected["explanation"])
            self.assertEqual([step.model_dump() for step in result["lesson_plan"]], saved)
            self.assertNotIn("Example:", result["explanation"])
        self.assertEqual(len(model.calls), 3)
        payload = json.loads(model.calls[2][1][-1].content)
        self.assertEqual(payload["question"], "What is n?")
        self.assertEqual(payload["step_index"], 1)
        self.assertEqual(payload["objective"], first["lesson_objective"])
        self.assertEqual(payload["current_explanation"], simplified["explanation"])
        next_step = await graph.ainvoke(Command(resume="ادامه"), thread)
        self.assertEqual(next_step["step_index"], 2)
        self.assertEqual(len(self.retrieval.calls), 3)

    async def test_full_explains_only_remainder_once_and_does_not_repeat_on_done(self):
        graph, thread, model, first = await self.start()
        await graph.ainvoke(Command(resume="next"), thread)
        full = await graph.ainvoke(Command(resume="کامل بگو"), thread)
        self.assertEqual(full["delivery_mode"], "full")
        self.assertTrue(full["lesson_complete"])
        self.assertEqual(full["step_index"], 3)
        self.assertEqual(full["last_emitted_step"], 3)
        self.assertNotIn(plan()["steps"][0]["explanation"], full["explanation"])
        self.assertNotIn(plan()["steps"][1]["explanation"], full["explanation"])
        self.assertIn(plan()["steps"][2]["explanation"], full["explanation"])
        self.assertEqual(full["explanation"].count("Example:"), 1)
        self.assertEqual(len(model.calls), 1)
        final = await graph.ainvoke(Command(resume="تمام"), thread)
        self.assertEqual(final["explanation_version"], full["explanation_version"])
        self.assertEqual(final["explanation"], full["explanation"])
        self.assertEqual(graph.get_state(thread).next, ())

    async def test_done_early_emits_no_future_material(self):
        graph, thread, model, first = await self.start()
        final = await graph.ainvoke(Command(resume={"action": "done"}), thread)
        self.assertEqual(final["step_index"], 0)
        self.assertEqual(final["explanation_version"], 1)
        self.assertNotIn("Example:", final["explanation"])
        self.assertEqual(len(model.calls), 1)
        self.assertFalse(graph.get_state(thread).next)

    async def test_explicit_example_request_is_one_example_without_advancing(self):
        answer = {"explanation": "Use the stated rule with exponent two. The sourced example below applies this same method.", "source_ids": ["power-rule"]}
        graph, thread, model, first = await self.start([plan(), answer])
        response = await graph.ainvoke(Command(resume="Show me an example"), thread)
        self.assertEqual(response["step_index"], 0)
        self.assertEqual(response["last_emitted_step"], 0)
        self.assertEqual(response["explanation"].count("Example:"), 1)
        first_example = response["selected_example_id"]
        final = await graph.ainvoke(Command(resume="full"), thread)
        self.assertEqual(final["explanation"].count("Example:"), 1)
        self.assertNotEqual(final["selected_example_id"], first_example)

    async def test_persian_step_plan_simplification_and_full_remain_in_persian(self):
        persian_plan = {"steps": [
            {"objective": "شناخت توان", "explanation": "توان n در این یادداشت عدد صحیح مثبت است. قاعده توان مشتق این عبارت را بیان می‌کند.", "source_ids": ["power-rule"]},
            {"objective": "روش", "kind": "method", "explanation": "ضریب را در توان n ضرب کنید. سپس یک واحد از توان کم کنید.", "source_ids": ["power-rule"]},
        ]}
        simple = {"explanation": "ابتدا عدد توان را پیدا کنید. در همین قاعده آن عدد ضریب مشتق می‌شود.", "source_ids": ["power-rule"]}
        model = FakeModelClient([persian_plan, simple])
        graph = agent.build_graph(self.config, model, retrieval_client=self.retrieval)
        thread = {"configurable": {"thread_id": "persian-step"}}
        first = await graph.ainvoke(self.state(language="fa"), thread)
        self.assertIn("مرحله 1 از 3", first["explanation"])
        self.assertIn("«بعدی»", first["__interrupt__"][0].value["prompt"])
        result = await graph.ainvoke(Command(resume="نفهمیدم"), thread)
        self.assertEqual(result["step_index"], 0)
        self.assertEqual(result["current_step_explanation"], simple["explanation"])
        full = await graph.ainvoke(Command(resume="کامل بگو"), thread)
        self.assertIn(persian_plan["steps"][1]["explanation"], full["explanation"])
        self.assertIn("مثال منبع", full["explanation"])
        self.assertEqual(full["delivery_mode"], "full")

    async def test_plan_provider_timeout_is_recoverable_without_advancing(self):
        class SlowModel:
            async def structured(self, messages, schema):
                await asyncio.sleep(1)
        config = self.config.model_copy(update={"limits": agent.Limits(request_timeout_seconds=0.03)})
        graph = agent.build_graph(config, SlowModel(), retrieval_client=self.retrieval)
        thread = {"configurable": {"thread_id": "plan-deadline"}}
        first = await graph.ainvoke(self.state(), thread)
        self.assertTrue(first["__interrupt__"])
        self.assertEqual(first["step_index"], 0)
        self.assertIn("planning failed", first["explanation"])
        self.assertEqual(len(sentences(first["current_step_explanation"])), 2)

    async def test_ambiguous_okay_with_question_is_followup_not_next(self):
        response = {"explanation": "The positive integer n is the exponent. It is the multiplier in the stated rule.", "source_ids": ["power-rule"]}
        graph, thread, model, first = await self.start([plan(), response])
        result = await graph.ainvoke(Command(resume="Okay, but why is n the multiplier?"), thread)
        self.assertEqual(result["step_index"], 0)
        self.assertEqual(result["user_action"], "followup")
        self.assertEqual(len(model.calls), 2)

    async def test_invalid_direct_replies_reinterrupt_without_advancing_or_replaying_model(self):
        graph, thread, model, first = await self.start()
        for reply in ["", {"action": "unknown"}]:
            result = await graph.ainvoke(Command(resume=reply), thread)
            self.assertTrue(result["__interrupt__"])
            self.assertIn("Invalid", result["__interrupt__"][0].value["prompt"])
            self.assertEqual(result["explanation_version"], 1)
            self.assertEqual(result["step_index"], 0)
        final = await graph.ainvoke(Command(resume="done"), thread)
        self.assertFalse(graph.get_state(thread).next)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(len(self.retrieval.calls), 3)

    async def test_invalid_reply_exhaustion_ends_safely(self):
        graph, thread, model, first = await self.start()
        for _ in range(3):
            result = await graph.ainvoke(Command(resume=123), thread)
        self.assertNotIn("__interrupt__", result)
        self.assertIn("invalid replies", result["final_answer"])
        self.assertEqual(result["step_index"], 0)
        self.assertEqual(len(model.calls), 1)

    async def test_malformed_plan_repairs_bounded_and_falls_back_without_secret_leak(self):
        broken = {"steps": [{"objective": "Bad", "explanation": "One sentence only.", "source_ids": ["invented"]}]}
        graph, thread, model, first = await self.start([broken, broken, RuntimeError("private-provider-secret")])
        self.assertEqual(len(model.calls), 3)
        self.assertEqual(first["step_index"], 0)
        self.assertIn("planning failed", first["explanation"])
        self.assertNotIn("private-provider-secret", first["explanation"])
        self.assertNotIn("One sentence only", first["explanation"])
        self.assertEqual(len(sentences(first["current_step_explanation"])), 2)
        self.assertTrue(first["__interrupt__"])

    async def test_step_response_failure_keeps_cached_position(self):
        bad = {"explanation": "A wrong citation. It was invented.", "source_ids": ["missing"]}
        graph, thread, model, first = await self.start([plan(), bad, bad, bad])
        result = await graph.ainvoke(Command(resume="simplify"), thread)
        self.assertEqual(result["step_index"], 0)
        self.assertEqual(result["current_step_explanation"], first["current_step_explanation"])
        self.assertNotIn("wrong citation", result["explanation"])
        self.assertIn("could not be synthesized", result["explanation"])
        self.assertEqual(len(model.calls), 4)

    async def test_example_followup_accepts_its_evidence_id_and_keeps_solution(self):
        response = {"explanation": "The exponent is two in this problem. The solution is twice x.",
                    "source_ids": ["fixture-beginner-1"]}
        graph, thread, model, first = await self.start([plan(), response])
        for _ in range(3):
            final = await graph.ainvoke(Command(resume="next"), thread)
        selected = final["selected_example_id"]
        result = await graph.ainvoke(Command(resume="Why does that solution work?"), thread)
        self.assertEqual(result["selected_example_id"], selected)
        self.assertIn(response["explanation"], result["explanation"])
        self.assertIn(example().statement, result["explanation"])
        self.assertIn(example().solution, result["explanation"])
        self.assertNotIn("could not be synthesized", result["explanation"])
        self.assertEqual(result["step_index"], 3)
        self.assertEqual(len(self.retrieval.calls), 3)

    async def test_failed_example_followup_still_displays_complete_cached_example(self):
        bad = {"explanation": "An invented response. It has no evidence.", "source_ids": ["missing"]}
        graph, thread, model, first = await self.start([plan(), bad, bad, bad])
        for _ in range(3):
            final = await graph.ainvoke(Command(resume="next"), thread)
        result = await graph.ainvoke(Command(resume="Why does that solution work?"), thread)
        self.assertEqual(result["selected_example_id"], final["selected_example_id"])
        self.assertIn(example().statement, result["explanation"])
        self.assertIn(example().solution, result["explanation"])
        self.assertEqual(result["explanation"].count("Example:"), 1)

    async def test_new_equation_at_reply_exits_old_lesson_without_synthesis(self):
        self.retrieval.results["read_source"].records.append(source().model_copy(update={"topic": "algebra"}))
        self.retrieval.results["verified_examples"].records.append(example().model_copy(update={"topic": "algebra"}))
        for initial, question in [("Explain derivatives", "Can you help me with x^2 - 5x + 6 = 0 step-by-step?"),
                                  ("Can you help me with x^2 - 1 = 0 step-by-step?", "Can you help me with x^2 - 5x + 6 = 0 step-by-step?")]:
            model = FakeModelClient([plan()])
            graph = agent.build_graph(self.config, model, retrieval_client=self.retrieval)
            thread = {"configurable": {"thread_id": initial}}
            await graph.ainvoke(agent.new_request_state(agent.Request(query=initial), self.config), thread)
            for _ in range(3):
                await graph.ainvoke(Command(resume="next"), thread)
            result = await graph.ainvoke(Command(resume=question), thread)
            self.assertEqual(result["new_topic_query"], question)
            self.assertFalse(graph.get_state(thread).next)
            self.assertEqual(len(model.calls), 1)

    async def test_cli_new_equation_starts_first_step_with_fresh_objective(self):
        self.retrieval.results["read_source"].records.append(source().model_copy(update={"topic": "algebra"}))
        self.retrieval.results["verified_examples"].records.append(example().model_copy(update={"topic": "algebra"}))
        model = FakeModelClient([plan(), plan()])
        graph = agent.build_graph(self.config, model, retrieval_client=self.retrieval)
        question = "Can you help me with x^2 - 5x + 6 = 0 step-by-step?"
        lines = iter(["Can you help me with x^2 - 1 = 0 step-by-step?", "next", "next", "next", question, "/exit"])
        output = []
        await cli.run_cli(self.config, graph=graph, read=lambda prompt: next(lines), display=output.append)
        headers = [line.splitlines()[0] for line in output if line.startswith("Step ")]
        self.assertEqual(headers, ["Step 1/4", "Step 2/4", "Step 3/4", "Step 4/4", "Step 1/4"])
        self.assertEqual(json.loads(model.calls[-1][1][-1].content)["objective"], question)
        self.assertFalse(any("could not be synthesized" in line for line in output))

    async def test_missing_sources_and_model_are_honest_short_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.config.model_copy(update={"sources_dir": Path(directory)})
            graph = agent.build_graph(config)
            thread = {"configurable": {"thread_id": "missing-step"}}
            first = await graph.ainvoke(self.state(), thread)
            self.assertEqual(len(first["lesson_plan"]), 1)
            self.assertEqual(len(sentences(first["current_step_explanation"])), 2)
            self.assertIn("No valid short source", first["explanation"])
            self.assertTrue(first["lesson_complete"])
            second = await graph.ainvoke(Command(resume="Why?"), thread)
            self.assertEqual(second["step_index"], 0)
            self.assertIn("configured model", second["explanation"])
            self.assertNotIn("Example:", second["explanation"])

    async def test_offline_source_steps_protect_formula_and_only_show_final_example(self):
        note = source().model_copy(update={"text": "Use the formula $x^{2.5}$. Preserve the real-domain assumptions. Read the exponent carefully. Keep the variable fixed."})
        retrieval = FakeRetrievalClient(source=evidence([note]), examples=evidence([example()]))
        graph = agent.build_graph(self.config, retrieval_client=retrieval)
        thread = {"configurable": {"thread_id": "offline-formula"}}
        first = await graph.ainvoke(self.state(), thread)
        self.assertIn("$x^{2.5}$", first["current_step_explanation"])
        self.assertEqual(len(first["lesson_plan"]), 3)
        self.assertNotIn("Example:", first["explanation"])
        simpler = await graph.ainvoke(Command(resume="simplify"), thread)
        self.assertEqual(simpler["step_index"], 0)
        self.assertIn("simplification is unavailable", simpler["explanation"])
        self.assertEqual(simpler["current_step_explanation"], first["current_step_explanation"])


class StepCliChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = agent.AppConfig(preferences=agent.Preferences(language="en"))

    async def test_all_commands_persian_controls_blank_bad_and_full_during_pause(self):
        model = FakeModelClient([plan()])
        retrieval = client()
        graph = agent.build_graph(self.config, model, retrieval_client=retrieval)
        commands = iter(["/mode learn", "/delivery step", "/level مبتدی", "/language en", "/debug on",
            "Explain derivatives", "", "/help", "/level expert", "/delivery nonsense", "/unknown", "بعدی", "/delivery full", "تمام", "/exit"])
        outputs = []
        code = await cli.run_cli(self.config, graph=graph, read=lambda _: next(commands), display=outputs.append)
        self.assertEqual(code, 0)
        lessons = [text for text in outputs if text.startswith("Step ")]
        self.assertEqual(len(lessons), 2)
        self.assertIn("Step 1/4", lessons[0])
        self.assertIn("Step 2/4", lessons[1])
        self.assertEqual(len([text for text in outputs if "Example:" in text]), 1)
        self.assertEqual(outputs.count("[classify: success]"), 1)
        self.assertEqual(outputs.count("[write_explanation: success]"), 3)
        self.assertEqual(outputs.count("Invalid preference. Use /help."), 2)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(len(retrieval.calls), 3)
        self.assertEqual(self.config.preferences.delivery_mode, "full")

    async def test_reset_discards_pending_plan_and_history_new_request_starts_step_zero(self):
        model = FakeModelClient([plan(), plan()])
        retrieval = client()
        self.config.preferences = agent.Preferences(mode="learn", delivery_mode="step", language="en", learner_level="beginner")
        graph = agent.build_graph(self.config, model, retrieval_client=retrieval)
        commands = iter(["Explain derivatives", "next", "/reset", "Explain derivatives", "done", "/exit"])
        outputs = []
        await cli.run_cli(self.config, graph=graph, read=lambda _: next(commands), display=outputs.append)
        lessons = [text.splitlines()[0] for text in outputs if text.startswith("Step ")]
        self.assertEqual(lessons, ["Step 1/4", "Step 2/4", "Step 1/4"])
        self.assertEqual(len(model.calls), 2)
        self.assertEqual(len(retrieval.calls), 6)
        self.assertIn("Session reset.", outputs)

    async def test_delivery_command_during_math_clarification_is_not_a_math_reply(self):
        graph = agent.build_graph(self.config, math_runner=lambda *args: agent.MathResult(status="solved", result="2*x"))
        commands = iter(["diff", "/delivery full", "diff x^2", "/exit"])
        outputs = []
        await cli.run_cli(self.config, graph=graph, read=lambda _: next(commands), display=outputs.append)
        self.assertEqual(outputs.count("2*x"), 1)
        self.assertEqual(outputs.count("Preference saved for the next request."), 1)

    async def test_eof_and_ctrl_c_while_paused_do_not_advance(self):
        for exception in [EOFError, KeyboardInterrupt]:
            config = self.config.model_copy(deep=True)
            config.preferences = agent.Preferences(mode="learn", delivery_mode="step", language="en")
            model = FakeModelClient([plan()])
            graph = agent.build_graph(config, model, retrieval_client=client())
            count = 0
            def read(_):
                nonlocal count
                count += 1
                if count == 1:
                    return "Explain derivatives"
                raise exception()
            outputs = []
            self.assertEqual(await cli.run_cli(config, graph=graph, read=read, display=outputs.append), 0)
            self.assertEqual(len([text for text in outputs if text.startswith("Step ")]), 1)
            self.assertIn("Goodbye.", outputs)
            self.assertEqual(len(model.calls), 1)

    async def test_one_shot_step_displays_chunk_and_pause_returns_two(self):
        self.config.preferences = agent.Preferences(mode="learn", delivery_mode="step", language="en", learner_level="beginner")
        graph = agent.build_graph(self.config, FakeModelClient([plan()]), retrieval_client=client())
        outputs = []
        code = await cli.run_cli(self.config, graph=graph, query="Explain derivatives", display=outputs.append)
        self.assertEqual(code, 2)
        self.assertEqual(len([text for text in outputs if text.startswith("Step ")]), 1)
        self.assertNotIn("Example:", "\n".join(outputs))
        self.assertIn("Reply 'next'", outputs[-1])


class ReplyContractChecks(unittest.TestCase):
    def test_reply_aliases_and_nonadvancing_questions(self):
        for value in ["بعدی", "ادامه", "اوکی", "next", "Okay!"]:
            self.assertEqual(parse_reply(value, 16000).action, "next")
        for value in ["نفهمیدم", "i don't understand", "متوجه نشدم چرا این درست است"]:
            self.assertEqual(parse_reply(value, 16000).action, "simplify")
        self.assertEqual(parse_reply("کامل بگو", 16000).action, "full")
        self.assertEqual(parse_reply("تمام", 16000).action, "done")
        for value in ["اوکی؟", "Okay, but why?", "next why?"]:
            self.assertEqual(parse_reply(value, 16000).action, "followup")
        for value in ["", "x" * 1001, {"action": "next", "unexpected": True}]:
            with self.assertRaises(ValueError):
                parse_reply(value, 1000)

    def test_chunk_contract_preserves_math_units_and_rejects_wall_of_text(self):
        text = "Use $x^{2.5}$ in its stated domain. Preserve $a.b$ as notation."
        self.assertEqual(len(sentences(text)), 2)
        self.assertEqual(StepDraft(explanation=text, source_ids=["power-rule"]).explanation, text)
        for text in ["One sentence.", "First. Second. Third. Fourth."]:
            with self.assertRaises(ValueError):
                StepDraft(explanation=text, source_ids=["power-rule"])


if __name__ == "__main__":
    unittest.main()
