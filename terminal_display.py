"""Persian shaping and visual order for terminals without native RTL support.

Only terminal output is transformed; model context and saved text stay logical.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import textwrap
import unicodedata

from arabic_reshaper import ArabicReshaper
from bidi.algorithm import get_display


RESHAPER = ArabicReshaper(configuration={
    "delete_harakat": False, "shift_harakat_position": True,
    "support_ligatures": False,
})
ARABIC = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
LTR_RUN = re.compile(r"[\x20-\x7e۰-۹٠-٩]+")
DIRECTION_CONTROLS = re.compile(r"[\u202a-\u202e\u2066-\u2069]")


def ltr_fragment(run: str, *, spaces: bool) -> str:
    if not any(c.isalnum() for c in run):
        return run
    core = run.strip()
    prefix = run[:len(run) - len(run.lstrip())]
    suffix = run[len(run.rstrip()):]
    # Parentheses around a Persian hint belong to that hint, not the adjacent
    # English command. Balanced formula brackets remain inside the LTR run.
    while core and core[-1] in "([{":
        opening = core[-1]
        closing = {"(": ")", "[": "]", "{": "}"}[opening]
        if core.count(opening) <= core.count(closing):
            break
        suffix = opening + suffix
        core = core[:-1]
    while core and core[0] in ")]}":
        closing = core[0]
        opening = {")": "(", "]": "[", "}": "{"}[closing]
        if core.count(closing) <= core.count(opening):
            break
        prefix += closing
        core = core[1:]
    return prefix + (core.replace(" ", "\u00a0") if spaces else "\u202a" + core + "\u202c") + suffix


def visual_rtl_enabled() -> bool:
    mode = os.environ.get("TUTOR_TERMINAL_RTL", "auto").lower()
    return mode == "visual" or (mode == "auto" and os.name == "nt" and sys.stdout.isatty())


def render_terminal(text: str, *, visual: bool | None = None, width: int | None = None) -> str:
    if visual is None:
        visual = visual_rtl_enabled()
    if not visual:
        return text
    width = max(1, width if width is not None else shutil.get_terminal_size((100, 24)).columns - 1)
    result = []
    for line in text.split("\n"):
        if not ARABIC.search(line):
            result.append(line)
            continue
        line = DIRECTION_CONTROLS.sub("", line)
        direction = next(("R" if unicodedata.bidirectional(c) in {"R", "AL"} else "L"
                          for c in line if unicodedata.bidirectional(c) in {"L", "R", "AL"}), "R")

        # Keep each ASCII formula intact when wrapping, then explicitly embed
        # its complete run LTR so unary signs, fractions and brackets survive.
        protected = LTR_RUN.sub(lambda m: ltr_fragment(m.group(), spaces=True), line)
        wrapped = textwrap.wrap(protected, width=width, break_long_words=False,
                                break_on_hyphens=False, replace_whitespace=False)
        for logical in wrapped:
            logical = logical.replace("\u00a0", " ")
            logical = LTR_RUN.sub(lambda m: ltr_fragment(m.group(), spaces=False), logical)
            rendered = get_display(RESHAPER.reshape(logical), base_dir=direction)
            cells = sum(not unicodedata.combining(c) for c in rendered)
            result.append(" " * max(0, width - cells) + rendered if direction == "R" else rendered)
    return "\n".join(result)
