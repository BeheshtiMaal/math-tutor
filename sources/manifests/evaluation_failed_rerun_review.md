# W3 failed-case rerun review

Reran exactly the 13 partial/missed item-language pairs preserved in `evaluation_run_aborted_42.json`. No complete cases or unattempted cases were included. Raw replies and original keyword scores are in `evaluation_failed_rerun.json`; the original evaluation and recovered aggregate were preserved.

Results: 13/13 finished; 7 complete, 5 partial, 1 missed by the unchanged keyword matcher; 0 runtime errors; 0 provider-degraded replies. This is a targeted rerun, not a full 80-case evaluation or mathematical certification.

## Review of the six non-complete scores

| Case | Keyword score | Review |
| --- | --- | --- |
| exponentials.intermediate.question/fa | partial | Correctly isolates `2^x = 16 = 2^4` and solves `x=4`; describes equal bases without the exact phrase `پایه یکسان`. However, the general injectivity statement says `b>0` without excluding `b=1`; the worked base-2 solution is unaffected. |
| exponentials.advanced.probe/en | partial | States `(b^x)^y=b^(xy)` and explicitly explains the product; missing literal `multiply` is a wording mismatch. It unnecessarily excludes `b=1` from exponent laws, which also hold at base 1. |
| trigonometry.advanced.probe/fa | partial | Rejects the proposed identity and gives the correct sine addition formula; missing literal `نادرست` is a wording mismatch. Discussion of special equality cases is imprecise. |
| trigonometry.advanced.probe/en | partial | Gives the correct sine addition formula but calls it an addition formula rather than the expected `sum formula`. **Actual mathematical defect:** claims equality can hold only when both angles are multiples of `2π`. Counterexample: `a=t, b=-t` gives equality for every real `t`. The reply correctly rejects the proposed identity in general, but its exceptional-case claim is wrong. |
| algebra.advanced.probe/fa | partial | Explains extraneous roots and checking the original equation, using the plural `ریشه‌های ناخواسته` rather than the expected singular `ریشه ناخواسته`. |
| derivative.advanced.probe/fa | missed | Contains `n \cdot x^{n-1}`, explains the missing factor `n`, and rejects the proposed rule. Missing `n*x^(n-1)` and literal `نادرست` are formatting/wording mismatches. Its claim that differentiation “usually” shrinks the domain is too broad, and the `1/x` example already excludes zero before differentiation. |

The rerun establishes that the repaired writer synthesises these requests and that the derivative intermediate/beginner coverage improved. It does not establish that all generated prose is correct. Remaining work is to address the identified mathematical overstatements and make concept scoring tolerant of notation and equivalent wording without weakening correctness checks. Automated scores have not been changed to manufacture passes.

Selection regression: `python -m unittest discover -s tests -p test_evaluation_selection.py -v` — 2 tests passed, including exact 13-pair selection, language preservation, deduplication, exclusion of completed cases and rejection of unknown IDs.
