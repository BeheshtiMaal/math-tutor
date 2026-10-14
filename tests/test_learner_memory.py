"""W8 learner adaptation through the actual graph and transient runtime context."""
import json
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from pydantic import ValidationError
import agent
from learner_memory import infer_level
from test_learning_graph import source,evidence
from fakes import FakeRetrievalClient
from test_web_refactors import make_app,config_for
from test_web_streaming import events
from test_ui_backend import direct_provider
from webapp.threads import new_thread_id

class MemoryModel:
    def __init__(self):self.calls=[]
    async def structured(self,messages,schema):
        data=json.loads(messages[-1].content);self.calls.append(data)
        if data.get('confusion_spots'):
            text='Review the base condition first. A logarithm needs a positive base different from one.'
        elif data['level']=='advanced':
            text='Use injectivity of the exponential map to establish the change-of-base identity. Preserve positive arguments and nonunit positive bases.'
        elif data['level']=='intermediate':
            text='Rewrite the expression with a common logarithm base. Apply the change-of-base identity within its domain.'
        else:
            text='A logarithm asks which exponent gives a number. Start with the meaning of a power.'
        if schema.__name__=='LessonPlanDraft':
            return schema.model_validate({'steps':[{'objective':'Meaning of logarithms','explanation':text,'source_ids':['power-rule']},
                {'objective':'Base conditions','explanation':'The base must be positive and not one. Keep the argument positive as well.','source_ids':['power-rule']}]})
        return schema.model_validate({'explanation':text,'source_ids':['power-rule']})

def setup_app():
    note=source().model_copy(update={'topic':'logarithms','text':'Logarithms invert powers. The base must be positive and not one. Exponential injectivity proves the change-of-base identity for positive arguments.'})
    model=MemoryModel();retrieval=FakeRetrievalClient(source=evidence([note]))
    app,service,graph=make_app(config=config_for(language='en'),model=model,retrieval=retrieval)
    return app,service,graph,model,retrieval

