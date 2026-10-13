"""Rebuild the embedding indexes with cache reuse and record model, dimension and content hashes.

Phase W3 task 6. ``VectorIndex.sync`` reuses every chunk whose content hash is
unchanged and only embeds what is new or edited, so re-running this after a note
edit costs one request per changed chunk, not a full re-embed. The report records
what actually happened: embedded vs reused counts, the settings the cache was
built under, and an aggregate content hash per index.

Writes ``sources/manifests/embedding_index_report.json``.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import load_config, run_math_worker  # noqa: E402
from retrieval import SemanticRetrievalClient  # noqa: E402


def cache_facts(path):
    """Read back what the cache actually stores, so the report is evidence, not intent."""
    if not path.exists():
        return dict(exists=False)
    with np.load(path, allow_pickle=False) as data:
        manifest = json.loads(str(data["manifest"].item()))
        vectors = data["vectors"]
    chunks = manifest["chunks"]
    digest = hashlib.sha256()
    for chunk in sorted(chunks, key=lambda row: row["id"]):
        digest.update(f"{chunk['id']}:{chunk['content_hash']}\n".encode("utf-8"))
    return dict(exists=True, bytes=path.stat().st_size, settings=manifest["settings"],
                chunks=len(chunks), records=len(manifest.get("records", {})),
                vector_shape=list(vectors.shape), dtype=str(vectors.dtype),
                aggregate_content_hash=digest.hexdigest(), warnings=manifest.get("warnings", []))


def main():
    config, credentials = load_config()
    if config.embedding_backend != "avalai":
        print("TUTOR_EMBEDDING_BACKEND must be avalai for the curated index build.", file=sys.stderr)
        return 2

    client = SemanticRetrievalClient(config, run_math_worker, credentials=credentials)
    reports = client.build_indexes()

    indexes = {}
    for kind in ("sources", "examples"):
        indexes[kind] = dict(sync=reports[kind], cache=cache_facts(config.embedding_cache_dir / f"{kind}.npz"))

    payload = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        curation_phase="W3",
        backend=config.embedding_backend,
        model=config.embedding_model,
        revision=config.embedding_revision,
        dimension=config.embedding_dimension,
        max_tokens=config.embedding_max_tokens,
        cache_dir=str(config.embedding_cache_dir.relative_to(ROOT)),
        semantic_enabled=config.semantic_enabled,
        api_requests=client.embedder.requests,
        prompt_tokens=client.embedder.prompt_tokens,
        local_embedding_model_loaded=False,
        indexes=indexes,
        note="'embedded' counts chunks sent to the provider this run; 'reused' counts chunks whose "
             "content hash was unchanged and whose stored vector was kept. Raw unreviewed book "
             "extracts are excluded from the index by extraction_status.",
    )
    destination = ROOT / "sources/manifests/embedding_index_report.json"
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for kind, entry in indexes.items():
        sync, cache = entry["sync"], entry["cache"]
        print(f"{kind}: status={sync.get('status')} records={sync.get('logical_records')} "
              f"chunks={sync.get('chunks')} embedded={sync.get('embedded')} reused={sync.get('reused')} "
              f"dim={cache.get('vector_shape')} hash={str(cache.get('aggregate_content_hash'))[:16]}")
    print(f"api_requests={client.embedder.requests} prompt_tokens={client.embedder.prompt_tokens}")
    failed = [kind for kind, entry in indexes.items() if entry["sync"].get("status") != "success"]
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
