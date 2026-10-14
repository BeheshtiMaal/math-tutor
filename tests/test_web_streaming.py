"""W4 acceptance: real LangGraph + SSE, with external services replaced only."""
import asyncio
import json
import unittest
from fastapi.testclient import TestClient
from fakes import FakeModelClient
from test_step_teaching import plan
from test_web_service import make_app
from test_learning_graph import client
from webapp.schemas import ChatTurnRequest
from webapp.threads import new_thread_id


def events(response):
    rows = []
    for frame in response.text.strip().split("\n\n"):
        lines = frame.splitlines()
        name = next(line[7:] for line in lines if line.startswith("event: "))
        data = json.loads(next(line[6:] for line in lines if line.startswith("data: ")))
        rows.append((name, data))
    return rows


class StreamingHTTPChecks(unittest.TestCase):
    def test_step_pause_next_done_and_exact_retry(self):
        model = FakeModelClient([plan()])
        app, service, graph = make_app(model=model, retrieval=client())
        thread = new_thread_id()
        with TestClient(app) as http:
            first = http.post('/api/chat/stream', json={'thread_id':thread,'message':'Explain derivatives','delivery':'step'}, headers={'X-Request-ID':'initial'})
            rows = events(first)
            self.assertIn('text/event-stream', first.headers['content-type'])
            self.assertEqual([name for name,_ in rows].count('turn_end'), 1)
            self.assertEqual(rows[-1][0], 'turn_end')
            self.assertTrue(rows[-1][1]['awaiting_user'])
            self.assertIn(('status',{'state':'waiting_for_user','message_key':'status.waiting_for_user'}), rows)
            self.assertFalse(any(name=='block' for name,_ in rows))
            second_body = {'thread_id':thread,'action':'next'}
            next_rows = events(http.post('/api/chat/stream',json=second_body,headers={'X-Request-ID':'next-1'}))
            retry_rows = events(http.post('/api/chat/stream',json=second_body,headers={'X-Request-ID':'next-1'}))
            self.assertEqual(next_rows,retry_rows)
            self.assertEqual(next_rows[-1][1]['lesson']['step_index'],1)
            self.assertEqual(graph.get_state({'configurable':{'thread_id':thread}}).values['step_index'],1)
            finished = events(http.post('/api/chat/stream',json={'thread_id':thread,'action':'done'}))
            self.assertFalse(finished[-1][1]['awaiting_user'])
            self.assertFalse(graph.get_state({'configurable':{'thread_id':thread}}).next)
            self.assertEqual(len(model.calls),1)

    def test_unknown_thread_has_no_text_and_one_terminal(self):
        app,service,_ = make_app()
        with TestClient(app) as http:
            rows = events(http.post('/api/chat/stream',json={'thread_id':new_thread_id(),'action':'next'},headers={'X-Request-ID':'unknown'}))
            self.assertEqual([name for name,_ in rows],['status','turn_end'])
            self.assertEqual(rows[0][1]['state'],'thread_not_found')
            self.assertFalse(service._streams)

    def test_unsupported_action_and_mismatched_request_id_are_safe(self):
        app,_,_ = make_app(model=FakeModelClient([plan()]),retrieval=client())
        thread=new_thread_id()
        with TestClient(app) as http:
            invalid=http.post('/api/chat/stream',json={'thread_id':thread,'action':'ui_event'})
            self.assertEqual(invalid.status_code,400)
            body={'thread_id':thread,'message':'Explain derivatives'}
            http.post('/api/chat/stream',json=body,headers={'X-Request-ID':'same'})
            rows=events(http.post('/api/chat/stream',json={**body,'message':'Different request'},headers={'X-Request-ID':'same'}))
            self.assertEqual(rows[0][1]['code'],'bad_request')


class StreamingLifetimeChecks(unittest.IsolatedAsyncioTestCase):
    async def test_disconnected_subscriber_replays_once_and_releases_thread(self):
        model=FakeModelClient([plan()])
        _,service,graph=make_app(model=model,retrieval=client())
        request=ChatTurnRequest(thread_id=new_thread_id(),message='Explain derivatives')
        iterator=service.stream(request,'replayable')
        seen=[]
        async for event in iterator:
            seen.append(event)
            if event[0]=='text':
                break
        await iterator.aclose()
        replay=[event async for event in service.stream(request,'replayable')]
        self.assertEqual(replay[:len(seen)],seen)
        self.assertEqual(replay[-1][0],'turn_end')
        self.assertFalse(service.registry.get(request.thread_id).active)
        self.assertEqual(len(model.calls),1)
        await service.close()

    async def test_transport_failure_is_redacted_and_ends(self):
        # A transport-specific error probe; not a fake graph acceptance claim.
        _,service,_=make_app()
        async def broken(*args,**kwargs):
            raise RuntimeError('private-provider-secret')
            yield
        service.graph.astream=broken
        rows=[event async for event in service.stream(ChatTurnRequest(thread_id=new_thread_id(),message='test'))]
        self.assertEqual(rows[-1][0],'turn_end')
        self.assertIn('error',[name for name,_ in rows])
        self.assertNotIn('private-provider-secret',json.dumps(rows))

if __name__=='__main__':
    unittest.main()