class MemoryChecks(unittest.TestCase):
    def post(self,http,message='Explain logarithms',**fields):
        payload={'thread_id':new_thread_id(),'message':message,'mode':'learn','delivery':'step',**fields}
        response=http.post('/api/chat/turn',json=payload);self.assertEqual(response.status_code,200)
        return payload,response.json()

    def test_novice_and_fluent_same_topic_produce_different_depth(self):
        app,service,graph,model,retrieval=setup_app()
        with patch('webapp.ui_pipeline.run_provider',direct_provider),TestClient(app) as http:
            _,novice=self.post(http,'Explain logarithms from scratch')
            _,fluent=self.post(http,'Prove the change-of-base identity for logarithms using injectivity and state necessary and sufficient domain assumptions')
            self.assertEqual(novice['topic'],fluent['topic']);self.assertEqual(novice['learner_level'],'beginner')
            self.assertEqual(fluent['learner_level'],'advanced');self.assertEqual(fluent['level_source'],'inferred')
            self.assertEqual(fluent['level_suggestion'],'advanced')
            self.assertIn('meaning of a power',novice['segments'][0]['text']);self.assertIn('injectivity',fluent['segments'][0]['text'])
            self.assertEqual([item[1].learner_level for item in retrieval.calls if item[0]=='read_source'],['beginner','advanced'])
            self.assertEqual(set(graph.get_graph().nodes)-{'__start__','__end__'},set(agent.NODE_NAMES))

    def test_confusion_changes_next_lesson_without_becoming_checkpoint_data(self):
        app,service,graph,model,_=setup_app();marker='PRIVATE_MEMORY_SENTINEL_8471'
        profile={'version':1,'topics':{'logarithms':{'level':'beginner','level_source':'inferred','confusion_spots':[{'concept':marker,'step_id':'s1','count':2}]}}}
        with patch('webapp.ui_pipeline.run_provider',direct_provider),TestClient(app) as http:
            _,plain=self.post(http)
            payload,adapted=self.post(http,learner_profile=profile)
            self.assertNotEqual(plain['segments'],adapted['segments']);self.assertIn('Review the base condition',adapted['segments'][0]['text'])
            self.assertEqual(model.calls[-1]['confusion_spots'][0]['concept'],marker)
            for snapshot in graph.get_state_history({'configurable':{'thread_id':payload['thread_id']}}):
                self.assertIsNone(snapshot.values.get('learner_profile'))
                self.assertNotIn(marker,repr((snapshot.values,snapshot.metadata,snapshot.config,snapshot.tasks)))
            self.assertNotIn(marker,repr(graph.checkpointer.storage))
            self.assertFalse(any('profile' in key for key in vars(service)))

    def test_manual_session_and_stored_corrections_override_suggestion(self):
        app,_,_,_,_=setup_app()
        stored={'topics':{'logarithms':{'level':'advanced','level_source':'manual'}}}
        with patch('webapp.ui_pipeline.run_provider',direct_provider),TestClient(app) as http:
            _,manual=self.post(http,'Explain logarithms from scratch',learner_profile=stored)
            self.assertEqual((manual['learner_level'],manual['level_source'],manual['level_suggestion']),('advanced','manual','beginner'))
            payload,_=self.post(http,level='beginner',level_source='manual',learner_profile=stored)
            corrected=http.post('/api/chat/resume',json={'thread_id':payload['thread_id'],'action':'next','level':'advanced','level_source':'manual','learner_profile':stored}).json()
            self.assertEqual(corrected['learner_level'],'advanced');self.assertEqual(corrected['lesson']['step_index'],1)
            self.assertIn('injectivity',corrected['segments'][0]['text'])

    def test_reset_profile_context_is_not_reused_in_a_new_lesson(self):
        app,_,graph,model,_=setup_app()
        profile={'topics':{'logarithms':{'level':'advanced','level_source':'inferred','confusion_spots':[{'concept':'base conditions','count':1}]}}}
        with patch('webapp.ui_pipeline.run_provider',direct_provider),TestClient(app) as http:
            _,remembered=self.post(http,learner_profile=profile)
            _,reset=self.post(http,learner_profile={'version':1,'topics':{},'recent_topics':[]})
            self.assertEqual(remembered['learner_level'],'advanced');self.assertEqual(reset['learner_level'],'beginner')
            self.assertEqual(model.calls[-1]['confusion_spots'],[])
            self.assertNotIn('Review the base condition',reset['segments'][0]['text'])

    def test_profile_removed_on_replay_is_not_a_new_turn_or_retained_in_cache(self):
        app,service,graph,model,_=setup_app();thread=new_thread_id();marker='PRIVATE_REPLAY_MEMORY_8472'
        body={'thread_id':thread,'message':'Explain logarithms','delivery':'step','mode':'learn','learner_profile':{'topics':{'logarithms':{'level':'beginner','level_source':'inferred','confusion_spots':[{'concept':marker}]}}}}
        with patch('webapp.ui_pipeline.run_provider',direct_provider),TestClient(app) as http:
            first=events(http.post('/api/chat/stream',json=body,headers={'X-Request-ID':'memory-replay'}))
            del body['learner_profile']
            replay=events(http.post('/api/chat/stream',json=body,headers={'X-Request-ID':'memory-replay'}))
            self.assertEqual(first,replay);self.assertEqual(len(model.calls),1)
            for entry in service._streams.values():self.assertNotIn(marker,repr(entry['events']))
            self.assertIsNone(graph.get_state({'configurable':{'thread_id':thread}}).values['learner_profile'])

    def test_profile_bytes_and_bilingual_inference_are_bounded_and_honest(self):
        self.assertEqual(infer_level('لگاریتم را از صفر توضیح بده'),'beginner')
        self.assertEqual(infer_level('اثبات رابطه تغییر پایه با تابع یک به یک و شرط لازم و کافی'),'advanced')
        self.assertIsNone(infer_level('logarithms'))
        raw={'topics':{str(i):{'level':'beginner','confusion_spots':[{'concept':'ژ'*120,'count':1} for _ in range(10)]} for i in range(8)}}
        self.assertLess(len(json.dumps(raw,ensure_ascii=False)),16384)
        with self.assertRaises(ValidationError):agent.LearnerProfile.model_validate(raw)
