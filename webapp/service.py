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
import time
from typing import Any

from langgraph.types import Command
from langsmith import tracing_context
from pydantic import ValidationError

from agent import AppConfig, LearnerProfile, LearnerRuntime, Request, load_core_topics, new_request_state

from .errors import ApiError, ErrorCode
from .schemas import (
    MAX_PROFILE_BYTES,
    ChatTurnRequest,
    ChatTurnResponse,
    InterruptInfo,
    LessonState,
    Segment,
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


class TutorService:
    """Invoke and resume the compiled graph; own thread bookkeeping."""

    def __init__(
        self,
        *,
        config: AppConfig,
        graph: Any,
        registry: ThreadRegistry,
        turn_timeout_seconds: float = 120.0,
        settings=None,
    ) -> None:
        self.config = config
        self.graph = graph
        self.registry = registry
        self.turn_timeout_seconds = turn_timeout_seconds
        # The same registry the graph itself uses (spec section 13.1).
        self._core_topics = load_core_topics(config.sources_dir)
        self._streams = {}
        self._ui_blocks = {}
        self._sample_limits = {}
        self._sample_slots = asyncio.Semaphore(4)
        self._event_limits = {}
        from .settings import ServerSettings
        from .usage import UsageLedger
        self.usage = UsageLedger(settings or ServerSettings())

    def remember_blocks(self, thread_id, blocks):
        """Keep bounded graph definitions for direct sampling of prior turns."""
        from .ui_blocks import block_adapter, GraphBlock, GraphRequest, GeometryBlock, GeometryRequest, StepBlock
        library = self._ui_blocks.setdefault(thread_id, {})
        for raw in blocks:
            block = block_adapter.validate_python(raw)
            if isinstance(block, GraphBlock):
                # Old slider definitions stay small: prior sampled point arrays
                # already live in the client transcript/current checkpoint.
                library[block.id] = GraphRequest(type=block.type, title=block.title,
                    fallback_text=block.fallback_text,
                    params=block.params.model_dump(exclude={"samples"}))
            elif isinstance(block, GeometryBlock):
                library[block.id] = GeometryRequest(type=block.type,title=block.title,
                    fallback_text=block.fallback_text,params=block.params.model_dump(exclude={"geometry"}))
            elif isinstance(block, StepBlock):
                library[block.id] = block
        while len(library) > 32:
            del library[next(iter(library))]

    async def sample(self, payload):
        from .providers import ProviderFailure, sample_graph
        from .ui_blocks import GraphRequest, SampleResult
        self.sweep()
        record = self.registry.get(payload.thread_id)
        if record is None:
            raise ApiError(ErrorCode.THREAD_NOT_FOUND, "error.thread_not_found")
        now = time.monotonic()
        tokens, last = self._sample_limits.get(payload.thread_id, (20.0, now))
        tokens = min(20.0, tokens + max(0, now - last) * 10)
        if tokens < 1 or self._sample_slots.locked():
            raise ApiError(ErrorCode.RATE_LIMITED, "error.rate_limited")
        self._sample_limits[payload.thread_id] = (tokens - 1, now)
        block = self._ui_blocks.get(payload.thread_id, {}).get(payload.block_id)
        if not isinstance(block, GraphRequest):
            raise ApiError(ErrorCode.BLOCK_INVALID, "error.block_invalid")
        params = block.params
        if (payload.expressions != params.expressions or payload.domain != params.domain
                or payload.highlight_points != params.highlight_points
                or set(payload.parameters) != {slider.name for slider in params.parameters}
                or any(not slider.min <= payload.parameters[slider.name] <= slider.max for slider in params.parameters)):
            raise ApiError(ErrorCode.BLOCK_INVALID, "error.block_invalid")
        async with self._sample_slots:
            try:
                samples = await sample_graph(payload, self.config.limits)
                record.last_active_at = self.registry._now()
                return samples
            except ProviderFailure as exc:
                if str(exc) == "timeout":
                    raise ApiError(ErrorCode.TURN_TIMEOUT, "error.math_timeout") from None
                if str(exc) == "busy":
                    raise ApiError(ErrorCode.RATE_LIMITED, "error.rate_limited") from None
                return SampleResult(status="invalid_expression", domain_warnings=[
                    "base must be > 0 and != 1" if str(exc) == "log_base" else "Sampling could not be completed safely."])

    async def geometry(self, payload):
        from .geometry import compute_geometry
        from .ui_blocks import GeometryRequest
        self.sweep()
        record = self.registry.get(payload.thread_id)
        if record is None:
            raise ApiError(ErrorCode.THREAD_NOT_FOUND, "error.thread_not_found")
        block = self._ui_blocks.get(payload.thread_id, {}).get(payload.block_id)
        if not isinstance(block, GeometryRequest) or payload.scene.kind != block.params.scene.kind:
            raise ApiError(ErrorCode.BLOCK_INVALID, "error.block_invalid")
        now = time.monotonic()
        tokens,last = self._sample_limits.get(payload.thread_id,(20.0,now))
        tokens = min(20.0,tokens + max(0,now-last)*10)
        if tokens<1 or self._sample_slots.locked():
            raise ApiError(ErrorCode.RATE_LIMITED,"error.rate_limited")
        self._sample_limits[payload.thread_id] = (tokens-1,now)
        async with self._sample_slots:
            result = compute_geometry(payload.scene)
            record.last_active_at = self.registry._now()
            return result

    # ---------------------------------------------------------------- topics

    def topic_kind(self, topic: str | None) -> str:
        """Fallback classifier; the graph's own ``topic_kind`` is preferred."""
        from agent import topic_kind_of

        return topic_kind_of(topic, self._core_topics)

    # ---------------------------------------------------------------- public

    async def turn(self, request: ChatTurnRequest) -> ChatTurnResponse:
        """Run one turn. Never raises for an unknown thread; returns a status."""
        self._sweep()
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
        awaiting = False
        meter, started, outcome = None, time.monotonic(), 'error'
        try:
            resume, ignored = await self.prepare_resume(request)
            if ignored:
                awaiting = bool(ignored.lesson and ignored.lesson.awaiting_user)
                return ignored
            from model_usage import usage_scope
            meter = self.usage.begin(request.thread_id)
            with usage_scope(meter):
                result = await self._run(request, profile)
            awaiting = bool(result.get("__interrupt__"))
            outcome = 'ok'
        except asyncio.TimeoutError:
            raise ApiError(
                ErrorCode.TURN_TIMEOUT,
                "error.turn_timeout",
                detail=f"The turn exceeded its {self.turn_timeout_seconds:g} second limit.",
            ) from None
        finally:
            if meter is not None:
                logged = self.usage.finish(request.thread_id,turn_id,meter,started,outcome)
            self.registry.end_turn(request.thread_id, awaiting_user=awaiting)
        response = self._response(request, result, turn_id, profile_status)
        if meter is not None:
            response.usage = Usage(**meter.public())
            if not logged: response.warnings.append('Local usage log could not be written.')
        return response

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
        self._ui_blocks.pop(thread_id, None)
        self._sample_limits.pop(thread_id, None)
        self._event_limits.pop(thread_id, None)
        self.usage.sessions.pop(thread_id,None)
        for key in [key for key in self._streams if key[0] == thread_id]:
            entry = self._streams.pop(key)
            if not entry["task"].done():
                entry["task"].cancel()
        checkpointer = getattr(self.graph, "checkpointer", None)
        delete = getattr(checkpointer, "delete_thread", None)
        if callable(delete):
            try:
                delete(thread_id)
            except Exception:  # a failed cleanup must not break the request
                pass

    async def _run(self, request: ChatTurnRequest, profile: LearnerProfile | None) -> dict[str, Any]:
        thread = {"configurable": {"thread_id": request.thread_id}}
        previous_warnings = 0
        if request.action != 'new_lesson':
            previous_warnings = len((await self.graph.aget_state(thread)).values.get('warnings',[]))
        with tracing_context(enabled=False):
            if request.action == "new_lesson":
                payload = self._new_state(request, profile)
                coroutine = self.graph.ainvoke(payload, thread, context=self.runtime_context(request,profile))
            else:
                resume, _ = await self.prepare_resume(request, consume=False)
                coroutine = self.graph.ainvoke(Command(resume=resume), thread, context=self.runtime_context(request,profile))
            async def complete_turn():
                result = await coroutine
                handoff = self.topic_handoff(result, request, profile)
                if handoff is not None:
                    result = await self.graph.ainvoke(handoff, thread, context=self.runtime_context(request,profile))
                return result
            result = await asyncio.wait_for(complete_turn(), timeout=self.turn_timeout_seconds)
        return {**result,'warnings':result.get('warnings',[])[previous_warnings:]}

    def topic_handoff(self, result, request, profile):
        """Consume the graph's explicit fresh-request signal, without classifying here."""
        question = result.get('new_topic_query')
        if not question or result.get('__interrupt__'):
            return None
        return self._new_state(request.model_copy(update={'action':'new_lesson','message':question}), profile)

    async def stream(self, request: ChatTurnRequest, request_id: str | None = None):
        """Translate actual graph updates to safe transport events; never route.

        Writer output is structured and validated before we emit bounded deltas.
        Raw provider tokens may contain JSON/source IDs and are never forwarded.
        """
        from .streaming import stream_turn
        self.sweep()
        if request.action != "new_lesson" and not self.registry.known(request.thread_id):
            # Unknown threads have no graph work to replay and must not grow the
            # in-memory response cache outside the bounded thread registry.
            async for event in stream_turn(self, request):
                yield event
            return
        if request_id is None:
            async for event in stream_turn(self, request):
                yield event
            return
        if not request_id or len(request_id) > 80 or not all(char.isalnum() or char in "-_" for char in request_id):
            yield ("error", {"code": "bad_request", "message_key": "error.bad_request", "recoverable": False})
            yield ("turn_end", {"thread_id": request.thread_id, "turn_id": None, "awaiting_user": False,
                               "lesson": None, "usage": {"prompt_tokens": None, "completion_tokens": None}})
            return
        key = (request.thread_id, request_id)
        import hashlib
        fingerprint = hashlib.sha256(request.model_dump_json(exclude={'learner_profile'}).encode("utf-8")).hexdigest()
        entry = self._streams.get(key)
        if entry is not None and entry["fingerprint"] != fingerprint:
            yield ("error", {"code": "bad_request", "message_key": "error.bad_request", "recoverable": False})
            yield ("turn_end", {"thread_id": request.thread_id, "turn_id": None, "awaiting_user": False,
                               "lesson": None, "usage": {"prompt_tokens": None, "completion_tokens": None}})
            return
        if entry is None:
            # Keep at most the latest completed turn and one active turn per thread.
            for old_key in [old for old, value in self._streams.items()
                            if old[0] == request.thread_id and value["done"]]:
                self._streams.pop(old_key)
            entry = {"fingerprint": fingerprint, "events": [], "changed": asyncio.Condition(), "done": False}
            self._streams[key] = entry

            async def run_turn():
                try:
                    async for event in stream_turn(self, request):
                        async with entry["changed"]:
                            entry["events"].append(event)
                            entry["changed"].notify_all()
                finally:
                    async with entry["changed"]:
                        entry["done"] = True
                        entry["changed"].notify_all()
            entry["task"] = asyncio.create_task(run_turn())
        cursor = 0
        # Disconnect only detaches this subscriber. The bounded graph turn finishes
        # once, allowing a retry to replay its exact events without advancing twice.
        while True:
            async with entry["changed"]:
                await entry["changed"].wait_for(lambda: cursor < len(entry["events"]) or entry["done"])
                buffered = entry["events"][cursor:]
                cursor += len(buffered)
                done = entry["done"]
            for event in buffered:
                yield event
            if done:
                break

    async def close(self):
        tasks = [entry["task"] for entry in self._streams.values() if not entry["task"].done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._ui_blocks.clear()
        self._sample_limits.clear()
        self._event_limits.clear()

    def _new_state(self, request: ChatTurnRequest, profile: LearnerProfile | None):
        try:
            payload = Request(
                query=request.message,
                mode=request.mode,
                language=request.language_override,
                learner_level=request.level if request.level_source!='inferred' else None,
                delivery_mode=request.delivery,
                # Spec section 8: the validated profile travels in the request
                # state so nodes may read it. It is never persisted by the server.
                learner_profile=None,
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

    def runtime_context(self,request,profile):
        manual=request.level if request.level_source!='inferred' else None
        if manual is None and request.level_source is None:
            manual=self.config.preferences.learner_level
        return LearnerRuntime(profile=profile,manual_level=manual,automatic=manual is None)

    async def prepare_resume(self, request, consume=True):
        """Bind an event to issued content; progression remains in user_input."""
        if request.action != 'ui_event':
            return (self._resume_text(request) if request.action != 'new_lesson' else None), None
        from ui_events import disposition
        from .ui_blocks import GraphRequest, StepBlock
        event = request.ui_event
        snapshot = await self.graph.aget_state({'configurable': {'thread_id': request.thread_id}})
        status = disposition(snapshot.values, event)
        if status != 'accepted':
            response = self._response(request, {**snapshot.values, '__interrupt__': snapshot.interrupts}, new_turn_id(), 'absent')
            return None, response.model_copy(update={'segments': [], 'blocks': [], 'event_status': status})
        block = self._ui_blocks.get(request.thread_id, {}).get(event.block_id)
        if block is None:
            raise ApiError(ErrorCode.BLOCK_INVALID, 'error.block_invalid')
        if event.type == 'step_confused':
            if not isinstance(block, StepBlock) or event.payload.step_id not in {s.step_id for s in block.params.steps}:
                raise ApiError(ErrorCode.BLOCK_INVALID, 'error.block_invalid')
        if event.type == 'graph_question':
            if (not isinstance(block, GraphRequest) or set(event.payload.params) != {s.name for s in block.params.parameters}
                    or any(not s.min <= event.payload.params[s.name] <= s.max for s in block.params.parameters)):
                raise ApiError(ErrorCode.BLOCK_INVALID, 'error.block_invalid')
        if not snapshot.interrupts:
            raise ApiError(ErrorCode.BAD_REQUEST, 'error.bad_request')
        if consume:
            now = time.monotonic()
            recent = [stamp for stamp in self._event_limits.get(request.thread_id, []) if now-stamp < 5]
            if len(recent) >= 5:
                raise ApiError(ErrorCode.RATE_LIMITED, 'error.rate_limited')
            self._event_limits[request.thread_id] = [*recent, now]
        return {'ui_event': event.model_dump(mode='json'), 'block': block.model_dump(mode='json')}, None

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
        if len(profile.model_dump_json().encode('utf-8')) > MAX_PROFILE_BYTES:
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
        degraded = any(any(term in warning for term in ('Explanation synthesis failed','Lesson planning failed','پاسخ تازه در دسترس نیست'))
                       for warning in result.get('warnings',[]))
        degraded = degraded or any(getattr(result.get(key),'status',None)=='error' for key in ('source','websearch'))
        degraded = degraded or 'Using labelled keyword/metadata fallback.' in (getattr(result.get('source'),'warning',None) or '')
        # Spec section 12.1: the writer returns typed segments and a separate
        # block list. The fallback only covers a graph that produced neither.
        raw_segments = result.get("explanation_segments") or []
        if raw_segments:
            segments = [
                Segment(kind=item["kind"], text=item["text"]) if isinstance(item, dict)
                else Segment(kind=item.kind, text=item.text)
                for item in raw_segments
            ]
        else:
            text = (result.get("explanation") or "") if mode == "learn" else (result.get("final_answer") or "")
            segments = [Segment(kind="text" if mode == "learn" else "answer", text=text)] if text else []

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
            concept=(plan[min(step_index,len(plan)-1)].objective[:120] if plan else (result.get('topic') or '')[:120]) or None,
            step_index=step_index,
            total_steps=len(plan),
            awaiting_user=bool(interrupt),
            can_continue=bool(plan) and not lesson_complete,
        )
        if result.get("level_source"):
            level_source = result["level_source"]
        elif request.level:
            level_source = request.level_source or "manual"
        else:
            level_source = "default"
        blocks = list(result.get("ui_blocks") or []) if request.action != "done" else []
        if blocks:
            self.remember_blocks(request.thread_id, blocks)
        return ChatTurnResponse(
            degraded=degraded,
            event_status='accepted' if request.action == 'ui_event' else None,
            status="ok",
            thread_id=request.thread_id,
            turn_id=turn_id,
            language=result.get("language"),
            language_source=result.get("language_source") or ("override" if request.language_override else "detected"),
            topic=result.get("topic"),
            topic_kind=result.get("topic_kind") or self.topic_kind(result.get("topic")),
            mode=mode,
            delivery=result.get("delivery_mode"),
            learner_level=result.get("learner_level"),
            level_source=level_source,
            level_suggestion=result.get('level_suggestion'),
            segments=segments,
            blocks=blocks,
            lesson=lesson,
            interrupt=interrupt,
            next_request=result.get("new_topic_query"),
            profile_status=profile_status,
            warnings=list(result.get("warnings") or []),
            usage=Usage(),
        )
