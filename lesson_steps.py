"""Validated lesson content and reply parsing; LangGraph owns progression."""
from __future__ import annotations

import re
from pydantic import Field, model_validator
from agent import Contract, LessonStep, UserAction


def sentences(text):
    """Protect explicit TeX/code units and decimals when identifying sentences."""
    units = []
    def protect(match):
        units.append(match.group())
        return f"MATHUNIT{len(units) - 1}TOKEN"
    protected = re.sub(r"```[\s\S]*?```|`[^`]*`|\$\$[\s\S]*?\$\$|\$[^$\n]*\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)", protect, text)
    parts = re.split(r"(?<=[.!?؟])\s+(?!\d)|(?<=\n)\n+", protected.strip())
    restored = []
    for part in parts:
        for index, unit in enumerate(units):
            part = part.replace(f"MATHUNIT{index}TOKEN", unit)
        if part.strip():
            restored.append(part.strip())
    return restored


class StepDraft(Contract):
    explanation: str = Field(min_length=1, max_length=1400)
    source_ids: list[str] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def short_chunk(self):
        if not 2 <= len(sentences(self.explanation)) <= 3:
            raise ValueError("A teaching chunk requires two or three sentences")
        return self


class PlannedStep(StepDraft):
    objective: str = Field(min_length=1, max_length=256)
    kind: str = Field(default="concept", pattern=r"^(concept|method|check)$")


class LessonPlanDraft(Contract):
    steps: list[PlannedStep] = Field(min_length=1, max_length=12)


class LessonReply(Contract):
    action: UserAction
    query: str | None = Field(default=None, min_length=1, max_length=100000)

    @model_validator(mode="after")
    def question_required(self):
        if self.action == "followup" and not self.query:
            raise ValueError("Follow-up requires a question")
        return self


def parse_reply(value, max_chars):
    if isinstance(value, dict):
        reply = LessonReply.model_validate(value)
        if len(reply.query or "") > max_chars:
            raise ValueError("Reply exceeds input limit")
        return reply
    if not isinstance(value, str) or not value.strip() or len(value) > max_chars:
        raise ValueError("Reply must be bounded nonempty text")
    value = value.strip()
    normalized = " ".join(value.lower().replace("ي", "ی").replace("ك", "ک").split()).rstrip(".!")
    aliases = {
        "done": {"done", "تمام", "پایان", "finish", "end"},
        "next": {"next", "continue", "بعدی", "ادامه", "اوکی", "ok", "okay"},
        "simplify": {"simplify", "simpler", "i don't understand", "i do not understand", "نفهمیدم", "متوجه نشدم", "گیج شدم"},
        "full": {"full", "explain fully", "full explanation", "کامل", "کامل بگو", "همه را بگو"},
    }
    for action, choices in aliases.items():
        if normalized in choices:
            return LessonReply(action=action)
    if normalized.startswith(("نفهمیدم ", "متوجه نشدم ", "i don't understand ", "i do not understand ")):
        return LessonReply(action="simplify", query=value)
    return LessonReply(action="followup", query=value)


def fallback_plan(sources, *, fa, output_limit):
    """Use actual passages in small chunks; never manufacture mathematical text."""
    plan, used, omitted = [], 0, False
    for record in sources:
        text = re.sub(r"(?m)^#{1,6} .*\n?", "", record.text).strip()
        pieces = sentences(text)
        for start in range(0, len(pieces), 2):
            selected = pieces[start:start + 2]
            selected = [piece if piece.endswith((".", "!", "?", "؟")) else piece + "." for piece in selected]
            if len(selected) == 1:
                selected.append("نمادها را همراه با فرض‌های گفته‌شده بخوانید." if fa else "Read the symbols together with the stated assumptions.")
            body = " ".join(selected)
            if len(body) > 1400 or used + len(body) > output_limit or len(plan) >= 11:
                omitted = True
                continue
            used += len(body)
            plan.append(LessonStep(id=f"step:{len(plan)}", objective=record.provenance.section_title,
                                   text=body, source_ids=[record.id]))
    if not plan:
        text = ("متن معتبر و کوتاه برای این درس در دسترس نیست. یادداشت محلی مناسب لازم است." if fa
                else "No valid short source passage is available for this lesson. Suitable prepared local notes are needed.")
        plan = [LessonStep(id="step:0", objective="Evidence unavailable", text=text)]
    return plan, omitted
