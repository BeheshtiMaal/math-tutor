"""Render recorded spot checks and apply hash-bound visual formula-review findings."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from prepare_core_sources import ROOT, sha


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", action="store_true", help="Render reviewed pages locally (requires PyMuPDF)")
    args = parser.parse_args(argv)
    path = ROOT / "sources/manifests/openstax_core.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    reviews = json.loads((ROOT / "sources/manifests/formula_reviews.json").read_text(encoding="utf-8"))
    for book in manifest["books"]:
        review = reviews.get(Path(book["raw_path"]).stem)
        if not review or review["raw_sha256"] != sha(ROOT / book["raw_path"]):
            raise ValueError("Missing or stale manual review for " + book["title"])
        book["formula_review_status"] = "spot_checked_problems_found"
        book["formula_review"] = review
        book["extraction_problems"]["observed_formula_problems"] = review["observations"]
        book["extraction_status"] = "incomplete"
        if args.render:
            import pymupdf
            output = ROOT / ".cache/phase3/review"
            output.mkdir(parents=True, exist_ok=True)
            with pymupdf.open(ROOT / book["raw_path"]) as pdf:
                for page in review["pdf_pages"]:
                    pdf[page-1].get_pixmap(matrix=pymupdf.Matrix(1, 1)).save(output / (Path(book["raw_path"]).stem + f"-{page}.png"))
    manifest["phase3_formula_exit"] = "incomplete: readable prose extracted, representative formulas lost or flattened; raw extracts excluded from teaching and embeddings"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(manifest["phase3_formula_exit"])


if __name__ == "__main__":
    main()
