"""W5 real-graph and HTTP acceptance; external services use deterministic fakes."""
import asyncio
import copy
import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import agent
from fakes import FakeModelClient, FakeRetrievalClient
from test_learning_graph import source, evidence
from test_step_teaching import plan
from test_web_service import make_app, make_config
from test_web_streaming import events
from test_ui_blocks import graph_request, step_request, sampling
from webapp.errors import ApiError
from webapp.providers import ProviderFailure, _sample, _steps
from webapp.schemas import ChatTurnRequest
from webapp.threads import new_thread_id
from webapp.ui_blocks import GraphBlock, SampleResult, SamplingRequest, StepDataParams


def setUpModule():
    global tracing
    tracing=patch.dict(os.environ,{'LANGSMITH_TRACING':'false','LANGCHAIN_TRACING_V2':'false','LANGCHAIN_TRACING':'false'})
    tracing.start()


def tearDownModule(): tracing.stop()


def full(blocks):
    return {'explanation':'The logarithm is the inverse of exponentiation. Keep positive arguments and a positive base different from one.',
        'source_ids':['power-rule'],'block_requests':blocks}


def client():
    record=source().model_copy(update={'topic':'logarithms','text':
        'Synthetic test note: logarithms invert exponentiation. log(x,2)=3 gives x=2^3=8. Arguments are positive and bases are positive and not one.'})
    return FakeRetrievalClient(source=evidence([record]))


async def direct_provider(kind,payload,limits):
    # Numerical unit integration only; separate acceptance below uses real spawn.
    if kind=='sample': return SampleResult.model_validate(_sample(payload,limits))
    return StepDataParams.model_validate(_steps(payload,limits))


def stored_graph():
    proposal=graph_request()
    params=proposal['params']
    return GraphBlock(id='blk_'+'0'*26,type='function_graph',title=proposal['title'],fallback_text=proposal['fallback_text'],
        params={**params,'samples':_sample(sampling(),agent.Limits())})


