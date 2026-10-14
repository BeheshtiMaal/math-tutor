"""Closed component-event protocol and bounded checkpointed ordering ledger."""
from datetime import datetime, timedelta
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator
from langchain_core.messages import AIMessage

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')

class StepPayload(Contract):
    step_id: str = Field(pattern=r'^[A-Za-z0-9:_-]{1,16}$')

class GraphPayload(Contract):
    params: dict[str, Annotated[float, Field(strict=True, allow_inf_nan=False, ge=-1_000_000, le=1_000_000)]] = Field(max_length=4)
    @field_validator('params')
    @classmethod
    def symbols(cls, value):
        import re
        if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,11}', key) for key in value):
            raise ValueError('Invalid parameter name')
        return value

class ErrorPayload(Contract):
    code: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')

class Envelope(Contract):
    event_id: str = Field(pattern=r'^evt_[0-7][0-9A-HJKMNP-TV-Z]{25}$')
    thread_id: str = Field(pattern=r'^thr_[0-7][0-9A-HJKMNP-TV-Z]{25}$')
    block_id: str = Field(pattern=r'^blk_[0-7][0-9A-HJKMNP-TV-Z]{25}$')
    seq: int = Field(strict=True, ge=1, le=9_007_199_254_740_991)
    sent_at: datetime
    @field_validator('sent_at', mode='before')
    @classmethod
    def timestamp(cls, value):
        if not isinstance(value,(str,datetime)) or (isinstance(value,str) and (len(value)>64 or 'T' not in value)):
            raise ValueError('ISO timestamp required')
        return value
    @field_validator('sent_at')
    @classmethod
    def utc(cls, value):
        if value.utcoffset() != timedelta(0):
            raise ValueError('UTC timestamp required')
        return value

class StepConfused(Envelope):
    type: Literal['step_confused']
    payload: StepPayload

class GraphQuestion(Envelope):
    type: Literal['graph_question']
    payload: GraphPayload

class BlockError(Envelope):
    type: Literal['block_error']
    payload: ErrorPayload

UIEvent = Annotated[StepConfused | GraphQuestion | BlockError, Field(discriminator='type')]
event_adapter = TypeAdapter(UIEvent)
HISTORY_ID = 'component_event_history'

def history(state):
    for message in reversed(state.get('messages', [])):
        if message.id == HISTORY_ID:
            return message.additional_kwargs
    return {'seq': 0, 'ids': []}

def disposition(state, event):
    saved = history(state)
    if event.event_id in saved.get('ids', []): return 'duplicate'
    if event.seq <= saved.get('seq', 0): return 'stale'
    return 'accepted'

def remember(state, event):
    saved = history(state)
    return AIMessage(id=HISTORY_ID, content='', additional_kwargs={
        'seq': event.seq, 'ids': [*saved.get('ids', []), event.event_id][-128:]})
