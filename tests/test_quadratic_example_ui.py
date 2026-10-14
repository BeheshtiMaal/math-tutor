"""The actual Persian quadratic request must render a complete verified reveal."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from langgraph.types import Command
from fastapi.testclient import TestClient
import agent
from fakes import FakeModelClient, FakeRetrievalClient
from test_learning_graph import source, evidence
from test_ui_blocks import step_request
from test_web_streaming import events
from webapp.example_ui import focused_quadratic_example
from webapp.providers import _steps, ProviderFailure
from webapp.main import create_app
from webapp.service import TutorService
from webapp.threads import ThreadRegistry, new_thread_id

QUERY='یه مثال معادله درجه دو برام بیار'
NOTES=Path('sources/topics/algebra.md').read_text(encoding='utf-8').split('### Worked example / مثال حل‌شده',1)[1].split('### Common mistakes',1)[0]


class QuadraticProviderChecks(unittest.TestCase):
    def test_source_selects_quadratic_instead_of_linear_and_preserves_both_roots(self):
        body,proposal=focused_quadratic_example(NOTES,query=QUERY,language='fa',limits=agent.Limits())
        self.assertNotIn('3*x - 7',body)
        self.assertNotIn('را حل کن',body)
        checked=_steps(proposal['params'],agent.Limits())
        self.assertEqual(len(checked['steps']),5)
        self.assertTrue(all(row['verification']=='verified' for row in checked['steps']))
        self.assertIn(r'\in',checked['final_expression'])
        self.assertIn('2, 3',checked['final_expression'])
        self.assertTrue(all('3*x - 7' not in row['state'] for row in proposal['params']['steps']))

    def test_wrong_factors_and_unrequested_quadratic_are_not_selected(self):
        self.assertIsNone(focused_quadratic_example(NOTES.replace('(x - 2)*(x - 3)','(x - 1)*(x - 6)'),query=QUERY,language='fa',limits=agent.Limits()))
        self.assertIsNone(focused_quadratic_example(NOTES,query='یه مثال معادله خطی بیار',language='fa',limits=agent.Limits()))
        self.assertIsNone(focused_quadratic_example(NOTES,query='بدون مثال معادله درجه دوم را توضیح بده',language='fa',limits=agent.Limits()))

    def test_finite_solution_set_is_bounded_and_cannot_drop_a_root(self):
        for bad in ('x in {2}', 'x in {2,4}', 'x in {__import__(os)}','x in {nan}', 'x in {1,2,3,4,5,6,7,8,9}'):
            with self.subTest(bad=bad),self.assertRaises((ProviderFailure,ValueError)):
                _steps(step_request(['(x-2)*(x-3)=0',bad])['params'],agent.Limits())
        checked=_steps(step_request(['(z+1)*(z-4)=0','z in {-1,4}'])['params'],agent.Limits())
        self.assertTrue(all(row['verification']=='verified' for row in checked['steps']))
        checked=_steps(step_request(['(x-2)^2=0','x in {2}'])['params'],agent.Limits())
        self.assertTrue(all(row['verification']=='verified' for row in checked['steps']))


class QuadraticGraphChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tracing=patch.dict(os.environ,{'LANGSMITH_TRACING':'false','LANGCHAIN_TRACING':'false','LANGCHAIN_TRACING_V2':'false'})
        self.tracing.start();self.addCleanup(self.tracing.stop)

    def graph(self,delivery='step',model=None):
        config=agent.AppConfig(preferences=agent.Preferences(mode='learn',delivery_mode=delivery,language='fa'),limits=agent.Limits(math_timeout_seconds=30))
        note=source().model_copy(update={'topic':'algebra','text':NOTES})
        retrieval=FakeRetrievalClient(source=evidence([note]))
        return config,agent.build_graph(config,model,retrieval_client=retrieval,channel='web')

    async def test_exact_request_produces_reveal_without_model_and_when_model_fails(self):
        for delivery,model in [('step',None),('full',None),('step',FakeModelClient([RuntimeError('unavailable')]))]:
            with self.subTest(delivery=delivery,model=model):
                config,graph=self.graph(delivery,model)
                result=await graph.ainvoke(agent.new_request_state(agent.Request(query=QUERY),config),{'configurable':{'thread_id':new_thread_id()}})
                self.assertEqual([block['type'] for block in result['ui_blocks']],['step_reveal'])
                self.assertEqual(len(result['ui_blocks'][0]['params']['steps']),5)
                self.assertTrue(all(row['verification']=='verified' for row in result['ui_blocks'][0]['params']['steps']))
                self.assertNotIn('3*x - 7',result['explanation'])
                self.assertNotIn('افزودن یا کاستن',result['explanation'])
                self.assertIn('در کادر زیر',result['explanation'])
                if model is not None:
                    self.assertEqual(model.calls,[])

    async def test_same_topic_example_does_not_advance_and_can_repeat_reveal(self):
        config,graph=self.graph()
        thread={'configurable':{'thread_id':new_thread_id()}}
        first=await graph.ainvoke(agent.new_request_state(agent.Request(query='جبر را توضیح بده'),config),thread)
        for _ in range(2):
            result=await graph.ainvoke(Command(resume=QUERY),thread)
            self.assertEqual(result['step_index'],first['step_index'])
            self.assertEqual([block['type'] for block in result['ui_blocks']],['step_reveal'])


class QuadraticStreamingChecks(unittest.TestCase):
    def test_real_stream_emits_verified_quadratic_block_without_model(self):
        with patch.dict(os.environ,{'LANGSMITH_TRACING':'false','LANGCHAIN_TRACING':'false','LANGCHAIN_TRACING_V2':'false'}):
            config=agent.AppConfig(preferences=agent.Preferences(mode='learn',language='fa'),limits=agent.Limits(math_timeout_seconds=30))
            retrieval=FakeRetrievalClient(source=evidence([source().model_copy(update={'topic':'algebra','text':NOTES})]))
            graph=agent.build_graph(config,retrieval_client=retrieval,channel='web')
            service=TutorService(config=config,graph=graph,registry=ThreadRegistry())
            app=create_app(service=service,config=config,credentials=agent.Credentials())
            with TestClient(app) as http:
                rows=events(http.post('/api/chat/stream',json={'thread_id':new_thread_id(),'message':QUERY,'mode':'learn','action':'new_lesson','delivery':'step'}))
                blocks=[body['block'] for event,body in rows if event=='block']
                self.assertEqual([block['type'] for block in blocks],['step_reveal'])
                self.assertTrue(all(row['verification']=='verified' for row in blocks[0]['params']['steps']))
                self.assertIn(r'\in',blocks[0]['params']['final_expression'])
                self.assertNotIn('3*x - 7',''.join(body['delta'] for event,body in rows if event=='text'))
