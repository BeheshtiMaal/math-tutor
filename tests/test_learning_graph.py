"""Real graph acceptance with synthetic evidence; no downloaded corpus claims."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from langgraph.types import Command
import agent
import cli
from learning import LocalRetrievalClient, STYLES
from fakes import FakeModelClient, FakeRetrievalClient, FakeSearchClient


def setUpModule():
    global tracing_env
    tracing_env = patch.dict(os.environ, {"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false", "LANGCHAIN_TRACING": "false"})
    tracing_env.start()


def tearDownModule():
    tracing_env.stop()


def provenance():
    return agent.Provenance(source_url="https://example.org/synthetic-lesson", section_title="Synthetic power rule",
        source_author="Test fixture author", retrieved_at="2026-10-09T00:00:00Z",
        usage_terms_url="https://example.org/fixture-terms", usage_terms="Synthetic testing material")


def source():
    return agent.SourceRecord(id="power-rule", topic="derivative", text="Synthetic note: d(x^n)/dx = n*x^(n-1), for positive integers n.", provenance=provenance())


def example(index=1, level="beginner", **changes):
    row = dict(id=f"fixture-{level}-{index}", example_id=f"fixture-{level}-{index}", topic="derivative", subtopic="power rule",
        course="Calculus I", learner_level=level, statement=f"Synthetic question {index}: differentiate x^2.",
        solution="Synthetic solution: 2*x.", source_example_label=f"Fixture example {index}", provenance=provenance())
    row.update(changes)
    return agent.ExampleRecord(**row)


def evidence(records):
    return agent.EvidenceResult(status="success", records=records, retrieval_method="fake")


def client(level="beginner"):
    return FakeRetrievalClient(source=evidence([source()]), examples=evidence([example(i, level) for i in range(1, 4)]),
        tips=evidence([agent.TeachingRule(id="symbols", text="Explain each symbol.", learner_levels=[level])]))


class LearningGraphChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = agent.AppConfig(preferences=agent.Preferences(mode="learn", language="en", learner_level="beginner"))

    def state(self, **changes):
        return agent.new_request_state(agent.Request(query="Explain derivatives", **changes), self.config)

    async def test_exact_edges_and_actual_all_predecessor_barrier(self):
        graph = agent.build_graph(self.config)
        self.assertEqual(set(graph.get_graph().nodes), {*agent.NODE_NAMES, "__start__", "__end__"})
        expected = set(agent.FIXED_EDGES)
        expected.update((name, "write_explanation") for name in agent.RESOURCE_NODES)
        expected.update((node, target) for node, routes in agent.CONDITIONAL_EDGES.items() for target in routes.values())
        self.assertEqual({(edge.source, edge.target) for edge in graph.get_graph().edges}, expected)
        # Inspect the actual StateGraph builder, not merely rendered parallel arrows.
        self.assertEqual(graph.builder.waiting_edges, {(agent.RESOURCE_NODES, "write_explanation")})

    async def test_event_controlled_four_worker_overlap_error_skip_and_one_writer(self):
        started = {name: asyncio.Event() for name in agent.RESOURCE_NODES}
        release = {name: asyncio.Event() for name in agent.RESOURCE_NODES}
        finished = []
        def worker(name):
            async def run(request):
                started[name].set()
                await release[name].wait()
                finished.append(name)
                if name == "teaching_bestpractices":
                    raise RuntimeError("private service token")
                if name == "web_search":
                    return agent.EvidenceResult(status="skipped", warning="Fixture backend skipped")
                return evidence([source()] if name == "read_source" else [example()])
            return run
        class ObservingModel(FakeModelClient):
            async def structured(inner, messages, schema):
                self.assertEqual(set(finished), set(agent.RESOURCE_NODES))
                return await super().structured(messages, schema)
        model = ObservingModel([{"explanation": "The power rule relates an exponent to its derivative.", "source_ids": ["power-rule"]}])
        graph = agent.build_graph(self.config, model, resource_workers={name: worker(name) for name in agent.RESOURCE_NODES})
        thread = {"configurable": {"thread_id": "barrier"}}
        invocation = asyncio.create_task(graph.ainvoke(self.state(), thread))
        try:
            await asyncio.wait_for(asyncio.gather(*(event.wait() for event in started.values())), 5)
            self.assertEqual(finished, [])
            # Release three branches. Each finishes but the writer must still wait.
            for name in agent.RESOURCE_NODES[:-1]:
                release[name].set()
            for _ in range(100):
                if len(finished) == 3:
                    break
                await asyncio.sleep(0.005)
            self.assertEqual(len(finished), 3)
            self.assertEqual(model.calls, [])
            self.assertFalse(invocation.done())
            release["web_search"].set()
            result = await asyncio.wait_for(invocation, 5)
        finally:
            for event in release.values():
                event.set()
            if not invocation.done():
                invocation.cancel()
                await asyncio.gather(invocation, return_exceptions=True)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(result["teaching_tips"].status, "error")
        self.assertEqual(result["websearch"].status, "skipped")
        self.assertNotIn("private service token", result["explanation"])
        events = [event.node for event in result["execution_trace"]]
        self.assertEqual(events.count("write_explanation"), 1)
        self.assertTrue(all(events.index(name) < events.index("write_explanation") for name in agent.RESOURCE_NODES))
        self.assertEqual(graph.get_state(thread).next, ("user_input",))

    async def test_full_lesson_provenance_one_example_followup_context_and_done(self):
        retrieval = client()
        model = FakeModelClient([
            {"explanation": "The exponent gives the multiplier; then reduce it by one.", "source_ids": ["power-rule"]},
            {"explanation": "In this lesson n is the positive integer exponent.", "source_ids": ["power-rule"]},
        ])
        graph = agent.build_graph(self.config, model, retrieval_client=retrieval)
        thread = {"configurable": {"thread_id": "followup"}}
        first = await graph.ainvoke(self.state(), thread)
        self.assertEqual(first["explanation"].count("Example:"), 1)
        self.assertNotIn("https://example.org/synthetic-lesson", first["explanation"])
        self.assertNotIn("Test fixture author", first["explanation"])
        self.assertNotIn("Synthetic testing material", first["explanation"])
        self.assertIn("Verification: unknown", first["explanation"])
        self.assertEqual(first["selected_example_id"], "fixture-beginner-1")
        second = await graph.ainvoke(Command(resume="What is n?"), thread)
        self.assertEqual(second["explanation_version"], 2)
        self.assertEqual(second["selected_example_id"], "fixture-beginner-2")
        self.assertEqual(len(retrieval.calls), 3)
        prompt = model.calls[1][1][-1].content
        self.assertIn("What is n?", prompt)
        self.assertIn(first["lesson_objective"], prompt)
        self.assertIn("The exponent gives", prompt)
        final = await graph.ainvoke(Command(resume="تمام"), thread)
        self.assertNotIn("__interrupt__", final)
        self.assertEqual(final["explanation_version"], 2)
        self.assertEqual(graph.get_state(thread).next, ())
        self.assertEqual(len(model.calls), 2)

    async def test_levels_change_writer_instructions_and_select_matching_pool(self):
        for level in STYLES:
            model = FakeModelClient([{"explanation": "A source-grounded lesson.", "source_ids": ["power-rule"]}])
            graph = agent.build_graph(self.config, model, retrieval_client=client(level))
            result = await graph.ainvoke(self.state(learner_level=level), {"configurable": {"thread_id": level}})
            self.assertIn(STYLES[level], model.calls[0][1][0].content)
            self.assertEqual(result["examples"].records[0].learner_level, level)
            self.assertEqual(result["explanation"].count("Example:"), 1)

    async def test_missing_evidence_no_model_fabrication_and_search_never_called(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.config.model_copy(update={"sources_dir": Path(directory), "search_enabled": False})
            model, search = FakeModelClient([]), FakeSearchClient()
            graph = agent.build_graph(config, model, search)
            result = await graph.ainvoke(self.state(), {"configurable": {"thread_id": "missing"}})
        self.assertEqual(model.calls, [])
        self.assertEqual(search.calls, [])
        self.assertEqual(result["source"].status, "empty")
        self.assertEqual(result["examples"].status, "empty")
        self.assertEqual(result["teaching_tips"].status, "empty")
        self.assertEqual(result["websearch"].status, "skipped")
        self.assertIn("cannot be produced", result["explanation"])
        self.assertNotIn("Example:", result["explanation"])

    async def test_resource_timeout_and_wrong_record_type_do_not_block_join(self):
        async def slow(request):
            await asyncio.sleep(1)
        async def wrong(request):
            return evidence([example()])
        config = self.config.model_copy(update={"limits": agent.Limits(request_timeout_seconds=0.02)})
        graph = agent.build_graph(config, retrieval_client=client(), resource_workers={"read_source": slow, "teaching_bestpractices": wrong})
        result = await graph.ainvoke(self.state(), {"configurable": {"thread_id": "timeout"}})
        self.assertEqual(result["source"].status, "error")
        self.assertEqual(result["teaching_tips"].status, "error")
        self.assertEqual(result["explanation_version"], 1)
        self.assertTrue(result["__interrupt__"])

    async def test_invalid_writer_citation_repairs_then_honest_fallback(self):
        model = FakeModelClient([{"explanation": "Invented citation.", "source_ids": ["missing"]}] * 3)
        graph = agent.build_graph(self.config, model, retrieval_client=client())
        result = await graph.ainvoke(self.state(), {"configurable": {"thread_id": "writer-repair"}})
        self.assertEqual(len(model.calls), 3)
        self.assertIn(source().text, result["explanation"])
        self.assertIn("synthesis failed", result["explanation"])
        self.assertNotIn("Invented citation", result["explanation"])

    async def test_persian_inference_provisional_level_and_step_pause(self):
        state = agent.new_request_state(agent.Request(query="مشتق را توضیح بده", mode="learn", language="fa", delivery_mode="step"), agent.AppConfig())
        graph = agent.build_graph(self.config, retrieval_client=client())
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "persian"}})
        self.assertEqual(result["topic"], "derivative")
        self.assertEqual(result["learner_level"], "beginner")
        self.assertEqual(result["delivery_mode"], "step")
        self.assertNotIn("incomplete until Phase 5", result["explanation"])
        self.assertIn("provisionally", result["explanation"])
        self.assertNotIn("مثال منبع", result["explanation"])
        self.assertEqual(result["step_index"], 0)
        self.assertTrue(result["__interrupt__"])

    async def test_cli_prints_each_lesson_once_and_done_does_not_repeat(self):
        graph = agent.build_graph(self.config, retrieval_client=client())
        commands = iter(["Explain derivatives", "/help", "What is n?", "done", "/exit"])
        outputs = []
        status = await cli.run_cli(self.config, graph=graph, read=lambda _: next(commands), display=outputs.append)
        self.assertEqual(status, 0)
        lessons = [output for output in outputs if "Example:" in output]
        self.assertEqual(len(lessons), 2)
        self.assertEqual(len([output for output in outputs if "Ask a follow-up question" in output]), 2)

    async def test_wholly_new_topic_ends_old_checkpoint_and_cli_starts_fresh_request(self):
        retrieval = client()
        graph = agent.build_graph(self.config, retrieval_client=retrieval)
        commands = iter(["Explain derivatives", "Explain integrals", "done", "/exit"])
        outputs = []
        await cli.run_cli(self.config, graph=graph, read=lambda _: next(commands), display=outputs.append)
        self.assertEqual(len(retrieval.calls), 6)
        self.assertEqual([request.topic for name, request in retrieval.calls if name == "read_source"], ["derivative", "integral"])
        self.assertEqual(len([output for output in outputs if "Ask a follow-up question" in output]), 2)


class LocalEvidenceChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = agent.AppConfig(sources_dir=self.root, semantic_enabled=False)
        self.client = LocalRetrievalClient(self.config, agent.run_math_worker)
        self.request = agent.EvidenceRequest(query="Explain derivatives", topic="derivative", learner_level="beginner", language="en")

    def tearDown(self):
        self.temp.cleanup()

    def notes(self):
        directory = self.root / "topics"
        directory.mkdir()
        (directory / "derivative.md").write_text("# Power rule\n" + source().text, encoding="utf-8")
        (directory / "derivative.metadata.json").write_text(json.dumps({"topic": "derivative", "provenance": provenance().model_dump(mode="json")}), encoding="utf-8")

    def bank(self, records):
        directory = self.root / "examples" / "paul"
        directory.mkdir(parents=True)
        (directory / "derivative.jsonl").write_text("\n".join(record.model_dump_json() for record in records), encoding="utf-8")

    async def test_real_local_files_feed_real_graph_with_provenance_and_one_example(self):
        self.notes()
        self.bank([example(1), example(2)])
        (self.root / "teaching_bestpractices.md").write_text("1. [beginner] Explain symbols.\n2. [advanced] Justify assumptions.", encoding="utf-8")
        graph = agent.build_graph(self.config)
        state = agent.new_request_state(agent.Request(query="Explain derivatives", mode="learn", language="en", learner_level="beginner"), self.config)
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "local-files"}})
        self.assertEqual(result["source"].status, "success")
        self.assertEqual(result["examples"].status, "success")
        self.assertEqual(result["teaching_tips"].status, "success")
        self.assertEqual(len(result["teaching_tips"].records), 1)
        self.assertIn("d(x^n)/dx", result["explanation"])
        self.assertNotIn("https://example.org/synthetic-lesson", result["explanation"])
        self.assertEqual(result["explanation"].count("Example:"), 1)

    async def test_compact_bank_dedup_level_rejection_and_no_false_verification(self):
        records = [example(i) for i in range(1, 6)] + [example(1), example(1, "advanced"), example(7, verification_status="rejected", verification_method="fixture rejection")]
        self.bank(records)
        result = await self.client.verified_examples(self.request)
        self.assertEqual(len(result.records), 3)
        self.assertEqual(len({record.example_id for record in result.records}), 3)
        self.assertTrue(all(record.learner_level == "beginner" and record.verification_status == "unknown" for record in result.records))
        missing = await self.client.verified_examples(self.request.model_copy(update={"learner_level": "intermediate"}))
        self.assertEqual(missing.status, "empty")
        self.assertIn("No suitable", missing.warning)

    async def test_missing_provenance_and_oversized_complete_record(self):
        self.notes()
        (self.root / "topics" / "derivative.metadata.json").unlink()
        result = await self.client.read_source(self.request)
        self.assertEqual(result.status, "error")
        self.assertIn("provenance", result.warning)
        self.bank([example(statement="x" * 3000)])
        result = await self.client.verified_examples(self.request.model_copy(update={"max_chars": 256}))
        self.assertEqual(result.status, "empty")
        self.assertIn("budget", result.warning)

    async def test_subtopic_filter_and_oversized_display_preserve_whole_formulas(self):
        self.notes()
        self.bank([example(1), example(2, subtopic="chain rule")])
        result = await self.client.verified_examples(self.request.model_copy(update={"subtopic": "chain rule"}))
        self.assertEqual([record.example_id for record in result.records], ["fixture-beginner-2"])
        config = self.config.model_copy(update={"limits": agent.Limits(max_output_chars=128)})
        (self.root / "topics" / "derivative.md").write_text("# Power rule\n" + "x^2 + " * 100, encoding="utf-8")
        graph = agent.build_graph(config)
        state = agent.new_request_state(agent.Request(query="Explain derivatives", mode="learn", language="en"), config)
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "display-budget"}})
        self.assertIn("no formulas were truncated", result["explanation"])
        self.assertNotIn("x^2 + x^2", result["explanation"])

    async def test_antiderivative_check_differentiates_candidate_with_arbitrary_constant(self):
        self.bank([example(operation_payload=agent.parse_request("integrate x"), proposed_result="x^2/2+7")])
        calls = []
        def runner(problem, limits):
            calls.append(problem.operation)
            if problem.operation == "integrate":
                raise AssertionError("Checking a given primitive must not depend on solving the integral first")
            return agent.MathResult(status="solved", result={"differentiate": "x", "simplify": "0"}[problem.operation])
        self.client.math_runner = runner
        result = await self.client.verified_examples(self.request)
        self.assertEqual(calls, ["differentiate", "simplify"])
        self.assertEqual(result.records[0].verification_status, "verified")
        self.assertIn("antiderivative differentiated", result.records[0].verification_method)

    async def test_supported_claim_verified_rejected_and_worker_unavailable(self):
        self.bank([example(operation_payload=agent.parse_request("diff x^2"), proposed_result="2*x", verification_status="verified", verification_method="untrusted stored assertion")])
        def unavailable(*args):
            return agent.MathResult(status="error", warning="Missing dependency")
        self.client.math_runner = unavailable
        result = await self.client.verified_examples(self.request)
        self.assertEqual(result.records[0].verification_status, "unknown")
        def correct(problem, limits):
            return agent.MathResult(status="solved", result="2*x" if problem.operation == "differentiate" else "0")
        self.client.math_runner = correct
        result = await self.client.verified_examples(self.request)
        self.assertEqual(result.records[0].verification_status, "verified")
        def incorrect(problem, limits):
            return agent.MathResult(status="solved", result="2*x" if problem.operation == "differentiate" else "1")
        self.client.math_runner = incorrect
        result = await self.client.verified_examples(self.request)
        self.assertEqual(result.status, "empty")

    @unittest.skipUnless(importlib.util.find_spec("sympy"), "SymPy is not installed")
    async def test_actual_symbolic_example_equivalence(self):
        self.client.config = self.config.model_copy(update={"limits": agent.Limits(math_timeout_seconds=20)})
        self.bank([example(operation_payload=agent.parse_request("diff x^2"), proposed_result="x+x")])
        result = await self.client.verified_examples(self.request)
        self.assertEqual(result.records[0].verification_status, "verified")

    async def test_complete_finite_equation_sets_include_singletons_and_empty_sets(self):
        problem = agent.parse_request("solve x^2-x=12")
        cases = [("x in {-3, 4}", "{-3,4}"), ("x=6", "{6}"), ("x in EmptySet", "{}")]
        for computed, proposed in cases:
            with self.subTest(computed=computed):
                calls = []
                def runner(payload, limits):
                    calls.append(payload.operation)
                    return agent.MathResult(status="solved", result=computed, exclusions=["x != 1"])
                self.client.math_runner = runner
                record = self.client._verify(example(operation_payload=problem, proposed_result=proposed))
                self.assertEqual(record.verification_status, "verified")
                self.assertIn("x != 1", record.assumptions)
                self.assertEqual(calls, ["solve"])

    async def test_equation_root_subsets_and_conditional_sets_are_never_verified(self):
        problem = agent.parse_request("solve x^2-x=12")
        self.client.math_runner = lambda *args: agent.MathResult(status="solved", result="x in {-3, 4}")
        record = self.client._verify(example(operation_payload=problem, proposed_result="{4}"))
        self.assertEqual(record.verification_status, "unknown")
        self.client.math_runner = lambda *args: agent.MathResult(status="solved", result="x in Reals")
        record = self.client._verify(example(operation_payload=problem, proposed_result="{}"))
        self.assertEqual(record.verification_status, "unsupported")


if __name__ == "__main__":
    unittest.main()
