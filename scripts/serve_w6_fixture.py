"""W6 acceptance only: real graph/SymPy, synthetic model/evidence, localhost."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'));sys.path.insert(0,str(ROOT/'scripts'))
import uvicorn
import agent
from fakes import FakeRetrievalClient
from test_learning_graph import client, source, evidence
from test_ui_blocks import graph_request, step_request
from serve_w4_fixture import DemoModel as W4Model
from webapp.main import create_app


class DemoRetrieval:
    def __init__(self):
        self.original=client()
        note=source().model_copy(update={'topic':'logarithms','text':
            'Synthetic test note: log(x,2)=3 means x=2^3=8. Logarithm bases are positive and not one; x must be positive. A base between zero and one gives a decreasing curve.'})
        self.logs=FakeRetrievalClient(source=evidence([note]))
    def choose(self,request):return self.logs if request.topic=='logarithms' else self.original
    async def read_source(self,request):return await self.choose(request).read_source(request)
    async def verified_examples(self,request):return await self.choose(request).verified_examples(request)
    async def teaching_bestpractices(self,request):return await self.choose(request).teaching_bestpractices(request)


class DemoModel(W4Model):
    async def structured(self,messages,schema):
        if schema.__name__ == 'UIReactionDraft':
            import json
            payload=json.loads(messages[-1].content)
            if payload['language']=='fa':
                text='در این گام، تعریف لگاریتم را به زبان توان می‌نویسیم. پایه همان 2 و توان همان 3 می‌ماند، پس مقدار مجهول برابر $2^3$ است.'
            else:
                text='Rewrite the logarithm as a power. Keep the same base and exponent to obtain the displayed next state.'
            return schema.model_validate({'explanation':text})
        if schema.__name__ in {'LessonDraft','LessonPlanDraft'} and 'logarithm' in messages[-1].content:
            graph=graph_request(); graph['title']='نمودار لگاریتم';graph['fallback_text']='با پایهٔ 2، لگاریتم 8 برابر 3 است. فقط x مثبت تعریف شده است.'
            graph['params']['sample_count']=101;graph['params']['y_domain']={'min':-5,'max':5}
            steps=step_request();steps['title']='حل معادلهٔ لگاریتمی';steps['fallback_text']='لگاریتم x در پایهٔ 2 برابر 3 است؛ پس x برابر 8 است.'
            for step,text in zip(steps['params']['steps'],['ابتدا پایه و دامنهٔ لگاریتم را مشخص می‌کنیم.','تعریف لگاریتم را به صورت توان می‌نویسیم.','توان را محاسبه می‌کنیم و مقدار x به دست می‌آید.']):step['justification']=text
            text='لگاریتم وارون توان است. در معادلهٔ $\\log_2(x)=3$، مقدار $x=8$ است.'
            if schema.__name__=='LessonDraft':return schema.model_validate({'explanation':text,'source_ids':['power-rule'],'block_requests':[graph,steps]})
            return schema.model_validate({'steps':[{'objective':'Meaning of logarithms','explanation':text,'source_ids':['power-rule'],'block_requests':[graph,steps]},
                {'objective':'Base below one','explanation':'وقتی پایه بین صفر و یک باشد، نمودار نزولی است. ورودی تابع همچنان باید مثبت باشد.','source_ids':['power-rule']} ]})
        return await super().structured(messages,schema)


config=agent.AppConfig(preferences=agent.Preferences(mode='learn',delivery_mode='step'),semantic_enabled=False)
config.limits.math_timeout_seconds=30
graph=agent.build_graph(config,model=DemoModel(),retrieval_client=DemoRetrieval(),channel='web')
app=create_app(config=config,credentials=agent.Credentials(),graph=graph)
if __name__=='__main__':uvicorn.run(app,host='127.0.0.1',port=8766)
