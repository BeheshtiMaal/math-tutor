# Remaining W3 evaluation cases

Completed the 10 unfinished pairs from `evaluation_unfinished_live.json`: the Persian/English probability advanced probe and all eight optimization pairs. Tavily was disabled (`search_enabled=False`) before the run; the model and embedding services remained enabled.

Raw results: `evaluation_remaining_10.json`. All 10 finished, with 9 complete / 0 partial / 1 missed by the unchanged keyword matcher, 0 runtime errors and 0 provider-degraded replies. No earlier completed case was rerun. The earlier 28 rows were preserved.

## Remaining score gap

`optimization.advanced.probe/fa` missed the exact words `نادرست` and `هیچ‌کدام`. It correctly states that a zero derivative is insufficient to conclude a maximum or minimum, but does not explicitly demonstrate a stationary point that is neither (for example `f(x)=x^3` at zero). Its illustrative `x+1/x` case instead demonstrates a genuine minimum.

There are also prose defects: it calls the positive-domain function `x+1/x` bounded despite correctly stating that it tends to infinity at both ends. Its derivative-zero necessity statement needs the differentiability condition and does not apply at nondifferentiable extrema. The general critical-point definition should require that the point belongs to the function's domain. Consequently the missed score is partly literal-word matching, but the answer is not certified fully correct.

The other nine scores mean all expected terms were found, not that every generated claim was mathematically verified. Windows emitted a pipe-cleanup warning after evaluation completion; the process exited 0 and all ten rows were saved.

The stopped 38-pair selection is now exhausted (28 earlier + 10 here). This does not convert the original 29 provider-degraded complete scores into repaired-writer validation, and it does not resolve quality findings from the failed-case rerun.

The evaluation harness was corrected to resume within the previous `selected_pairs` rather than treating every absent case in the full 80-pair dataset as unfinished. Five selection tests passed, including a new subset-resume regression check.
