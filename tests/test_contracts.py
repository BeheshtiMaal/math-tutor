import asyncio
from datetime import datetime, timezone
import operator
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages
from pydantic import ValidationError

import agent
from fakes import FakeModelClient, FakeRetrievalClient, FakeSearchClient

X = {"op": "symbol", "value": "x"}
ONE = {"op": "number", "value": "1"}


class ConfigurationChecks(unittest.TestCase):
    def test_blank_template_is_offline_valid_and_secrets_excluded(self):
        from dotenv import dotenv_values
        config, credentials = agent.load_config(env=dotenv_values(agent.PROJECT_ROOT / ".env.example"))
        self.assertEqual(config.preferences, agent.Preferences())
        self.assertIsNone(config.model)
        self.assertIsNone(credentials.openai_api_key)
        config, credentials = agent.load_config(env={"OPENAI_API_KEY": "test-secret", "TUTOR_SEARCH_API_KEY": "test-search-secret"})
        self.assertNotIn("test-secret", repr(credentials))
        self.assertEqual(credentials.model_dump(), {})
        self.assertNotIn("test-secret", config.model_dump_json())

    def test_environment_config_and_safe_validation_errors(self):
        config, _ = agent.load_config(env={"TUTOR_LEVEL": "advanced", "TUTOR_DELIVERY": "step", "TUTOR_LANGUAGE": "en", "TUTOR_MAX_MATRIX_DIMENSION": "3", "TUTOR_SEARCH_ENABLED": "false"})
        self.assertEqual(config.preferences.learner_level, "advanced")
        self.assertEqual(config.preferences.delivery_mode, "step")
        self.assertEqual(config.limits.max_matrix_dimension, 3)
        self.assertFalse(config.search_enabled)
        for env in [{"TUTOR_LEVEL": "expert"}, {"TUTOR_MAX_EXPRESSION_DEPTH": "0"}, {"TUTOR_PROVIDER": "secret-invalid-value"}, {"TUTOR_WRITER_REPAIRS": "3"}]:
            with self.assertRaises(agent.ConfigurationError) as caught:
                agent.load_config(env=env)
            self.assertNotIn("secret-invalid-value", str(caught.exception))

    def test_dotenv_is_explicit_once_and_does_not_override_environment(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("TUTOR_LANGUAGE=fa\nTUTOR_MODEL=first-model\n")
            with patch.dict(os.environ, {"TUTOR_LANGUAGE": "en"}, clear=True):
                first, _ = agent.load_config(dotenv_path=path)
                path.write_text("TUTOR_MODEL=changed-model\n")
                second, _ = agent.load_config(dotenv_path=path)
                self.assertEqual(first.preferences.language, "en")
                self.assertEqual(second.model, "first-model")

    def test_provider_missing_configuration_does_not_expose_secrets(self):
        with self.assertRaisesRegex(agent.ConfigurationError, "OPENAI_API_KEY"):
            agent.OpenAIModelClient(agent.AppConfig(), agent.Credentials())
        with self.assertRaisesRegex(agent.ConfigurationError, "TUTOR_MODEL"):
            agent.OpenAIModelClient(agent.AppConfig(), agent.Credentials(openai_api_key="test-secret"))

    def test_imports_and_client_construction_make_no_network_calls(self):
        code = '''import socket
def forbidden(*args, **kwargs):
    raise AssertionError("Unexpected network access")
socket.socket.connect = forbidden
socket.create_connection = forbidden
import agent, cli
agent.OpenAIModelClient(agent.AppConfig(model="offline-construction-only"), agent.Credentials(openai_api_key="fake-offline-key"))
print("offline imports and provider construction OK")
'''
        result = subprocess.run([sys.executable, "-c", code], cwd=agent.PROJECT_ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("offline imports", result.stdout)


class ProblemChecks(unittest.TestCase):
    def test_math_result_cannot_claim_solved_without_a_result(self):
        with self.assertRaises(ValidationError):
            agent.MathResult(status="solved")
        with self.assertRaises(ValidationError):
            agent.MathResult(status="timeout")
        result = agent.MathResult(status="solved", result="x=6", conditions=["x real"])
        self.assertEqual(result.result, "x=6")

    def test_supported_problem_shapes(self):
        payloads = [
            {"operation": "differentiate", "expression": X},
            {"operation": "integrate", "expression": X},
            {"operation": "integrate", "expression": X, "lower": ONE, "upper": {"op": "constant", "value": "oo"}},
            {"operation": "limit", "expression": X, "point": ONE, "direction": "left"},
            {"operation": "solve", "lhs": X, "rhs": ONE, "domain": "complex"},
            {"operation": "matrix", "action": "inverse", "matrix": [[ONE, ONE], [ONE, ONE]]},
            {"operation": "simplify", "expression": {"op": "div", "args": [X, X]}},
        ]
        for payload in payloads:
            with self.subTest(operation=payload["operation"]):
                result = agent.validate_problem(payload)
                self.assertEqual(result.operation, payload["operation"])

    def test_untrusted_math_input_is_rejected_without_execution(self):
        invalid = [
            {"operation": "execute", "code": "print(1)"},
            {"operation": "simplify", "expression": "__import__('os')"},
            {"operation": "simplify", "expression": {"op": "call", "value": "eval"}},
            {"operation": "simplify", "expression": {"op": "symbol", "value": "__import__"}},
            {"operation": "simplify", "expression": {"op": "number", "value": "nan"}},
            {"operation": "simplify", "expression": {"op": "number", "value": "1/0"}},
            {"operation": "integrate", "expression": X, "lower": ONE},
            {"operation": "differentiate", "expression": X, "order": 0},
            {"operation": "differentiate", "expression": X, "order": True},
            {"operation": "matrix", "action": "inverse", "matrix": [[ONE, ONE]]},
            {"operation": "matrix", "action": "rank", "matrix": [[ONE], [ONE, ONE]]},
            {"operation": "matrix", "action": "multiply", "matrix": [[ONE, ONE]], "other": [[ONE]]},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises((ValidationError, ValueError)):
                    agent.validate_problem(payload)

    def test_configured_expression_and_matrix_limits(self):
        nested = X
        for _ in range(5):
            nested = {"op": "neg", "args": [nested]}
        with self.assertRaisesRegex(ValueError, "node/depth"):
            agent.validate_problem({"operation": "simplify", "expression": nested}, agent.Limits(max_expression_depth=4))
        with self.assertRaisesRegex(ValueError, "node/depth"):
            agent.validate_problem({"operation": "simplify", "expression": {"op": "add", "args": [X, ONE]}}, agent.Limits(max_expression_nodes=2))
        with self.assertRaisesRegex(ValueError, "dimension"):
            agent.validate_problem({"operation": "matrix", "action": "rank", "matrix": [[ONE, ONE]]}, agent.Limits(max_matrix_dimension=1))
        with self.assertRaisesRegex(ValueError, "size"):
            agent.validate_problem({"operation": "simplify", "expression": X, "assumptions": ["a" * 200]}, agent.Limits(max_input_chars=128))


class StateAndEvidenceChecks(unittest.TestCase):
    def test_request_reset_preserves_explicit_preferences_and_bounded_history(self):
        config = agent.AppConfig(preferences=agent.Preferences(mode="learn", learner_level="advanced"), limits=agent.Limits(max_history_messages=3))
        first = agent.new_request_state(agent.Request(query="درس مشتق", delivery_mode="step"), config)
        first["examples"] = agent.EvidenceResult(status="empty")
        first["step_index"] = 4
        history = [HumanMessage(content=str(i)) for i in range(10)]
        second = agent.new_request_state(agent.Request(query="2x+5=17", mode="answer", language="en"), config, history)
        self.assertEqual(second["mode"], "answer")
        self.assertEqual(second["learner_level"], "advanced")
        self.assertEqual(second["language"], "en")
        self.assertEqual(second["step_index"], 0)
        self.assertIsNone(second["examples"])
        self.assertEqual(len(second["messages"]), 3)
        self.assertEqual(len(history), 10)
        self.assertFalse(any("key" in field for field in agent.TutorState.__annotations__))
        first["warnings"].append("old request")
        self.assertEqual(second["warnings"], [])

    def test_three_levels_full_step_and_validated_routes(self):
        for level in ["beginner", "intermediate", "advanced"]:
            for delivery in ["full", "step"]:
                route = agent.RoutingOutput(mode="learn", topic="limits", language="fa", learner_level=level, delivery_mode=delivery)
                self.assertEqual(route.learner_level, level)
        for override in [{"mode": "anything"}, {"learner_level": "expert"}, {"delivery_mode": "auto"}]:
            with self.assertRaises(ValidationError):
                agent.RoutingOutput.model_validate({"mode": "learn", "topic": "limits", "language": "fa", **override})

    def test_message_reducer_replaces_same_id_and_append_reducers(self):
        result = add_messages([HumanMessage(content="old", id="a")], [HumanMessage(content="new", id="a")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].content, "new")
        self.assertEqual(operator.add(["read_source"], ["web_search"]), ["read_source", "web_search"])
        self.assertEqual(len(set(agent.EVIDENCE_OWNERS.values())), 4)

    def test_evidence_status_and_provenance_are_honest(self):
        for payload in [{"status": "success"}, {"status": "error"}, {"status": "invented"}]:
            with self.assertRaises(ValidationError):
                agent.EvidenceResult.model_validate(payload)
        with self.assertRaises(ValidationError):
            agent.SourceRecord(id="a", topic="limits", text="actual passage")
        provenance = agent.Provenance(source_url="https://example.org/lesson", section_title="Limits", source_author="Fixture Author", retrieved_at=datetime.now(timezone.utc), usage_terms_url="https://example.org/terms", usage_terms="Synthetic fixture")
        example = agent.ExampleRecord(id="a", example_id="a", topic="limits", subtopic="one-sided", course="Calculus I", learner_level="beginner", statement="A fixture", solution="A fixture solution", source_example_label="Fixture example", provenance=provenance)
        self.assertEqual(example.verification_status, "unknown")
        with self.assertRaises(ValidationError):
            agent.ExampleRecord.model_validate({**example.model_dump(), "verification_status": "verified"})
        result = agent.EvidenceResult(status="success", records=[example], retrieval_method="fake")
        self.assertEqual(str(result.records[0].provenance.source_url), "https://example.org/lesson")

    def test_graph_has_authorized_exact_topology(self):
        self.assertEqual(len(agent.NODE_NAMES), 11)
        self.assertEqual(len(agent.RESOURCE_BARRIER[0]), 4)
        self.assertEqual(agent.RESOURCE_BARRIER[1], "write_explanation")
        graph = agent.build_graph(agent.AppConfig())
        self.assertEqual(set(graph.get_graph().nodes), {"__start__", "__end__", *agent.NODE_NAMES})


class InterfaceChecks(unittest.IsolatedAsyncioTestCase):
    async def test_injected_offline_services_and_malformed_provider_output(self):
        request = agent.EvidenceRequest(query="Explain limits", topic="limits", learner_level="beginner", language="en")
        model = FakeModelClient([{"mode": "learn", "topic": "limits", "language": "en"}, {"mode": "bad"}, RuntimeError("offline provider failure")])
        self.assertIsInstance(model, agent.ModelClient)
        route = await model.structured([], agent.RoutingOutput)
        self.assertEqual(route.mode, "learn")
        with self.assertRaises(ValidationError):
            await model.structured([], agent.RoutingOutput)
        with self.assertRaisesRegex(RuntimeError, "offline provider failure"):
            await model.text([])
        search = FakeSearchClient()
        retrieval = FakeRetrievalClient()
        self.assertIsInstance(search, agent.SearchClient)
        self.assertIsInstance(retrieval, agent.RetrievalClient)
        self.assertEqual((await search.search(request)).status, "skipped")
        responses = await asyncio.gather(retrieval.read_source(request), retrieval.verified_examples(request), retrieval.teaching_bestpractices(request))
        self.assertEqual([r.status for r in responses], ["empty"] * 3)
        responses[0].warning = "changed fixture"
        self.assertIsNone((await retrieval.read_source(request)).warning)


if __name__ == "__main__":
    unittest.main()
