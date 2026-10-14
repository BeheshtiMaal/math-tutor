"""An example request chooses step reveal using that exact sourced example."""
import os
import unittest
from unittest.mock import patch

import agent
from langgraph.types import Command
from fakes import FakeModelClient, FakeRetrievalClient
from test_learning_graph import source, example, evidence
from test_ui_blocks import step_request
from webapp.example_ui import requests_example, prepare_example_steps, example_reveal
from webapp.providers import _steps, parse_state, ProviderFailure


def setUpModule():
    global tracing
    tracing=patch.dict(os.environ,{'LANGSMITH_TRACING':'false','LANGCHAIN_TRACING_V2':'false','LANGCHAIN_TRACING':'false'})
    tracing.start()


def tearDownModule():
    tracing.stop()


class ExampleIntentChecks(unittest.TestCase):
    def test_english_persian_and_explicit_mode(self):
        for query in ['Give me an example of logarithms','Give examples of logarithms','یک مثال از لگاریتم بزن','یک نمونه از مشتق بگو','یه مثال برام میزنی']:
            self.assertTrue(requests_example(query))
            self.assertEqual(agent.new_request_state(agent.Request(query=query),agent.AppConfig())['mode'],'learn')
        self.assertFalse(requests_example('Explain without examples'))
        self.assertFalse(requests_example('بدون مثال توضیح بده'))
        self.assertEqual(agent.new_request_state(agent.Request(query='Give an example',mode='answer'),agent.AppConfig())['mode'],'answer')

    def test_source_variable_and_named_function_steps_are_safe_and_honest(self):
        checked=_steps(step_request(['z+z','2*z'])['params'],agent.Limits())
        self.assertTrue(all(row['verification']=='verified' for row in checked['steps']))
        self.assertIn('z',checked['final_expression'])
        formal=_steps(step_request(['R(z)=sqrt(5*z-8)',"R'(z)=5/(2*sqrt(5*z-8))"])['params'],agent.Limits())
        self.assertTrue(all(row['verification']=='unsupported' for row in formal['steps']))
        with self.assertRaises(ProviderFailure):
            parse_state('f(x)=__import__(os)',agent.Limits())

    def test_example_rows_include_endpoints_and_keep_restrictions_out_of_states(self):
        raw=step_request(['f(z)=sqrt(z)','z>8/5'])
        raw['params']['initial_expression']='R(z)=sqrt(5*z-8)'
        raw['params']['final_expression']="R'(z)=5/(2*sqrt(5*z-8))"
        prepared=prepare_example_steps(raw,'en',agent.Limits())
        rows=prepared['params']['steps']
        self.assertEqual(rows[0]['state'],prepared['params']['initial_expression'])
        self.assertEqual(rows[-1]['state'],prepared['params']['final_expression'])
        self.assertNotIn('z>8/5',[row['state'] for row in rows])


