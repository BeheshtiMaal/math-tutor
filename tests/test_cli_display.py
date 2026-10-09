"""Readable terminal output without changing mathematical calculations."""
import unittest
import io
import os
from contextlib import redirect_stdout
from unittest.mock import patch

import cli
import agent
from terminal_display import render_terminal


class DisplayChecks(unittest.TestCase):
    def test_persian_is_joined_and_visually_reordered(self):
        result = render_terminal("سلام دنیا", visual=True, width=20)
        self.assertEqual(result.strip(), "ﺎﯿﻧﺩ ﻡﺎﻠﺳ")
        self.assertEqual(len(result), 20)

    def test_formulas_keep_their_exact_ltr_order(self):
        for expression in ("2x^2 - 1 = 0", "x = -sqrt(2)/2", "x in {-1, 1}", "(a)/(b)", "۲x^2 - ۱ = ۰"):
            result = render_terminal("معادله " + expression + " را حل کنید", visual=True, width=80)
            self.assertIn(expression, result)

    def test_wrap_before_reordering_and_keep_formula_together(self):
        text = "این معادله را گام به گام حل می‌کنیم و مقدار مجهول را به دست می‌آوریم: 2x^2 - 1 = 0"
        result = render_terminal(text, visual=True, width=32)
        self.assertGreater(len(result.splitlines()), 1)
        self.assertTrue(all(len(line) <= 32 for line in result.splitlines()))
        self.assertIn("2x^2 - 1 = 0", result)

    def test_native_output_and_english_are_unchanged(self):
        text = "مرحله 1: x = -1"
        self.assertEqual(render_terminal(text, visual=False), text)
        self.assertEqual(render_terminal("math-tutor\nx = -1", visual=True), "math-tutor\nx = -1")

    def test_help_keeps_english_commands_in_order(self):
        result = render_terminal("  next  Advance one step  (بعدی)", visual=True, width=80)
        self.assertIn("next  Advance one step", result)
        self.assertIn("(ﯼﺪﻌﺑ)", result)

    def test_common_nested_math_and_persian_survive(self):
        self.assertEqual(cli.terminal_text(r"\[\boxed{x = \pm\frac{1}{\sqrt{2}}}\]"), "x = +/-(1)/(sqrt(2))")
        self.assertEqual(cli.terminal_text("پاسخ: x² − 1 = 0"), "پاسخ: x^2 - 1 = 0")
        self.assertEqual(cli.terminal_text(r"\unknown{x}"), r"\unknown{x}")

    def test_help_has_grouped_commands_and_no_box_characters(self):
        for heading in ("GET STARTED", "SETTINGS", "DURING A LESSON", "SESSION"):
            self.assertIn(heading, cli.HELP)
        self.assertNotIn("Phase 7", cli.HELP)
        self.assertNotIn("\u2502", cli.HELP)

class HelpSessionChecks(unittest.IsolatedAsyncioTestCase):
    async def test_actual_print_path_applies_rtl_only_at_display(self):
        class PersianGraph:
            async def ainvoke(self, *args):
                return {"mode": "answer", "final_answer": "پاسخ x = -1 است"}
        output = io.StringIO()
        with patch.dict(os.environ, {"TUTOR_TERMINAL_RTL": "visual"}), redirect_stdout(output):
            await cli.run_cli(agent.AppConfig(), graph=PersianGraph(), query="x+1=0")
        self.assertIn("x = -1", output.getvalue())
        self.assertNotIn("پاسخ", output.getvalue())
        self.assertIn("ﺦﺳﺎﭘ", output.getvalue())

    async def test_help_and_exit_do_not_invoke_graph(self):
        class NoGraph:
            async def ainvoke(self, *args):
                raise AssertionError("Help must not invoke services")
        lines = iter(["/help", "/exit"])
        output = []
        await cli.run_cli(agent.AppConfig(), graph=NoGraph(), read=lambda prompt: next(lines), display=output.append)
        self.assertIn("math-tutor", output[0])
        self.assertNotIn("Phase 7", "".join(output))
        self.assertIn("GET STARTED", output[1])


if __name__ == "__main__":
    unittest.main()
