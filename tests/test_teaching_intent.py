"""Natural teaching requests must reach the real learning graph without a mode toggle."""
import unittest
from langsmith import tracing_context
from agent import AppConfig, Request, build_graph, new_request_state, run_math_worker
from learning import LocalRetrievalClient


class TeachingIntentChecks(unittest.IsolatedAsyncioTestCase):
    async def test_plain_logarithm_request_reaches_lesson_and_resume(self):
        from langgraph.types import Command
        config = AppConfig()
        graph = build_graph(config, retrieval_client=LocalRetrievalClient(config, run_math_worker), channel="web")
        thread = {"configurable": {"thread_id": "teaching-intent-logarithms"}}
        with tracing_context(enabled=False):
            result = await graph.ainvoke(new_request_state(
                Request(query="hey explain me logarithm"), config), thread)
            self.assertEqual(result["mode"], "learn")
            self.assertEqual(result["topic"], "logarithms")
            self.assertEqual(result["language"], "en")
            self.assertEqual(result["learner_level"], "beginner")
            self.assertTrue(result["__interrupt__"])
            self.assertIn("learn", [event.node for event in result["execution_trace"]])
            self.assertNotIn("math_tool", [event.node for event in result["execution_trace"]])
            finished = await graph.ainvoke(Command(resume="done"), thread)
            self.assertFalse(graph.get_state(thread).next)

    def test_explicit_modes_and_calculation_requests_keep_their_choice(self):
        config = AppConfig()
        for mode in ("answer", "learn"):
            state = new_request_state(Request(query="explain logarithms", mode=mode), config)
            self.assertEqual(state["mode"], mode)
        self.assertEqual(new_request_state(Request(query="2x+5=17"), config)["mode"], "answer")
        for query in ("teach me derivatives", "I want to learn logarithms", "لگاریتم را توضیح بده"):
            self.assertEqual(new_request_state(Request(query=query), config)["mode"], "learn")

if __name__ == "__main__":
    unittest.main()
