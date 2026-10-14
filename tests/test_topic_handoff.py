"""A named example in another subject must leave the active lesson context."""
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from langgraph.types import Command

import agent
from fakes import FakeRetrievalClient
from test_learning_graph import source, evidence
from test_web_service import make_app, make_config
from test_web_streaming import events
from webapp.threads import new_thread_id

QUERY = 'یه مثال معادله درجه دو برام بیار'


class TopicRetrieval(FakeRetrievalClient):
    async def read_source(self, request):
        self.calls.append(('read_source', request))
        text = ('بردار جابه‌جایی را توصیف می‌کند. دو مؤلفه دارد. مؤلفه‌ها را جدا بررسی می‌کنیم. هر مؤلفه یک جهت دارد.'
                if request.topic == 'geometry' else
                'معادله درجه دوم توان دو دارد. نمونه آن x^2 - 5*x + 6 = 0 است. آن را به صورت (x-2)*(x-3)=0 تجزیه می‌کنیم. جواب‌ها دو و سه هستند.')
        return evidence([source().model_copy(update={'topic':request.topic,'text':text})])


class TopicHandoffChecks(unittest.TestCase):
    def setUp(self):
        self.tracing = patch.dict(os.environ, {'LANGSMITH_TRACING':'false','LANGCHAIN_TRACING':'false','LANGCHAIN_TRACING_V2':'false'})
        self.tracing.start()
        self.addCleanup(self.tracing.stop)

    def test_exact_persian_example_switches_vector_context_in_json_and_sse(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                retrieval=TopicRetrieval()
                app,service,graph=make_app(config=make_config(language='fa'),retrieval=retrieval)
                thread=new_thread_id()
                with TestClient(app) as http:
                    first=http.post('/api/chat/turn',json={'thread_id':thread,'message':'بردار را توضیح بده','action':'new_lesson','mode':'learn','delivery':'step'}).json()
                    self.assertEqual(first['topic'],'geometry')
                    request={'thread_id':thread,'message':QUERY,'action':'followup','mode':'learn','delivery':'step'}
                    if streaming:
                        rows=events(http.post('/api/chat/stream',json=request))
                        result=next(body for event,body in rows if event=='turn_end')
                        body=''.join(body['delta'] for event,body in rows if event=='text')
                    else:
                        result=http.post('/api/chat/resume',json=request).json()
                        body=' '.join(segment['text'] for segment in result['segments'])
                    self.assertEqual(result['topic'],'algebra')
                    self.assertEqual(result['language'],'fa')
                    self.assertIsNone(result['next_request'])
                    self.assertIn('معادله',body)
                    self.assertNotIn('بردار',body)
                    self.assertEqual([request.topic for node,request in retrieval.calls if node=='read_source'],['geometry','algebra'])
                    self.assertEqual(graph.get_state({'configurable':{'thread_id':thread}}).values['query'],QUERY)

    def test_unspecified_example_keeps_the_active_topic_and_step(self):
        app,service,graph=make_app(config=make_config(language='fa'),retrieval=TopicRetrieval())
        thread=new_thread_id()
        with TestClient(app) as http:
            first=http.post('/api/chat/turn',json={'thread_id':thread,'message':'بردار را توضیح بده','action':'new_lesson','mode':'learn','delivery':'step'}).json()
            result=http.post('/api/chat/resume',json={'thread_id':thread,'message':'یه مثال برام بیار','action':'followup','mode':'learn','delivery':'step'}).json()
            self.assertEqual(result['topic'],'geometry')
            self.assertEqual(result['lesson']['step_index'],first['lesson']['step_index'])
            self.assertIsNone(result['next_request'])