class HTTPBlockChecks(unittest.TestCase):
    def test_stream_emits_validated_blocks_then_interrupt_and_replays_ids(self):
        config=make_config(delivery='full'); config.limits.math_timeout_seconds=30
        model=FakeModelClient([full([graph_request(),step_request()])])
        graph=agent.build_graph(config,model,retrieval_client=client(),channel='web')
        app,service,_=make_app(config=config)
        service.graph=graph
        thread=new_thread_id()
        body={'thread_id':thread,'message':'Explain logarithms','mode':'learn','delivery':'full'}
        with TestClient(app) as http:
            response=http.post('/api/chat/stream',json=body,headers={'X-Request-ID':'visual-1'})
            rows=events(response)
            replay=events(http.post('/api/chat/stream',json=body,headers={'X-Request-ID':'visual-1'}))
            self.assertEqual(rows,replay)
            blocks=[data['block'] for name,data in rows if name=='block']
            self.assertEqual([block['type'] for block in blocks],['function_graph','step_reveal'])
            self.assertNotEqual(blocks[0]['id'],blocks[1]['id'])
            self.assertAlmostEqual(blocks[0]['params']['samples']['highlight_points'][0]['y'],3)
            self.assertTrue(all(step['verification']=='verified' for step in blocks[1]['params']['steps']))
            self.assertEqual(rows[-1][0],'turn_end'); self.assertTrue(rows[-1][1]['awaiting_user'])
            text=''.join(data['delta'] for name,data in rows if name=='text')
            self.assertIn(blocks[0]['fallback_text'],text)
            self.assertIn(blocks[1]['fallback_text'],text)
            self.assertEqual(len(model.calls),1)
            self.assertEqual(set(graph.get_graph().nodes)-{'__start__','__end__'},set(agent.NODE_NAMES))
            payload=sampling(); payload.update(thread_id=thread,block_id=blocks[0]['id'],parameters={'b':0.5})
            resampled=http.post('/api/ui/sample',json=payload)
            self.assertEqual(resampled.status_code,200)
            self.assertAlmostEqual(resampled.json()['highlight_points'][0]['y'],-3)
            payload['parameters']['b']=1
            rejected=http.post('/api/ui/sample',json=payload)
            self.assertEqual(rejected.json()['status'],'invalid_expression')
            self.assertEqual(len(model.calls),1)
            self.assertEqual(graph.get_state({'configurable':{'thread_id':thread}}).values['explanation_version'],1)
            done=http.post('/api/chat/resume',json={'thread_id':thread,'action':'done'})
            self.assertEqual(done.json()['blocks'],[])

    def test_json_response_contains_closed_blocks_and_step_resume(self):
        draft=plan(); draft['steps'][0]['block_requests']=[graph_request()]
        draft['steps'][1]['block_requests']=[step_request()]
        config=make_config(); model=FakeModelClient([draft])
        graph=agent.build_graph(config,model,retrieval_client=client(),channel='web')
        app,service,_=make_app(config=config); service.graph=graph
        thread=new_thread_id()
        with patch('webapp.ui_pipeline.run_provider',direct_provider), TestClient(app) as http:
            first=http.post('/api/chat/turn',json={'thread_id':thread,'message':'Explain logarithms','delivery':'step'})
            self.assertEqual(first.status_code,200)
            self.assertEqual(first.json()['blocks'][0]['type'],'function_graph')
            following=http.post('/api/chat/resume',json={'thread_id':thread,'action':'next'})
            self.assertEqual(following.json()['lesson']['step_index'],1)
            self.assertEqual(following.json()['blocks'][0]['type'],'step_reveal')
            self.assertEqual(len(model.calls),1)

    def test_failed_block_repairs_keep_text_and_use_grounded_automatic_visual(self):
        bad=graph_request(); bad['params']['expressions'][0]['expression']='__import__(os)'
        model=FakeModelClient([full([bad]),{'block':bad},{'block':bad}])
        config=make_config(delivery='full')
        graph=agent.build_graph(config,model,retrieval_client=client(),channel='web')
        app,service,_=make_app(config=config); service.graph=graph
        with TestClient(app) as http:
            rows=events(http.post('/api/chat/stream',json={'thread_id':new_thread_id(),'message':'Explain logarithms','delivery':'full'}))
            blocks = [data['block'] for name,data in rows if name=='block']
            self.assertEqual(len(blocks),1)
            self.assertEqual(blocks[0]['params']['expressions'][0]['expression'],'log(x,b)')
            self.assertNotIn('__import__',json.dumps(blocks))
            self.assertFalse(any(name=='error' for name,_ in rows))
            self.assertIn('inverse of exponentiation',''.join(data['delta'] for name,data in rows if name=='text'))
            self.assertEqual(len(model.calls),3)
            self.assertTrue(rows[-1][1]['awaiting_user'])

    def test_sampling_binds_to_issued_definition_and_validates_sizes(self):
        app,service,_=make_app(); thread=new_thread_id(); service.registry.register(thread)
        service.remember_blocks(thread,[stored_graph()])
        self.assertFalse(hasattr(service._ui_blocks[thread]['blk_'+'0'*26].params,'samples'))
        payload=sampling(); payload['thread_id']=thread
        with TestClient(app) as http:
            bad=copy.deepcopy(payload); bad['expressions'][0]['expression']='x^2'
            self.assertEqual(http.post('/api/ui/sample',json=bad).status_code,422)
            bad=copy.deepcopy(payload); bad['parameters']['b']=10
            self.assertEqual(http.post('/api/ui/sample',json=bad).status_code,422)
            bad=copy.deepcopy(payload); bad['sample_count']=2001
            self.assertEqual(http.post('/api/ui/sample',json=bad).status_code,400)
            bad=copy.deepcopy(payload); bad['thread_id']=new_thread_id()
            self.assertEqual(http.post('/api/ui/sample',json=bad).status_code,404)
            bad=copy.deepcopy(payload); bad['block_id']='blk_'+'1'*26
            self.assertEqual(http.post('/api/ui/sample',json=bad).status_code,422)
            with patch('webapp.providers.sample_graph',side_effect=ProviderFailure('timeout')):
                timeout=http.post('/api/ui/sample',json=payload)
                self.assertEqual(timeout.status_code,504)

    def test_rate_limiter_burst_and_cleanup(self):
        app,service,_=make_app(); thread=new_thread_id(); service.registry.register(thread)
        payload=sampling(); payload['thread_id']=thread
        with TestClient(app) as http, patch('webapp.service.time') as clock:
            clock.monotonic.return_value=0
            for _ in range(20):
                self.assertEqual(http.post('/api/ui/sample',json=payload).status_code,422)
            self.assertEqual(http.post('/api/ui/sample',json=payload).status_code,429)
            clock.monotonic.return_value=0.1
            self.assertEqual(http.post('/api/ui/sample',json=payload).status_code,422)
            service.remember_blocks(thread,[stored_graph()])
            service._forget_checkpoint(thread)
            self.assertNotIn(thread,service._sample_limits)
            self.assertNotIn(thread,service._ui_blocks)


if __name__=='__main__': unittest.main()
