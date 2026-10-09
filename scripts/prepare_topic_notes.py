"""Write original starter explanations; never treat unreviewed PDF text as evidence."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES = {
    "derivative": ("calculus-volume-1", "3.3 Differentiation Rules", "beginner: rate of change; intermediate: power rules; advanced: domain and local definition", r"""# Derivatives / مشتق
These are original MathTutor starter notes, not an OpenStax transcript. Reference: Calculus Volume 1, section 3.3. The positive integer power rule was visually reviewed on PDF page 226 (printed page 218).

## Meaning and notation / مفهوم و نمادها
The derivative measures local change. For a function f, f'(a) is the limit of [f(a+h)-f(a)]/h as h approaches zero, if that finite two-sided limit exists. Here h is a nonzero change in the input. A corner may prevent a derivative even when the function is continuous.

## Power rule / قاعده توان
For a positive integer n, d(x^n)/dx = n*x^(n-1). Constants differentiate to zero; sums differentiate term by term. Negative powers require x != 0. For arbitrary real exponents, use x > 0 unless a wider real domain has been justified. A constant-base exponential needs its exponential rule, not the power rule.

## Level adaptation / سطح یادگیری
Beginner: define slope, input and output before the rule. Intermediate: rewrite polynomial terms before differentiating. Advanced: state the domain and distinguish a derivative formula from a proof that the function is differentiable. Connect a verified selected example to the rule; do not invent a replacement.
"""),
    "integral": ("calculus-volume-1", "5.3 The Fundamental Theorem of Calculus; 5.4 Integration Formulas", "beginner: primitive; intermediate: rewriting; advanced: convergence and conditions", r"""# Integrals / انتگرال
Original MathTutor starter exposition, referencing Calculus Volume 1, sections 5.3–5.4, and Calculus Volume 2, chapter 1. Raw PDF extracts are not formula-reviewed teaching evidence.

## Antiderivatives / پادمشتق
An antiderivative F of f satisfies F'(x)=f(x) on the stated interval. An indefinite integral represents a family F(x)+C. For integer n != -1, integrate x^n as x^(n+1)/(n+1)+C, respecting the original domain. The exceptional case is integral 1/x dx = ln|x|+C on an interval excluding zero. Differentiating a proposed primitive checks its derivative, not an arbitrary value of C.

## Definite integrals / انتگرال معین
If f is continuous on [a,b] and F'=f there, the integral from a to b equals F(b)-F(a). Reversing the bounds reverses its sign. A definite integral is signed accumulation, not always geometric area. Singularities or infinite bounds require an improper-integral convergence argument before endpoint substitution.

## Level adaptation / سطح یادگیری
Beginner: separate definite and indefinite questions and define C. Intermediate: expand or simplify before choosing a rule, retaining exclusions. Advanced: check hypotheses of the fundamental theorem and every improper endpoint. Do not claim an initial-value problem solved until all conditions are checked.
"""),
    "limits": ("calculus-volume-1", "2.2 The Limit of a Function; 2.3 The Limit Laws", "beginner: approach; intermediate: one-sided comparison; advanced: squeeze and existence", r"""# Limits / حد
Original MathTutor starter notes referencing Calculus Volume 1, sections 2.2–2.3.

## Approaching a value / نزدیک شدن
The limit describes outputs near an input a; f(a) itself may be missing or different. A two-sided finite limit exists only when the left and right limits exist and agree. Substitute directly only when continuity at the point justifies it.

## Choosing a method / انتخاب روش
For an indeterminate ratio 0/0, try factoring or a conjugate. Cancellation changes the expression only away from excluded inputs: preserve x != a while taking the limit. For piecewise definitions, compute both branches near the junction. A graph or decimal table suggests behavior but does not prove a limit.

## Level adaptation / سطح یادگیری
Beginner: explain 'near' with a simple input-output description. Intermediate: explain why a transformation preserves a punctured neighborhood. Advanced: justify existence, compare one-sided limits, or use the squeeze theorem with explicit bounds. Oscillation alone does not imply failure if its amplitude tends to zero.
"""),
    "algebra": ("college-algebra-2e", "2.2 Linear Equations in One Variable; 2.5 Quadratic Equations", "beginner: inverse operations; intermediate: method choice; advanced: excluded and repeated roots", r"""# Equations / معادله و جبر
