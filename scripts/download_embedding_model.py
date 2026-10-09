"""Explicit opt-in model download; tutor runtime itself is strictly local-only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import load_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Destination; defaults to configured model directory or .cache/models/multilingual-e5-small")
    args = parser.parse_args(argv)
    try:
        config, _ = load_config()
        from huggingface_hub import snapshot_download
        destination = (args.output or config.embedding_model_dir or
                       config.embedding_cache_dir.parent / "models" / "multilingual-e5-small").resolve()
        identity = {"model_id": config.embedding_model, "revision": config.embedding_revision}
        marker = destination / ".math_tutor_model.json"
        if marker.exists() and json.loads(marker.read_text(encoding="utf-8")) != identity:
            print("Destination contains another model identity; choose a separate --output directory.")
            return 2
        snapshot_download(repo_id=config.embedding_model, revision=config.embedding_revision,
                          local_dir=str(destination), ignore_patterns=["onnx/*", "openvino/*"])
        marker.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
        print("Downloaded pinned model to " + str(destination))
        print("Set TUTOR_EMBEDDING_MODEL_DIR to this directory, then run cli.py --index.")
        return 0
    except Exception:
        print("Model download failed or its dependency is unavailable. Install requirements-embeddings.txt and retry on a network-enabled machine.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
