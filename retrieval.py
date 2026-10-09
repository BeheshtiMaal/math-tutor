"""Local bilingual retrieval, structural chunks and hash-bound NumPy caches."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
from pathlib import Path
from uuid import uuid4

import numpy as np
from agent import Contract, EvidenceResult, SourceRecord, ExampleRecord, Provenance
from learning import LocalRetrievalClient, canonical_topic, matching, bounded
from pydantic import Field

PREPROCESSING = "structural-math-v1"


class EmbeddingUnavailable(ValueError):
    pass


class CacheIncompatible(ValueError):
    pass


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class LocalE5:
    """Lazy local-only adapter. Neither imports nor runtime queries download models."""
    def __init__(self, config):
        self.config = config
        self.model_id, self.revision = config.embedding_model, config.embedding_revision
        self.dimension, self.max_tokens = config.embedding_dimension, config.embedding_max_tokens
        self._model = None
        self.lock = threading.RLock()

    def load(self):
        with self.lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import SentenceTransformer
                directory = self.config.embedding_model_dir
                if directory:
                    identity = json.loads((directory / ".math_tutor_model.json").read_text(encoding="utf-8"))
                    if identity != {"model_id": self.model_id, "revision": self.revision}:
                        raise EmbeddingUnavailable("Local embedding model identity does not match configuration.")
                model = SentenceTransformer(str(directory) if directory else self.model_id,
                    revision=self.revision, local_files_only=True, trust_remote_code=False,
                    cache_folder=str(self.config.embedding_cache_dir.parent / "models"), device="cpu")
                dimension_method = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
                if dimension_method() != self.dimension or self.max_tokens > model.max_seq_length:
                    raise EmbeddingUnavailable("Embedding dimension or token limit does not match the local model.")
                self._model = model
                return model
            except EmbeddingUnavailable:
                raise
            except Exception:
                raise EmbeddingUnavailable("Local embedding package/model is unavailable; install/download it explicitly.") from None

    def count_tokens(self, text):
        # Count oversized candidates before structural splitting and inference.
        # Preserve the full count without emitting an inference warning.
        return len(self.load().tokenizer.encode("passage: " + text, add_special_tokens=True, truncation=False, verbose=False))

    def encode(self, texts, *, query=False):
        with self.lock:
            model = self.load()
            prefix = "query: " if query else "passage: "
            inputs = [prefix + text for text in texts]
            if any(len(model.tokenizer.encode(text, add_special_tokens=True, truncation=False, verbose=False)) > self.max_tokens for text in inputs):
                raise EmbeddingUnavailable("A complete embedding input exceeds the model token limit.")
            return model.encode(inputs, normalize_embeddings=True, convert_to_numpy=True,
                                show_progress_bar=False, batch_size=16)


class Chunk(Contract):
    id: str
    record_id: str
    parent_id: str
    text: str
    context: str = ""
    content_hash: str
    previous_id: str | None = None
    next_id: str | None = None


def paragraphs(text):
    """Only split at structural boundaries outside display math/code fences."""
    units, current, fence = [], [], None
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if fence is None:
            if stripped.startswith("```"):
                fence = "```"
            elif stripped.startswith("$$") and stripped.count("$$") == 1:
                fence = "$$"
            elif r"\[" in stripped and r"\]" not in stripped:
                fence = r"\]"
            elif re.search(r"\\begin\{(equation\*?|align\*?|gather\*?)\}", stripped):
                environment = re.search(r"\\begin\{(equation\*?|align\*?|gather\*?)\}", stripped).group(1)
                if "\\end{" + environment + "}" not in stripped:
                    fence = "\\end{" + environment + "}"
        elif (fence == "```" and stripped.startswith("```")) or (fence == "$$" and "$$" in stripped) or (fence.startswith("\\") and fence in stripped):
            fence = None
        boundary = fence is None and (not stripped or re.match(r"^(?:#{1,6} |(?:Definition|Theorem|Rule|Example|فرض|تعریف|قضیه|مثال)\b)", stripped, re.I))
        if boundary and current:
            units.append("".join(current).strip())
            current = []
        if stripped or fence is not None:
            current.append(line)
    if current:
        units.append("".join(current).strip())
    return [unit for unit in units if unit]


def heading_sections(text):
    sections, current, title = [], [], "Introduction"
    for unit in paragraphs(text):
        if re.match(r"^#{1,6} ", unit):
            if current:
                sections.append((title, "\n\n".join(current)))
            title, current = unit.splitlines()[0].lstrip("# "), []
        current.append(unit)
    if current:
        sections.append((title, "\n\n".join(current)))
    return sections


def record_key(record):
    return ("example:" + record.example_id) if isinstance(record, ExampleRecord) else "source:" + record.id


def embedding_text(record, text, context=""):
    tags = [record.topic, record.subtopic or "", record.learner_level or "any", record.provenance.section_title]
    if isinstance(record, ExampleRecord):
        tags.extend([record.course, record.source_example_label])
    return " | ".join(tags) + "\n" + (context + "\n\n" if context else "") + text


def make_chunks(records, embedder):
    chunks, warnings = [], []
    for record in records:
        key = record_key(record)
        full = record.statement + "\n\n" + record.solution if isinstance(record, ExampleRecord) else record.text
        units = paragraphs(record.solution if isinstance(record, ExampleRecord) else record.text)
        context = record.statement if isinstance(record, ExampleRecord) else "\n\n".join(
            unit for unit in units if re.match(r"^(?:#{1,6}\s*)?(?:assum\w*|domain|where|let|defined|for positive|provided|hypothes\w*|definition|فرض|دامنه|نماد)\b", unit, re.I))
        if embedder.count_tokens(embedding_text(record, full)) <= embedder.max_tokens:
            groups = [(full, "")]
        else:
            groups, pending = [], ""
            for unit in units:
                anchor = context if unit != context else ""
                proposed = pending + "\n\n" + unit if pending else unit
                if embedder.count_tokens(embedding_text(record, proposed, anchor)) <= embedder.max_tokens:
                    pending = proposed
                else:
                    if pending:
                        groups.append((pending, context if pending != context else ""))
                        pending = ""
                    if embedder.count_tokens(embedding_text(record, unit, anchor)) <= embedder.max_tokens:
                        pending = unit
                    else:
                        warnings.append(f"{key}: an indivisible unit plus its assumptions exceeds the token limit; omitted without truncation.")
            if pending:
                groups.append((pending, context if pending != context else ""))
        own = []
        for index, (text, anchor) in enumerate(groups):
            payload = embedding_text(record, text, anchor)
            if embedder.count_tokens(payload) > embedder.max_tokens:
                warnings.append(f"{key}: linked context exceeds token limit; unit omitted.")
                continue
            own.append(Chunk(id=digest(f"{key}:{index}")[:24], record_id=key, parent_id=key,
                             text=text, context=anchor, content_hash=digest(payload)))
        for index, chunk in enumerate(own):
            chunk.previous_id = own[index - 1].id if index else None
            chunk.next_id = own[index + 1].id if index + 1 < len(own) else None
        chunks.extend(own)
    return chunks, list(dict.fromkeys(warnings))


_LOCKS, _LOCK_GUARD = {}, threading.Lock()


class VectorIndex:
    """Atomic single-file cache per evidence type; no pickle or database service."""
    def __init__(self, path, embedder):
        self.path, self.embedder = Path(path), embedder
        with _LOCK_GUARD:
            self.lock = _LOCKS.setdefault(str(self.path.resolve()), threading.RLock())

    def settings(self):
        return {"model_id": self.embedder.model_id, "revision": self.embedder.revision,
                "dimension": self.embedder.dimension, "normalization": "l2", "metric": "cosine",
                "max_tokens": self.embedder.max_tokens, "preprocessing_version": PREPROCESSING,
                "document_prefix": "passage: ", "query_prefix": "query: "}

    def validate_vectors(self, values, count):
        vectors = np.asarray(values, dtype=np.float32)
        if vectors.shape != (count, self.embedder.dimension) or not np.isfinite(vectors).all():
            raise CacheIncompatible("Embedding/cache vectors have invalid dimensions or nonfinite values.")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if np.any(norms <= 0):
            raise CacheIncompatible("Embedding/cache contains a zero vector.")
        return vectors / norms

    def load(self):
        try:
            if self.path.stat().st_size > 128_000_000:
                raise CacheIncompatible("Embedding cache exceeds size limit.")
            with np.load(self.path, allow_pickle=False) as data:
                manifest = json.loads(str(data["manifest"].item()))
                if manifest["settings"] != self.settings():
                    raise CacheIncompatible("Embedding cache model/settings mismatch; explicit rebuild required.")
                chunks = [Chunk.model_validate(row) for row in manifest["chunks"]]
                if len({chunk.id for chunk in chunks}) != len(chunks):
                    raise CacheIncompatible("Embedding cache has duplicate chunk IDs.")
                vectors = self.validate_vectors(data["vectors"], len(chunks))
                return manifest, chunks, vectors
        except CacheIncompatible:
            raise
        except Exception:
            raise CacheIncompatible("Embedding cache is corrupt or incompatible; explicit rebuild required.") from None

    def sync(self, records, *, rebuild=False):
        with self.lock:
            if len(records) > 32768:
                raise EmbeddingUnavailable("Corpus exceeds the configured local index record budget; coverage is incomplete.")
            previous, old_vectors = {}, None
            if self.path.exists() and not rebuild:
                _, old_chunks, old_vectors = self.load()
                previous = {chunk.id: (index, chunk.content_hash) for index, chunk in enumerate(old_chunks)}
            chunks, warnings = make_chunks(records, self.embedder)
            if len(chunks) > 32768:
                raise EmbeddingUnavailable("Corpus exceeds the local index chunk budget; coverage is incomplete.")
            changed = [chunk for chunk in chunks if chunk.id not in previous or previous[chunk.id][1] != chunk.content_hash]
            lookup = {record_key(record): record for record in records}
            encoded = self.validate_vectors(self.embedder.encode([embedding_text(lookup[chunk.record_id], chunk.text, chunk.context) for chunk in changed]), len(changed)) if changed else np.empty((0, self.embedder.dimension), np.float32)
            new = {chunk.id: vector for chunk, vector in zip(changed, encoded)}
            vectors = np.stack([new[chunk.id] if chunk.id in new else old_vectors[previous[chunk.id][0]] for chunk in chunks]) if chunks else np.empty((0, self.embedder.dimension), np.float32)
            manifest = {"settings": self.settings(), "chunks": [chunk.model_dump() for chunk in chunks],
                        "records": {key: record.model_dump(mode="json") for key, record in lookup.items()},
                        "warnings": warnings}
            if chunks:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_name(self.path.name + "." + uuid4().hex + ".tmp")
                try:
                    with temporary.open("wb") as output:
                        np.savez_compressed(output, manifest=np.array(json.dumps(manifest, ensure_ascii=False)), vectors=vectors)
                    temporary.replace(self.path)
                finally:
                    temporary.unlink(missing_ok=True)
            elif self.path.exists():
                self.path.unlink()
            return chunks, vectors, {"logical_records": len(lookup), "chunks": len(chunks), "embedded": len(changed),
                                     "reused": len(chunks) - len(changed), "warnings": warnings}

    def rank(self, records, query, eligible_ids=None):
        chunks, vectors, report = self.sync(records)
        if not chunks:
            raise EmbeddingUnavailable("No complete structural units fit the embedding token budget.")
        query_vector = self.validate_vectors(self.embedder.encode([query], query=True), 1)[0]
        selected = [index for index, chunk in enumerate(chunks) if eligible_ids is None or chunk.record_id in eligible_ids]
        scores = vectors[selected] @ query_vector
        return [chunks[selected[index]] for index in np.argsort(-scores, kind="stable")], report


TRANSLATIONS = {
    "مشتق": "derivative", "شیب": "slope derivative", "نرخ": "rate derivative", "تغییر": "change",
    "انتگرال": "integral", "مساحت": "area integral", "حد": "limit", "نزدیک": "approach limit",
    "ماتریس": "matrix", "احتمال": "probability", "معادله": "equation algebra", "توان": "power",
    "زنجیره": "chain", "جایگذاری": "substitution", "steepness": "slope derivative",
    "instantaneous": "rate derivative", "derivatives": "derivative", "integrals": "integral",
}


def terms(text):
    words = re.findall(r"\w+", text.lower().replace("ي", "ی").replace("ك", "ک"))
    return set(word for value in words for word in (value + " " + TRANSLATIONS.get(value, "")).split())


def keyword_rank(records, query):
    query_terms = terms(query) - {"explain", "the", "a", "of", "me", "how", "what", "is", "را", "چیست", "بده"}
    def score(record):
        text = record.statement + " " + record.solution if isinstance(record, ExampleRecord) else record.text
        return len(query_terms & terms(text)) + 2 * len(query_terms & terms(record.topic + " " + (record.subtopic or "")))
    return sorted(records, key=lambda record: (-score(record), record.id))


class SemanticRetrievalClient(LocalRetrievalClient):
    """Default file/vector adapter; injectable embeddings never replace LangGraph."""
    def __init__(self, config, math_runner, *, embedding_client=None):
        super().__init__(config, math_runner)
        self.embedder = embedding_client or LocalE5(config)
        self.indexes = {kind: VectorIndex(config.embedding_cache_dir / (kind + ".npz"), self.embedder) for kind in ["sources", "examples"]}

    def load_sources(self):
        records, warning = super().load_sources()
        # Converted, reviewed text uses the same explicit provenance sidecar format.
        directory = self.root / "text"
        invalid = False
        # Raw Phase 3 extracts are deliberately unreviewed, not broken runtime
        # evidence. Exclude them even if a sidecar is added before review.
        unreviewed = set()
        manifest_path = self.root / "manifests/openstax_core.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(self.read_file(manifest_path))
                for book in manifest["books"]:
                    if book.get("extraction_status") != "reviewed":
                        unreviewed.add((self.root.parent / book["text_path"]).resolve())
            except (ValueError, OSError, KeyError, TypeError):
                invalid = True
        paths = [path for path in directory.rglob("*") if path.suffix in {".md", ".txt"}] if directory.is_dir() else []
        if len(paths) > 512:
            return records, "Converted corpus exceeds the file-count budget; coverage is incomplete."
        for path in sorted(paths):
            if path.suffix not in {".md", ".txt"}:
                continue
            if path.resolve() in unreviewed:
                continue
            try:
                metadata = json.loads(self.read_file(path.with_suffix(".metadata.json")))
                provenance = Provenance.model_validate(metadata["provenance"])
                if path.stat().st_size > 64_000_000:
                    raise ValueError("Converted source exceeds read budget")
                seen = {}
                for title, text in heading_sections(path.read_text(encoding="utf-8-sig")):
                    seen[title] = seen.get(title, 0) + 1
                    section = metadata.get("sections", {}).get(title, metadata)
                    identity = "text:" + path.relative_to(directory).as_posix() + ":" + digest(title)[:16] + ":" + str(seen[title])
                    records.append(SourceRecord(id=identity, topic=section.get("topic", metadata["topic"]),
                        learner_level=section.get("learner_level"), subtopic=section.get("subtopic"),
                        text=text, provenance=provenance.model_copy(update={"section_title": title})))
            except (ValueError, OSError, KeyError, TypeError):
                invalid = True
        unique = {}
        for record in records:
            key = record_key(record)
            if key in unique and unique[key] != record:
                invalid = True
                continue
            unique[key] = record
        if records and warning and "missing" in warning.lower() and not (self.root / "topics").is_dir():
            warning = None
        if invalid:
            warning = "Some source files/IDs have invalid or missing provenance and were excluded."
        return list(unique.values()), warning

    def eligible(self, records, request, kind):
        if kind == "examples":
            return [record for record in records if matching(record, request)], False
        order = {"beginner": 0, "intermediate": 1, "advanced": 2}
        compatible = [record for record in records if record.learner_level is None or order[record.learner_level] <= order[request.learner_level]]
        exact = [record for record in compatible if canonical_topic(record.topic) == canonical_topic(request.topic)
                 and (request.subtopic is None or record.subtopic in {None, request.subtopic})]
        return (exact, False) if exact else (compatible, bool(compatible))

    def retrieve(self, request, kind):
        records, warning = self.load_sources() if kind == "sources" else self.load_examples()
        eligible, broader = self.eligible(records, request, kind)
        method, ranked = "keyword", keyword_rank(eligible, request.query)
        reasons = [warning] if warning else []
        if broader:
            reasons.append("No exact inferred-topic coverage; a broader compatible-source search was used.")
        if records and self.config.semantic_enabled:
            try:
                ids = {record_key(record): record for record in eligible}
                chunks, report = self.indexes[kind].rank(records, request.query, set(ids))
                ranked, seen = [], set()
                for chunk in chunks:
                    if chunk.record_id not in ids:
                        continue
                    record = ids[chunk.record_id]
                    if kind == "examples":
                        if record.example_id in seen:
                            continue
                        seen.add(record.example_id)
                    else:
                        record = record.model_copy(update={"id": chunk.id, "text": (chunk.context + "\n\n" if chunk.context else "") + chunk.text,
                            "parent_id": chunk.parent_id, "previous_chunk_id": chunk.previous_id, "next_chunk_id": chunk.next_id})
                    ranked.append(record)
                method = "semantic"
                reasons.extend(report["warnings"])
            except Exception as exc:
                safe = str(exc) if isinstance(exc, (EmbeddingUnavailable, CacheIncompatible)) else "Embedding service failed safely."
                reasons.append(safe + " Using labelled keyword/metadata fallback.")
        elif records:
            reasons.append("Semantic embeddings are disabled; using keyword/metadata fallback.")
        if kind == "examples":
            ranked = [self._verify(record) for record in ranked[:3]]
            ranked = [record for record in ranked if record.verification_status != "rejected"]
            request = request.model_copy(update={"max_records": min(request.max_records, 3)})
            if not ranked and not warning:
                reasons.append("No suitable Paul example exists for this topic and learner level.")
        result = bounded(ranked, request, " ".join(dict.fromkeys(reasons)) or None)
        return result.model_copy(update={"retrieval_method": method, "broader_search": broader})

    async def read_source(self, request):
        return await asyncio.to_thread(self.retrieve, request, "sources")

    async def verified_examples(self, request):
        return await asyncio.to_thread(self.retrieve, request, "examples")

    def build_indexes(self, *, rebuild=False):
        reports = {}
        for kind, loader in [("sources", self.load_sources), ("examples", self.load_examples)]:
            records, warning = loader()
            if not records:
                reports[kind] = {"status": "empty", "logical_records": 0, "warning": warning}
                continue
            try:
                _, _, report = self.indexes[kind].sync(records, rebuild=rebuild)
                reports[kind] = {"status": "success" if report["chunks"] else "empty", **report}
            except (ValueError, OSError):
                reports[kind] = {"status": "error", "warning": "Embedding model/cache unavailable or incompatible; no successful index build."}
        return reports
