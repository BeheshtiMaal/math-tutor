import asyncio
import importlib.util
import os
import socket
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from langgraph.types import Command
import agent
import cli
from fakes import FakeModelClient

HAS_SYMPY = importlib.util.find_spec("sympy") is not None


def setUpModule():
    global tracing_env
    tracing_env = patch.dict(os.environ, {"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false", "LANGCHAIN_TRACING": "false"})
    tracing_env.start()


def tearDownModule():
    tracing_env.stop()


class AnswerGraphChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Missing-evidence cases must remain independent of prepared private
        # project sources and must not initialize the semantic model.
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.config = agent.AppConfig(sources_dir=Path(directory.name), semantic_enabled=False)

    def state(self, query, **kwargs):
        return agent.new_request_state(agent.Request(query=query, **kwargs), self.config)

    async def test_actual_compiled_graph_and_concise_injected_result(self):
        calls = []
        def runner(problem, limits):
            calls.append(problem)
            return agent.MathResult(status="solved", result="x=6")
        graph = agent.build_graph(self.config, math_runner=runner)
        self.assertEqual(set(graph.get_graph().nodes), {"__start__", "__end__", *agent.NODE_NAMES})
        edges = {(e.source, e.target) for e in graph.get_graph().edges}
        self.assertIn(("classify", "learn"), edges)
        self.assertNotIn(("classify", "__end__"), edges)
        result = await graph.ainvoke(self.state("2x+5=17"), {"configurable": {"thread_id": "answer"}})
        self.assertEqual(result["final_answer"], "x=6")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].operation, "solve")
        self.assertEqual([e.node for e in result["execution_trace"]], ["classify", "answer", "math_tool", "write_answer"])

    async def test_checkpointed_interrupt_resume_inside_answer(self):
        graph = agent.build_graph(self.config, math_runner=lambda p,l: agent.MathResult(status="solved", result="2*x"))
        thread = {"configurable": {"thread_id": "clarification"}}
        first = await graph.ainvoke(self.state("diff"), thread)
        self.assertTrue(first["__interrupt__"])
        self.assertEqual(graph.get_state(thread).next, ("answer",))
        final = await graph.ainvoke(Command(resume="diff x^2"), thread)
        self.assertNotIn("__interrupt__", final)
        self.assertEqual(final["final_answer"], "2*x")
        self.assertEqual(final["clarification_count"], 1)
        self.assertEqual(graph.get_state(thread).next, ())

    async def test_provider_extraction_is_not_repeated_on_resume(self):
        model = FakeModelClient([{"clarification": "Which equation?"}])
        graph = agent.build_graph(self.config, model=model, math_runner=lambda p,l: agent.MathResult(status="solved", result="x=6"))
        thread = {"configurable": {"thread_id": "provider-pause"}}
        first = await graph.ainvoke(self.state("Find the solution please"), thread)
        self.assertTrue(first["__interrupt__"])
        final = await graph.ainvoke(Command(resume="2x+5=17"), thread)
        self.assertEqual(final["final_answer"], "x=6")
        self.assertEqual(len(model.calls), 1)

    async def test_missing_query_and_bounded_clarifications(self):
        graph = agent.build_graph(self.config, math_runner=lambda p,l: agent.MathResult(status="solved", result="x=6"))
        thread = {"configurable": {"thread_id": "missing"}}
        first = await graph.ainvoke({"query": "", "mode": "answer"}, thread)
        self.assertEqual(graph.get_state(thread).next, ("classify",))
        final = await graph.ainvoke(Command(resume="2x+5=17"), thread)
        self.assertEqual(final["final_answer"], "x=6")
        thread = {"configurable": {"thread_id": "bounded"}}
        await graph.ainvoke(self.state("diff"), thread)
        await graph.ainvoke(Command(resume="diff"), thread)
        final = await graph.ainvoke(Command(resume="diff"), thread)
        self.assertIn("allowed clarification", final["final_answer"])
        self.assertEqual(final["clarification_count"], 2)
        self.assertEqual(graph.get_state(thread).next, ())

    async def test_provider_repair_and_failure_do_not_leak_exceptions(self):
        model = FakeModelClient([{"unexpected": "invalid"}, {"problem": agent.parse_request("2x+5=17").model_dump()}])
        graph = agent.build_graph(self.config, model=model, math_runner=lambda p,l: agent.MathResult(status="solved", result="x=6"))
        result = await graph.ainvoke(self.state("Please find the unknown value"), {"configurable": {"thread_id": "repair"}})
        self.assertEqual(result["final_answer"], "x=6")
        self.assertEqual(len(model.calls), 2)
        self.assertEqual(result["repair_count"], 1)
        for responses in [[{"bad": 1}, {"bad": 2}], [RuntimeError("secret-provider-token")]]:
            model = FakeModelClient(responses)
            graph = agent.build_graph(self.config, model=model)
            result = await graph.ainvoke(self.state("A natural language request"), {"configurable": {"thread_id": str(len(responses))}})
            self.assertEqual(result["math_result"].status, "error")
            self.assertNotIn("secret-provider-token", result["final_answer"])
            self.assertLessEqual(len(model.calls), 2)

    async def test_provider_deadline_is_recoverable(self):
        class SlowModel:
            async def structured(self, messages, schema):
                await asyncio.sleep(1)
        config = agent.AppConfig(limits=agent.Limits(request_timeout_seconds=0.01))
        graph = agent.build_graph(config, model=SlowModel())
        result = await graph.ainvoke(self.state("Some verbal request"), {"configurable": {"thread_id": "deadline"}})
        self.assertIn("timed out", result["final_answer"])

    async def test_learn_missing_evidence_unsafe_input_and_missing_provider(self):
        def forbidden(*args):
            raise AssertionError("Tool must not run")
        graph = agent.build_graph(self.config, math_runner=forbidden)
        result = await graph.ainvoke(self.state("Explain limits", mode="learn"), {"configurable": {"thread_id": "learn"}})
        self.assertEqual(result["source"].status, "empty")
        self.assertTrue(result["__interrupt__"])
        self.assertEqual(result["websearch"].status, "skipped")
        for query in ["simplify __import__('os')", "Unrecognized verbal request"]:
            result = await graph.ainvoke(self.state(query), {"configurable": {"thread_id": query}})
            self.assertEqual(result["math_result"].status, "error")
        self.assertIn("TUTOR_MODEL", result["final_answer"])

    async def test_malformed_routing_and_nontext_input_are_recoverable(self):
        graph = agent.build_graph(self.config, math_runner=lambda *args: self.fail("Tool must not run"))
        for state in [{"query": "2x+5=17", "mode": "bad"}, {"query": 123, "mode": "answer"}, {"query": "2x+5=17", "mode": "answer", "topic": 123}]:
            result = await graph.ainvoke(state, {"configurable": {"thread_id": str(state)}})
            self.assertEqual(result["math_result"].status, "error")
            self.assertTrue(result["final_answer"])

    async def test_cli_repeated_input_commands_during_pause_and_reset(self):
        calls = []
        def runner(problem, limits):
            calls.append(problem)
            return agent.MathResult(status="solved", result="x=6")
        graph = agent.build_graph(self.config, math_runner=runner)
        lines = iter(["diff", "/help", "/reset", "2x+5=17", "/language en", "2x+5=17", "/exit"])
        output = []
        code = await cli.run_cli(self.config, graph=graph, read=lambda _: next(lines), display=output.append)
        self.assertEqual(code, 0)
        self.assertEqual(output.count("x=6"), 2)
        self.assertEqual(len(calls), 2)
        self.assertIn("Session reset.", output)
        self.assertTrue(any("Supply the complete" in line for line in output))

    async def test_cli_eof_empty_unicode_and_invalid_commands(self):
        graph = agent.build_graph(self.config, math_runner=lambda p,l: agent.MathResult(status="solved", result="2*x"))
        lines = iter(["", "/unknown", "/mode wrong", "مشتق x^۲"])
        def reader(prompt):
            try: return next(lines)
            except StopIteration: raise EOFError
        output = []
        await cli.run_cli(self.config, graph=graph, read=reader, display=output.append)
        self.assertIn("2*x", output)
        self.assertIn("Goodbye.", output)
        self.assertIn("Invalid preference. Use /help.", output)

    async def test_cli_disables_inherited_network_tracing(self):
        graph = agent.build_graph(self.config, math_runner=lambda p,l: agent.MathResult(status="solved", result="x=6"))
        output = []
        with patch.dict(os.environ, {"LANGSMITH_TRACING": "true", "LANGCHAIN_TRACING_V2": "true"}):
            with patch.object(socket.socket, "connect", side_effect=AssertionError("Unexpected network")) as connect:
                code = await cli.run_cli(self.config, graph=graph, query="2x+5=17", display=output.append)
                self.assertEqual(code, 0)
                connect.assert_not_called()
        self.assertIn("x=6", output)


