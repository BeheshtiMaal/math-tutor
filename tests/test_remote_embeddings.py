import asyncio
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import httpx
import numpy as np

from agent import AppConfig, Credentials, EvidenceRequest, SourceRecord, load_config
from remote_embeddings import AvalAIEmbeddings
from retrieval import EmbeddingUnavailable, SemanticRetrievalClient, VectorIndex
from test_learning_graph import provenance


class RemoteEmbeddingsChecks(unittest.TestCase):
    def adapter(self, handler, **settings):
        config = AppConfig(embedding_backend="avalai", embedding_dimension=2, **settings)
        embedder = AvalAIEmbeddings(config, "fixture-secret", transport=httpx.MockTransport(handler))
        embedder._tokenizer = types.SimpleNamespace(encode=lambda text, **kwargs: text.split())
        return embedder

    def response(self, request):
        body = json.loads(request.content)
        return httpx.Response(200, json={"model": body["model"], "data": [
            {"index": i, "embedding": [i+1, 1]} for i in reversed(range(len(body["input"])))], "usage": {"prompt_tokens": 3}})

    def test_key_selection_remote_defaults_and_credential_serialization(self):
        config, credentials = load_config(env={"TUTOR_EMBEDDING_BACKEND": "avalai", "AVALAI_API_KEY": "fixture-secret"})
        self.assertEqual((config.embedding_model, config.embedding_dimension, config.embedding_max_tokens), ("text-embedding-3-large", 3072, 2048))
        self.assertEqual(credentials.embedding_api_key.get_secret_value(), "fixture-secret")
        self.assertNotIn("fixture-secret", credentials.model_dump_json() + repr(credentials) + config.model_dump_json())
        _, separate = load_config(env={"AVALAI_API_KEY": "shared", "TUTOR_EMBEDDING_API_KEY": "separate"})
        self.assertEqual(separate.embedding_api_key.get_secret_value(), "separate")

    def test_request_uses_avalai_route_and_restores_order_and_normalizes(self):
        calls = []
        def handler(request):
            calls.append(request)
            return self.response(request)
        embedder = self.adapter(handler)
        vectors = embedder.encode(["English document", "متن فارسی"], query=True)
        self.assertEqual(str(calls[0].url), "https://api.avalai.ir/v1/embeddings")
        self.assertEqual(calls[0].headers["Authorization"], "Bearer fixture-secret")
        body = json.loads(calls[0].content)
        self.assertEqual(body["input"], ["English document", "متن فارسی"])
        self.assertEqual(body["dimensions"], 2)
        np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), [1,1], rtol=1e-6)
        np.testing.assert_allclose(vectors[0], [2**-0.5,2**-0.5], rtol=1e-6)

    def test_bounded_batching_and_usage(self):
        sizes = []
        def handler(request):
            sizes.append(len(json.loads(request.content)["input"]))
            return self.response(request)
        embedder = self.adapter(handler)
        self.assertEqual(embedder.encode(["document"]*65).shape, (65,2))
        self.assertEqual(sizes, [32,32,1])
        self.assertEqual((embedder.requests, embedder.prompt_tokens), (3,9))

    def test_missing_key_oversize_and_empty_input_make_no_requests(self):
        embedder = self.adapter(lambda request: self.fail("Invalid input reached network"), embedding_max_tokens=32)
        with self.assertRaises(EmbeddingUnavailable):
            embedder.encode(["word "*33])
        with self.assertRaises(EmbeddingUnavailable):
            embedder.encode([""])
        embedder._api_key = None
        with self.assertRaises(EmbeddingUnavailable):
            embedder.encode(["valid"])

    def test_bad_responses_never_become_valid_vectors_or_expose_raw_errors(self):
        payloads = [
            {"data": []},
            {"data": [{"index":0,"embedding":[1]}]},
            {"data": [{"index":0,"embedding":[0,0]}]},
            {"data": [{"index":1,"embedding":[1,1]}]},
            {"model":"wrong-model", "data":[{"index":0,"embedding":[1,1]}]},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                embedder = self.adapter(lambda request: httpx.Response(200,json=payload))
                with self.assertRaises(EmbeddingUnavailable):
                    embedder.encode(["document"])
        embedder = self.adapter(lambda request: httpx.Response(401,json={"error":"fixture-secret"}))
        with self.assertRaises(EmbeddingUnavailable) as raised:
            embedder.encode(["document"])
        self.assertIn("HTTP 401", str(raised.exception))
        self.assertNotIn("fixture-secret", str(raised.exception))

    def test_remote_caches_reuse_documents_and_record_provider_identity(self):
        calls = []
        def handler(request):
            calls.append(json.loads(request.content)["input"])
            return self.response(request)
        embedder = self.adapter(handler)
        note = SourceRecord(id="fixture",topic="derivative",text="The derivative is a local rate of change.",provenance=provenance())
        with tempfile.TemporaryDirectory() as directory:
            index = VectorIndex(Path(directory)/"sources.npz",embedder)
            first = index.sync([note])[2]
            second = index.sync([note])[2]
            self.assertEqual((first["embedded"],second["embedded"],second["reused"]), (1,0,1))
            self.assertEqual(len(calls),1)
            settings = index.load()[0]["settings"]
            self.assertEqual(settings["provider"], "avalai")
            self.assertEqual(settings["document_prefix"], "")
            self.assertEqual(settings["endpoint"], embedder.endpoint)

    def test_failure_uses_keyword_fallback_without_loading_local_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"topics").mkdir()
            note = SourceRecord(id="fixture",topic="derivative",text="The derivative is a local rate of change.",provenance=provenance())
            (root/"topics/notes.json").write_text(json.dumps([note.model_dump(mode="json")]),encoding="utf-8")
            config = AppConfig(embedding_backend="avalai",sources_dir=root,embedding_cache_dir=root/"cache")
            with patch("retrieval.LocalE5",side_effect=AssertionError("Local model must not be used")):
                client = SemanticRetrievalClient(config,lambda *args: None)
                result = asyncio.run(client.read_source(EvidenceRequest(query="مشتق",topic="derivative",language="fa",learner_level="beginner")))
            self.assertEqual((result.status,result.retrieval_method), ("success","keyword"))
            self.assertIn("embedding key missing",result.warning)

    def test_cli_offline_disables_remote_embeddings(self):
        import cli
        captured = []
        async def run(config, *args, **kwargs):
            captured.append(config.semantic_enabled)
            return 0
        with patch("cli.load_config", return_value=(AppConfig(embedding_backend="avalai"),Credentials())), patch("cli.run_cli",side_effect=run):
            self.assertEqual(cli.main(["--offline","--query","2x+5=17"]),0)
        self.assertEqual(captured,[False])


if __name__ == "__main__":
    unittest.main()
