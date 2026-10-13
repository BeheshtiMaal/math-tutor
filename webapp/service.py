"""Graph-invocation service layer.

This module owns exactly one thing: turning a validated HTTP request into an
``ainvoke`` on the compiled LangGraph, and mapping the resulting state back to
a response. It never inspects ``mode`` to pick a branch, never builds a route
table, and never re-implements progression — LangGraph owns all of that
(spec v3.0 section 4).

Resume semantics mirror ``cli.py``: a paused graph is continued with
``Command(resume=<text>)`` on the same thread, and the graph's own
``user_input`` node decides what that text means.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from langgraph.types import Command
from langsmith import tracing_context
from pydantic import ValidationError

from agent import AppConfig, Request, new_request_state

from .errors import ApiError, ErrorCode
from .schemas import (
    MAX_PROFILE_BYTES,
    ChatTurnRequest,
    ChatTurnResponse,
    InterruptInfo,
    LearnerProfile,
    LessonState,
    Segment,
    TopicKind,
    Usage,
)
from .threads import ThreadRegistry, new_turn_id

# Canonical control text for the existing graph actions. ``user_input`` parses
# these with ``lesson_steps.parse_reply``; the web layer adds no new meaning.
RESUME_TEXT: dict[str, str] = {
    "next": "next",
    "simplify": "simplify",
    "full": "full",
    "done": "done",
}


def load_core_topics(sources_dir: Path) -> set[str]:
    """Topic keys that have prepared local notes (spec section 13)."""
    keys: set[str] = set()
    registry = sources_dir / "manifests" / "topic_registry.json"
    if registry.is_file():
        try:
            data = json.loads(registry.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        for entry in data.get("topics", []) if isinstance(data, dict) else []:
            if not isinstance(entry, dict):
                continue
            for field in ("topic", "english", "persian"):
                value = entry.get(field)
                if isinstance(value, str) and value.strip():
                    keys.add(value.strip().lower())
    topics_dir = sources_dir / "topics"
    if topics_dir.is_dir():
        keys.update(path.stem.lower() for path in topics_dir.glob("*.md"))
    return keys


class TutorService:
    """Invoke and resume the compiled graph; own thread bookkeeping."""

    def __init__(
        self,
        *,
        config: AppConfig,
        graph: Any,
        registry: ThreadRegistry,
        turn_timeout_seconds: float = 120.0,
    ) -> None:
        self.config = config
        self.graph = graph
        self.registry = registry
        self.turn_timeout_seconds = turn_timeout_seconds
        self._core_topics = load_core_topics(config.sources_dir)
        self._last_awaiting = False

    # ---------------------------------------------------------------- topics

    def topic_kind(self, topic: str | None) -> TopicKind:
        if topic and topic.strip().lower() in self._core_topics:
            return "core"
        return "open"

    # ---------------------------------------------------------------- public

    async def turn(self, request: ChatTurnRequest) -> ChatTurnResponse:
        """Run one turn. Never raises for an unknown thread; returns a status."""
        self._sweep()
        if request.action == "ui_event":
            raise ApiError(
                ErrorCode.BAD_REQUEST,
                "error.action_not_supported",
                detail="ui_event is implemented in phase W7.",
            )
        if request.action != "new_lesson" and not self.registry.known(request.thread_id):
            return ChatTurnResponse(status="thread_not_found", thread_id=request.thread_id)

        turn_id = new_turn_id()
        profile, profile_status = self._profile(request)
        if not self.registry.begin_turn(request.thread_id):
            raise ApiError(
                ErrorCode.TURN_IN_PROGRESS,
                "error.turn_in_progress",
                detail="A turn is already running for this thread.",
            )
        try:
            result = await self._run(request)
        except asyncio.TimeoutError:
            raise ApiError(
                ErrorCode.TURN_TIMEOUT,
                "error.turn_timeout",
                detail=f"The turn exceeded its {self.turn_timeout_seconds:g} second limit.",
            ) from None
        finally:
            self.registry.end_turn(request.thread_id, awaiting_user=self._last_awaiting)
        return self._response(request, result, turn_id, profile_status)

    def sweep(self) -> list[str]:
        """Evict idle threads and drop their checkpoints. Never evicts active ones."""
        return self._sweep()

    # --------------------------------------------------------------- internal

    def _sweep(self) -> list[str]:
        evicted = self.registry.evict_idle()
        for thread_id in evicted:
            self._forget_checkpoint(thread_id)
        return evicted

    def _forget_checkpoint(self, thread_id: str) -> None:
        checkpointer = getattr(self.graph, "checkpointer", None)
        delete = getattr(checkpointer, "delete_thread", None)
        if callable(delete):
            try:
                delete(thread_id)
            except Exception:  # a failed cleanup must not break the request
                pass

    async def _run(self, request: ChatTurnRequest) -> dict[str, Any]:
        self._last_awaiting = False
        thread = {"configurable": {"thread_id": request.thread_id}}
        with tracing_context(enabled=False):
            if request.action == "new_lesson":
                payload = self._new_state(request)
                coroutine = self.graph.ainvoke(payload, thread)
            else:
                coroutine = self.graph.ainvoke(Command(resume=self._resume_text(request)), thread)
            result = await asyncio.wait_for(coroutine, timeout=self.turn_timeout_seconds)
        self._last_awaiting = bool(result.get("__interrupt__"))
        return result

    def _new_state(self, request: ChatTurnRequest):
        try:
            payload = Request(
                query=request.message,
                mode=request.mode,
                language=request.language_override,
                learner_level=request.level,
                delivery_mode=request.delivery,
            )
            return new_request_state(payload, self.config)
        except ValueError:
            raise ApiError(
                ErrorCode.BAD_REQUEST,
                "error.bad_request",
                detail="The request could not be prepared within the configured limits.",
            ) from None

    def _resume_text(self, request: ChatTurnRequest) -> str:
        if request.action == "followup":
            if not request.message:
                raise ApiError(
                    ErrorCode.BAD_REQUEST,
                    "error.bad_request",
                    detail="A follow-up requires a message.",
                )
            return request.message
        text = RESUME_TEXT.get(request.action)
        if text is None:
            raise ApiError(ErrorCode.BAD_REQUEST, "error.bad_request", detail="Unsupported action.")
        return text

    def _profile(self, request: ChatTurnRequest) -> tuple[LearnerProfile | None, str]:
        """Validate the client profile. An unusable profile never fails the turn.

        Spec section 8: bounded size, bounded lists, ignored unknown fields; on
        failure the turn proceeds without a profile and reports ``rejected``.
        """
        raw = request.learner_profile
        if raw is None:
            return None, "absent"
        try:
            profile = LearnerProfile.model_validate(raw)
        except ValidationError:
            return None, "rejected"
        if len(profile.model_dump_json()) > MAX_PROFILE_BYTES:
            return None, "rejected"
        return profile, "accepted"

    def _response(
        self,
        request: ChatTurnRequest,
        result: dict[str, Any],
        turn_id: str,
        profile_status: str,
    ) -> ChatTurnResponse:
        mode = result.get("mode")
        if mode == "learn":
            explanation = result.get("explanation") or ""
            segments = [Segment(kind="text", text=explanation)] if explanation else []
        else:
            answer = result.get("final_answer") or ""
            segments = [Segment(kind="answer", text=answer)] if answer else []

        plan = result.get("lesson_plan") or []
        step_index = int(result.get("step_index") or 0)
        interruptions = tuple(result.get("__interrupt__") or ())
        interrupt = None
        if interruptions:
            value = getattr(interruptions[0], "value", None) or {}
            interrupt = InterruptInfo(
                kind=str(value.get("kind") or "lesson"),
                prompt=str(value.get("prompt") or ""),
                delivery_mode=value.get("delivery_mode"),
                step_index=value.get("step_index"),
                lesson_complete=value.get("lesson_complete"),
            )
        lesson_complete = bool(result.get("lesson_complete"))
        lesson = LessonState(
            step_index=step_index,
            total_steps=len(plan),
            awaiting_user=bool(interrupt),
            can_continue=bool(plan) and not lesson_complete,
        )
        if request.level:
            level_source = request.level_source or "manual"
        else:
            level_source = "default"
        return ChatTurnResponse(
            status="ok",
            thread_id=request.thread_id,
            turn_id=turn_id,
            language=result.get("language"),
            language_source="override" if request.language_override else "detected",
            topic=result.get("topic"),
            topic_kind=self.topic_kind(result.get("topic")),
            mode=mode,
            delivery=result.get("delivery_mode"),
            learner_level=result.get("learner_level"),
            level_source=level_source,
            segments=segments,
            blocks=[],
            lesson=lesson,
            interrupt=interrupt,
            next_request=result.get("new_topic_query"),
            profile_status=profile_status,
            warnings=list(result.get("warnings") or []),
            usage=Usage(),
        )
