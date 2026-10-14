"""W9 usage, budgets and request-boundary checks without external services."""
import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult,ChatGeneration
import agent
from model_usage import TurnUsage, UsageCallback, usage_scope, model_call_config, SessionLimitReached
from webapp.usage import UsageLedger
from webapp.settings import ServerSettings
from webapp.security import LocalRequestGuard
from webapp.errors import ApiError
from webapp.main import create_app
from webapp.threads import new_thread_id
from webapp.schemas import ChatTurnRequest
from test_learner_memory import setup_app
from test_learning_graph import source,evidence
from test_web_streaming import events
from test_ui_backend import direct_provider

def reported(meter,prompt=10,completion=4):
    message=AIMessage(content='SECRET_MESSAGE_NOT_LOGGED',usage_metadata={'input_tokens':prompt,'output_tokens':completion,'total_tokens':prompt+completion})
    UsageCallback(meter).on_llm_end(LLMResult(generations=[[ChatGeneration(message=message)]]),run_id=uuid4())

class UsageChecks(unittest.IsolatedAsyncioTestCase):
    async def test_context_isolation_and_unknown_metadata(self):
        async def call(prompt):
            meter=TurnUsage()
            with usage_scope(meter):
                config=model_call_config();await asyncio.sleep(0)
                self.assertEqual(len(config['callbacks']),1)
                reported(meter,prompt)
            return meter.public()
        left,right=await asyncio.gather(call(12),call(30))
        self.assertEqual(left['prompt_tokens'],12);self.assertEqual(right['prompt_tokens'],30)
        self.assertEqual(model_call_config(),{})
        missing=TurnUsage();missing.start_call();self.assertIsNone(missing.public()['prompt_tokens'])

    async def test_adapter_collects_structured_and_text_usage_without_changing_output(self):
        class Delegate:
            def with_structured_output(self,schema,**kwargs):self.schema=schema;return self
            async def ainvoke(self,messages,config=None):
                result=LLMResult(generations=[[ChatGeneration(message=AIMessage(content='ok',usage_metadata={'input_tokens':5,'output_tokens':2,'total_tokens':7}))]])
                for callback in (config or {}).get('callbacks',[]):callback.on_llm_end(result,run_id=uuid4())
                return SimpleNamespace(content='ok') if self.schema is None else self.schema.model_validate({'action':'done'})
        client=object.__new__(agent.OpenAIModelClient);client._client=Delegate();client._client.schema=None
        from lesson_steps import LessonReply
        meter=TurnUsage()
        with usage_scope(meter):
            self.assertEqual((await client.structured([],LessonReply)).action,'done')
            client._client.schema=None;self.assertEqual(await client.text([]),'ok')
        self.assertEqual(meter.public(),{'prompt_tokens':10,'completion_tokens':4,'limit_reached':False})

    async def test_duplicate_callback_does_not_double_charge(self):
        meter=TurnUsage();meter.start_call();callback=UsageCallback(meter);identity=uuid4()
        result=LLMResult(generations=[[ChatGeneration(message=AIMessage(content='',usage_metadata={'input_tokens':7,'output_tokens':3,'total_tokens':10}))]])
        callback.on_llm_end(result,run_id=identity);callback.on_llm_end(result,run_id=identity)
        self.assertEqual(meter.public()['prompt_tokens'],7)