class ParserAndWorkerChecks(unittest.TestCase):
    def test_safe_local_syntax_and_exact_literals(self):
        for query, kind in [("2x+5=17", "solve"), ("diff x^2", "differentiate"), ("diff y^2 wrt y", "differentiate"), ("integrate x^2", "integrate"), ("integrate x from 0 to 1", "integrate"), ("limit 1/x at 0 left", "limit"), ("matrix inverse [[1,2],[3,4]]", "matrix"), ("simplify 2(x+1)", "simplify")]:
            with self.subTest(query=query):
                self.assertEqual(agent.parse_request(query).operation, kind)
        self.assertEqual(agent.parse_expression("0.1").value, "0.1")
        for query in ["simplify x.__class__", "simplify [1,2]", "simplify eval(1)", "simplify 2**", "matrix inverse [[1,2],[3]]"]:
            with self.assertRaises(ValueError):
                agent.parse_request(query)

    def test_worker_timeout_kills_and_reaps_process(self):
        problem = agent.parse_request("diff x^2")
        result = agent.run_math_worker(problem, agent.Limits(math_timeout_seconds=0.001))
        self.assertEqual(result.status, "timeout")
        self.assertIn("time limit", result.warning)

    @unittest.skipIf(HAS_SYMPY, "Specifically tests the missing SymPy environment")
    def test_missing_sympy_is_readable_from_actual_spawned_worker(self):
        result = agent.run_math_worker(agent.parse_request("diff x^2"), agent.Limits(math_timeout_seconds=20))
        self.assertEqual(result.status, "error")
        self.assertIn("SymPy is missing", result.warning)


