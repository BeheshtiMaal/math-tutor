"""Finite acquisition/selection integrity, independent of network and private corpus."""
import io
from contextlib import redirect_stdout
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_core_sources as core
import prepare_paul_examples as paul

HTML = r'''<html><title>Fixture lesson</title><div class="example">
<span class="example-title">Example 7</span><p>Differentiate on x&gt;0.</p>
<ol class="example_parts_list"><li>\(x^2\)</li><li>\(x^3\)</li></ol>
<div class="example-content"><details class="sh"><summary><span class="soln-list-subitem">a</span> Show Solution</summary>
<div class="soln-content"><p>Use the power rule.</p>\[2x\]<p>Units m<sup>2</sup>.</p><img src="plot.png" alt="A described curve"></div></details>
<details class="sh"><summary><span class="soln-list-subitem">b</span> Show Solution</summary><div class="soln-content">\[3x^2\]</div></details></div></div></html>'''


def selection():
    return dict(page="CalcI/DiffFormulas", example=7, part="a", topic="derivative", subtopic="power rule", level="beginner")


class Phase3Checks(unittest.TestCase):
    def test_download_allowlist_and_wrong_response_remain_failed(self):
        self.assertEqual(len(core.BOOKS), 4)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                core.prepare_book(("Extra book", "extra"), root, download=True)
            response = io.BytesIO(b"<html>not a PDF</html>")
            response.headers = {}  # Missing Content-Length is unknown, not zero.
            with patch.object(core, "resolve_book", return_value={"pdf_url": "https://assets.openstax.org/book.pdf"}), patch.object(core, "fetch", return_value=response):
                record = core.prepare_book(core.BOOKS[0], root, download=True)
            self.assertEqual(record["download_status"], "failed")
            self.assertIsNone(record["actual_file_size_bytes"])
            self.assertIsNone(record["reported_content_length"])
            self.assertGreater(record["partial_transfer_bytes"], 0)
            self.assertFalse((root / record["raw_path"]).exists())

    def test_incomplete_transfer_is_not_promoted(self):
        with tempfile.TemporaryDirectory() as temporary:
            response = io.BytesIO(b"%PDF-short")
            response.headers = {"Content-Length": "999"}
            with patch.object(core, "resolve_book", return_value={"pdf_url": "https://assets.openstax.org/book.pdf"}), patch.object(core, "fetch", return_value=response):
                row = core.prepare_book(core.BOOKS[0], Path(temporary), download=True)
            self.assertEqual(row["download_status"], "failed")
            self.assertIn("Incomplete transfer", row["failure"]["message"])

    def test_selected_problem_solution_tex_conditions_and_diagram_survive(self):
        row = paul.extract(HTML, selection(), "2026-10-09T00:00:00Z")
        self.assertIn("x>0", row.statement)
        self.assertIn(r"\(x^2\)", row.statement)
        self.assertNotIn(r"\(x^3\)", row.statement)
        self.assertIn(r"\[2x\]", row.solution)
        self.assertIn("m^{2}", row.solution)
        self.assertIn("A described curve", row.solution)
        self.assertIn("/Classes/CalcI/plot.png", row.solution)
        self.assertEqual(row.source_example_label, "Example 7 (a)")
        self.assertEqual(row.provenance.source_author, "Paul Dawkins")

    def test_missing_solution_never_becomes_a_success(self):
        with self.assertRaises(ValueError):
            paul.extract(HTML.replace('class="soln-content"', 'class="missing"'), selection(), "2026-10-09T00:00:00Z")

    def test_import_dedup_reuse_and_quota_are_atomic(self):
        record = paul.extract(HTML, selection(), "2026-10-09T00:00:00Z")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "selected.jsonl"
            paul.import_records(path, [record, record])
            self.assertEqual(len(paul.import_records(path, [record])), 1)
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                paul.import_records(path, [record.model_copy(update={"learner_level": "advanced"})])
            extra = [record.model_copy(update={"id": f"extra:{i}", "example_id": f"extra:{i}"}) for i in range(3)]
            with self.assertRaises(ValueError):
                paul.import_records(path, extra)
            self.assertEqual(path.read_bytes(), before)

    def test_plan_is_finite_unique_and_records_level_gaps(self):
        plan = paul.plan()
        self.assertEqual(len(plan), 51)
        self.assertEqual(len({r["page"] for r in plan}), 8)
        self.assertEqual(len({(r["page"], r["example"], r["part"]) for r in plan}), 51)
        from collections import Counter
        counts = Counter((r["topic"], r["subtopic"], r["level"]) for r in plan)
        self.assertLessEqual(max(counts.values()), 3)
        self.assertEqual(counts[("matrix", "augmented systems", "advanced")], 0)

    def test_repeat_inventory_preserves_reviews_but_never_invents_missing_downloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "sources/manifests/openstax_core.json"
            path.parent.mkdir(parents=True)
            prior = [dict(title=title, raw_sha256=slug, download_status="downloaded", retrieved_at="2026-10-09T00:00:00Z",
                extraction_status="incomplete", extraction_problems={}, text_size_bytes=10, text_sha256="text", page_count=50,
                formula_review=dict(observations=["Missing image formulas"]), formula_review_status="spot_checked_problems_found") for title, slug in core.BOOKS]
            path.write_text(json.dumps(dict(books=prior)), encoding="utf-8")
            fresh = [dict(title=title, raw_sha256=slug, download_status="existing_local", actual_file_size_bytes=100,
                         partial_transfer_bytes=0, transferred_this_run_bytes=0, extraction_status="not_attempted", extraction_problems=[]) for title, slug in core.BOOKS]
            def prepared(book, **kwargs):
                return deepcopy(fresh[core.BOOKS.index(book)])
            with patch.object(core, "ROOT", root), patch.object(core, "prepare_book", side_effect=prepared), redirect_stdout(io.StringIO()):
                self.assertEqual(core.main(["--download"]), 2)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["total_extracted_text_bytes"], 40)
            self.assertTrue(all(b["extraction_status"] == "incomplete" for b in saved["books"]))
            for row in fresh:
                row.pop("raw_sha256")
                row.update(download_status="not_attempted", actual_file_size_bytes=None)
            with patch.object(core, "ROOT", root), patch.object(core, "prepare_book", side_effect=prepared), redirect_stdout(io.StringIO()):
                self.assertEqual(core.main(["--extract"]), 2)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["total_actual_download_bytes"], 0)
            self.assertFalse(any(b["download_status"] == "downloaded" for b in saved["books"]))


if __name__ == "__main__":
    unittest.main()