class LedgerChecks(unittest.TestCase):
    def test_limits_rotation_and_metadata_only_log(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'usage.jsonl'
            ledger=UsageLedger(ServerSettings(usage_log_path=str(path),session_max_turns=2,session_max_model_calls=1,session_max_tokens=5))
            meter=ledger.begin('thread');meter.start_call();reported(meter,4,2)
            with self.assertRaises(SessionLimitReached):meter.start_call()
            self.assertTrue(meter.limit_reached)
            self.assertTrue(ledger.finish('thread','turn',meter,time.monotonic(),'ok'))
            with self.assertRaises(ApiError):ledger.begin('thread')
            text=path.read_text();self.assertNotIn('SECRET_MESSAGE',text);self.assertNotIn('learner_profile',text)
            path.write_text('x'*2_000_000)
            next_meter=ledger.begin('other');ledger.finish('other','turn2',next_meter,time.monotonic(),'ok')
            self.assertTrue(path.with_suffix('.jsonl.1').exists());self.assertLess(path.stat().st_size,1000)

    def test_stream_replay_is_logged_once_and_limit_is_visible(self):
        app,service,_,_,_=setup_app()
        with tempfile.TemporaryDirectory() as folder,patch('webapp.ui_pipeline.run_provider',direct_provider):
            path=Path(folder)/'usage.jsonl';service.usage=UsageLedger(ServerSettings(session_max_turns=1,usage_log_path=str(path)))
            thread=new_thread_id();body={'thread_id':thread,'message':'Explain logarithms','mode':'learn','delivery':'step'}
            with TestClient(app) as http:
                first=events(http.post('/api/chat/stream',json=body,headers={'X-Request-ID':'usage-replay'}))
                replay=events(http.post('/api/chat/stream',json=body,headers={'X-Request-ID':'usage-replay'}))
                self.assertEqual(first,replay);self.assertEqual(len(path.read_text().splitlines()),1)
                next_events=events(http.post('/api/chat/stream',json={'thread_id':thread,'action':'next'}))
                self.assertEqual(next(event[1]['code'] for event in next_events if event[0]=='error'),'session_limit')
                self.assertEqual(next_events[-1][0],'turn_end')
                self.assertEqual(service.usage.sessions[thread]['turns'],1)

    def test_log_failure_does_not_break_a_response_and_eviction_drops_budget(self):
        app,service,_,_,_=setup_app()
        with TestClient(app) as http,patch('webapp.ui_pipeline.run_provider',direct_provider),patch.object(service.usage,'finish',return_value=False):
            thread=new_thread_id();response=http.post('/api/chat/turn',json={'thread_id':thread,'message':'Explain logarithms','mode':'learn','delivery':'step'})
            self.assertEqual(response.status_code,200);self.assertIn('Local usage log could not be written.',response.json()['warnings'])
            service._forget_checkpoint(thread);self.assertNotIn(thread,service.usage.sessions)
            fallback=service._response(ChatTurnRequest(thread_id=thread,message='2x+5=17'),{'mode':'answer','source':evidence([source()]).model_copy(update={'warning':'Embedding service failed safely. Using labelled keyword/metadata fallback.'})},'turn','absent')
            self.assertTrue(fallback.degraded)

class BoundaryChecks(unittest.IsolatedAsyncioTestCase):
    async def test_chunked_oversize_is_rejected_before_downstream(self):
        sent=[];called=[]
        async def app(scope,receive,send):called.append(True)
        messages=iter([{'type':'http.request','body':b'x'*700,'more_body':True},{'type':'http.request','body':b'x'*700,'more_body':False}])
        async def receive():return next(messages)
        async def send(message):sent.append(message)
        guard=LocalRequestGuard(app,max_bytes=1024,origins=['http://localhost:3000'])
        await guard({'type':'http','method':'POST','headers':[]},receive,send)
        self.assertEqual(sent[0]['status'],413);self.assertEqual(called,[])

    async def test_backend_rejects_foreign_and_null_origins_without_secret_echo(self):
        app,_,_,_,_=setup_app()
        with TestClient(app) as http:
            for origin in ('https://attacker.example','null'):
                response=http.post('/api/chat/turn',json={'secret':'NEVER_ECHO_THIS'},headers={'Origin':origin})
                self.assertEqual(response.status_code,403);self.assertNotIn('NEVER_ECHO_THIS',response.text)
            for headers in ({'Content-Type':'application/json'},{'Content-Type':'application/problem+json'},{}):
                number=http.post('/api/chat/turn',content='{"unknown":'+'9'*300+'}',headers=headers)
                self.assertEqual(number.status_code,400)