@unittest.skipUnless(HAS_SYMPY, "Real SymPy math acceptance blocked: dependency is not installed")
class RealMathAcceptance(unittest.TestCase):
    def compute(self, query):
        return agent.run_math_worker(agent.parse_request(query), agent.Limits(math_timeout_seconds=20))

    def test_real_compiled_graph_returns_x6(self):
        config = agent.AppConfig(limits=agent.Limits(math_timeout_seconds=20))
        graph = agent.build_graph(config)
        result = asyncio.run(graph.ainvoke(agent.new_request_state(agent.Request(query="2x+5=17"), config), {"configurable": {"thread_id": "real-answer"}}))
        self.assertEqual(result["final_answer"], "x=6")

    def test_derivative_and_integrals(self):
        derivative = self.compute("diff x^3")
        self.assertEqual(derivative.status, "solved")
        self.assertEqual(derivative.result, "3*x**2")
        indefinite = self.compute("integrate x^2")
        self.assertEqual(indefinite.result, "x**3/3")
        self.assertTrue(indefinite.integration_constant_required)
        self.assertIn("+ C", agent.format_answer(indefinite))
        definite = self.compute("integrate x^2 from 0 to 1")
        self.assertEqual(definite.result, "1/3")
        self.assertFalse(definite.integration_constant_required)

    def test_limits_direction_and_real_domain(self):
        self.assertEqual(self.compute("limit sin(x)/x at 0 both").result, "1")
        left = self.compute("limit 1/x at 0 left")
        self.assertEqual(left.result, "-oo")
        self.assertTrue(left.conditions)
        self.assertIn("does not exist", self.compute("limit 1/x at 0 both").result)
        self.assertEqual(self.compute("limit sqrt(x) at 0 both").status, "unsupported")

    def test_roots_and_excluded_equation_root(self):
        self.assertEqual(self.compute("x^2=4").result, "x in {-2, 2}")
        excluded = self.compute("(x^2-1)/(x-1)=2")
        self.assertIn("EmptySet", excluded.result)
        self.assertTrue(excluded.exclusions)

    def test_matrix_and_singular_inverse(self):
        self.assertEqual(self.compute("matrix determinant [[1,2],[3,4]]").result, "-2")
        singular = self.compute("matrix inverse [[1,2],[2,4]]")
        self.assertEqual(singular.status, "error")
        self.assertIn("singular", singular.warning)

    def test_simplification_preserves_exclusions_and_invalid_numbers(self):
        simplified = self.compute("simplify x/x")
        self.assertEqual(simplified.result, "1")
        self.assertTrue(simplified.exclusions)
        for query in ["simplify 1/0", "simplify 2^100000", "simplify 2^(2^100)"]:
            self.assertEqual(self.compute(query).status, "error")

    def test_improper_integral_and_unevaluated_result(self):
        self.assertIn("diverges", self.compute("integrate 1/x from 0 to 1").result)
        self.assertEqual(self.compute("integrate 1/x from -1 to 1").status, "unsupported")
        result = self.compute("integrate exp(-x^x)")
        self.assertIn(result.status, {"unevaluated", "timeout"})


if __name__ == "__main__":
    unittest.main()
