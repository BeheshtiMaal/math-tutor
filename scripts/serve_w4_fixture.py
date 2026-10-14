"""Offline browser acceptance server: real graph, synthetic provider/evidence."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
import uvicorn
import agent
from fakes import FakeModelClient
from test_learning_graph import client
from test_step_teaching import plan
from webapp.main import create_app

class DemoModel(FakeModelClient):
    async def structured(self,messages,schema):
        if schema.__name__=='LessonPlanDraft':
            import json
            payload=json.loads(messages[-1].content)
            draft=plan()
            if payload.get('language')=='fa':
                for step,text in zip(draft['steps'],[
                    'مشتق نرخ تغییر را نشان می‌دهد. برای تابع \\(x^n\\)، قاعده توان به صورت \\(n x^{n-1}\\) است.',
                    'در توان n ضرب کن. توان را یکی کم کن تا $n x^{n-1}$ به دست آید.',
                    'این یادداشت قاعده را برای n صحیح مثبت بیان می‌کند. این فرض را هنگام استفاده از قاعده نگه دار.']):
                    step['explanation']=text
            return schema.model_validate(draft)
        if schema.__name__ in {'StepDraft','LessonDraft'}:
            return schema.model_validate({'explanation':'این ایده را با تعریف نمادها دوباره بررسی می‌کنیم. توان، تعداد عامل‌های یک ضرب را مشخص می‌کند.','source_ids':['power-rule']})
        return await super().structured(messages,schema)

config=agent.AppConfig(preferences=agent.Preferences(mode='learn',delivery_mode='step'),semantic_enabled=False)
graph=agent.build_graph(config,model=DemoModel(),retrieval_client=client(),channel='web')
app=create_app(config=config,credentials=agent.Credentials(),graph=graph)
if __name__=='__main__':
    uvicorn.run(app,host='127.0.0.1',port=8766)
