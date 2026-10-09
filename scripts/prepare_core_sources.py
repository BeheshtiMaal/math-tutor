"""Phase 3: four-book allowlisted acquisition and measured PDF extraction only."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit, urlencode
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
BOOKS = [("Calculus Volume 1", "calculus-volume-1"), ("Calculus Volume 2", "calculus-volume-2"),
         ("College Algebra 2e", "college-algebra-2e"), ("Introductory Statistics 2e", "introductory-statistics-2e")]


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def fetch(url):
    if urlsplit(url).scheme != "https" or urlsplit(url).hostname not in {"openstax.org", "assets.openstax.org"}:
        raise ValueError("Only official OpenStax endpoints are allowed")
    return urlopen(Request(url, headers={"User-Agent": "MathTutor-PrivatePreparation/0.3", "Accept-Encoding": "identity"}), timeout=60)


def read_url(url):
    with fetch(url) as response:
        data = response.read(8_000_001)
    if len(data) > 8_000_000:
        raise ValueError("Discovery response exceeds budget")
    return data


def resolve_book(title, slug):
    """Resolve the official page's discovered app CMS, not a guessed PDF filename."""
    source = "https://openstax.org/details/books/" + slug
    page = read_url(source)
    soup = BeautifulSoup(page, "html.parser")
    scripts = [urljoin(source, tag["src"]) for tag in soup.find_all("script", src=True) if "/main-" in tag["src"]]
    if len(scripts) != 1:
        raise ValueError("Official page app bundle cannot be identified")
    bundle = read_url(scripts[0]).decode("utf-8")
    api = re.search(r'["\x27](/apps/cms/api/v2)["\x27]', bundle)
    if not api:
        raise ValueError("Official app CMS endpoint not found")
    listing = urljoin(source, api.group(1) + "/pages/?" + urlencode({"slug": slug}))
    rows = json.loads(read_url(listing))["items"]
    candidates = [row for row in rows if row["meta"]["type"] == "books.Book" and row["meta"]["slug"] == slug]
    if len(candidates) != 1:
        raise ValueError("Official CMS book is ambiguous or missing")
    detail_url = candidates[0]["meta"]["detail_url"]
    detail = json.loads(read_url(detail_url))
    if detail["title"].strip().casefold() != title.casefold():
        raise ValueError("Resolved book title does not match allowlist")
    pdf = detail.get("pdf_url")
    if not pdf:
        raise ValueError("Official book has no PDF link")
    return {"pdf_url": pdf, "license": " ".join(filter(None, [detail.get("license_name"), detail.get("license_version")])),
            "license_url": detail.get("license_url"), "license_text": BeautifulSoup(detail.get("license_text") or "", "html.parser").get_text(" ", strip=True),
            "authors": detail.get("authors"), "pdf_updated_at": detail.get("last_updated_pdf"),
            "resolution": {"source_page": source, "app_bundle_url": scripts[0], "cms_listing_url": listing, "cms_detail_url": detail_url, "resolved_at": now()}}


def extract_pdf(path, destination):
    from pypdf import PdfReader
    reader = PdfReader(path, strict=False)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF requires explicit handling")
    sparse, replacement, errors, pages = [], [], [], []
    for index, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
            if len(text.strip()) < 100:
                sparse.append(index)
            if "\ufffd" in text or "\x00" in text:
                replacement.append(index)
            pages.append(f"## PDF page {index}\n\n{text.strip()}\n")
        except Exception as exc:
            errors.append({"page": index, "error_type": type(exc).__name__})
            pages.append(f"## PDF page {index}\n\n[Extraction failed; consult the original PDF.]\n")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".md.tmp")
    temporary.write_text("# " + path.stem + " — unreviewed PDF extraction\n\n" + "\n".join(pages), encoding="utf-8")
    temporary.replace(destination)
    return {"extraction_status": "incomplete" if errors or len(sparse) > len(pages) / 5 else "extracted_needs_formula_review",
            "page_count": len(pages), "text_size_bytes": destination.stat().st_size, "text_sha256": sha(destination),
            "extraction_problems": {"sparse_pages": sparse, "replacement_or_null_character_pages": replacement,
                                    "page_errors": errors, "math_layout_risk": "PDF extraction can flatten fractions, powers, bounds, matrices and diagrams; raw extracted text is not reviewed teaching evidence."},
            "formula_review_status": "pending"}


