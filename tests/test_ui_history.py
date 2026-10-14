"""Visual novelty survives text-only turns and checkpointed lesson controls."""
import os
import unittest
from unittest.mock import patch

import agent
from langgraph.types import Command
from fakes import FakeModelClient, FakeRetrievalClient
from test_learning_graph import source, evidence
from test_ui_blocks import graph_request
from webapp.ui_history import fresh_requests, remember_visuals, shown_keys
from webapp.providers import run_provider


def setUpModule():
    global tracing
    tracing = patch.dict(os.environ, {'LANGSMITH_TRACING':'false','LANGCHAIN_TRACING_V2':'false','LANGCHAIN_TRACING':'false'})
    tracing.start()


def tearDownModule():
    tracing.stop()


class VisualHistoryChecks(unittest.TestCase):
    def test_cosmetic_changes_do_not_make_a_new_visual_and_new_lesson_resets(self):
        raw=graph_request()
        state={'lesson_objective':'Logarithms','explanation_version':1,'messages':[]}
        _, _, update=remember_visuals(state,[agent.BlockRequest.model_validate(raw)],[raw])
        state.update(update)
        changed=graph_request()
        changed['title']='A different title'
        changed['params']['domain']={'min':.2,'max':8.}
        changed['params']['sample_count']=100
        self.assertEqual(fresh_requests([changed],state),[])
        state['explanation_version']=0
        self.assertEqual(fresh_requests([changed],state),[changed])


class VisualConversationChecks(unittest.IsolatedAsyncioTestCase):
    def setup_graph(self, responses, delivery):
        config=agent.AppConfig(preferences=agent.Preferences(mode='learn',delivery_mode=delivery,learner_level='beginner',language='en'),
                               limits=agent.Limits(math_timeout_seconds=30))
        note=source().model_copy(update={'topic':'logarithms','text':'A logarithm is an exponent. log_2(8) = 3 because 2^3 = 8. The graph of x^2 is a quadratic.'})
        graph=agent.build_graph(config,FakeModelClient(responses),retrieval_client=FakeRetrievalClient(source=evidence([note])),channel='web')
        return graph, config

    async def test_step_followup_next_and_full_do_not_repeat_graph(self):
        plan={'steps':[
            {'objective':'Definition','explanation':'A logarithm is an exponent. Its argument is positive.','source_ids':['power-rule']},
            {'objective':'Example','explanation':'The value log_2(8) = 3. This follows from 2^3 = 8.','source_ids':['power-rule']},
        ]}
        response={'explanation':'The argument is positive. Real powers of a positive base are positive.','source_ids':['power-rule']}
        graph,config=self.setup_graph([plan,response],'step')
        thread={'configurable':{'thread_id':'no-repeated-step-graph'}}
        with patch('webapp.ui_pipeline.run_provider',wraps=run_provider) as provider:
            first=await graph.ainvoke(agent.new_request_state(agent.Request(query='Explain logarithms'),config),thread)
            self.assertEqual([b['type'] for b in first['ui_blocks']],['function_graph'])
            followup=await graph.ainvoke(Command(resume='Why is the argument positive?'),thread)
            self.assertEqual(followup['ui_blocks'],[])
            full=await graph.ainvoke(Command(resume='full'),thread)
            self.assertEqual([b['type'] for b in full['ui_blocks']],['step_reveal'])
            self.assertEqual([call.args[0] for call in provider.call_args_list],['sample','steps'])
            self.assertEqual(len(shown_keys(full)),2)

    async def test_full_followups_keep_history_through_text_turn_and_allow_new_function(self):
        initial=graph_request()
        repeated=graph_request(); repeated['title']='Same function again'
        different=graph_request(); different['params']['expressions']=[{'label':'y','expression':'x^2'}]; different['params']['parameters']=[]
        drafts=[{'explanation':'A logarithm is an exponent.','source_ids':['power-rule'],'block_requests':[initial]},
                {'explanation':'Its argument is positive.','source_ids':['power-rule'],'block_requests':[repeated]},
                {'explanation':'The base is positive and different from one.','source_ids':['power-rule']},
                {'explanation':'Now compare the quadratic x^2.','source_ids':['power-rule'],'block_requests':[different]}]
        graph,config=self.setup_graph(drafts,'full')
        thread={'configurable':{'thread_id':'no-repeated-full-graph'}}
        with patch('webapp.ui_pipeline.run_provider',wraps=run_provider) as provider:
            first=await graph.ainvoke(agent.new_request_state(agent.Request(query='Explain logarithms'),config),thread)
            self.assertEqual(len(first['ui_blocks']),1)
            second=await graph.ainvoke(Command(resume='Why is the argument positive?'),thread)
            self.assertEqual(second['ui_blocks'],[])
            third=await graph.ainvoke(Command(resume='What about the base?'),thread)
            self.assertEqual(third['ui_blocks'],[])
            fourth=await graph.ainvoke(Command(resume='How does the quadratic compare?'),thread)
            self.assertEqual(len(fourth['ui_blocks']),1)
            self.assertEqual(fourth['ui_blocks'][0]['params']['expressions'][0]['expression'],'x^2')
            self.assertEqual(provider.call_count,2)
