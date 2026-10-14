"""Checkpointed visual novelty, using the existing message-history state."""
import json
import re

from langchain_core.messages import AIMessage

from agent import BlockRequest

HISTORY_ID = "lesson_visual_history"


def visual_key(raw):
    """Compare teaching content, ignoring titles, sampling and cosmetic changes."""
    raw = raw.model_dump(mode="json") if isinstance(raw, BlockRequest) else raw
    if not isinstance(raw, dict) or not isinstance(raw.get("params"), dict):
        return None
    params = raw["params"]
    def expression(value):
        return re.sub(r"\s+", "", value).replace("**", "^") if isinstance(value, str) else None
    if raw.get("type") == "function_graph":
        values = params.get("expressions")
        if not isinstance(values, list) or not values or any(not isinstance(row, dict) for row in values):
            return None
        content = sorted(expression(row.get("expression")) or "" for row in values)
        if not all(content):
            return None
    elif raw.get("type") == "step_reveal":
        values = params.get("steps")
        if not isinstance(values, list) or any(not isinstance(row, dict) for row in values):
            return None
        content = [expression(row.get("state")) for row in values]
    elif raw.get("type") == "geometry_canvas":
        scene = params.get("scene")
        if not isinstance(scene,dict):
            return None
        content = dict(scene)
        if content.get("kind") == "unit_circle":
            content.pop("angle_degrees",None)
    else:
        return None
    return json.dumps([raw["type"], content], ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def shown_keys(state):
    if not state.get("explanation_version"):
        return []
    for message in reversed(state.get("messages", [])):
        if message.id == HISTORY_ID:
            history = message.additional_kwargs
            if history.get("lesson_objective") == state.get("lesson_objective"):
                return list(history.get("visual_keys", []))
    return []


def fresh_requests(raw, state, *, repeat_types=()):
    seen = set(shown_keys(state))
    kept, current = [], set()
    for item in raw:
        key = visual_key(item)
        kind=item.type if isinstance(item,BlockRequest) else item.get('type') if isinstance(item,dict) else None
        if key is None or key not in seen or (kind in repeat_types and key not in current):
            kept.append(item)
            if key is not None:
                seen.add(key)
                current.add(key)
    return kept


def fresh_defaults(raw, state):
    # A generic topic graph is an introduction, not a replacement for the chart
    # already teaching that lesson. New functions can still come from the writer.
    has_intro_visual = bool(shown_keys(state))
    return fresh_requests([item for item in raw if not (has_intro_visual and item.get("type") == "function_graph")], state)


def remember_visuals(state, requested, emitted, *, repeat_types=()):
    """Record only successfully emitted visuals; rejected requests can retry."""
    seen = set(shown_keys(state))
    keys = list(shown_keys(state))
    fresh_requests_out, fresh_blocks = [], []
    current=set()
    for request, block in zip(requested, emitted):
        key = visual_key(block)
        if key in current or (key in seen and block.get('type') not in repeat_types):
            continue
        fresh_requests_out.append(request)
        fresh_blocks.append(block)
        current.add(key)
        if key is not None and key not in seen:
            keys.append(key)
            seen.add(key)
    update = {}
    if fresh_blocks:
        update["messages"] = [AIMessage(id=HISTORY_ID, content="", additional_kwargs={
            "lesson_objective": state.get("lesson_objective"), "visual_keys": keys[-64:]})]
    return fresh_requests_out, fresh_blocks, update
