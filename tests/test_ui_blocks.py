"""W5 schema, numerical domain, verification and worker-lifetime checks."""
import asyncio
import copy
import math
import unittest
from unittest.mock import patch

from pydantic import ValidationError
import agent
from fakes import FakeModelClient
from webapp.providers import ProviderFailure, _sample, _steps, run_provider
from webapp.ui_blocks import SamplingRequest, SampleResult, StepDataParams, proposal_adapter
from webapp.ui_pipeline import validate_blocks


def graph_request():
    return {'type':'function_graph', 'title':'Logarithm graph',
        'fallback_text':'For base 2, the logarithm of 8 is 3. Only positive x is defined.',
        'params':{'expressions':[{'label':'y', 'expression':'log(x,b)'}],
            'domain':{'min':-1,'max':9}, 'parameters':[{'name':'b','min':0.1,'max':4,'step':0.1,'default':2}],
            'sample_count':51, 'highlight_points':[{'x':8,'label':'x = 8'},{'x':0,'label':'undefined'}]}}


def step_request(states=None):
    states = states or ['log(x,2)=3','x=2^3','x=8']
    return {'type':'step_reveal','title':'Solve a logarithm equation',
        'fallback_text':'The logarithm of x to base 2 equals 3, so x equals 8.',
        'params':{'initial_expression':states[0],'final_expression':states[-1],
            'steps':[{'step_id':f's{i}', 'state':state,'justification':'Use an equivalent real equation.'} for i,state in enumerate(states)]}}


def sampling(expression='log(x,b)', **changes):
    row = dict(thread_id='thr_'+'0'*26,block_id='blk_'+'0'*26,
        expressions=[{'label':'y','expression':expression}], variable='x',
        domain={'min':-1,'max':9}, parameters={'b':2} if 'b' in expression else {},
        sample_count=51, highlight_points=[{'x':8,'label':'x = 8'},{'x':0,'label':'undefined'}])
    row.update(changes)
    return SamplingRequest.model_validate(row).model_dump(mode='json')


class SchemaChecks(unittest.TestCase):
    def test_closed_types_and_no_model_computed_fields(self):
        for mutation in [lambda row: row.update(type='html'),
                         lambda row: row.update(id='blk_'+'0'*26),
                         lambda row: row['params'].update(samples={}),
                         lambda row: row['params']['highlight_points'][0].update(y=3),
                         lambda row: row.update(title='<svg onload=alert(1)>')]:
            row=graph_request(); mutation(row)
            with self.subTest(row=row), self.assertRaises(ValidationError):
                proposal_adapter.validate_python(row)
        row=step_request(); row['params']['steps'][1]['verification']='verified'
        with self.assertRaises(ValidationError): proposal_adapter.validate_python(row)

    def test_numeric_bounds_and_sizes(self):
        mutations = [lambda p:p.update(sample_count=2001), lambda p:p.update(sample_count=True),
            lambda p:p.update(domain={'min':0,'max':201}), lambda p:p.update(domain={'min':2,'max':2}),
            lambda p:p.update(domain={'min':math.nan,'max':10}),
            lambda p:p.update(parameters=p['parameters']*5),
            lambda p:p['parameters'][0].update(step=0),
            lambda p:p['parameters'][0].update(default=10),
            lambda p:p.update(expressions=p['expressions']*4),
            lambda p:p.update(highlight_points=p['highlight_points']*3)]
        for mutate in mutations:
            row=graph_request(); mutate(row['params'])
            with self.subTest(params=row['params']), self.assertRaises(ValidationError):
                proposal_adapter.validate_python(row)
        for count in (1,13):
            row=step_request(['x=8']*count)
            with self.assertRaises(ValidationError): proposal_adapter.validate_python(row)

    def test_unique_step_and_slider_ids(self):
        row=step_request(); row['params']['steps'][1]['step_id']='s0'
        with self.assertRaises(ValidationError): proposal_adapter.validate_python(row)
        row=graph_request(); row['params']['parameters']*=2
        with self.assertRaises(ValidationError): proposal_adapter.validate_python(row)


