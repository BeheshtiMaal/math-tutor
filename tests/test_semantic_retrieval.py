"""Cache/chunk/graph acceptance. Toy embeddings test plumbing, not E5 quality."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
from langgraph.types import Command
import agent
from retrieval import (SemanticRetrievalClient, VectorIndex, CacheIncompatible, LocalE5,
                       EmbeddingUnavailable, make_chunks, paragraphs, heading_sections)
from test_learning_graph import provenance, example


def setUpModule():
    global env
    env = patch.dict(os.environ, {"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false", "LANGCHAIN_TRACING": "false"})
    env.start()


def tearDownModule():
    env.stop()


class ToyEmbeddings:
    """Deterministic semantic service fixture; never labelled a tested real model."""
    model_id, revision, dimension, max_tokens = "test-only-bilingual", "fixture-v1", 4, 512
    def __init__(self):
        self.calls = []
    def count_tokens(self, text):
        return len(text.split()) + 3
    def encode(self, texts, *, query=False):
        self.calls.append((query, list(texts)))
        values = []
        for text in texts:
            text = text.lower()
            values.append([float(any(term in text for term in ["derivative", "slope", "steepness", "rate of change", "مشتق", "شیب", "نرخ تغییر"])),
                           float(any(term in text for term in ["limit", "approach", "حد", "نزدیک"])),
                           float(any(term in text for term in ["matrix", "determinant", "ماتریس"])), 0.05])
        return np.asarray(values, np.float32).reshape((-1, self.dimension))


def records():
    return [agent.SourceRecord(id="derivative-note", topic="derivative", text="The derivative is the instantaneous rate of change. It gives the slope of the tangent to a curve.", provenance=provenance()),
            agent.SourceRecord(id="limit-note", topic="limits", text="A limit describes the value approached by a function. A two-sided limit requires agreement from both sides.", provenance=provenance()),
            agent.SourceRecord(id="matrix-note", topic="matrix", text="A matrix is a rectangular array. For a square matrix the determinant detects singularity.", provenance=provenance())]


class RetrievalChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = agent.AppConfig(sources_dir=self.root / "sources", embedding_cache_dir=self.root / "cache")
        self.embedder = ToyEmbeddings()
        self.client = SemanticRetrievalClient(self.config, agent.run_math_worker, embedding_client=self.embedder)
        self.notes = records()
        self.write_notes()
        self.request = agent.EvidenceRequest(query="Explain the derivative", topic="derivative", learner_level="beginner", language="en", max_records=1)

    def tearDown(self):
        self.temp.cleanup()

    def write_notes(self):
        directory = self.config.sources_dir / "topics"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "notes.json").write_text(json.dumps([record.model_dump(mode="json") for record in self.notes]), encoding="utf-8")

    def write_bank(self, rows):
        directory = self.config.sources_dir / "examples" / "paul"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "derivative.jsonl").write_text("\n".join(row.model_dump_json() for row in rows), encoding="utf-8")

    async def test_fixed_english_persian_queries_and_distractors_return_actual_passages(self):
        for query, topic, expected in [("What is the instantaneous rate of change?", "derivative", "derivative-note"),
                                       ("شیب لحظه‌ای منحنی را توضیح بده", "mathematics", "derivative-note"),
                                       ("تابع به چه مقداری نزدیک می‌شود؟", "mathematics", "limit-note"),
                                       ("What does a determinant detect?", "matrix", "matrix-note")]:
            result = await self.client.read_source(self.request.model_copy(update={"query": query, "topic": topic}))
            self.assertEqual(result.retrieval_method, "semantic")
            self.assertEqual(result.records[0].parent_id, "source:" + expected)
            original = next(record for record in self.notes if record.id == expected)
            self.assertEqual(result.records[0].text, original.text)
            self.assertEqual(result.records[0].provenance, original.provenance)
        documents = [text for query, batch in self.embedder.calls if not query for text in batch]
        self.assertEqual(len(documents), 3)
        self.assertEqual(len([query for query, _ in self.embedder.calls if query]), 4)

    async def test_repeat_ingestion_restart_and_queries_reuse_document_vectors(self):
        first = self.client.build_indexes()
        self.assertEqual(first["sources"]["embedded"], 3)
        second = self.client.build_indexes()
        self.assertEqual(second["sources"]["embedded"], 0)
        self.assertEqual(second["sources"]["reused"], 3)
        fresh = ToyEmbeddings()
        restarted = SemanticRetrievalClient(self.config, agent.run_math_worker, embedding_client=fresh)
        await restarted.read_source(self.request)
        self.assertEqual([query for query, _ in fresh.calls], [True])
        manifest, chunks, vectors = self.client.indexes["sources"].load()
        self.assertEqual(len(chunks), 3)
        self.assertEqual(vectors.shape, (3, 4))
        self.assertEqual(manifest["settings"]["normalization"], "l2")
        self.assertEqual(manifest["settings"]["preprocessing_version"], "structural-math-v1")
        self.assertTrue(all(len(chunk.content_hash) == 64 for chunk in chunks))

    async def test_changed_content_only_reembeds_changed_chunk_and_deleted_record_disappears(self):
        self.client.build_indexes()
        self.notes[0] = self.notes[0].model_copy(update={"text": self.notes[0].text + " Preserve the variable's domain."})
        self.write_notes()
        changed = self.client.build_indexes()
        self.assertEqual(changed["sources"]["embedded"], 1)
        self.assertEqual(changed["sources"]["reused"], 2)
        self.notes = self.notes[:1]
        self.write_notes()
        removed = self.client.build_indexes()
        self.assertEqual(removed["sources"]["logical_records"], 1)
        self.assertEqual(removed["sources"]["chunks"], 1)

    async def test_model_settings_mismatch_is_explicit_and_requires_rebuild(self):
        self.client.build_indexes()
        self.embedder.revision = "fixture-v2"
        result = await self.client.read_source(self.request)
        self.assertEqual(result.retrieval_method, "keyword")
        self.assertIn("settings mismatch", result.warning)
        with self.assertRaises(CacheIncompatible):
            self.client.indexes["sources"].load()
        report = self.client.build_indexes(rebuild=True)
        self.assertEqual(report["sources"]["embedded"], 3)
        self.assertEqual((await self.client.read_source(self.request)).retrieval_method, "semantic")

    async def test_corrupt_or_wrong_dimension_vectors_fall_back_without_fake_semantics(self):
        index = self.client.indexes["sources"]
        self.client.build_indexes()
        manifest, _, _ = index.load()
        with index.path.open("wb") as output:
            np.savez(output, manifest=np.array(json.dumps(manifest)), vectors=np.ones((3, 2)))
        result = await self.client.read_source(self.request)
        self.assertEqual(result.retrieval_method, "keyword")
        self.assertIn("dimensions", result.warning)
        self.assertEqual(result.records[0].id, "derivative-note")
        index.path.write_bytes(b"not a vector archive")
        result = await self.client.read_source(self.request)
        self.assertEqual(result.retrieval_method, "keyword")
        self.assertIn("corrupt", result.warning)

    async def test_unavailable_model_labelled_bilingual_keyword_fallback_and_no_cache(self):
        class Missing(ToyEmbeddings):
            def count_tokens(self, text):
                raise EmbeddingUnavailable("Fixture model unavailable")
        client = SemanticRetrievalClient(self.config, agent.run_math_worker, embedding_client=Missing())
        result = await client.read_source(self.request.model_copy(update={"query": "نرخ تغییر لحظه‌ای چیست؟", "topic": "mathematics"}))
        self.assertEqual(result.retrieval_method, "keyword")
        self.assertIn("fallback", result.warning)
        self.assertEqual(result.records[0].id, "derivative-note")
        self.assertFalse(self.config.embedding_cache_dir.exists())

    async def test_example_level_filter_compact_quota_dedup_and_unknown_verification(self):
        self.write_bank([example(i) for i in range(1, 6)] + [example(1), example(1, "advanced")])
        first = await self.client.verified_examples(self.request)
        self.assertEqual(first.retrieval_method, "semantic")
        self.assertEqual(first.records[0].learner_level, "beginner")
        self.assertEqual(first.records[0].verification_status, "unknown")
        self.assertEqual(first.records[0].provenance, provenance())
        second = self.client.build_indexes()
        self.assertEqual(second["examples"]["logical_records"], 4)
        self.assertEqual(second["examples"]["embedded"], 0)
        advanced = await self.client.verified_examples(self.request.model_copy(update={"learner_level": "advanced"}))
        self.assertEqual(advanced.records[0].learner_level, "advanced")
        missing = await self.client.verified_examples(self.request.model_copy(update={"learner_level": "intermediate"}))
        self.assertEqual(missing.status, "empty")
        self.assertEqual(missing.records, [])

    async def test_linked_oversized_example_children_remain_one_logical_example(self):
        self.embedder.max_tokens = 65
        solution = "\n\n".join(f"Differentiate the expression in stage {index}. Keep the same variable and inspect the resulting derivative." for index in range(8))
        self.write_bank([example(solution=solution)])
        result = await self.client.verified_examples(self.request)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].solution, solution)
        manifest, chunks, _ = self.client.indexes["examples"].load()
        self.assertGreater(len(chunks), 1)
        self.assertEqual(len(manifest["records"]), 1)
        self.assertEqual(len({chunk.record_id for chunk in chunks}), 1)
        self.assertIsNone(chunks[0].previous_id)
        self.assertEqual(chunks[0].next_id, chunks[1].id)
        self.assertEqual(chunks[1].previous_id, chunks[0].id)
        self.assertTrue(all(chunk.context == example().statement for chunk in chunks))

    async def test_actual_graph_preserves_semantic_label_and_broader_evidence_no_new_nodes(self):
        graph = agent.build_graph(self.config, embedding_client=self.embedder)
        self.assertEqual(set(graph.get_graph().nodes), {*agent.NODE_NAMES, "__start__", "__end__"})
        thread = {"configurable": {"thread_id": "semantic-graph"}}
        state = agent.new_request_state(agent.Request(query="شیب لحظه‌ای چیست؟", topic="uncertain", mode="learn", language="fa"), self.config)
        first = await graph.ainvoke(state, thread)
        self.assertEqual(first["source"].retrieval_method, "semantic")
        self.assertTrue(first["source"].broader_search)
        self.assertTrue(any("tangent" in record.text for record in first["source"].records))
        doc_calls = len([query for query, _ in self.embedder.calls if not query])
        final = await graph.ainvoke(Command(resume="تمام"), thread)
        self.assertNotIn("__interrupt__", final)
        self.assertEqual(len([query for query, _ in self.embedder.calls if not query]), doc_calls)

    async def test_converted_heading_corpus_sidecars_and_changed_ids_preserve_provenance(self):
        directory = self.config.sources_dir / "text" / "book"
        directory.mkdir(parents=True)
        path = directory / "converted.md"
        path.write_text("# Derivatives\n" + self.notes[0].text + "\n\n# Limits\n" + self.notes[1].text, encoding="utf-8")
        path.with_suffix(".metadata.json").write_text(json.dumps({"topic": "calculus", "provenance": provenance().model_dump(mode="json"),
            "sections": {"Derivatives": {"topic": "derivative"}, "Limits": {"topic": "limits"}}}), encoding="utf-8")
        loaded, warning = self.client.load_sources()
        converted = [record for record in loaded if record.id.startswith("text:")]
        self.assertEqual(len(converted), 2)
        before = {record.provenance.section_title: record.id for record in converted}
        path.write_text("# Intro\nA newly inserted section.\n\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
        after, _ = self.client.load_sources()
        self.assertEqual({record.provenance.section_title: record.id for record in after if record.id in before.values()}, before)
        self.assertTrue(all(str(record.provenance.source_url) == str(provenance().source_url) for record in converted))

    async def test_bounded_context_returns_whole_record_or_explicit_empty(self):
        result = await self.client.read_source(self.request.model_copy(update={"max_chars": 256}))
        self.assertEqual(result.status, "empty")
        self.assertIn("budget", result.warning)

    async def test_registered_unreviewed_extract_is_not_a_provenance_error_or_evidence(self):
        path = self.config.sources_dir / "text/openstax/raw.md"
        path.parent.mkdir(parents=True)
        path.write_text("# Incomplete book\nFormula images omitted.", encoding="utf-8")
        manifest = self.config.sources_dir / "manifests/openstax_core.json"
        manifest.parent.mkdir(parents=True)
        relative = path.relative_to(self.config.sources_dir.parent).as_posix()
        manifest.write_text(json.dumps({"books": [{"text_path": relative, "extraction_status": "incomplete"}]}), encoding="utf-8")
        loaded, warning = self.client.load_sources()
        self.assertIsNone(warning)
        self.assertFalse(any("Incomplete book" in record.text for record in loaded))
        # Ordinary malformed evidence must still be diagnosed.
        (path.parent / "unexpected.md").write_text("# Missing metadata", encoding="utf-8")
        _, warning = self.client.load_sources()
        self.assertIn("missing provenance", warning)


class ChunkChecks(unittest.TestCase):
    def test_oversized_token_count_stays_complete_and_is_blocked_before_inference(self):
        calls = []
        def tokenize(text, **kwargs):
            calls.append(kwargs)
            return text.split()
        model = types.SimpleNamespace(tokenizer=types.SimpleNamespace(encode=tokenize),
                                      encode=lambda *args, **kwargs: self.fail("Oversized text reached model inference"))
        embedder = LocalE5(agent.AppConfig())
        embedder._model = model
        self.assertGreater(embedder.count_tokens("word " * 1106), 512)
        with self.assertRaises(EmbeddingUnavailable):
            embedder.encode(["word " * 1106])
        self.assertTrue(all(c["truncation"] is False and c["verbose"] is False for c in calls))

    def test_adapter_uses_local_only_pinned_identity_and_bilingual_prefixes(self):
        calls = []
        class Model:
            max_seq_length = 512
            tokenizer = types.SimpleNamespace(encode=lambda text, **kwargs: text.split())
            def __init__(self, name, **kwargs):
                calls.append((name, kwargs))
            def get_sentence_embedding_dimension(self):
                raise AssertionError("Prefer the current embedding dimension API")
            def get_embedding_dimension(self):
                return 384
            def encode(self, texts, **kwargs):
                calls.append((texts, kwargs))
                return np.ones((len(texts), 384), np.float32)
        module = types.SimpleNamespace(SentenceTransformer=Model)
        with tempfile.TemporaryDirectory() as directory, patch.dict("sys.modules", {"sentence_transformers": module}):
            config = agent.AppConfig(embedding_cache_dir=Path(directory) / "cache")
            embedder = LocalE5(config)
            embedder.encode(["A tangent slope."])
            embedder.encode(["شیب منحنی چیست؟"], query=True)
            self.assertTrue(calls[0][1]["local_files_only"])
            self.assertFalse(calls[0][1]["trust_remote_code"])
            self.assertEqual(calls[0][1]["revision"], config.embedding_revision)
            self.assertEqual(calls[1][0], ["passage: A tangent slope."])
            self.assertEqual(calls[2][0], ["query: شیب منحنی چیست؟"])
            self.assertTrue(calls[1][1]["normalize_embeddings"])
            config.embedding_model_dir = Path(directory)
            (Path(directory) / ".math_tutor_model.json").write_text(json.dumps({"model_id": "wrong", "revision": "wrong"}))
            with self.assertRaises(EmbeddingUnavailable):
                LocalE5(config).load()

    def test_cache_rejects_normalization_and_preprocessing_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            index = VectorIndex(Path(directory) / "index.npz", ToyEmbeddings())
            index.sync(records())
            manifest, _, vectors = index.load()
            for key, value in [("normalization", "none"), ("preprocessing_version", "obsolete")]:
                modified = json.loads(json.dumps(manifest))
                modified["settings"][key] = value
                np.savez_compressed(index.path, manifest=np.array(json.dumps(modified)), vectors=vectors)
                with self.assertRaises(CacheIncompatible):
                    index.load()

    def test_formula_boundaries_and_assumptions_in_linked_children(self):
        embedder = ToyEmbeddings()
        embedder.max_tokens = 60
        formula = "$$\nx^2\n\n+ 2*x + 1\n$$"
        text = "Assume x is real and positive.\n\n" + formula + "\n\n" + "\n\n".join("The derivative preserves this stated assumption while the next mathematical paragraph gives another coherent instructional unit." for _ in range(6))
        record = records()[0].model_copy(update={"text": text})
        chunks, warnings = make_chunks([record], embedder)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(any(formula in chunk.text for chunk in chunks))
        self.assertTrue(all("Assume x" in chunk.text + chunk.context for chunk in chunks))
        self.assertTrue(all(embedder.count_tokens(chunk.text + " " + chunk.context) <= embedder.max_tokens for chunk in chunks))
        self.assertEqual(chunks[0].next_id, chunks[1].id)

    def test_indivisible_oversized_formula_not_cut_or_claimed_embedded(self):
        embedder = ToyEmbeddings()
        embedder.max_tokens = 40
        formula = "$$\n" + " + ".join("x" for _ in range(100)) + "\n$$"
        record = records()[0].model_copy(update={"text": formula})
        chunks, warnings = make_chunks([record], embedder)
        self.assertEqual(chunks, [])
        self.assertIn("without truncation", warnings[0])
        self.assertEqual(paragraphs(formula), [formula])

    def test_display_environment_blank_lines_do_not_split_math(self):
        formula = r"\begin{align}" + "\nx^2\n\n+1\n" + r"\end{align}"
        self.assertEqual(paragraphs(formula), [formula])
        self.assertEqual(len(heading_sections("# One\n" + formula + "\n\n# Two\nOther text.")), 2)

    def test_nonfinite_or_zero_embeddings_are_rejected(self):
        index = VectorIndex("unused.npz", ToyEmbeddings())
        for values in [np.zeros((1, 4)), np.full((1, 4), np.nan), np.ones((1, 3))]:
            with self.assertRaises(CacheIncompatible):
                index.validate_vectors(values, 1)


@unittest.skipUnless(importlib.util.find_spec("sentence_transformers"), "Actual multilingual E5 acceptance blocked: embedding package/model unavailable")
class ActualE5Checks(unittest.TestCase):
    def test_real_model_persian_english_paraphrases_against_english_passages(self):
        config, _ = agent.load_config()
        embedder = LocalE5(config)
        try:
            vectors = embedder.encode([record.text for record in records()])
        except EmbeddingUnavailable as exc:
            self.skipTest(str(exc))
        for query, expected in [("Explain the instantaneous rate of change", 0), ("شیب لحظه‌ای و نرخ تغییر تابع چیست؟", 0), ("تابع به چه مقداری نزدیک می‌شود؟", 1)]:
            query_vector = embedder.encode([query], query=True)[0]
            self.assertEqual(int(np.argmax(vectors @ query_vector)), expected)


if __name__ == "__main__":
    unittest.main()
