"""W4 SSE transport for the existing compiled graph, with cancellation cleanup."""
import asyncio
import json
import time
from contextlib import suppress

from langgraph.types import Command
from langsmith import tracing_context

from .errors import ApiError, ErrorCode
from .threads import new_turn_id


def sse(event, payload):
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def progress(state):
    return ("status", {"state": state, "message_key": f"status.{state}"})


async def stream_turn(service, request):
    turn_id, owned, awaiting = new_turn_id(), False, False
    terminal = {"thread_id": request.thread_id, "turn_id": turn_id,
                "awaiting_user": False, "lesson": None,
                "usage": {"prompt_tokens": None, "completion_tokens": None}}
    producer = None
    meter, started, outcome = None, time.monotonic(), 'error'
    try:
        service.sweep()
        if request.action != "new_lesson" and not service.registry.known(request.thread_id):
            yield progress("thread_not_found")
            terminal["status"] = "thread_not_found"
        else:
            profile, profile_status = service._profile(request)
            if not service.registry.begin_turn(request.thread_id):
                raise ApiError(ErrorCode.TURN_IN_PROGRESS, "error.turn_in_progress")
            owned = True
            resume, ignored = await service.prepare_resume(request)
            if ignored:
                awaiting = bool(ignored.lesson and ignored.lesson.awaiting_user)
                terminal.update(ignored.model_dump(mode='json', exclude={'segments', 'blocks'}))
                terminal['awaiting_user'] = awaiting
                yield ('turn_end', terminal)
                return
            input_state = service._new_state(request, profile) if request.action == "new_lesson" else Command(resume=resume)
            from model_usage import usage_scope
            meter = service.usage.begin(request.thread_id)
            thread = {"configurable": {"thread_id": request.thread_id}}
            queue = asyncio.Queue(maxsize=8)

            async def produce():
                try:
                    with tracing_context(enabled=False), usage_scope(meter):
                        current_input = input_state
                        # The graph, including user_input, decides whether this
                        # is a new topic. Complete its handoff in this same turn.
                        for invocation in range(2):
                            handoff = None
                            async for update in service.graph.astream(current_input, thread, stream_mode="updates",context=service.runtime_context(request,profile)):
                                values = update.get('user_input') or {}
                                if isinstance(values, dict) and invocation == 0:
                                    handoff = service.topic_handoff(values, request, profile) or handoff
                                await queue.put(update)
                            if handoff is None:
                                break
                            current_input = handoff
                except Exception as exc:
                    await queue.put(exc)
                else:
                    await queue.put(None)

            producer = asyncio.create_task(produce())
            yield progress("queued")
            phase = "classifying" if request.action == "new_lesson" else "writing"
            yield progress(phase)
            deadline = time.monotonic() + service.turn_timeout_seconds
            interruptions = ()
            emitted = False
            turn_warnings = []
            resources_pending = {"read_source", "verified_examples", "teaching_bestpractices", "web_search"}
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise asyncio.TimeoutError()
                try:
                    update = await asyncio.wait_for(queue.get(), min(10, remaining))
                except asyncio.TimeoutError:
                    if time.monotonic() >= deadline:
                        raise
                    # Keep intermediaries alive while a bounded provider call runs.
                    yield progress(phase)
                    continue
                if update is None:
                    break
                if isinstance(update, Exception):
                    raise update
                if "__interrupt__" in update:
                    interruptions = update["__interrupt__"]
                for node, values in update.items():
                    if node == "__interrupt__" or not isinstance(values, dict):
                        continue
                    turn_warnings.extend(values.get('warnings',[]))
                    next_phase = {"learn": "retrieving", "answer": "computing", "math_tool": "writing"}.get(node)
                    if node in resources_pending:
                        resources_pending.remove(node)
                        if not resources_pending:
                            next_phase = "writing"
                    if next_phase and phase != next_phase:
                        phase = next_phase
                        yield progress(phase)
                    if node in {"write_explanation", "write_answer"}:
                        for index, segment in enumerate(values.get("explanation_segments") or []):
                            kind = segment["kind"] if isinstance(segment, dict) else segment.kind
                            text = segment["text"] if isinstance(segment, dict) else segment.text
                            if kind not in {"text", "answer"}:
                                continue
                            for offset in range(0, len(text), 96):
                                yield ("text", {"segment_index": index, "kind": kind, "delta": text[offset:offset + 96]})
                                emitted = True
                                await asyncio.sleep(0.008)
                        blocks = values.get("ui_blocks") or []
                        if blocks:
                            from .ui_blocks import block_adapter
                            yield progress("validating_block")
                            validated = [block_adapter.validate_python(block).model_dump(mode="json", by_alias=True) for block in blocks]
                            service.remember_blocks(request.thread_id, validated)
                            for block in validated:
                                yield ("block", {"block": block})
            snapshot = await service.graph.aget_state(thread)
            result = {**snapshot.values, "__interrupt__": interruptions,'warnings':turn_warnings}
            response = service._response(request, result, turn_id, profile_status)
            # Some safe graph exits have only a final deterministic response.
            if not emitted and request.action != "done":
                for index, segment in enumerate(response.segments):
                    yield ("text", {"segment_index": index, "kind": segment.kind, "delta": segment.text})
            awaiting = bool(response.interrupt)
            terminal.update(response.model_dump(mode="json", exclude={"segments", "blocks"}))
            terminal["awaiting_user"] = awaiting
            terminal['usage'] = meter.public()
            outcome = 'ok'
            yield progress("waiting_for_user" if awaiting else "done")
    except asyncio.CancelledError:
        # A disconnected socket cannot receive a terminal event. Stop graph work.
        raise
    except Exception as exc:
        code = exc.code if isinstance(exc, ApiError) else (ErrorCode.TURN_TIMEOUT if isinstance(exc, asyncio.TimeoutError) else ErrorCode.INTERNAL_ERROR)
        key = exc.message_key if isinstance(exc, ApiError) else f"error.{code.value}"
        yield ("error", {"code": code.value, "message_key": key,
                         "recoverable": code in {ErrorCode.TURN_TIMEOUT, ErrorCode.TURN_IN_PROGRESS}})
        terminal["status"] = "error"
    finally:
        if producer is not None:
            if not producer.done():
                producer.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await producer
        if owned:
            if meter is not None:
                terminal['usage'] = meter.public()
                if not service.usage.finish(request.thread_id,turn_id,meter,started,outcome):
                    terminal.setdefault('warnings',[]).append('Local usage log could not be written.')
            service.registry.end_turn(request.thread_id, awaiting_user=awaiting)
    yield ("turn_end", terminal)
