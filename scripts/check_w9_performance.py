"""Opt-in local fixture performance probe; never connects to paid services."""
import asyncio,json,math,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import httpx
from webapp.threads import new_thread_id

async def main():
    runs=[];sampling=[]
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8766',trust_env=False,timeout=150) as client:
        state=(await client.get('/__qa/state')).json()
        if state.get('fixture')!='w9':raise RuntimeError('Dedicated W9 fixture required')
        await client.post('/__qa/fault',json={'kind':'none'})
        for index in range(5):
            thread=new_thread_id();started=time.perf_counter();first_text=None;first_block=None;graph=None
            async with client.stream('POST','/api/chat/stream',json={'thread_id':thread,'message':'لگاریتم را توضیح بده','mode':'learn','delivery':'step','level_source':'inferred'}) as response:
                response.raise_for_status();event=None
                async for line in response.aiter_lines():
                    if line.startswith('event:'):event=line[6:].strip()
                    if not line.startswith('data:'):continue
                    data=json.loads(line[5:]);elapsed=time.perf_counter()-started
                    if event=='text' and first_text is None:first_text=elapsed
                    if event=='block':
                        if first_block is None:first_block=elapsed
                        if data['block']['type']=='function_graph':graph=data['block']
                    if event=='error':raise RuntimeError(data['code'])
            if graph is None:raise RuntimeError('No fixture graph emitted')
            runs.append({'run':index+1,'first_displayed_text_seconds':round(first_text,3),'first_block_seconds':round(first_block,3),'total_seconds':round(time.perf_counter()-started,3)})
            p=graph['params'];started=time.perf_counter()
            sample=await client.post('/api/ui/sample',json={'thread_id':thread,'block_id':graph['id'],'expressions':p['expressions'],'variable':p['variable'],'domain':p['domain'],'parameters':{s['name']:s['default'] for s in p['parameters']},'sample_count':101,'highlight_points':p['highlight_points']})
            sample.raise_for_status()
            if sample.json()['status']!='ok':raise RuntimeError('Sampling failed')
            sampling.append(round(time.perf_counter()-started,3))
    def stats(values):
        ordered=sorted(values);return {'median':ordered[len(ordered)//2],'p95':ordered[math.ceil(.95*len(ordered))-1],'max':max(ordered)}
    result={'scope':'localhost real graph/SymPy, deterministic external services; five independent lessons and five samples',
            'text_metric':'first validated SSE text delta, not a raw provider token','runs':runs,'sampling_seconds':sampling,
            'summary':{'first_text':stats([row['first_displayed_text_seconds'] for row in runs]),'first_block':stats([row['first_block_seconds'] for row in runs]),'sampling':stats(sampling)},
            'budgets_seconds':{'first_text':45,'first_block':60,'sampling_p95':10}}
    result['within_budget']={key:result['summary'][metric]['p95']<=budget for key,metric,budget in [('first_text','first_text',45),('first_block','first_block',60),('sampling_p95','sampling',10)]}
    (ROOT/'sources/manifests/phase_w9_performance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result['summary']),flush=True)
if __name__=='__main__':asyncio.run(main())
