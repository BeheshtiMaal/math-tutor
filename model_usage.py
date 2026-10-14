"""Ephemeral per-turn usage; never messages, keys, profiles or checkpoint state."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock
from langchain_core.callbacks import BaseCallbackHandler

CURRENT_USAGE = ContextVar('tutor_usage', default=None)

class SessionLimitReached(RuntimeError):
    pass

@dataclass
class TurnUsage:
    before_call: object = None
    attempted_calls: int = 0
    reported_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    limit_reached: bool = False

    def start_call(self):
        if self.before_call:
            self.before_call(self)
        self.attempted_calls += 1

    def public(self):
        complete = self.attempted_calls == self.reported_calls
        return {'prompt_tokens': self.prompt_tokens if complete else None,
                'completion_tokens': self.completion_tokens if complete else None,
                'limit_reached':self.limit_reached}

@contextmanager
def usage_scope(meter):
    token = CURRENT_USAGE.set(meter)
    try: yield meter
    finally: CURRENT_USAGE.reset(token)

class UsageCallback(BaseCallbackHandler):
    def __init__(self, meter):
        self.meter = meter
        self.lock = Lock()
        self.seen = set()

    def on_llm_end(self, response, *, run_id, **kwargs):
        with self.lock:
            if run_id in self.seen: return
            self.seen.add(run_id)
            for group in response.generations:
                for generation in group[:1]:
                    message = getattr(generation, 'message', None)
                    usage = getattr(message, 'usage_metadata', None)
                    if not usage:
                        raw = getattr(message, 'response_metadata', {}) or {}
                        raw = raw.get('token_usage') or (response.llm_output or {}).get('token_usage') or {}
                        usage = {'input_tokens':raw.get('prompt_tokens'), 'output_tokens':raw.get('completion_tokens')}
                    prompt, completion = usage.get('input_tokens'), usage.get('output_tokens')
                    if type(prompt) is int and type(completion) is int and prompt >= 0 and completion >= 0:
                        self.meter.prompt_tokens += prompt
                        self.meter.completion_tokens += completion
                        self.meter.reported_calls += 1

def model_call_config():
    meter = CURRENT_USAGE.get()
    if meter is None: return {}
    meter.start_call()
    return {'callbacks':[UsageCallback(meter)]}
