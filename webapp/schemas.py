"""Request and response contracts for the local web service (W1).

Shapes follow spec v3.0 sections 7 and 8. Fields that later phases fill are
present with explicit empty values rather than omitted, so the client contract
does not change between phases:

* ``blocks`` is always empty until phase W5.
* ``level_suggestion`` is always ``None`` until phase W8.
* ``usage`` values are ``None`` until phase W9 measures token usage.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .threads import normalize_thread_id, valid_thread_id

Mode = Literal["answer", "learn"]
Language = Literal["fa", "en"]
LearnerLevel = Literal["beginner", "intermediate", "advanced"]
DeliveryMode = Literal["full", "step"]
ChatAction = Literal["new_lesson", "followup", "next", "simplify", "full", "done", "ui_event"]
TopicKind = Literal["core", "open"]
LevelSource = Literal["manual", "inferred", "default"]
LanguageSource = Literal["detected", "override"]

MAX_MESSAGE_CHARS = 8_000
MAX_PROFILE_BYTES = 16 * 1024
MAX_PROFILE_TOPICS = 50
MAX_CONFUSION_SPOTS = 10
MAX_RECENT_TOPICS = 20
FUTURE_TOLERANCE = timedelta(minutes=5)


class WebContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _clamp_timestamp(value: datetime | None) -> datetime | None:
    """Reject nonsense timestamps: a future value is clamped to now."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return now if value - now > FUTURE_TOLERANCE else value


class ConfusionSpot(BaseModel):
    """One recorded confusion, keyed by topic and concept (spec section 8)."""

    model_config = ConfigDict(extra="ignore")

    concept: str = Field(min_length=1, max_length=120)
    step_id: str | None = Field(default=None, max_length=120)
    count: int = Field(default=1, ge=1, le=1000)
    last_seen: datetime | None = None

    @field_validator("last_seen")
    @classmethod
    def _normalize_last_seen(cls, value: datetime | None) -> datetime | None:
        return _clamp_timestamp(value)


class TopicProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    level: LearnerLevel
    level_source: Literal["manual", "inferred"] = "manual"
    confusion_spots: list[ConfusionSpot] = Field(default_factory=list, max_length=MAX_CONFUSION_SPOTS)
    last_seen: datetime | None = None

    @field_validator("last_seen")
    @classmethod
    def _normalize_last_seen(cls, value: datetime | None) -> datetime | None:
        return _clamp_timestamp(value)


class LearnerProfile(BaseModel):
    """Browser-stored learner profile. Never persisted server-side."""

    model_config = ConfigDict(extra="ignore")

    version: Literal[1] = 1
    topics: dict[str, TopicProfile] = Field(default_factory=dict)
    recent_topics: list[str] = Field(default_factory=list, max_length=MAX_RECENT_TOPICS)
    updated_at: datetime | None = None

    @field_validator("updated_at")
    @classmethod
    def _normalize_updated_at(cls, value: datetime | None) -> datetime | None:
        return _clamp_timestamp(value)

    @model_validator(mode="after")
    def bounded(self):
        if len(self.topics) > MAX_PROFILE_TOPICS:
            raise ValueError("Profile exceeds the topic limit")
        if any(len(key) > 128 for key in self.topics):
            raise ValueError("Profile topic key is too long")
        if any(len(value) > 120 for value in self.recent_topics):
            raise ValueError("Profile recent topic entry is too long")
        if len(self.model_dump_json()) > MAX_PROFILE_BYTES:
            raise ValueError("Profile exceeds the size limit")
        return self


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

    @model_validator(mode="after")
    def message_required_for_text_actions(self):
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
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)


class ChatTurnResponse(WebContract):
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
    blocks: list[dict[str, Any]] = Field(default_factory=list)
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
