"""Regressions from real Persian lessons, without calling external models."""
import unittest
import os
from unittest.mock import patch

import agent
from langgraph.types import Command
from lesson_presentation import (language_matches, source_language, without_attribution,
                                 protect_math, restore_math, automatic_blocks)
from lesson_steps import fallback_plan
from fakes import FakeModelClient, FakeRetrievalClient
from test_learning_graph import source, example, evidence


def setUpModule():
    global tracing_env
    tracing_env = patch.dict(os.environ, {'LANGSMITH_TRACING':'false', 'LANGCHAIN_TRACING_V2':'false', 'LANGCHAIN_TRACING':'false'})
    tracing_env.start()


def tearDownModule():
    tracing_env.stop()


class PresentationChecks(unittest.TestCase):
    def test_formula_only_followup_does_not_switch_language(self):
        self.assertIsNone(agent.detect_language(r'$\log_{2}(x)=\frac{\sqrt{x}}{\ln(x)}$'))
        self.assertEqual(agent.detect_language(r'چرا $\log_{2}(x)$ برای x مثبت است؟'), 'fa')
        self.assertEqual(agent.detect_language('Please explain the logarithm in English'), 'en')
        self.assertFalse(language_matches('این یک توضیح طولانی به فارسی است. ' * 30 + 'Find the derivative of this function.', 'fa'))

    def test_bilingual_fallback_keeps_persian_and_math(self):
        note = source().model_copy(update={'text': 'A logarithm is an exponent. Its argument is positive.\nلگاریتم یک توان است. شرط آن x > 0 است.'})
        plan, _ = fallback_plan([note], fa=True, output_limit=6000)
        self.assertIn('x > 0', plan[0].text)
        self.assertNotIn('A logarithm', plan[0].text)
        advanced = note.model_copy(update={'text': 'At this level the learner must state hypotheses. Preserve uncertainty and say which claims were machine-checked. Strict monotonicity guarantees the unique inverse. Its domain is positive.\nدر این سطح یادگیرنده باید فرض‌ها را بیان کند. عدم قطعیت را حفظ کن و بگو کدام ادعا بررسی شد. یکنوایی اکید وجود و یگانگی وارون را تضمین می‌کند. دامنه آن مثبت است.'})
        for fa in (True, False):
            adapted, _ = fallback_plan([advanced], fa=fa, output_limit=6000)
            self.assertNotIn('machine-checked', adapted[0].text)
            self.assertNotIn('عدم قطعیت', adapted[0].text)
            self.assertIn('یکنوایی' if fa else 'monotonicity', adapted[0].text)
        review = note.model_copy(update={'text': 'A logarithm gives an exponent. It reverses a power. The base must be positive. The base cannot equal one.'})
        adapted, _ = fallback_plan([review], fa=False, output_limit=6000, review_concepts=['positive base'])
        self.assertIn('base must be positive', adapted[0].text)
        self.assertEqual([step.id for step in adapted], ['step:0', 'step:1'])
        self.assertIn('$$\nx^2\n$$', source_language('English only.\nفرمول زیر را بخوان.\n$$\nx^2\n$$', 'fa'))

    def test_citations_removed_but_numbered_math_preserved(self):
        text = 'رابطه $x=2$ برقرار است (source: b21926aa07aa3d5d7c9ae707). [1] [قاعده](https://example.org/rule) \\(\\eqref{eq:eq2}\\)\nمنابع: کتاب'
        cleaned = without_attribution(text)
        self.assertIn('$x=2$', cleaned)
        self.assertNotIn('b21926', cleaned)
        self.assertNotIn('https:', cleaned)
        self.assertNotIn('[1]', cleaned)
        self.assertNotIn('منابع:', cleaned)
        self.assertNotIn('eqref', cleaned)

    def test_translation_keeps_exact_math_and_rejects_changed_tokens(self):
        original = 'Find $f(x)=x^2$. Its derivative is $2x$.'
        protected, held = protect_math(original)
        translated = protected.replace('Find', 'بیاب').replace('Its derivative is', 'مشتق آن برابر است با')
        self.assertEqual(restore_math(translated, held), 'بیاب $f(x)=x^2$. مشتق آن برابر است با $2x$.')
        with self.assertRaises(ValueError):
            restore_math(translated.replace('MATHHOLD0TOKEN', '$x^3$'), held)
        with self.assertRaises(ValueError):
            restore_math(translated + ' $x^3$', held)

    def test_automatic_graph_grounded_and_no_early_derivation(self):
        note = source().model_copy(update={'topic':'logarithms', 'text': 'log_b(x) = y. Worked example: log_2(8) = 3.'})
        blocks = automatic_blocks('logarithms', 'لگاریتم را تعریف می‌کنیم.', [note], 'fa')
        self.assertEqual([b['type'] for b in blocks], ['function_graph'])
        self.assertTrue(language_matches(blocks[0]['title'], 'fa'))
        self.assertEqual(automatic_blocks('logarithms', 'لگاریتم', [], 'fa'), [])
        solved = automatic_blocks('logarithms', 'مثال log_2(8) = 3', [note], 'fa')
        self.assertEqual([b['type'] for b in solved], ['function_graph', 'step_reveal'])


