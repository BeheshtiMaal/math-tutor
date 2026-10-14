"""W8 browser acceptance: real graph/SymPy, deterministic external services."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import agent
from serve_w6_fixture import DemoModel as W6Model,DemoRetrieval
from webapp.main import create_app

class DemoModel(W6Model):
    async def structured(self,messages,schema):
        if schema.__name__=='LessonPlanDraft':
            payload=json.loads(messages[-1].content)
            draft=await super().structured(messages,schema)
            if 'لگاریتم' in payload.get('objective',''):
                if payload.get('confusion_spots'):
                    draft.steps[0].explanation='ابتدا شرط پایه را مرور کنیم. پایهٔ لگاریتم باید مثبت و نابرابر با 1 باشد، و ورودی آن نیز باید مثبت باشد.'
                elif payload['level']=='advanced':
                    draft.steps[0].explanation='از یک به یک بودن تابع نمایی برای اثبات رابطهٔ تغییر پایه استفاده می‌کنیم. فرض مثبت بودن ورودی و پایهٔ مثبت نابرابر با 1 را حفظ می‌کنیم.'
            return schema.model_validate(draft.model_dump())
        return await super().structured(messages,schema)

config=agent.AppConfig(preferences=agent.Preferences(mode='learn',delivery_mode='step'),semantic_enabled=False)
config.limits.math_timeout_seconds=30
graph=agent.build_graph(config,DemoModel(),retrieval_client=DemoRetrieval(),channel='web')
app=create_app(config=config,credentials=agent.Credentials(),graph=graph)
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8766)
