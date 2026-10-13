"""One-off W3 migration: fold each level introduction into that level's Definition unit.

Why: the curated notes used to put a short bilingual framing paragraph directly under
each ``## <Level>`` heading. The evidence loader splits a note on every heading, so each
level heading became its own record, and those records are generic pedagogical prose.
They are not evidence, and in semantic ranking they act as hubs that can outrank real
content for short queries.

After this migration a level heading is immediately followed by ``### Definition``, so the
level record has no body and the loader drops it, while no content is lost: the framing
sentence now opens the Definition unit of the same level and language.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPICS = ROOT / "sources/topics"
LEVELS = ("Beginner", "Intermediate", "Advanced")
PERSIAN = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")


def migrate(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    out, index = [], 0
    moves = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^## (" + "|".join(LEVELS) + r") / ", line)
        if not match:
            out.append(line)
            index += 1
            continue
        # Collect the level heading and the intro lines up to the first ### heading.
        heading = line
        index += 1
        intro = []
        while index < len(lines) and not lines[index].startswith("### "):
            if lines[index].strip():
                intro.append(lines[index].strip())
            index += 1
        if not intro:
            out.append(heading)
            continue
        # Split the intro into its English and Persian halves, in order.
        english = [row for row in intro if not PERSIAN.search(row)]
        persian = [row for row in intro if PERSIAN.search(row)]
        if len(english) != 1 or len(persian) != 1:
            raise ValueError(f"{path.name}: level {match.group(1)} intro is not one English and one Persian line")
        # The next block must be the Definition unit; prepend the matching language.
        if index >= len(lines) or not lines[index].startswith("### Definition / "):
            raise ValueError(f"{path.name}: level {match.group(1)} is not followed by a Definition unit")
        out.append(heading)
        out.append("")
        out.append(lines[index])
        index += 1
        body = []
        while index < len(lines) and not lines[index].startswith("### "):
            if lines[index].strip():
                body.append(lines[index].strip())
            index += 1
        if len(body) != 2:
            raise ValueError(f"{path.name}: Definition body has {len(body)} lines, expected 2")
        merged = []
        for row in body:
            if PERSIAN.search(row):
                merged.append(persian[0] + " " + row)
            else:
                merged.append(english[0] + " " + row)
        out.extend(merged)
        out.append("")
        moves += 1
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return moves


def main():
    total = 0
    for path in sorted(TOPICS.glob("*.md")):
        count = migrate(path)
        total += count
        print(f"{path.name}: folded {count} level introductions")
    print(f"total {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