class LessonBoundaryChecks(unittest.IsolatedAsyncioTestCase):
    def config(self):
        return agent.AppConfig(preferences=agent.Preferences(mode='learn', delivery_mode='step', learner_level='beginner'),
                               limits=agent.Limits(math_timeout_seconds=30))

    async def test_natural_request_without_model_blocks_gets_automatic_graph(self):
        note = source().model_copy(update={'topic':'logarithms', 'text':'لگاریتم توان مورد نیاز است. رابطه log_b(x)=y یعنی b^y=x.'})
        model = FakeModelClient([{'steps':[{'objective':'تعریف', 'explanation':'لگاریتم توان مورد نیاز است. ورودی آن باید مثبت باشد.', 'source_ids':[note.id]}]}])
        retrieval = FakeRetrievalClient(source=evidence([note]))
        config = self.config()
        graph = agent.build_graph(config, model, retrieval_client=retrieval, channel='web')
        result = await graph.ainvoke(agent.new_request_state(agent.Request(query='لگاریتم را از ابتدا توضیح بده'), config),
                                    {'configurable':{'thread_id':'natural-persian-log'}})
        self.assertEqual(result['language'], 'fa')
        self.assertEqual([b['type'] for b in result['ui_blocks']], ['function_graph'])
        self.assertEqual(len(model.calls), 1)
        self.assertNotRegex(result['explanation'], r'Paul|پاول|coverage|source:')

    async def test_wrong_language_model_falls_back_without_diagnostics_or_citations(self):
        note = source().model_copy(update={'text':'English source. Its argument is positive.\nتوان یک عدد صحیح است. فرمول $x^2$ را حفظ کن.'})
        model = FakeModelClient([{'explanation':'English answer.', 'source_ids':[note.id]}]*3)
        config = self.config().model_copy(update={'preferences':agent.Preferences(mode='learn', delivery_mode='full', learner_level='beginner')})
        retrieval = FakeRetrievalClient(source=evidence([note]), examples=agent.EvidenceResult(status='empty', warning='No suitable Paul example exists.', retrieval_method='fake'))
        graph = agent.build_graph(config, model, retrieval_client=retrieval, channel='web')
        result = await graph.ainvoke(agent.new_request_state(agent.Request(query='مشتق را توضیح بده'), config), {'configurable':{'thread_id':'wrong-language'}})
        self.assertIn('توان یک عدد صحیح', result['explanation'])
        self.assertNotIn('English', result['explanation'])
        self.assertNotRegex(result['explanation'], r'Paul|پاول|failed|source:')
        self.assertTrue(any('synthesis failed' in w for w in result['warnings']))

    async def test_persian_example_translates_prose_preserving_formulas(self):
        note = source().model_copy(update={'text':'توان یک عدد صحیح است. مشتق توان را کم می‌کند.'})
        row = example().model_copy(update={'statement':'Find $x^2$.', 'solution':'The derivative is $2x$.'})
        model = FakeModelClient([{'explanation':'مشتق نرخ تغییر است. فرمول را به کار ببر.', 'source_ids':[note.id]},
                                 'مقدار MATHHOLD0TOKEN را بیاب. مشتق برابر MATHHOLD1TOKEN است.'])
        config = self.config().model_copy(update={'preferences':agent.Preferences(mode='learn', delivery_mode='full', learner_level='beginner')})
        graph = agent.build_graph(config, model, retrieval_client=FakeRetrievalClient(source=evidence([note]),examples=evidence([row])))
        result = await graph.ainvoke(agent.new_request_state(agent.Request(query='مشتق را توضیح بده'), config), {'configurable':{'thread_id':'translated-example'}})
        self.assertIn('مثال:', result['explanation'])
        self.assertIn('$x^2$', result['explanation'])
        self.assertIn('$2x$', result['explanation'])
        self.assertNotRegex(result['explanation'], r'Find|derivative|Verification|Assumptions')

    async def test_deliberate_language_switch_updates_full_writer_and_cached_steps(self):
        note = source().model_copy(update={'text':'The exponent is an integer. Keep this assumption.\nتوان عدد صحیح است. این فرض را حفظ کن.'})
        fa_plan = {'steps':[
            {'objective':'تعریف','explanation':'توان عدد صحیح است. این فرض را حفظ کن.','source_ids':[note.id]},
            {'objective':'روش','explanation':'قاعده را به کار ببر. فرض را فراموش نکن.','source_ids':[note.id]},
        ]}
        en_plan = {'steps':[
            {'objective':'Definition','explanation':'The exponent is an integer. Keep this assumption.','source_ids':[note.id]},
            {'objective':'Method','explanation':'Apply the rule. Retain the assumption.','source_ids':[note.id]},
        ]}
        model=FakeModelClient([fa_plan, {'explanation':'The exponent is an integer. This is the stated assumption.','source_ids':[note.id]}, en_plan])
        config=self.config()
        graph=agent.build_graph(config,model,retrieval_client=FakeRetrievalClient(source=evidence([note])))
        thread={'configurable':{'thread_id':'language-switch-cache'}}
        await graph.ainvoke(agent.new_request_state(agent.Request(query='مشتق را توضیح بده'),config),thread)
        switched=await graph.ainvoke(Command(resume='Why is the exponent an integer?'),thread)
        self.assertEqual(switched['evidence_request']['language'],'en')
        self.assertEqual(switched['step_index'],0)
        continued=await graph.ainvoke(Command(resume='next'),thread)
        self.assertEqual(continued['step_index'],1)
        self.assertTrue(language_matches(continued['current_step_explanation'],'en'))