class MathDataChecks(unittest.TestCase):
    limits=agent.Limits(math_timeout_seconds=30)

    def test_log_samples_domain_and_highlights(self):
        result=SampleResult.model_validate(_sample(sampling(),self.limits))
        self.assertTrue(all(point.x>0 for point in result.series[0].points))
        self.assertTrue(any(gap.from_<=-1 and gap.to>=0 for gap in result.series[0].gaps))
        self.assertAlmostEqual(result.highlight_points[0].y,3)
        self.assertEqual(len(result.highlight_points),1)
        self.assertIn('highlight_undefined:0',result.domain_warnings)

    def test_subunit_base_and_invalid_bases(self):
        result=_sample(sampling(parameters={'b':0.5}),self.limits)
        self.assertAlmostEqual(result['highlight_points'][0]['y'],-3)
        for base in (0,1,-2):
            with self.subTest(base=base), self.assertRaisesRegex(ProviderFailure,'log_base'):
                _sample(sampling(parameters={'b':base}),self.limits)

    def test_discontinuity_between_grid_points_and_removable_hole(self):
        for expression in ('1/(x-0.13)','(x-0.13)/(x-0.13)'):
            result=_sample(sampling(expression,domain={'min':-1,'max':1},sample_count=50,highlight_points=[]),self.limits)
            self.assertTrue(any(abs(gap['from']-0.13)<1e-10 and gap['reason']=='discontinuity' for gap in result['series'][0]['gaps']))
        result=_sample(sampling('tan(x)',domain={'min':-2,'max':2},highlight_points=[]),self.limits)
        self.assertEqual(len(result['series'][0]['gaps']),2)

    def test_sqrt_undefined_and_numeric_overflow_gaps(self):
        result=_sample(sampling('sqrt(x)',highlight_points=[]),self.limits)
        self.assertTrue(all(point['x']>=0 for point in result['series'][0]['points']))
        result=_sample(sampling('exp(x)',domain={'min':700,'max':800},highlight_points=[]),self.limits)
        self.assertTrue(any(gap['reason']=='out_of_range' for gap in result['series'][0]['gaps']))

    def test_hostile_grammar_and_unbound_symbols(self):
        for expression in ('__import__(os)','x.__class__','open(x)','x[0]','x;exec(x)','x^(2^1000)','log(x,x)','z+x','tan(1000000*x)','1/sin(x^2)'):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                _sample(sampling(expression,parameters={},highlight_points=[]),self.limits)

    def test_log_equation_steps_are_checked_and_rendered(self):
        result=StepDataParams.model_validate(_steps(step_request()['params'],self.limits))
        self.assertEqual([step.verification for step in result.steps],['verified']*3)
        self.assertIn('\\log',result.steps[0].state)
        self.assertIn('8',result.final_expression)
        latex=step_request([r'\log_{2}(x)=3','x=2^{3}','x=8'])
        self.assertTrue(all(step['verification']=='verified' for step in _steps(latex['params'],self.limits)['steps']))

    def test_false_steps_and_lost_domain_are_rejected(self):
        for states in (['log(x,2)=3','x=9'],['x=2','x^2=4'],['x/x','1'],['log(x^2)','2*log(x)']):
            with self.subTest(states=states), self.assertRaisesRegex(ProviderFailure,'false_transformation'):
                _steps(step_request(states)['params'],self.limits)

    def test_unsupported_and_unknown_are_not_verified(self):
        unsupported=_steps(step_request([r'\int x','x^2/2'])['params'],self.limits)
        self.assertEqual(unsupported['steps'][1]['verification'],'unsupported')
        unknown=_steps(step_request(['x+sin(x)=0','sin(x)+x=0'])['params'],self.limits)
        self.assertIn('unknown',[step['verification'] for step in unknown['steps']])
        row=step_request(); row['params']['final_expression']='x=9'
        with self.assertRaisesRegex(ProviderFailure,'step_endpoints'): _steps(row['params'],self.limits)