Original MathTutor starter notes referencing College Algebra 2e, sections 2.2 and 2.5.

## Linear equations / معادلات خطی
In ax+b=c with a != 0, x=(c-b)/a. Apply the same operation to both sides. If a=0, decide whether the resulting constant equality is true (all allowed values) or false (no solutions). Record denominator restrictions before clearing fractions.

## Quadratic equations / معادلات درجه دوم
For ax^2+bx+c=0 with a != 0, the discriminant is D=b^2-4ac. The quadratic formula is x=(-b ± sqrt(D))/(2a). Over the reals, D<0 has no roots, D=0 has one repeated root, and D>0 has two distinct roots. Factoring may be simpler. A transformation involving division by an unknown expression can lose roots; squaring or clearing denominators can introduce invalid candidates.

## Level adaptation / سطح یادگیری
Beginner: name the variable and inverse operation. Intermediate: compare factoring, completing the square and the formula. Advanced: justify equivalence of transformations, original domain restrictions and solution-set completeness. Substituting candidates proves that they are roots, not that every root was found.
"""),
    "matrix": ("college-algebra-2e", "7.5 Matrices and Matrix Operations; 7.6 Solving Systems with Gaussian Elimination", "beginner: entries and rows; intermediate: elimination; advanced: rank and solution families", r"""# Matrices / ماتریس
Original MathTutor starter notes referencing College Algebra 2e, sections 7.5–7.6.

## Shapes and multiplication / ابعاد و ضرب
A matrix with m rows and n columns has shape m by n. Addition requires equal shapes. A product AB exists when the number of columns of A equals the number of rows of B; its (i,j) entry is the sum of A[i,k]*B[k,j] over k. In general AB differs from BA.

## Systems and inverse / دستگاه و وارون
An augmented matrix preserves the coefficients and right-hand sides of a linear system. Row swaps, nonzero row scaling and adding a multiple of another row preserve the solution set. A row [0 ... 0 | c] with c != 0 is inconsistent. For [[a,b],[c,d]], the determinant is ad-bc; an inverse exists exactly when this determinant is nonzero. An underdetermined consistent system needs free variables, not an invented unique solution.

## Level adaptation / سطح یادگیری
Beginner: label entries, shapes and what a row represents. Intermediate: show each row operation and recover the variables. Advanced: distinguish rank, consistency and a complete solution family. A determinant check alone does not verify a full worked elimination.
"""),
    "probability": ("introductory-statistics-2e", "3.1 Terminology; 3.3 Two Basic Rules of Probability", "beginner: outcomes; intermediate: conditional probability; advanced: independence assumptions", r"""# Probability / احتمال
Original MathTutor starter notes referencing Introductory Statistics 2e, sections 3.1 and 3.3. No Paul probability examples are in the existing selected lesson links; this gap is explicit.

## Outcomes and events / پیشامدها
A sample space contains possible outcomes. An event A is a subset of those outcomes. Probability lies between zero and one. Counting favorable outcomes divided by all outcomes is valid only for a finite equally likely sample space.

## Conditional and joint events / احتمال شرطی
P(A complement)=1-P(A). P(A union B)=P(A)+P(B)-P(A intersection B). If P(B)>0, P(A|B)=P(A intersection B)/P(B). Independence means P(A intersection B)=P(A)*P(B); it must be justified. Mutually exclusive nonzero-probability events cannot also be independent.

## Level adaptation / سطح یادگیری
Beginner: identify outcomes and equally likely assumptions. Intermediate: distinguish 'and', 'or' and 'given'. Advanced: state conditioning assumptions and explain why dependence changes a calculation. Do not label unverified real-world frequency assumptions as mathematical facts.
"""),
    "optimization": ("calculus-volume-1", "4.7 Applied Optimization Problems", "beginner: objective; intermediate: constraint; advanced: global extremum and endpoints", r"""# Optimization / بهینه‌سازی
Original MathTutor starter notes referencing Calculus Volume 1, section 4.7.