class ExampleRevealChecks(unittest.IsolatedAsyncioTestCase):
    async def test_saved_chat_derivative_shape_gets_validated_reveal_on_conversion_failure(self):
        config=agent.AppConfig(preferences=agent.Preferences(mode='learn',delivery_mode='step',language='fa'),limits=agent.Limits(math_timeout_seconds=30))
        note=source().model_copy(update={'topic':'mathematics','text':"### مثال حل‌شده\nتابع f(x) = 4*x^3 - 2*x + 7 را مشتق بگیر. جمله ثابت صفر می‌دهد. پس f'(x) = 12*x^2 - 2."})
        plan={'steps':[{'objective':'مشتق','explanation':'مشتق نرخ تغییر را می‌دهد. قاعده توان را به کار می‌بریم.','source_ids':[note.id]}]}
        answer={'explanation':'از قاعده توان استفاده می‌کنیم. مثال زیر را بخوان.','source_ids':[note.id]}
        model=FakeModelClient([plan,answer,RuntimeError('translation unavailable'),{'block':None}])
        english=example().model_copy(update={'statement':'Differentiate f(x)=4*x^3-2*x+7.','solution':"The derivative is f'(x)=12*x^2-2."})
        graph=agent.build_graph(config,model,retrieval_client=FakeRetrievalClient(source=evidence([note]),examples=evidence([english])),channel='web')
        thread={'configurable':{'thread_id':'saved-shape-example'}}
        first=await graph.ainvoke(agent.new_request_state(agent.Request(query='ریاضی را توضیح بده'),config),thread)
        result=await graph.ainvoke(Command(resume='یه مثال برام میزنی'),thread)
        self.assertEqual(result['step_index'],first['step_index'])
        self.assertEqual([b['type'] for b in result['ui_blocks']],['step_reveal'])
        self.assertEqual(result['ui_blocks'][0]['params']['final_expression'],'12 x^{2} - 2')
        self.assertIn("f'(x) = 12*x^2 - 2",result['explanation'])
        self.assertNotIn('ترجمه این مثال اکنون در دسترس نیست',result['explanation'])
        self.assertNotIn('Differentiate',result['explanation'])

    async def test_source_derivative_gets_reveal_when_optional_model_conversion_fails(self):
        text="تابع f(x) = 4*x^3 - 2*x + 7 را مشتق بگیر. جمله ثابت صفر می‌دهد. پس f'(x) = 12*x^2 - 2."
        config=agent.AppConfig()
        for model in (None,FakeModelClient([{'block':None}])):
            blocks=await example_reveal(text,language='fa',model=model,config=config)
            self.assertEqual(len(blocks),1)
            self.assertEqual(blocks[0]['params']['final_expression'],'12*x^2 - 2')
            self.assertIn('4*x^3 - 2*x + 7',blocks[0]['params']['initial_expression'])
            checked=_steps(blocks[0]['params'],config.limits)
            self.assertTrue(all(row['verification']=='unsupported' for row in checked['steps']))
        self.assertEqual(await example_reveal('تابع f(x)=__import__(os) و مشتق f\'(x)=1.',language='fa',model=None,config=config),[])
        self.assertEqual(await example_reveal("R(z)=sqrt(5*z-8). R'(z)=5/(2*sqrt(5*z-8)).",language='en',model=None,config=config),[])
        self.assertEqual(await example_reveal("f(x)=4x^3. f'(x)=12x^2.",language='en',model=None,config=config),[])
        delimited=await example_reveal(r"\(f(x)=4*x^3-2*x+7\). \(f'(x)=12*x^2-2\).",language='fa',model=None,config=config)
        self.assertEqual(delimited[0]['params']['final_expression'],'12*x^2-2')

    async def test_colloquial_persian_example_repeats_reveal_but_not_chart_or_lesson_step(self):
        plan={'steps':[{'objective':'Definition','explanation':'لگاریتم یک توان است. ورودی باید مثبت باشد.','source_ids':['power-rule']}]}
        answer={'explanation':'از تعریف لگاریتم استفاده می‌کنیم. مثال را مرحله‌به‌مرحله بخوان.','source_ids':['power-rule']}
        graph,config,_=self.setup_graph([plan,answer,answer],language='fa',bank=False)
        thread={'configurable':{'thread_id':'colloquial-repeat-example'}}
        first=await graph.ainvoke(agent.new_request_state(agent.Request(query='لگاریتم را توضیح بده'),config),thread)
        for _ in range(2):
            result=await graph.ainvoke(Command(resume='یه مثال برام میزنی'),thread)
            self.assertEqual(result['step_index'],first['step_index'])
            self.assertEqual([b['type'] for b in result['ui_blocks']],['step_reveal'])
            self.assertIn('مقدار log_2(8)',result['explanation'])

    def setup_graph(self, responses, delivery='step', language='en', bank=True):
        config=agent.AppConfig(preferences=agent.Preferences(mode='learn',delivery_mode=delivery,learner_level='beginner',language=language),limits=agent.Limits(math_timeout_seconds=30))
        note=source().model_copy(update={'topic':'logarithms','text':'### Worked example / مثال حل‌شده\nFind log_2(8). Since 2^3=8, log_2(8)=3.\nمقدار log_2(8) را بیاب. چون 2^3=8، جواب برابر 3 است.'})
        row=example().model_copy(update={'topic':'logarithms','statement':'Solve log(x,2)=3.','solution':'Use x=2^3, so x=8.'})
        retrieval=FakeRetrievalClient(source=evidence([note]),examples=evidence([row]) if bank else None)
        model=FakeModelClient(responses)
        graph=agent.build_graph(config,model,retrieval_client=retrieval,channel='web')
        return graph,config,model

    async def test_followup_example_gets_reveal_without_advancing_or_duplicate_graph(self):
        plan={'steps':[{'objective':'Definition','explanation':'A logarithm is an exponent. Its argument is positive.','source_ids':['power-rule']}]}
        answer={'explanation':'Apply the logarithm definition. The example below uses base two.','source_ids':['power-rule']}
        graph,config,model=self.setup_graph([plan,answer,{'block':step_request()}])
        thread={'configurable':{'thread_id':'example-reveal-request'}}
        first=await graph.ainvoke(agent.new_request_state(agent.Request(query='Explain logarithms'),config),thread)
        result=await graph.ainvoke(Command(resume='Give me an example'),thread)
        self.assertEqual(result['step_index'],first['step_index'])
        self.assertEqual([block['type'] for block in result['ui_blocks']],['step_reveal'])
        self.assertIn('Solve log(x,2)=3.',result['explanation'])
        self.assertIn('Use x=2^3, so x=8.',model.calls[-1][1][-1].content)
        self.assertTrue(all(step['verification']=='verified' for step in result['ui_blocks'][0]['params']['steps']))

    async def test_initial_persian_example_without_bank_uses_curated_note_and_reveal(self):
        reveal=step_request()
        reveal['title']='حل مرحله‌ای مثال'
        reveal['fallback_text']='رابطه لگاریتمی را به توان تبدیل می‌کنیم و جواب هشت است.'
        for row in reveal['params']['steps']:row['justification']='از تعریف لگاریتم استفاده می‌کنیم.'
        graph,config,model=self.setup_graph([{'explanation':'لگاریتم توان مورد نیاز است. پایه دو را در نظر بگیر.','source_ids':['power-rule']},
                                           {'explanation':'ورودی باید مثبت باشد. این شرط تعریف لگاریتم است.','source_ids':['power-rule']}],delivery='full',language='fa',bank=False)
        thread={'configurable':{'thread_id':'persian-note-example'}}
        result=await graph.ainvoke(agent.new_request_state(agent.Request(query='یک مثال از لگاریتم بزن'),config),thread)
        self.assertIn('مقدار log_2(8) را بیاب',result['explanation'])
        self.assertEqual(result['ui_blocks'][0]['type'],'step_reveal')
        self.assertEqual(result['ui_blocks'][0]['params']['final_expression'],'3')
        self.assertTrue(all(row['verification']=='verified' for row in result['ui_blocks'][0]['params']['steps']))
        self.assertNotIn('Find',result['explanation'])
        followup=await graph.ainvoke(Command(resume='چرا ورودی باید مثبت باشد؟'),thread)
        self.assertEqual(followup['ui_blocks'],[])
        self.assertEqual(len(model.calls),2)

    async def test_unavailable_reveal_preserves_complete_example_text(self):
        graph,config,_=self.setup_graph([{'explanation':'A logarithm is an exponent.','source_ids':['power-rule']},{'block':None}],delivery='full')
        result=await graph.ainvoke(agent.new_request_state(agent.Request(query='Give an example of logarithms'),config),{'configurable':{'thread_id':'example-reveal-fallback'}})
        self.assertIn('Solve log(x,2)=3.',result['explanation'])
        self.assertIn('Use x=2^3, so x=8.',result['explanation'])

    async def test_derivative_reveal_preserves_operator_and_does_not_claim_equivalence(self):
        config=agent.AppConfig(preferences=agent.Preferences(mode='learn',delivery_mode='full',learner_level='beginner',language='en'),limits=agent.Limits(math_timeout_seconds=30))
        note=source()
        row=example().model_copy(update={'statement':'Differentiate x^2.','solution':'Its derivative is 2*x.'})
        reveal=step_request([r'\mathrm{d}(x^2)/\mathrm{dx}','2*x'])
        reveal['title']='Derivative worked example'
        model=FakeModelClient([{'explanation':'Apply the power rule.','source_ids':[note.id]},{'block':reveal}])
        graph=agent.build_graph(config,model,retrieval_client=FakeRetrievalClient(source=evidence([note]),examples=evidence([row])),channel='web')
        result=await graph.ainvoke(agent.new_request_state(agent.Request(query='Give an example of a derivative'),config),{'configurable':{'thread_id':'derivative-example-reveal'}})
        self.assertEqual(result['ui_blocks'][0]['type'],'step_reveal')
        self.assertIn(r'\mathrm{d}',result['ui_blocks'][0]['params']['initial_expression'])
        self.assertTrue(all(step['verification']=='unsupported' for step in result['ui_blocks'][0]['params']['steps']))
