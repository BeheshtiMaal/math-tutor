"""Request and response contracts for the local web service (W1).

Shapes follow spec v3.0 sections 7 and 8. Fields that later phases fill are
present with explicit empty values rather than omitted, so the client contract
does not change between phases:

* ``blocks`` is the closed, backend-validated W5 component union.
* ``level_suggestion`` reports the W8 wording heuristic separately from manual settings.
* ``usage`` values are ``None`` until phase W9 measures token usage.

The learner-profile contracts live in the core (``agent.py``) because the graph
state carries them, and are re-exported here for the HTTP layer and its tests.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent import (
    MAX_CONFUSION_SPOTS,
    MAX_PROFILE_BYTES,
    MAX_PROFILE_TOPICS,
    MAX_RECENT_TOPICS,
    ConfusionSpot,
    LearnerProfile,
    TopicProfile,
)

from .threads import normalize_thread_id, valid_thread_id
from .ui_blocks import UIBlock
from ui_events import UIEvent

Mode = Literal["answer", "learn"]
Language = Literal["fa", "en"]
LearnerLevel = Literal["beginner", "intermediate", "advanced"]
DeliveryMode = Literal["full", "step"]
ChatAction = Literal["new_lesson", "followup", "next", "simplify", "full", "done", "ui_event"]
TopicKind = Literal["core", "open"]
LevelSource = Literal["manual", "inferred", "default"]
LanguageSource = Literal["detected", "override"]

MAX_MESSAGE_CHARS = 8_000


class WebContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ClientInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    app_version: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)


class ChatTurnRequest(WebContract):
    thread_id: str = Field(min_length=30, max_length=30)
    message: str = Field(default="", max_length=MAX_MESSAGE_CHARS)
    action: ChatAction = "new_lesson"
    mode: Mode | None = None
    delivery: DeliveryMode | None = None
    level: LearnerLevel | None = None
    level_source: Literal["manual", "inferred"] | None = None
    language_override: Language | None = None
    # Deliberately unvalidated here: spec section 8 requires an unusable profile
    # to be dropped with ``profile_invalid`` while the turn still succeeds, so
    # validation happens in the service rather than in request parsing.
    learner_profile: dict[str, Any] | None = None
    client: ClientInfo | None = None
    ui_event: UIEvent | None = None

    @model_validator(mode="after")
    def message_required_for_text_actions(self):
        if self.action == 'ui_event':
            if self.ui_event is None or self.message or self.ui_event.thread_id != self.thread_id:
                raise ValueError('UI event requires matching thread and empty message')
        elif self.ui_event is not None:
            raise ValueError('UI event requires ui_event action')
        if self.action in {"new_lesson", "followup"} and not self.message:
            raise ValueError(f"action '{self.action}' requires a non-empty message")
        return self

    @field_validator("thread_id")
    @classmethod
    def _valid_thread_id(cls, value: str) -> str:
        normalized = normalize_thread_id(value)
        if not valid_thread_id(normalized):
            raise ValueError("thread_id must be 'thr_' followed by 26 Crockford base32 characters")
        return normalized


class Segment(WebContract):
    """Typed text channel (spec section 12.1)."""

    kind: Literal["text", "answer"]
    text: str


class LessonState(WebContract):
    concept: str | None = Field(default=None,max_length=120)
    step_index: int = Field(ge=0)
    total_steps: int = Field(ge=0)
    awaiting_user: bool
    can_continue: bool


class InterruptInfo(WebContract):
    """The pause the graph is currently sitting on, if any."""

    kind: str = Field(min_length=1, max_length=32)
    prompt: str
    delivery_mode: DeliveryMode | None = None
    step_index: int | None = Field(default=None, ge=0)
    lesson_complete: bool | None = None


class Usage(WebContract):
    limit_reached: bool = False
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)


class ChatTurnResponse(WebContract):
    degraded: bool = False
    event_status: Literal['accepted', 'duplicate', 'stale'] | None = None
    status: Literal["ok", "thread_not_found"] = "ok"
    thread_id: str
    turn_id: str | None = None
    language: Language | None = None
    language_source: LanguageSource = "detected"
    topic: str | None = None
    topic_kind: TopicKind = "open"
    mode: Mode | None = None
    delivery: DeliveryMode | None = None
    learner_level: LearnerLevel | None = None
    level_source: LevelSource = "default"
    level_suggestion: LearnerLevel | None = None
    segments: list[Segment] = Field(default_factory=list)
    blocks: list[UIBlock] = Field(default_factory=list, max_length=2)
    lesson: LessonState | None = None
    interrupt: InterruptInfo | None = None
    next_request: str | None = None
    profile_status: Literal["absent", "accepted", "rejected"] = "absent"
    warnings: list[str] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)


class ServiceStatus(WebContract):
    model: Literal["configured", "missing", "disabled"]
    search: Literal["configured", "missing", "disabled"]
    embedding: Literal["configured", "missing", "disabled"]


class HealthResponse(WebContract):
    status: Literal["ok"] = "ok"
    version: str = "3.0"
    graph_nodes: list[str]
    offline: bool
    services: ServiceStatus
    known_threads: int = Field(ge=0)
    active_threads: int = Field(ge=0)
