"""Historical reference utilities; executable bulk acquisition is retired.

No model calls, embeddings, runtime example imports or publication.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "sources/manifests/references.json"


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def local_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Manifest path escapes workspace")
    return path


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def catalog(spec):
    """Read the two explicit reference tables, not every discovery URL."""
    text = spec.read_text(encoding="utf-8")
    records = []
    for kind, start, end in [
        ("openstax", "## OpenStax", "## نقطه"),
        ("paul", "## Paul", "## فهرست کامل"),
    ]:
        section = text.split(start, 1)[1].split(end, 1)[0]
        for line in section.splitlines():
            match = re.match(r"\|\s*([^|]+?)\s*\|.*?(https://[^\s)|]+)", line)
            if not match:
                continue
            title, url = match.groups()
            if kind == "openstax":
                slug = url.split("/books/", 1)[1].split("/", 1)[0]
            else:
                slug = urlparse(url).path.rsplit("/", 1)[-1].removesuffix(".aspx")
            records.append(record(kind, slug, title.strip(), url, "pdf" if kind == "openstax" else "html"))
    records.extend([
        record("teaching", "ies-learning-guide", "IES: Organizing Instruction and Study to Improve Student Learning", "https://ies.ed.gov/ncee/WWC/Docs/PracticeGuide/20072004.pdf", "pdf"),
        record("teaching", "paul-study-math", "Paul: How To Study Math", "https://tutorial.math.lamar.edu/", "html", discover="How To Study Math"),
        record("teaching", "paul-common-math-errors", "Paul: Common Math Errors", "https://tutorial.math.lamar.edu/", "html", discover="Common Math Errors"),
    ])
    if sum(r["kind"] == "openstax" for r in records) != 4:
        raise ValueError("Expected exactly four OpenStax titles in the current reference list")
    if sum(r["kind"] == "paul" for r in records) != 25:
        raise ValueError("Expected exactly 25 listed Paul lessons")
    if len({r["id"] for r in records}) != len(records):
        raise ValueError("Duplicate reference IDs")
    return records


def record(kind, slug, title, url, fmt, **extra):
    is_paul = kind == "paul" or slug.startswith("paul-")
    return {
        "id": f"{kind}/{slug}", "kind": kind, "title": title,
        "edition": "2e" if "2e" in title else "as listed; exact edition/date must be checked in original",
        "source_url": url, "resolved_url": url if url.lower().endswith(".pdf") or kind == "paul" else None,
        "local_path": f"sources/raw/{kind}/{slug}.{fmt}",
        "text_path": f"sources/text/{kind}/{slug}.md",
        "terms_url": "https://tutorial.math.lamar.edu/terms.aspx" if is_paul else url,
        "usage_status": "product reuse requires Paul Dawkins consent; private reference only" if is_paul else "check exact original license and AI ingestion restrictions; not cleared for tutor use" if kind == "openstax" else "check original rights notices",
        "status": "missing", "retrieved_at": None, "downloaded_bytes": None,
        "reported_content_length_before_transfer": None, "sha256": None,
        "formula_review": "pending", **extra,
    }


def request(url):
    if urlparse(url).scheme != "https":
        raise ValueError("Only HTTPS reference URLs are accepted")
    return urlopen(Request(url, headers={"User-Agent": "MathTutor-ReferencePreparation/0.1", "Accept-Encoding": "identity"}), timeout=30)


def download(r, root):
    """Resolve explicit PDF links from the authoritative page; never guess filenames."""
    from bs4 import BeautifulSoup
    target = local_path(root, r["local_path"])
    if target.exists():
        return
    url = r.get("resolved_url")
    if not url:
        with request(r["source_url"]) as response:
            page_url = response.url
            soup = BeautifulSoup(response.read(), "html.parser")
        if r.get("discover"):
            matches = [a for a in soup.find_all("a", href=True) if r["discover"].lower() in a.get_text(" ", strip=True).lower()]
        else:
            matches = [a for a in soup.find_all("a", href=True) if urlparse(a["href"]).path.lower().endswith(".pdf")]
            matches.sort(key=lambda a: ("web" not in a["href"].lower(), "english" not in a.get_text().lower()))
        if not matches:
            raise ValueError("No explicit download link in authoritative HTML. Use browser Download PDF and save to listed path; do not save the book-details page as the book.")
        url = urljoin(page_url, matches[0]["href"])
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".partial")
    r["download_attempted_at"] = now()
    with request(url) as response:
        r["resolved_url"] = response.url
        length = response.headers.get("Content-Length")
        r["reported_content_length_before_transfer"] = int(length) if length and length.isdecimal() else None
        print(f"{r['id']}: before transfer Content-Length={r['reported_content_length_before_transfer']} (None=unavailable)", flush=True)
        measured = 0
        with partial.open("wb") as stream:
            while block := response.read(1024 * 1024):
                stream.write(block)
                measured += len(block)
        if length and length.isdecimal() and measured != int(length):
            raise ValueError(f"Incomplete transfer: expected {length}, received {measured}")
    with partial.open("rb") as stream:
        prefix = stream.read(1024)
    if target.suffix == ".pdf" and not prefix.lstrip().startswith(b"%PDF-"):
        raise ValueError("Download is not a PDF; partial retained for inspection")
    if target.suffix == ".html" and b"<html" not in prefix.lower() and b"<!doctype html" not in prefix.lower():
        raise ValueError("Download is not an HTML document")
    partial.replace(target)
    r["retrieved_at"] = now()
    r["acquisition_method"] = "script"


def html_text(path):
    """Keep hidden solutions, TeX math scripts and MathML; omit site navigation."""
    from bs4 import BeautifulSoup, NavigableString
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    body = soup.select_one("#content") or soup.select_one("main") or soup.select_one("article")
    if body is None:
        raise ValueError("No instructional content container; selector needs inspection")
    for tag in body.select("nav, style, header, footer"):
        tag.decompose()
    for tag in body.find_all("script"):
        if "math/tex" in tag.get("type", ""):
            delimiter = "$$" if "display" in tag.get("type", "") else "$"
            tag.replace_with(NavigableString(delimiter + tag.get_text() + delimiter))
        else:
            tag.decompose()
    mathml = list(body.find_all("math"))
    for tag in mathml:
        tag.replace_with(NavigableString(str(tag)))
    for tag in body.find_all(re.compile(r"^h[1-6]$")):
        tag.insert_before(NavigableString("\n" + "#" * int(tag.name[1]) + " "))
        tag.insert_after(NavigableString("\n"))
    text = body.get_text("\n", strip=False)
    # Preserve internal equation spacing and original TeX rather than reformatting it.
    text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text).strip()
    if len(text) < 200:
        raise ValueError("Instructional text unexpectedly short; likely an error/landing page")
    warnings = []
    images = body.find_all("img")
    if images:
        warnings.append(f"{len(images)} images require original-file inspection; figures not converted to text")
    return text, {"mathml_elements": len(mathml), "warnings": warnings, "tex_delimiters": text.count("\\(") + text.count("\\[") + text.count("$$")}


def pdf_text(path):
    # Parsing validates the PDF independently of its filename and header.
    from pypdf import PdfReader
    reader = PdfReader(path, strict=True)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF requires an authorized readable original")
    if not reader.pages:
        raise ValueError("PDF has no pages")
    pages = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    empty = [i + 1 for i, text in enumerate(pages) if len(text.strip()) < 20]
    text = "\n\n".join(f"## Original PDF page {i + 1}\n\n{page}" for i, page in enumerate(pages))
    return text, {"page_count": len(pages), "empty_or_image_pages": empty,
                  "warnings": ["PDF text extraction does not establish formula fidelity. Review fractions, powers, limits, matrices and symbols against original; use full MathML/TeX HTML when necessary."],
                  "pdf_metadata": {str(k): str(v) for k, v in (reader.metadata or {}).items()}}


def inventory(r, root, convert):
    path = local_path(root, r["local_path"])
    r["downloaded_bytes"] = path.stat().st_size if path.exists() else None
    r["sha256"] = digest(path) if path.exists() else None
    if not path.exists():
        r["status"] = "download_failed" if r.get("download_error") else "missing"
        return
    previous_hash = r.get("converted_from_sha256")
    if previous_hash and previous_hash != r["sha256"]:
        r["formula_review"] = "pending"
        r.pop("quality_review", None)
    if not r.get("retrieved_at"):
        # An mtime is not a known source retrieval date.
        r["acquisition_method"] = "manual; retrieval date unknown"
    with path.open("rb") as stream:
        prefix = stream.read(1024)
    if path.suffix.lower() == ".pdf":
        if not prefix.lstrip().startswith(b"%PDF-"):
            raise ValueError("File is not PDF content")
        r["file_type"] = "PDF"
    elif path.suffix.lower() in {".html", ".htm"}:
        if b"<html" not in prefix.lower() and b"<!doctype html" not in prefix.lower():
            raise ValueError("File is not HTML content")
        r["file_type"] = "HTML"
    else:
        raise ValueError("Unsupported raw format")
    r["status"] = "raw_present_unvalidated"
    if not convert:
        output = local_path(root, r["text_path"])
        if output.exists() and previous_hash == r["sha256"] and r.get("text_sha256") == digest(output):
            r["status"] = "complete" if reviewed(r) else "converted_review_pending"
        return
    text, checks = pdf_text(path) if r["file_type"] == "PDF" else html_text(path)
    output = local_path(root, r["text_path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    heading = f"# {r['title']}\n\nSource: {r['source_url']}\nResolved URL: {r.get('resolved_url')}\nTerms: {r['terms_url']}\nRaw SHA-256: {r['sha256']}\nUsage: {r['usage_status']}\n\n"
    output.write_text(heading + text + "\n", encoding="utf-8")
    r.update(text_bytes=output.stat().st_size, text_sha256=digest(output), converted_from_sha256=r["sha256"], conversion_checks=checks)
    approved = reviewed(r)
    r["formula_review"] = "passed" if approved else "pending"
    r["status"] = "complete" if approved else "converted_review_pending"


def reviewed(r):
    review = r.get("quality_review", {})
    approved = all(review.get(k) is True for k in ["complete_reference", "formula_fidelity", "headings_and_assumptions", "terms_recorded"])
    approved = approved and review.get("raw_sha256") == r["sha256"] and review.get("text_sha256") == r["text_sha256"]
    approved = approved and bool(review.get("reviewer")) and bool(review.get("reviewed_at")) and bool(r.get("retrieved_at"))
    return approved


def byte_total(folder):
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) if folder.exists() else 0


def report(records, root):
    report_path = root / "sources/manifests/acquisition_report.md"
    lines = ["# Phase 0 acquisition report", "", f"Generated (UTC): {now()}", "",
             "Sizes below are measured local bytes, not estimates or remote Content-Length.", "",
             "| Reference | Status | Raw bytes | Text bytes |", "|---|---|---:|---:|"]
    for r in records:
        text = local_path(root, r["text_path"])
        lines.append(f"| {r['title']} | {r['status']} | {r.get('downloaded_bytes') if r.get('downloaded_bytes') is not None else 'missing'} | {text.stat().st_size if text.exists() else 'missing'} |")
    lines.extend(["", f"Raw disk usage: {byte_total(root / 'sources/raw')} bytes.",
                  f"Extracted text disk usage: {byte_total(root / 'sources/text')} bytes.", "", "## Unresolved gaps", ""])
    for r in records:
        if r["status"] != "complete":
            lines.append(f"- {r['id']}: {r.get('error') or r.get('download_error') or r['status']}")
    lines.extend(["", "All usage restrictions remain separate from conversion completion. No records are approved for tutor ingestion by this report."])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Keep total outside the report to avoid a self-referential byte count.
    usage = {"measured_at": now(), "raw_bytes": byte_total(root / "sources/raw"),
             "text_bytes": byte_total(root / "sources/text"),
             "sources_bytes_excluding_disk_usage_json": sum(p.stat().st_size for p in (root / "sources").rglob("*") if p.is_file() and p.name != "disk_usage.json")}
    save_json(root / "sources/manifests/disk_usage.json", usage)
    print(json.dumps(usage, indent=2))
    print(f"Complete: {sum(r['status'] == 'complete' for r in records)}/{len(records)}")


def checklist(records, root):
    lines = ["# Manual reference download checklist", "",
             "Save each original to the exact relative path below. OpenStax: open the official page and use Download PDF; do not save the landing page as the textbook. Paul: save the complete HTML source, including hidden worked solutions and copyright notices. Index pages are discovery aids and do not replace lessons.", "",
             "| Reference | Official source | Save original as |", "|---|---|---|"]
    for r in records:
        lines.append(f"| {r['title']} | [Open source]({r['source_url']}) | `{r['local_path']}` |")
    lines.extend(["", "For the two Paul teaching pages, follow the named link on the homepage before saving. Record the actual page URL as resolved_url in references.json.", "",
                  "Record the actual retrieval date (ISO 8601), resolved download URL and edition in references.json. Missing metadata is left unknown, never invented. For private reference acquisition only; later product reuse/AI ingestion has separate permission requirements.", "",
                  "If a book is HTML-only, retain every instructional section and its table of contents. A single preface is not a complete book. This script does not automatically certify multi-page HTML coverage; full-book HTML conversion needs a section manifest and separate review."])
    (root / "sources/manifests/DOWNLOAD_CHECKLIST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def legacy_main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Attempt downloads; existing files are preserved")
    parser.add_argument("--convert", action="store_true", help="Convert existing PDFs/HTML; requires acquisition requirements")
    parser.add_argument("--only", help="One reference ID (e.g. openstax/calculus-volume-1)")
    args = parser.parse_args(argv)
    for folder in ["raw/openstax", "raw/paul", "raw/teaching", "text", "manifests"]:
        (ROOT / "sources" / folder).mkdir(parents=True, exist_ok=True)
    records = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else catalog(ROOT / "specs/math_tutor_download_links.md")
    if args.only and not any(r["id"] == args.only for r in records):
        parser.error("Unknown reference ID")
    for r in records:
        if args.only and r["id"] != args.only:
            continue
        r.pop("error", None)
        if args.download:
            try:
                download(r, ROOT)
                r.pop("download_error", None)
            except Exception as exc:
                r["download_error"] = f"{type(exc).__name__}: {exc}"
        try:
            inventory(r, ROOT, args.convert)
        except Exception as exc:
            r["status"] = "conversion_failed" if args.convert else "invalid_raw"
            r["error"] = f"{type(exc).__name__}: {exc}"
        print(f"{r['id']}: {r['status']}")
        save_json(MANIFEST, records)
    checklist(records, ROOT)
    report(records, ROOT)
    return 0 if all(r["status"] == "complete" for r in records) else 2


def main(argv=None):
    print("Bulk acquisition retired. Phase 3: run scripts/prepare_core_sources.py --download --extract, then scripts/prepare_paul_examples.py --fetch --verify. Existing historical files are preserved.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