class PipelineChecks(unittest.IsolatedAsyncioTestCase):
    async def validate(self, raw, model=None, channel='web'):
        warnings=[]
        result=await validate_blocks(raw,model=model,config=agent.AppConfig(),channel=channel,warnings=warnings)
        return *result,warnings

    async def test_repairs_are_bounded_per_reply_and_text_can_continue(self):
        bad={'type':'evil','title':'bad','fallback_text':'fallback','params':{}}
        model=FakeModelClient([{'block':bad},{'block':bad},{'block':graph_request()}])
        requested,blocks,warnings=await self.validate([bad,bad],model)
        self.assertFalse(blocks); self.assertFalse(requested); self.assertTrue(warnings)
        self.assertEqual(len(model.calls),2)

    async def test_one_good_block_survives_a_bad_neighbor_and_repair(self):
        from webapp.ui_blocks import StepDataParams
        async def provider(kind,payload,limits):
            return StepDataParams.model_validate(_steps(payload,limits))
        bad={'type':'invalid'}
        model=FakeModelClient([{'block':step_request()}])
        with patch('webapp.ui_pipeline.run_provider',provider):
            requested,blocks,warnings=await self.validate([step_request(),bad],model)
        self.assertEqual(len(blocks),2); self.assertEqual(len(model.calls),1)
        self.assertTrue(all(s['verification']=='verified' for s in blocks[0]['params']['steps']))
        self.assertTrue(blocks[0]['fallback_text'])

    async def test_timeout_and_hostility_drop_without_exception(self):
        with patch('webapp.ui_pipeline.run_provider',side_effect=ProviderFailure('timeout')):
            requested,blocks,warnings=await self.validate([graph_request()])
        self.assertFalse(blocks); self.assertTrue(warnings)
        bad=graph_request(); bad['params']['expressions'][0]['expression']='__import__(os)'
        with patch('webapp.ui_pipeline.run_provider') as worker:
            requested,blocks,warnings=await self.validate([bad])
            worker.assert_not_called()
        self.assertFalse(blocks)

    async def test_cli_and_oversized_proposals_never_start_a_worker(self):
        with patch('webapp.ui_pipeline.run_provider') as worker:
            self.assertEqual((await self.validate([graph_request()],channel='cli'))[1],[])
            self.assertEqual((await self.validate([graph_request()]*3))[1],[])
            row=graph_request(); row['params']['junk']='x'*17000
            self.assertEqual((await self.validate([row]))[1],[])
            worker.assert_not_called()

    async def test_real_spawn_returns_samples_and_timeout_kills_child(self):
        result=await run_provider('sample',sampling(),agent.Limits(math_timeout_seconds=30))
        self.assertAlmostEqual(result.highlight_points[0].y,3)
        original=asyncio.create_subprocess_exec
        children=[]
        async def capture(*args,**kwargs):
            child=await original(*args,**kwargs); children.append(child); return child
        with patch('webapp.providers.asyncio.create_subprocess_exec',capture):
            with self.assertRaisesRegex(ProviderFailure,'timeout'):
                await run_provider('sample',sampling(),agent.Limits(math_timeout_seconds=0.001))
        self.assertIsNotNone(children[0].returncode)

    async def test_cancelled_work_reaps_child(self):
        original=asyncio.create_subprocess_exec
        ready=asyncio.Event(); children=[]
        async def capture(*args,**kwargs):
            child=await original(*args,**kwargs); children.append(child); ready.set(); return child
        with patch('webapp.providers.asyncio.create_subprocess_exec',capture):
            task=asyncio.create_task(run_provider('sample',sampling(),agent.Limits(math_timeout_seconds=30)))
            await ready.wait(); await asyncio.sleep(0.01); task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
        self.assertIsNotNone(children[0].returncode)


if __name__=='__main__': unittest.main()