## Model the question / مدل‌سازی
Define the quantity to maximize or minimize, the variables, their units and the constraint. Express the objective as a function of one independent variable when justified. Translate physical restrictions into a feasible domain before differentiating.

## Check candidates / بررسی جواب‌ها
For a differentiable interior optimum, a vanishing derivative is a candidate condition. Also inspect nondifferentiable points and included endpoints. Compare objective values or give a global monotonicity argument. A critical point can be a minimum, maximum or neither; unbounded domains need additional analysis.

## Level adaptation / سطح یادگیری
Beginner: sketch the quantities and write a simple objective. Intermediate: substitute the constraint and retain units. Advanced: justify global optimality, feasible boundaries and whether a best value is attained. A derivative calculation alone does not verify a complete optimization solution.
"""),
}

RULES = [
    "[beginner] Ask about one prerequisite and define every new symbol before using it.",
    "[beginner] Connect a concrete quantity to its expression before giving a general rule.",
    "[beginner] Use short steps and explain the purpose of the current operation.",
    "[beginner] Pair a described diagram with words and equations when it clarifies the idea.",
    "[beginner] Show one complete worked example, then invite a small independent attempt.",
    "[intermediate] Explain why the chosen method fits the expression or domain.",
    "[intermediate] Ask the learner to explain one transition before revealing the next step.",
    "[intermediate] Interleave a worked solution with a related retrieval question.",
    "[intermediate] Revisit a prior concept after a delay instead of relying only on repetition now.",
    "[intermediate] Diagnose a specific misconception and correct it with a reason.",
    "[advanced] State domain restrictions and the hypotheses required by each theorem.",
    "[advanced] Separate a calculation, a proof of existence and a proof of completeness.",
    "[advanced] Discuss a boundary or counterexample that tests the claim's scope.",
    "[advanced] Preserve uncertainty and identify exactly which claims SymPy checked.",
    "[advanced] Invite an explanatory argument, then verify assumptions and special cases.",
]


def main():
    manifest = json.loads((ROOT / "sources/manifests/openstax_core.json").read_text(encoding="utf-8"))
    books = {Path(b["raw_path"]).stem: b for b in manifest["books"]}
    directory = ROOT / "sources/topics"
    directory.mkdir(parents=True, exist_ok=True)
    registry = []
    for topic, (book, section, levels, text) in NOTES.items():
        record = books[book]
        path = directory / (topic + ".md")
        path.write_text(text.strip() + "\n", encoding="utf-8")
        metadata = dict(topic=topic, provenance=dict(source_url=record["source_url"], section_title=section,
            source_author="MathTutor project (original exposition), referencing " + record["title"],
            retrieved_at=record["retrieved_at"], usage_terms_url=record["license_url"],
            usage_terms="Original project exposition; reference textbook license observed: " + record["license"] + ". Raw extracted text has not been cleared for formula fidelity or embedding use."))
        path.with_suffix(".metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        registry.append(dict(topic=topic, english=topic, persian=text.splitlines()[0].split(" / ")[1],
                             path=path.relative_to(ROOT).as_posix(), reference_book=record["title"], reference_section=section,
                             level_objectives=levels, note_origin="original_project_exposition", textbook_transcript=False))
    (ROOT / "sources/manifests/topic_registry.json").write_text(json.dumps(dict(phase=3, topics=registry, raw_book_retrieval_enabled=False,
        limitation="Starter notes do not establish whole-book coverage. Calculus Volume 2 is acquired but no direct transcript is indexed."), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    header = "# Original teaching guidance\n\nProject-authored rules: five per level. Rules about spacing, worked examples, explanatory questions and connecting representations are informed by the IES practice guide [Organizing Instruction and Study to Improve Student Learning](https://ies.ed.gov/ncee/wwc/PracticeGuide/1). Other rules implement the tutor's own domain, verification and interaction policy. These are adaptations, not quoted rules or a claim of experimentally proven tutoring quality.\n\n"
    (ROOT / "sources/teaching_bestpractices.md").write_text(header + "\n".join(f"{i}. {rule}" for i, rule in enumerate(RULES, 1)) + "\n", encoding="utf-8")
    print("Prepared seven original starter topic notes and 15 level-specific teaching rules.")


if __name__ == "__main__":
    main()