def prepare_book(book, root=ROOT, *, download=False, extract=False):
    title, slug = book
    if book not in BOOKS:
        raise ValueError("Book is outside the four-book allowlist")
    record = {"title": title, "source_url": "https://openstax.org/details/books/" + slug,
              "pdf_url": None, "license": None, "license_url": None,
              "raw_path": f"sources/raw/openstax/{slug}.pdf", "text_path": f"sources/text/openstax/{slug}.md",
              "download_status": "not_attempted", "actual_file_size_bytes": None,
              "partial_transfer_bytes": 0, "transferred_this_run_bytes": 0,
              "extraction_status": "not_attempted", "extraction_problems": []}
    raw, text = root / record["raw_path"], root / record["text_path"]
    partial = raw.with_suffix(".pdf.partial")
    try:
        if download:
            record.update(resolve_book(title, slug))
            if not raw.exists():
                raw.parent.mkdir(parents=True, exist_ok=True)
                with fetch(record["pdf_url"]) as response, partial.open("wb") as stream:
                    length = response.headers.get("Content-Length")
                    record["reported_content_length"] = int(length) if length and length.isdecimal() else None
                    print(f"{title}: download starting, Content-Length={record['reported_content_length']}", flush=True)
                    for data in iter(lambda: response.read(1024 * 1024), b""):
                        stream.write(data)
                        if stream.tell() > 512_000_000:
                            raise ValueError("PDF exceeds transfer limit")
                record["transferred_this_run_bytes"] = partial.stat().st_size
                if length and length.isdecimal() and int(length) != partial.stat().st_size:
                    raise ValueError("Incomplete transfer")
                with partial.open("rb") as stream:
                    if stream.read(5) != b"%PDF-":
                        raise ValueError("Downloaded response is not PDF")
                from pypdf import PdfReader
                if len(PdfReader(partial).pages) < 50:
                    raise ValueError("Downloaded PDF is unexpectedly short")
                partial.replace(raw)
                record["retrieved_at"] = now()
                record["download_status"] = "downloaded"
            else:
                record["download_status"] = "existing_local"
        if raw.exists():
            record["actual_file_size_bytes"] = raw.stat().st_size
            record["raw_sha256"] = sha(raw)
        if extract and raw.exists():
            record.update(extract_pdf(raw, text))
        print(f"{title}: {record['download_status']}, {record['extraction_status']}", flush=True)
    except Exception as exc:
        record["failure"] = {"error_type": type(exc).__name__, "message": str(exc)[:400]}
        if not raw.exists():
            record["download_status"] = "failed" if download else "not_attempted"
        elif extract:
            record["extraction_status"] = "failed"
        if partial.exists():
            record["partial_transfer_bytes"] = partial.stat().st_size
        print(f"{title}: failed ({type(exc).__name__})", flush=True)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Resolve and download only the four core PDFs")
    parser.add_argument("--extract", action="store_true", help="Extract all PDF pages with diagnostic flags")
    args = parser.parse_args(argv)
    if not (args.download or args.extract):
        parser.error("Use --download and/or --extract")
    # Discovery/download is independent per book; never traverse linked resources.
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda book: prepare_book(book, download=args.download, extract=args.extract), BOOKS))
    path = ROOT / "sources/manifests/openstax_core.json"
    if path.exists():
        old = {row["title"]: row for row in json.loads(path.read_text(encoding="utf-8"))["books"]}
        for row in records:
            prior = old.get(row["title"], {})
            same_original = bool(prior.get("raw_sha256")) and prior.get("raw_sha256") == row.get("raw_sha256")
            if row["download_status"] == "existing_local" and prior.get("raw_sha256") == row.get("raw_sha256"):
                row["retrieved_at"] = prior.get("retrieved_at")
                row["download_status"] = prior.get("download_status", "existing_local")
            if not args.download:
                for key in ["pdf_url", "license", "license_url", "authors", "license_text", "resolution"]:
                    if key in prior:
                        row[key] = prior[key]
                if same_original:
                    row["retrieved_at"] = prior.get("retrieved_at")
                    row["download_status"] = prior.get("download_status", "existing_local")
            if same_original and not args.extract:
                for key in ["extraction_status", "extraction_problems", "formula_review_status", "text_size_bytes", "text_sha256", "page_count"]:
                    if key in prior:
                        row[key] = prior[key]
            # A repeat extraction does not erase observed formula loss on the
            # same original. Changed originals require a new visual review.
            if same_original and prior.get("formula_review"):
                row["formula_review"] = prior["formula_review"]
                row["formula_review_status"] = prior.get("formula_review_status", "pending")
                row["extraction_status"] = "incomplete"
                if not isinstance(row["extraction_problems"], dict):
                    row["extraction_problems"] = {}
                row["extraction_problems"]["observed_formula_problems"] = prior["formula_review"]["observations"]
    manifest = {"phase": 3, "scope": "Four OpenStax PDFs only; no full-site or example-collection crawl", "updated_at": now(),
                "books": records, "total_actual_download_bytes": sum(row["actual_file_size_bytes"] or 0 for row in records if row["download_status"] == "downloaded"),
                "total_partial_transfer_bytes": sum(row["partial_transfer_bytes"] for row in records),
                "transferred_this_run_bytes": sum(row["transferred_this_run_bytes"] for row in records),
                "total_extracted_text_bytes": sum(row.get("text_size_bytes", 0) for row in records)}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    print(json.dumps({key: value for key, value in manifest.items() if key != "books"}, indent=2), flush=True)
    # Download success is separate from full Phase 3 formula readiness.
    return 0 if all(row["download_status"] == "downloaded" and row["extraction_status"] == "reviewed" for row in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
