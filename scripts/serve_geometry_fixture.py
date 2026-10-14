"""Deterministic external model for browser QA; actual graph/geometry/API."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import agent
from learning import LocalRetrievalClient
from webapp.main import create_app
from webapp.service import TutorService
from webapp.threads import ThreadRegistry


class GeometryModel:
    async def structured(self,messages,schema):
        payload=json.loads(messages[-1].content)
        sources=payload.get('sources',[])
        ids=[sources[0]['id']]
        objective=payload.get('objective','')
        if 'بردار' in objective:
            body='بردار دو مؤلفه افقی و عمودی دارد. جمع دو بردار مؤلفه‌به‌مؤلفه انجام می‌شود.'
        elif 'مثلث' in objective:
            body='سه رأس غیرهم‌خط یک مثلث می‌سازند. مجموع زاویه‌های داخلی آن 180 درجه است.'
        else:
            body='دایره واحد شعاع یک دارد. مؤلفه افقی نقطه کسینوس و مؤلفه عمودی آن سینوس زاویه است.'
        if schema.__name__=='LessonPlanDraft':
            return schema.model_validate({'steps':[
                {'objective':'فهم شکل','explanation':body,'source_ids':ids},
                {'objective':'مقایسه','explanation':'نقطه‌ها را جابه‌جا کن و اندازه‌ها را مقایسه کن. فرض‌های تعریف شکل را حفظ کن.','source_ids':ids}]})
        return schema.model_validate({'explanation':body,'source_ids':ids})


def app():
    config=agent.AppConfig(search_enabled=False,semantic_enabled=False,preferences=agent.Preferences(mode='learn',language='fa',learner_level='beginner',delivery_mode='step'))
    graph=agent.build_graph(config,GeometryModel(),retrieval_client=LocalRetrievalClient(config,agent.run_math_worker),channel='web')
    return create_app(service=TutorService(config=config,graph=graph,registry=ThreadRegistry()),config=config,credentials=agent.Credentials())


if __name__=='__main__':
    import uvicorn
    uvicorn.run(app(),host='127.0.0.1',port=8766)
