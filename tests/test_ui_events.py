"""W7 actual checkpoint/resume/API/SymPy acceptance with fake external services."""
import copy
import json
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from langgraph.types import Command
from fakes import FakeModelClient
from test_step_teaching import plan
from test_ui_backend import client, direct_provider
from test_ui_blocks import graph_request, step_request
from test_web_service import make_app, make_config
from test_web_streaming import events
from webapp.schemas import ChatTurnRequest
from webapp.threads import new_thread_id
from pydantic import ValidationError
import agent

def event(thread,block,kind='step_confused',seq=1,payload=None):
    return {'thread_id':thread,'action':'ui_event','ui_event':{
        'thread_id':thread,'block_id':block,'event_id':'evt_'+f'{seq:026d}',
        'type':kind,'payload':payload or {'step_id':'s2'},'seq':seq,'sent_at':'2026-10-14T06:00:00Z'}}

class EventChecks(unittest.TestCase):
    def setup_app(self,delivery='step'):
        config=make_config(delivery=delivery);config.limits.math_timeout_seconds=30
        draft=plan();draft['steps'][0]['block_requests']=[graph_request(),step_request()]
        if delivery=='full': draft={'explanation':'Logarithms invert powers. Positive arguments and valid bases are required.','source_ids':['power-rule'],'block_requests':[graph_request(),step_request()]}
        model=FakeModelClient([draft,{'explanation':'Rewrite the logarithm as a power with the same base. The exponent stays three, so x equals two cubed.'}])
        retrieval=client();graph=agent.build_graph(config,model,retrieval_client=retrieval,channel='web')
        app,service,_=make_app(config=config);service.graph=graph
        return app,service,graph,model,retrieval

    def first(self,http,delivery='step'):
        thread=new_thread_id()
        with patch('webapp.ui_pipeline.run_provider',direct_provider):
            data=http.post('/api/chat/turn',json={'thread_id':thread,'message':'Explain logarithms','mode':'learn','delivery':delivery}).json()
        self.assertEqual(len(data['blocks']),2)
        return thread,{block['type']:block for block in data['blocks']}

    def test_step_targets_issued_row_keeps_index_and_no_retrieval(self):
        app,service,graph,model,retrieval=self.setup_app()
        with TestClient(app) as http:
            thread,blocks=self.first(http)
            before=graph.get_state({'configurable':{'thread_id':thread}}).values
            result=http.post('/api/chat/resume',json=event(thread,blocks['step_reveal']['id'])).json()
            self.assertEqual(result['event_status'],'accepted');self.assertEqual(result['lesson']['step_index'],0)
            self.assertIn('same base',result['segments'][0]['text']);self.assertEqual(result['blocks'],[])
            after=graph.get_state({'configurable':{'thread_id':thread}}).values
            self.assertEqual(after['lesson_plan'],before['lesson_plan']);self.assertEqual(after['source'],before['source'])
            self.assertEqual([x.node for x in after['execution_trace'][len(before['execution_trace']):]],['user_input','write_explanation'])
            payload=json.loads(model.calls[-1][1][-1].content)
            self.assertEqual(payload['current_step']['step_id'],'s2')
            self.assertEqual(set(graph.get_graph().nodes)-{'__start__','__end__'},set(agent.NODE_NAMES))

    def test_graph_question_real_sympy_uses_current_base_and_full_delivery(self):
        app,service,graph,model,_=self.setup_app('full')
        with TestClient(app) as http:
            thread,blocks=self.first(http,'full')
            body=event(thread,blocks['function_graph']['id'],'graph_question',payload={'params':{'b':.5}})
            rows=events(http.post('/api/chat/stream',json=body,headers={'X-Request-ID':'curve'}))
            text=''.join(value['delta'] for name,value in rows if name=='text')
            self.assertIn('b = 0.5',text);self.assertIn('y=-3',text)
            self.assertEqual(rows[-1][1]['event_status'],'accepted')
            self.assertEqual(rows[-1][1]['lesson']['step_index'],0)
            self.assertEqual(len(model.calls),1)
            replay=events(http.post('/api/chat/stream',json=body,headers={'X-Request-ID':'curve'}))
            self.assertEqual(replay,rows)

    def test_duplicate_and_stale_are_ignored_after_stream_cache_changes(self):
        app,service,graph,model,_=self.setup_app()
        with TestClient(app) as http:
            thread,blocks=self.first(http)
            body=event(thread,blocks['step_reveal']['id'],seq=2)
            http.post('/api/chat/turn',json=body)
            version=graph.get_state({'configurable':{'thread_id':thread}}).values['explanation_version']
            duplicate=http.post('/api/chat/turn',json=body).json()
            self.assertEqual(duplicate['event_status'],'duplicate');self.assertEqual(duplicate['segments'],[])
            rows=events(http.post('/api/chat/stream',json=event(thread,blocks['step_reveal']['id'],seq=1)))
            self.assertEqual([name for name,_ in rows],['turn_end']);self.assertEqual(rows[-1][1]['event_status'],'stale')
            self.assertEqual(graph.get_state({'configurable':{'thread_id':thread}}).values['explanation_version'],version)
            self.assertEqual(len(model.calls),2)

    def test_binding_and_closed_envelope_reject_client_facts(self):
        app,service,_,_,_=self.setup_app()
        with TestClient(app) as http:
            thread,blocks=self.first(http)
            for kind,block,payload in [('step_confused',blocks['function_graph']['id'],{'step_id':'s2'}),
                                       ('step_confused',blocks['step_reveal']['id'],{'step_id':'missing'}),
                                       ('graph_question',blocks['function_graph']['id'],{'params':{'evil':.5}}),
                                       ('graph_question',blocks['function_graph']['id'],{'params':{'b':999.}})]:
                self.assertEqual(http.post('/api/chat/turn',json=event(thread,block,kind,payload=payload)).status_code,422)
            body=event(thread,blocks['step_reveal']['id']);body['ui_event']['payload']['state']='forged'
            self.assertEqual(http.post('/api/chat/turn',json=body).status_code,400)
            body=event(thread,blocks['step_reveal']['id']);body['ui_event']['thread_id']=new_thread_id()
            self.assertEqual(http.post('/api/chat/turn',json=body).status_code,400)

    def test_block_error_text_rate_limit_and_checkpoint_cleanup(self):
        app,service,graph,model,_=self.setup_app()
        with TestClient(app) as http:
            thread,blocks=self.first(http)
            for seq in range(1,6):
                data=http.post('/api/chat/turn',json=event(thread,blocks['function_graph']['id'],'block_error',seq,{'code':'render_failed'})).json()
                self.assertIn('continue with text',data['segments'][0]['text']);self.assertEqual(data['blocks'],[])
            self.assertEqual(http.post('/api/chat/turn',json=event(thread,blocks['function_graph']['id'],'block_error',6,{'code':'render_failed'})).status_code,429)
            self.assertEqual(len(model.calls),1)
            service._forget_checkpoint(thread)
            self.assertNotIn(thread,service._event_limits);self.assertNotIn(thread,service._ui_blocks)

    def test_api_rejects_informational_and_malformed_events(self):
        for change in [{'seq':True},{'seq':0},{'sent_at':'2026-10-14T06:00:00'},{'sent_at':0},{'type':'graph_slider'},{'payload':{'step_id':'<script>'}}]:
            body=event('thr_'+'0'*26,'blk_'+'0'*26);body['ui_event'].update(change)
            with self.assertRaises(ValidationError):ChatTurnRequest.model_validate(body)
