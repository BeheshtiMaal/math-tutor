import unittest
from agent import AppConfig, Request, new_request_state, parse_request
from learning import infer_topic


class ConversationalEquations(unittest.TestCase):
    def test_user_equation_keeps_both_sides_and_requests_step_learning(self):
        query = "can you help me with 2x^2 - 1 = 0 step-by-step?"
        problem = parse_request(query)
        self.assertEqual(problem.model_dump(), parse_request("2x^2-1=0").model_dump())
        state = new_request_state(Request(query=query), AppConfig())
        self.assertEqual((state["mode"], state["delivery_mode"]), ("learn", "step"))
        self.assertEqual(infer_topic(query), "algebra")

    def test_explicit_request_settings_remain_authoritative(self):
        state = new_request_state(Request(query="solve 2x^2-1=0 step by step", mode="answer", delivery_mode="full"), AppConfig())
        self.assertEqual((state["mode"], state["delivery_mode"]), ("answer", "full"))

    def test_conversational_envelope_does_not_allow_code(self):
        with self.assertRaises(ValueError):
            parse_request("can you help me with __import__('os') = 0 step-by-step?")


if __name__ == "__main__":
    unittest.main()
