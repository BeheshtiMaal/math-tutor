"""Bounded local token log and per-server-session admission limits."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from model_usage import TurnUsage, SessionLimitReached
from .errors import ApiError, ErrorCode

class UsageLedger:
    def __init__(self, settings):
        self.settings = settings
        self.sessions = {}

    def begin(self, thread_id):
        row = self.sessions.setdefault(thread_id, {'turns':0,'calls':0,'tokens':0})
        if (row['turns'] >= self.settings.session_max_turns or row['calls'] >= self.settings.session_max_model_calls
                or row['tokens'] >= self.settings.session_max_tokens):
            raise ApiError(ErrorCode.SESSION_LIMIT,'error.session_limit')
        row['turns'] += 1
        def admit(meter):
            if (row['calls'] >= self.settings.session_max_model_calls or
                    row['tokens'] + meter.prompt_tokens + meter.completion_tokens >= self.settings.session_max_tokens):
                meter.limit_reached = True
                raise SessionLimitReached('Session limit reached')
            row['calls'] += 1
        return TurnUsage(before_call=admit)

    def finish(self, thread_id, turn_id, meter, started, status):
        row = self.sessions.get(thread_id)
        if row is not None: row['tokens'] += meter.prompt_tokens + meter.completion_tokens
        record = {'timestamp':datetime.now(timezone.utc).isoformat(), 'thread_id':thread_id, 'turn_id':turn_id,
                  **meter.public(), 'reported_prompt_tokens':meter.prompt_tokens,
                  'reported_completion_tokens':meter.completion_tokens,
                  'model_calls':meter.attempted_calls, 'reported_calls':meter.reported_calls,
                  'elapsed_seconds':round(time.monotonic()-started,3),'status':status}
        try:
            path = Path(self.settings.usage_log_path)
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists() and path.stat().st_size >= 2_000_000:
                path.replace(path.with_suffix(path.suffix+'.1'))
            with path.open('a',encoding='utf-8') as output:
                output.write(json.dumps(record,separators=(',',':'))+'\n')
            return True
        except OSError:
            return False
