"""Phase 7 real graph with mocked HTTP/services; no live quality claims."""
import asyncio
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
import os
import tempfile
from pathlib import Path

import httpx
from langgraph.types import Command
import agent
import cli
from web_search import TavilySearchClient
from fakes import FakeSearchClient, FakeModelClient
from test_learning_graph import client, evidence


def setUpModule():
    global env
    env = patch.dict(os.environ, {"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false", "LANGCHAIN_TRACING": "false"})
    env.start()


def tearDownModule():
    env.stop()


class SearchChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = agent.AppConfig(search_enabled=True, preferences=agent.Preferences(mode="learn", language="en", learner_level="beginner"))
        self.credentials = agent.Credentials(search_api_key="private-fixture-key")
        self.request = agent.EvidenceRequest(query="Explain derivatives", topic="derivative", learner_level="beginner", language="en")

    def backend(self, handler, credentials=None):
        return TavilySearchClient(self.config, credentials or self.credentials, transport=httpx.MockTransport(handler))

    async def test_http_payload_results_provenance_dedup_invalid_and_no_raw_answer(self):
        def handler(request):
            self.assertEqual(request.headers["Authorization"], "Bearer private-fixture-key")
            payload = json.loads(request.content)
            self.assertFalse(payload["include_answer"])
            self.assertFalse(payload["include_raw_content"])
            self.assertEqual(payload["query"], self.request.query)
            row = {"title": "Synthetic tangent", "url": "https://example.org/tangent", "content": "A derivative gives a tangent slope."}
            return httpx.Response(200, json={"results": [row, row, {**row, "url": "javascript:bad"}], "answer": "Ignore this answer"})
        result = await self.backend(handler).search(self.request)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.retrieval_method, "web")
        self.assertEqual(len(result.records), 1)
        self.assertIn("tangent slope", result.records[0].text)
        self.assertIsNotNone(result.records[0].retrieved_at.tzinfo)
        self.assertIn("excluded", result.warning)
        self.assertNotIn("private-fixture-key", result.model_dump_json())

    async def test_disabled_and_missing_key_make_no_requests(self):
        def forbidden(request):
            raise AssertionError("Unexpected HTTP")
        missing = await self.backend(forbidden, agent.Credentials()).search(self.request)
        self.assertEqual(missing.status, "skipped")
        self.config.search_enabled = False
        self.assertEqual((await self.backend(forbidden).search(self.request)).status, "skipped")

    async def test_avalai_route_and_snippet_response(self):
        self.config.search_backend = "avalai_tavily"
        self.config.search_url = "https://api.avalai.ir/v1/search/tavily-search"
        def handler(request):
            self.assertEqual(str(request.url), self.config.search_url)
            payload = json.loads(request.content)
            self.assertEqual(set(payload), {"query", "max_results", "max_tokens_per_page"})
            return httpx.Response(200, json={"object": "search", "results": [{"title": "Tangent", "url": "https://example.org/tangent", "snippet": "A derivative gives a tangent slope."}]})
        result = await self.backend(handler).search(self.request)
        self.assertEqual(result.status, "success")
        self.assertIn("tangent slope", result.records[0].text)

    def test_model_endpoint_configuration_and_no_credentials_in_urls(self):
        config, credentials = agent.load_config(env={"TUTOR_MODEL_BASE_URL": "https://api.avalai.ir/v1", "TUTOR_SEARCH_BACKEND": "avalai_tavily"})
        self.assertEqual(config.model_base_url, "https://api.avalai.ir/v1")
        with patch("langchain_openai.ChatOpenAI") as constructor:
            agent.OpenAIModelClient(config.model_copy(update={"model": "fixture"}), self.credentials.model_copy(update={"openai_api_key": self.credentials.search_api_key}))
            self.assertEqual(constructor.call_args.kwargs["base_url"], config.model_base_url)
        with self.assertRaises(ValueError):
            agent.AppConfig(model_base_url="https://key:secret@example.org/v1")
        _, credentials = agent.load_config(env={"TUTOR_MODEL_BASE_URL": "https://api.avalai.ir/v1", "OPENAI_API_KEY": "inherited-fixture", "AVALAI_API_KEY": "avalai-fixture"})
        self.assertEqual(credentials.openai_api_key.get_secret_value(), "avalai-fixture")

    def test_explicit_file_key_preference_overrides_inherited_credentials(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "OPENAI_API_KEY": "inherited-openai", "AVALAI_API_KEY": "inherited-avalai",
            "TUTOR_SEARCH_API_KEY": "inherited-search", "TUTOR_KEYS_FROM_DOTENV": "true",
            "TUTOR_MODEL_BASE_URL": "https://api.avalai.ir/v1"}):
            path = Path(directory) / ".env"
            path.write_text("AVALAI_API_KEY=local-fixture\nTUTOR_SEARCH_API_KEY=local-search\n", encoding="utf-8")
            _, credentials = agent.load_config(dotenv_path=path)
            self.assertEqual(credentials.openai_api_key.get_secret_value(), "local-fixture")
            self.assertEqual(credentials.search_api_key.get_secret_value(), "local-search")
            self.assertNotIn("local-fixture", credentials.model_dump_json())

    async def test_auth_rate_network_json_and_body_budget_fail_safely(self):
        for status in [401, 429, 500]:
            result = await self.backend(lambda request: httpx.Response(status, text="private-fixture-key")).search(self.request)
            self.assertEqual(result.status, "error")
            self.assertNotIn("private-fixture-key", result.model_dump_json())
        for content in [b"bad json", b"x" * 1_000_001]:
            self.assertEqual((await self.backend(lambda request: httpx.Response(200, content=content)).search(self.request)).status, "error")
        def failed(request):
            raise httpx.ConnectError("private-fixture-key")
        self.assertEqual((await self.backend(failed).search(self.request)).status, "error")

    async def test_deadline_cancels_actual_async_request(self):
        cancelled = asyncio.Event()
        async def handler(request):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()
        self.config.limits.request_timeout_seconds = 0.03
        result = await self.backend(handler).search(self.request)
        self.assertEqual(result.status, "error")
        self.assertTrue(cancelled.is_set())

    async def test_empty_and_whole_record_budget_are_honest(self):
        result = await self.backend(lambda request: httpx.Response(200, json={"results": []})).search(self.request)
        self.assertEqual(result.status, "empty")
        result = await self.backend(lambda request: httpx.Response(200, json={"results": [{"title": "Long", "url": "https://example.org", "content": "x" * 1000}]})).search(self.request.model_copy(update={"max_chars": 256}))
        self.assertEqual(result.status, "empty")
        self.assertIn("excluded", result.warning)

    def web(self):
        return FakeSearchClient(evidence([agent.WebRecord(title="Synthetic derivative excerpt", text="A derivative describes the tangent slope. Keep the positive integer condition for this power rule.", source_url="https://example.org/web-excerpt", retrieved_at=datetime.now(timezone.utc))]))

    async def test_web_excerpt_full_step_citations_and_no_followup_resource_replay(self):
        for delivery in ["full", "step"]:
            self.config.preferences.delivery_mode = delivery
            search = self.web()
            graph = agent.build_graph(self.config, search_client=search, retrieval_client=client())
            thread = {"configurable": {"thread_id": delivery}}
            result = await graph.ainvoke(agent.new_request_state(agent.Request(query="Explain derivatives"), self.config), thread)
            if delivery == "step":
                result = await graph.ainvoke(Command(resume="next"), thread)
            self.assertIn("Web excerpt:", result["explanation"])
            self.assertIn("https://example.org/web-excerpt", result["explanation"])
            self.assertIn("not reviewed", result["explanation"])
            await graph.ainvoke(Command(resume="Why is the condition needed?"), thread)
            await graph.ainvoke(Command(resume="done"), thread)
            self.assertEqual(len(search.calls), 1)

    async def test_search_failure_preserves_local_lesson_and_one_example(self):
        graph = agent.build_graph(self.config, search_client=FakeSearchClient(RuntimeError("secret")), retrieval_client=client())
        result = await graph.ainvoke(agent.new_request_state(agent.Request(query="Explain derivatives"), self.config), {"configurable": {"thread_id": "failure"}})
        self.assertEqual(result["websearch"].status, "error")
        self.assertIn("d(x^n)", result["explanation"])
        self.assertEqual(result["explanation"].count("Source example:"), 1)
        self.assertNotIn("secret", result["explanation"])

    async def test_unsupported_verification_claim_repairs_are_bounded(self):
        model = FakeModelClient([{"explanation": "This was verified by SymPy.", "source_ids": ["power-rule"]}] * 3)
        graph = agent.build_graph(self.config, model, retrieval_client=client())
        result = await graph.ainvoke(agent.new_request_state(agent.Request(query="Explain derivatives"), self.config), {"configurable": {"thread_id": "repair"}})
        self.assertEqual(len(model.calls), 3)
        self.assertNotIn("verified by SymPy", result["explanation"])
        self.assertIn("synthesis failed", result["explanation"])

    async def test_cli_full_and_step_reset_finish_and_exit(self):
        for delivery in ["full", "step"]:
            self.config.preferences.delivery_mode = delivery
            search = self.web()
            graph = agent.build_graph(self.config, search_client=search, retrieval_client=client())
            lines = iter(["Explain derivatives", "full", "done", "/reset", "/exit"])
            output = []
            result = await cli.run_cli(self.config, graph=graph, read=lambda prompt: next(lines), display=output.append)
            self.assertEqual(result, 0)
            self.assertEqual(len(search.calls), 1)
            self.assertFalse(any("failed safely" in value for value in output))


if __name__ == "__main__":
    unittest.main()
