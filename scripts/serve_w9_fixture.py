"""Acceptance-only localhost fixture: real graph/math, deterministic services.

Never use this server for normal tutoring. Its /__qa routes inject failures and
report the owned process identity for the literal restart acceptance drill.
"""
import asyncio,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import agent
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult,ChatGeneration
from model_usage import model_call_config
from serve_w8_fixture import DemoModel as W8Model,DemoRetrieval
from serve_geometry_fixture import GeometryModel
from learning import LocalRetrievalClient
from webapp.main import create_app
from webapp.settings import ServerSettings
from pydantic import BaseModel,ConfigDict
from typing import Literal

fault={'kind':'none'}
class Model(W8Model):
    async def structured(self,messages,schema):
        config=model_call_config()
        if fault['kind']=='model_timeout':raise asyncio.TimeoutError()
        if fault['kind']=='slow':await asyncio.sleep(60)
        payload=json.loads(messages[-1].content)
        geometry=any(word in payload.get('objective','') for word in ('دایره','مثلث','بردار'))
        result=await GeometryModel().structured(messages,schema) if geometry else await super().structured(messages,schema)
        if fault['kind']=='invalid_ui' and schema.__name__=='LessonPlanDraft':
            from test_ui_blocks import graph_request
            block=graph_request();block['params']['expressions'][0]['expression']='__import__(os)'
            result.steps[0].block_requests=[agent.BlockRequest.model_validate(block)]
        response=LLMResult(generations=[[ChatGeneration(message=AIMessage(content='',usage_metadata={'input_tokens':30,'output_tokens':12,'total_tokens':42}))]])
        for callback in config.get('callbacks',[]):callback.on_llm_end(response,run_id=__import__('uuid').uuid4())
        return result

class Retrieval(DemoRetrieval):
    def __init__(self,config):
        super().__init__();self.geometry=LocalRetrievalClient(config,agent.run_math_worker)
    def choose(self,request):return self.geometry if request.topic=='geometry' else super().choose(request)
    async def read_source(self,request):
        result=await super().read_source(request)
        if fault['kind']=='embedding_failure':return result.model_copy(update={'retrieval_method':'keyword','warning':'Embedding service failed safely. Using labelled keyword/metadata fallback.'})
        return result

class Search:
    async def search(self,request):
        if fault['kind']=='search_failure':raise RuntimeError('PRIVATE_SERVICE_FAILURE')
        return agent.EvidenceResult(status='empty',retrieval_method='synthetic_fixture')

config=agent.AppConfig(semantic_enabled=False,search_enabled=True,preferences=agent.Preferences(mode='learn',delivery_mode='step'))
config.limits.math_timeout_seconds=30
graph=agent.build_graph(config,Model(),retrieval_client=Retrieval(config),search_client=Search(),channel='web')
app=create_app(config=config,credentials=agent.Credentials(),graph=graph,settings=ServerSettings(usage_log_path='.cache/w9-fixture-usage.jsonl'))

class Fault(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['none','model_timeout','slow','search_failure','embedding_failure','invalid_ui']

@app.get('/__qa/state')
async def state():return {'fixture':'w9','pid':os.getpid(),**app.state.service.registry.stats()}
@app.post('/__qa/fault')
async def set_fault(value:Fault):fault['kind']=value.kind;return {'kind':value.kind}

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8766)
