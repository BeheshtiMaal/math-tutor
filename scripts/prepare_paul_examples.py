"""Select finite, reviewed Paul examples; never crawl a course or invent coverage."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bs4 import BeautifulSoup
from agent import AppConfig, ExampleRecord, Limits, parse_expression, run_math_worker, validate_problem
from learning import LocalRetrievalClient

BASE = "https://tutorial.math.lamar.edu/Classes/"
TERMS = "https://tutorial.math.lamar.edu/terms.aspx"
NOTICE = "© 2003 - 2026 Paul Dawkins. All rights reserved. Private noncommercial reference copy; retain notices. Product incorporation and networked redistribution require express written consent."
LEVELS = ("beginner", "intermediate", "advanced")
# Manually selected from eight existing linked lesson pages. Difficulty is local
# editorial judgment; the source itself does not label these learner levels.
POOLS = [
    ("algebra", "linear equations", "Alg/SolveLinearEqns", ["1:a 1:b", "1:c 1:d", "2:a 2:b"],
     ["Distribution and one-denominator arithmetic", "Rational equations with denominator restrictions", "Excluded roots and identity/no-solution distinctions"]),
    ("algebra", "quadratic equations", "Alg/SolveQuadraticEqnsI", ["1:a 1:c 1:d", "1:e 1:f 1:g", "2:a 2:b"],
     ["Basic factoring and repeated roots", "Nonmonic factoring and zero-product choices", "Rational equations and excluded roots"]),
    ("algebra", "quadratic equations", "Alg/SolveQuadraticEqnsII", ["", "", "3:d"],
     ["", "", "Rational quadratic requiring domain restrictions and formula"]),
    ("derivative", "power rule", "CalcI/DiffFormulas", ["1:a 1:b 1:c", "1:d 2:a 2:b", "1:e 3 4"],
     ["Direct integer power rule", "Rewrite products, quotients and radicals first", "Irrational exponents, monotonicity or tangent application"]),
    ("integral", "antiderivatives", "CalcI/ComputingIndefiniteIntegrals", ["1:a 1:b 1:d", "1:c 1:e 1:f", "2:a 3 4:b"],
     ["Direct power rule and constant of integration", "Algebraic rewriting and logarithmic exceptions", "Mixed functions, trigonometric identities or initial conditions"]),
    ("matrix", "augmented systems", "Alg/AugmentedMatrix", ["1:a 1:b 1:c", "2:a 2:b", ""],
     ["Two-variable row operations", "Three-variable elimination", "No suitable advanced example on this selected page"]),
    ("limits", "evaluating limits", "CalcI/ComputingLimits", ["1 2 4:a", "3 4:b 5", "6"],
     ["Factoring, expansion or an ordinary piecewise branch", "Conjugates and one-sided piecewise reasoning", "Squeeze theorem for an oscillatory expression"]),
    ("optimization", "constrained optimization", "CalcI/Optimization", ["1 3", "2 4", "5 6"],
     ["Simple area and square-base constraints", "Cost or cylinder constraints with several quantities", "Feasible domains, boundary comparison and multiple dimensions"]),
]
CHECKS = {
    "CalcI/DiffFormulas:1:a": ("differentiate", "15*x**100-3*x**12+5*x-46", "x", "1500*x**99-36*x**11+5"),
    "CalcI/DiffFormulas:1:b": ("differentiate", "2*t**6+7*t**(-6)", "t", "12*t**5-42*t**(-7)"),
    "CalcI/DiffFormulas:1:c": ("differentiate", "8*z**3-1/(3*z**5)+z-23", "z", "24*z**2+5/(3*z**6)+1"),
    "CalcI/DiffFormulas:2:b": ("differentiate", "(2*t**5+t**2-5)/t**2", "t", "6*t**2+10/t**3"),
    "CalcI/ComputingIndefiniteIntegrals:1:a": ("integrate", "5*t**3-10*t**(-6)+4", "t", "5*t**4/4+2/t**5+4*t"),
    "CalcI/ComputingIndefiniteIntegrals:1:b": ("integrate", "x**8+x**(-8)", "x", "x**9/9-1/(7*x**7)"),
    "CalcI/ComputingIndefiniteIntegrals:1:d": ("integrate", "1", "y", "y"),
    "CalcI/ComputingIndefiniteIntegrals:1:f": ("integrate", "(4*x**10-2*x**4+15*x**2)/x**3", "x", "x**8/2-x**2+15*log(abs(x))"),
    "CalcI/ComputingIndefiniteIntegrals:2:a": ("integrate", "3*exp(x)+5*cos(x)-10/cos(x)**2", "x", "3*exp(x)+5*sin(x)-10*tan(x)"),
    "CalcI/ComputingIndefiniteIntegrals:3": ("integrate", "sin(t/2)*cos(t/2)", "t", "sin(t/2)**2"),
    "CalcI/ComputingLimits:1": ("limit", "(x**2+4*x-12)/(x**2-2*x)", "x", "4", "2"),
    "CalcI/ComputingLimits:2": ("limit", "(2*(-3+h)**2-18)/h", "h", "-12", "0"),
    "CalcI/ComputingLimits:3": ("limit", "(t-sqrt(3*t+4))/(4-t)", "t", "-5/8", "4"),
}
EQUATIONS = {
    "Alg/SolveLinearEqns:1:a": ("3*(x+5)", "2*(-6-x)-2*x", "x", "{-27/7}"),
    "Alg/SolveLinearEqns:1:b": ("(m-2)/3+1", "2*m/7", "m", "{-7}"),
    "Alg/SolveLinearEqns:1:c": ("5/(2*y-6)", "(10-y)/(y**2-6*y+9)", "y", "{5}"),
    "Alg/SolveLinearEqns:1:d": ("2*z/(z+3)", "3/(z-10)+2", "z", "{17/3}"),
    "Alg/SolveLinearEqns:2:a": ("2/(x+2)", "-x/(x**2+5*x+6)", "x", "{}"),
    "Alg/SolveLinearEqns:2:b": ("2/(x+1)", "4-2*x/(x+1)", "x", "{}"),
    "Alg/SolveQuadraticEqnsI:1:a": ("x**2-x", "12", "x", "{-3,4}"),
    "Alg/SolveQuadraticEqnsI:1:c": ("y**2+12*y+36", "0", "y", "{-6}"),
    "Alg/SolveQuadraticEqnsI:1:d": ("4*m**2-1", "0", "m", "{-1/2,1/2}"),
    "Alg/SolveQuadraticEqnsI:1:e": ("3*x**2", "2*x+8", "x", "{-4/3,2}"),
    "Alg/SolveQuadraticEqnsI:1:f": ("10*z**2+19*z+6", "0", "z", "{-3/2,-2/5}"),
    "Alg/SolveQuadraticEqnsI:1:g": ("5*x**2", "2*x", "x", "{0,2/5}"),
    "Alg/SolveQuadraticEqnsI:2:a": ("1/(x+1)", "1-5/(2*x-4)", "x", "{-1/2,5}"),
    "Alg/SolveQuadraticEqnsI:2:b": ("x+3+3/(x-1)", "(4-x)/(x-1)", "x", "{-4}"),
    "Alg/SolveQuadraticEqnsII:3:d": ("3/(y-2)", "1/y+1", "y", "{2-sqrt(6),2+sqrt(6)}"),
}


def plan():
    rows = []
    for topic, subtopic, page, selections, rationales in POOLS:
        for level, selection, rationale in zip(LEVELS, selections, rationales):
            for item in selection.split():
                number, _, part = item.partition(":")
                rows.append(dict(page=page, example=int(number), part=part or None,
                                 topic=topic, subtopic=subtopic, level=level, level_rationale=rationale))
    return rows


def render(tag, url):
    """Retain TeX, superscript/subscript and source diagrams without image downloads."""
    tag = deepcopy(tag)
    for element in tag.select("sup"):
        element.replace_with("^{" + element.get_text() + "}")
    for element in tag.select("sub"):
        element.replace_with("_{" + element.get_text() + "}")
    for image in tag.select("img"):
        alt = image.get("alt", "").strip()
        if not alt:
            raise ValueError("Selected diagram has no descriptive alt text")
        image.replace_with("\n![" + alt + "](" + urljoin(url, image["src"]) + ")\n")
    # Inline nodes must not split mathematical prose. Block boundaries remain.
    for element in tag.select("p, div.math, li, br"):
        element.insert_before("\n")
        element.insert_after("\n")
    return re.sub(r"\n\s*\n+", "\n\n", tag.get_text()).strip()


def extract(html, selection, retrieved_at):
    page = selection["page"]
    url = BASE + page + ".aspx"
    soup = BeautifulSoup(html, "html.parser")
    wanted = f"Example {selection['example']}"
    found = [ex for ex in soup.select("div.example")
             if ex.select_one(".example-title") and ex.select_one(".example-title").get_text(" ", strip=True) == wanted]
    if len(found) != 1:
        raise ValueError("Visible source example label absent or ambiguous: " + wanted)
    ex = found[0]
    part = selection["part"]
    header = deepcopy(ex)
    for element in header.select(".example-content, .example-title, .SH-Link"):
        element.decompose()
    details = ex.select("details.sh")
    if part:
        matches = [d for d in details if d.select_one("summary .soln-list-subitem")
                   and d.select_one("summary .soln-list-subitem").get_text(strip=True) == part]
        if len(matches) != 1:
            raise ValueError("Selected part has no unique complete solution")
        items = header.select("ol.example_parts_list > li")
        index = ord(part) - ord("a")
        if index >= len(items):
            raise ValueError("Original problem part is missing")
        problem = render(items[index], url)
        for element in header.select("ol.example_parts_list"):
            element.decompose()
        statement = render(header, url) + "\n\n" + problem
        solution = matches[0].select_one(".soln-content")
    else:
        statement = render(header, url)
        matches = [d.select_one(".soln-content") for d in details
                   if d.select_one("summary") and "Show Solution" in d.select_one("summary").get_text()]
        if len(matches) != 1:
            raise ValueError("Single example has no unique complete solution")
        solution = matches[0]
    if solution is None:
        raise ValueError("Source solution missing")
    shared = [render(d.select_one(".soln-content"), url) for d in details
              if d.select_one("summary") and "Show Discussion" in d.select_one("summary").get_text()
              and d.select_one(".soln-content")]
    solution_text = "\n\n".join(shared + [render(solution, url)])
    suffix = f":{part}" if part else ""
    key = f"{page}:{selection['example']}{suffix}"
    identifier = "paul:" + key
    row = dict(id=identifier, example_id=identifier, topic=selection["topic"], subtopic=selection["subtopic"],
               learner_level=selection["level"], course="Algebra" if page.startswith("Alg/") else "Calculus I",
               statement=statement, solution=solution_text, source_example_label=wanted + (f" ({part})" if part else ""),
               provenance=dict(source_url=url, section_title=soup.title.get_text(strip=True), source_author="Paul Dawkins",
                               retrieved_at=retrieved_at, usage_terms_url=TERMS, usage_terms=NOTICE),
               verification_status="unsupported", verification_method="Complete example claim has no supported bounded equivalence check (sets, row reduction, piecewise/domain proof or multistage application).")
    if key in CHECKS:
        operation, expression, variable, candidate, *point = CHECKS[key]
        payload = dict(operation=operation, expression=parse_expression(expression).model_dump(), variable=variable)
        if point:
            payload["point"] = parse_expression(point[0]).model_dump()
        row.update(operation_payload=validate_problem(payload).model_dump(), proposed_result=candidate,
                   verification_status="unknown", verification_method=None)
    if key in EQUATIONS:
        lhs, rhs, variable, candidate = EQUATIONS[key]
        row.update(operation_payload=dict(operation="solve", lhs=parse_expression(lhs).model_dump(),
                   rhs=parse_expression(rhs).model_dump(), variable=variable), proposed_result=candidate,
                   verification_status="unknown", verification_method=None)
    return ExampleRecord.model_validate(row)


def import_records(path, records):
    """Merge stable IDs atomically; reject level reuse and quota overflow."""
    existing = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = ExampleRecord.model_validate_json(line)
                if row.example_id in existing:
                    raise ValueError("Existing duplicate example ID")
                existing[row.example_id] = row
    for row in records:
        row = ExampleRecord.model_validate(row)
        prior = existing.get(row.example_id)
        if prior and (prior.topic, prior.subtopic, prior.learner_level) != (row.topic, row.subtopic, row.learner_level):
            raise ValueError("A source example cannot be reused under another level/topic")
        existing[row.example_id] = row
    counts = Counter((r.topic, r.subtopic, r.learner_level) for r in existing.values())
    if any(n > 3 for n in counts.values()):
        raise ValueError("Pool exceeds three selected examples")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".jsonl.tmp")
    temporary.write_text("".join(r.model_dump_json() + "\n" for r in sorted(existing.values(), key=lambda r: r.example_id)), encoding="utf-8")
    temporary.replace(path)
    return list(existing.values())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Fetch exactly the eight selected lesson pages; never follow links")
    parser.add_argument("--verify", action="store_true", help="Run supported claims in the bounded SymPy worker")
    parser.add_argument("--retry-unverified", action="store_true", help="Reuse unchanged verified records and retry other supported claims")
    parser.add_argument("--import-jsonl", type=Path, help="Validate/deduplicate an existing selected bank, without fetching")
    args = parser.parse_args(argv)
    target = ROOT / "sources/examples/paul/selected.jsonl"
    schema = ROOT / "sources/examples/schema.json"
    schema.parent.mkdir(parents=True, exist_ok=True)
    schema.write_text(json.dumps(ExampleRecord.model_json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.import_jsonl:
        records = [ExampleRecord.model_validate_json(line) for line in args.import_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
        imported = import_records(target, records)
        print(f"Validated import: {len(imported)} unique records")
        return 0
    cache = ROOT / ".cache/phase3/paul"
    cache.mkdir(parents=True, exist_ok=True)
    rows, failures, pages = [], [], {}
    for page in dict.fromkeys(row["page"] for row in plan()):
        path = cache / (page.replace("/", "-") + ".html")
        metadata_path = path.with_suffix(".metadata.json")
        try:
            if args.fetch:
                with urlopen(Request(BASE + page + ".aspx", headers={"User-Agent": "Mozilla/5.0"}), timeout=45) as response:
                    raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError("Lesson page exceeds selective fetch limit")
                path.write_bytes(raw)
                metadata_path.write_text(json.dumps(dict(retrieved_at=datetime.now(timezone.utc).isoformat(), sha256=hashlib.sha256(raw).hexdigest())), encoding="utf-8")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            raw = path.read_bytes()
            if metadata["sha256"] != hashlib.sha256(raw).hexdigest():
                raise ValueError("Cached page hash differs; fetch again")
            pages[page] = (raw.decode("utf-8"), metadata["retrieved_at"])
        except Exception as exc:
            failures.append(dict(page=page, error=str(exc)))
    verifier = LocalRetrievalClient(AppConfig(limits=Limits(math_timeout_seconds=30)), run_math_worker)
    selections = []
    prior = {r.example_id: r for r in [ExampleRecord.model_validate_json(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]} if args.retry_unverified and target.exists() else {}
    for selection in plan():
        if selection["page"] not in pages:
            continue
        try:
            row = extract(*[pages[selection["page"]][0], selection, pages[selection["page"]][1]])
            old = prior.get(row.example_id)
            if old and old.verification_status == "verified" and all(getattr(old, field) == getattr(row, field) for field in ["statement", "solution", "operation_payload", "proposed_result"]):
                row = old
            elif (args.verify or args.retry_unverified) and row.operation_payload:
                row = verifier._verify(row)
            rows.append(row)
            selections.append(dict(**selection, example_id=row.example_id, verification_status=row.verification_status))
            print(f"{row.example_id}: {row.verification_status}", flush=True)
        except Exception as exc:
            failures.append(dict(selection=selection, error=str(exc)))
    imported = import_records(target, rows)
    counts = Counter((r.topic, r.subtopic, r.learner_level) for r in imported if r.verification_status != "rejected")
    pools = list(dict.fromkeys((p[0], p[1]) for p in POOLS)) + [("probability", "basic probability")]
    coverage = [dict(topic=topic, subtopic=subtopic, learner_level=level, selected=counts[(topic, subtopic, level)],
                     target=3, missing=max(0, 3-counts[(topic, subtopic, level)])) for topic, subtopic in pools for level in LEVELS]
    manifest = dict(phase=3, prepared_at=datetime.now(timezone.utc).isoformat(), selected_count=len(imported),
                    fetched_pages=list(pages), selections=selections, coverage=coverage, failures=failures,
                    verification_counts=dict(Counter(r.verification_status for r in imported)),
                    notice=NOTICE, limitations="Difficulty is editorial. Gaps reflect this finite selection, not proof that no other suitable examples exist. Unknown/unsupported examples remain source-backed, not mathematically verified. Diagram URLs and alt descriptions retained; no images downloaded.")
    destination = ROOT / "sources/manifests/paul_selection.json"
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ["selected_count", "verification_counts", "failures"]}, indent=2), flush=True)
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
