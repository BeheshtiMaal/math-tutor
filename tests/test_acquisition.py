import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/acquire_references.py"
spec = importlib.util.spec_from_file_location("acquisition", MODULE_PATH)
acquisition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acquisition)


class AcquisitionChecks(unittest.TestCase):
    def test_catalog_covers_unique_required_references_not_indexes(self):
        records = acquisition.catalog(acquisition.ROOT / "specs/math_tutor_download_links.md")
        self.assertEqual(len(records), 32)
        self.assertEqual(sum(r["kind"] == "openstax" for r in records), 4)
        self.assertEqual(sum(r["kind"] == "paul" for r in records), 25)
        self.assertEqual(len({r["local_path"] for r in records}), 32)
        self.assertFalse(any("/problems/" in r["source_url"] for r in records))

    def test_manifest_cannot_write_outside_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                acquisition.local_path(Path(directory), "../escaped.pdf")

    def test_wrong_file_and_missing_file_are_not_acquisitions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            r = acquisition.record("openstax", "test", "Test", "https://example.org/book", "pdf")
            acquisition.inventory(r, root, False)
            self.assertEqual(r["status"], "missing")
            self.assertIsNone(r["downloaded_bytes"])
            raw = acquisition.local_path(root, r["local_path"])
            raw.parent.mkdir(parents=True)
            raw.write_bytes(b"<html>Access denied</html>")
            with self.assertRaisesRegex(ValueError, "not PDF"):
                acquisition.inventory(r, root, False)

    def test_hidden_solutions_and_mathml_and_tex_survive(self):
        original = '<html><body><nav>unrelated navigation</nav><main><h1>Chain rule</h1><p>' + 'Instructional explanation. ' * 15 + '</p><div style="display:none">Example 1 solution: \\(x^2\\)</div><script type="math/tex; mode=display">\\frac{1}{x}</script><math><msup><mi>x</mi><mn>2</mn></msup></math></main></body></html>'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lesson.html"
            path.write_text(original, encoding="utf-8")
            text, checks = acquisition.html_text(path)
            self.assertIn("Example 1 solution", text)
            self.assertIn(r"\(x^2\)", text)
            self.assertIn(r"$$\frac{1}{x}$$", text)
            self.assertIn("<msup>", text)
            self.assertNotIn("unrelated navigation", text)
            self.assertEqual(checks["mathml_elements"], 1)

    def test_changed_raw_invalidates_quality_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            r = acquisition.record("paul", "test", "Test", "https://example.org/lesson", "html")
            raw = acquisition.local_path(root, r["local_path"])
            raw.parent.mkdir(parents=True)
            raw.write_text('<html><main>' + 'Lesson content. ' * 40 + '</main></html>')
            r["retrieved_at"] = acquisition.now()
            acquisition.inventory(r, root, True)
            r["quality_review"] = {"complete_reference": True, "formula_fidelity": True, "headings_and_assumptions": True, "terms_recorded": True, "reviewer": "fixture", "reviewed_at": acquisition.now(), "raw_sha256": r["sha256"], "text_sha256": r["text_sha256"]}
            acquisition.inventory(r, root, True)
            self.assertEqual(r["status"], "complete")
            acquisition.inventory(r, root, False)
            self.assertEqual(r["status"], "complete")
            raw.write_text(raw.read_text() + " changed")
            acquisition.inventory(r, root, True)
            self.assertEqual(r["status"], "converted_review_pending")
            self.assertNotIn("quality_review", r)

    def test_partial_transfer_is_not_promoted_to_original(self):
        class Response:
            url = "https://example.org/reference.pdf"
            headers = {"Content-Length": "100"}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size):
                if getattr(self, "sent", False): return b""
                self.sent = True
                return b"%PDF-1.7 truncated"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            r = acquisition.record("teaching", "test", "Test", Response.url, "pdf")
            with patch.object(acquisition, "request", return_value=Response()):
                with self.assertRaisesRegex(ValueError, "Incomplete transfer"):
                    acquisition.download(r, root)
            raw = acquisition.local_path(root, r["local_path"])
            self.assertFalse(raw.exists())
            self.assertTrue(raw.with_suffix(".pdf.partial").exists())


if __name__ == "__main__":
    unittest.main()
