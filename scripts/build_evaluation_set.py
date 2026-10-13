"""Build the fixed Persian/English evaluation set for the ten curated core topics.

Phase W3 task 7. Forty items: for each core topic one question at each level plus
one misconception probe. Every item carries both a Persian and an English prompt
and the key concepts a correct answer must contain. The set is fixed so W9 can
re-run it against the final system and compare.

Writes ``sources/manifests/evaluation_set.json`` and ``sources/manifests/evaluation_set.md``.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ("beginner", "intermediate", "advanced")

# topic -> four items. kind is "question" for the level items and "probe" for the
# misconception probe, which also records the wrong belief and the correct claim.
ITEMS = [
    ("logarithms", "beginner", "question",
     "لگاریتم چیست و چگونه وارون توان‌رسانی است؟",
     "What is a logarithm and in what sense is it the inverse of exponentiation?",
     ["لگاریتم", "پایه", "توان", "وارون"],
     ["logarithm", "base", "exponent", "inverse"]),
    ("logarithms", "intermediate", "question",
     "عبارت log_b(x^2*y) را با قواعد لگاریتم بگشا و بگو چرا هر قاعده معتبر است.",
     "Expand log_b(x^2*y) using the logarithm rules and explain why each rule applies.",
     ["قاعده ضرب", "قاعده توان", "دامنه"],
     ["product rule", "power rule", "domain"]),
    ("logarithms", "advanced", "question",
     "معادله log_2(x) + log_2(x - 2) = 3 را حل کن و توضیح بده چرا یک ریشه رد می‌شود.",
     "Solve log_2(x) + log_2(x - 2) = 3 and explain why one root is rejected.",
     ["دامنه", "x = 4", "ریشه ناخواسته"],
     ["domain", "x = 4", "extraneous"]),
    ("logarithms", "advanced", "probe",
     "آیا log_b(x + y) برابر log_b(x) + log_b(y) است؟",
     "Is log_b(x + y) equal to log_b(x) + log_b(y)?",
     ["ضرب", "جمع", "نادرست"],
     ["product", "sum", "not"],
     "Treating a logarithm as linear: the sum rule applies to a product, not a sum.",
     "log_b(x*y) = log_b(x) + log_b(y); no rule turns a sum inside the argument into a sum of logarithms."),

    ("exponentials", "beginner", "question",
     "تابع نمایی چیست و چرا خطی نیست؟",
     "What is an exponential function and why is it not linear?",
     ["پایه", "توان", "ضرب مکرر"],
     ["base", "exponent", "repeated multiplication"]),
    ("exponentials", "intermediate", "question",
     "معادله 5 * 2^x = 80 را حل کن و هر گام را توضیح بده.",
     "Solve 5 * 2^x = 80 and explain each step.",
     ["جدا کردن", "x = 4", "پایه یکسان"],
     ["isolate", "x = 4", "same base"]),
    ("exponentials", "advanced", "question",
     "معادله 2^x = 30 را دقیق و عددی حل کن و بگو چرا گرفتن لگاریتم معتبر است.",
     "Solve 2^x = 30 exactly and numerically, and explain why taking logarithms is valid.",
     ["لگاریتم طبیعی", "یک‌به‌یک", "4.9069"],
     ["natural logarithm", "injective", "4.9069"]),
    ("exponentials", "advanced", "probe",
     "آیا (b^x)^y با b^(x^y) برابر است؟",
     "Is (b^x)^y equal to b^(x^y)?",
     ["نادرست", "ضرب"],
     ["not", "multiply"],
     "Confusing the two exponent laws, so that (b^x)^y and b^(x^y) are treated as interchangeable.",
     "(b^x)^y = b^(x*y), which is not b^(x^y); for example (2^2)^3 = 64 while 2^(2^3) = 256."),

    ("trigonometry", "beginner", "question",
     "سینوس، کسینوس و تانژانت را روی دایره واحد تعریف کن و مقدارشان را در pi/6 بگو.",
     "Define sine, cosine and tangent on the unit circle and give their values at pi/6.",
     ["دایره واحد", "مختصات", "1/2"],
     ["unit circle", "coordinates", "1/2"]),
    ("trigonometry", "intermediate", "question",
     "معادله 2*sin(t)^2 - sin(t) - 1 = 0 را برای t حقیقی حل کن.",
     "Solve 2*sin(t)^2 - sin(t) - 1 = 0 for real t.",
     ["تجزیه", "جواب کلی", "2k*pi"],
     ["factor", "general solution", "2*k*pi"]),
    ("trigonometry", "advanced", "question",
     "ثابت کن که (1 - cos(2t))/2 = sin(t)^2 برای هر t حقیقی.",
     "Prove that (1 - cos(2t))/2 = sin(t)^2 for every real t.",
     ["زاویه دوبرابر", "اتحاد فیثاغورسی"],
     ["double angle", "Pythagorean"]),
    ("trigonometry", "advanced", "probe",
     "آیا sin(a + b) برابر sin(a) + sin(b) است؟",
     "Is sin(a + b) equal to sin(a) + sin(b)?",
     ["نادرست", "فرمول جمع"],
     ["not", "sum formula"],
     "Assuming the sine is linear, so that sin(a + b) is written as sin(a) + sin(b).",
     "sin(a + b) = sin(a)cos(b) + cos(a)sin(b); the sine is not linear."),

    ("algebra", "beginner", "question",
     "معادله 3*x - 7 = 8 را با عملیات وارون حل کن.",
     "Solve 3*x - 7 = 8 using inverse operations.",
     ["x = 5", "وارون"],
     ["x = 5", "inverse"]),
    ("algebra", "intermediate", "question",
     "معادله 2*x^2 + 4*x - 6 = 0 را با تجزیه حل کن و پاسخ را بررسی کن.",
     "Solve 2*x^2 + 4*x - 6 = 0 by factoring and check the answer.",
     ["تجزیه", "x = -3", "x = 1"],
     ["factor", "x = -3", "x = 1"]),
    ("algebra", "advanced", "question",
     "معادله sqrt(x + 5) = x - 1 را حل کن و توضیح بده کدام ریشه ناخواسته است.",
     "Solve sqrt(x + 5) = x - 1 and explain which root is extraneous.",
     ["x = 4", "ریشه ناخواسته", "شرط"],
     ["x = 4", "extraneous", "condition"]),
    ("algebra", "advanced", "probe",
     "آیا توان‌رسانی دو طرف معادله همیشه مجموعه جواب را حفظ می‌کند؟",
     "Does squaring both sides of an equation always preserve the solution set?",
     ["نادرست", "ریشه ناخواسته"],
     ["not", "extraneous"],
     "Believing that squaring is a reversible step, so that no candidate root needs checking.",
     "Squaring is not reversible and can introduce extraneous roots, so every candidate must be checked in the original equation."),

    ("derivative", "beginner", "question",
     "مشتق چه چیزی را اندازه می‌گیرد و f'(a) چگونه تعریف می‌شود؟",
     "What does the derivative measure and how is f'(a) defined?",
     ["نرخ تغییر", "حد", "خارج قسمت تفاضلی"],
     ["rate of change", "limit", "difference quotient"]),
    ("derivative", "intermediate", "question",
     "تابع f(x) = 4*x^3 - 2*x + 7 را مشتق بگیر و f'(2) را بیاب.",
     "Differentiate f(x) = 4*x^3 - 2*x + 7 and find f'(2).",
     ["12*x^2 - 2", "46"],
     ["12*x^2 - 2", "46"]),
    ("derivative", "advanced", "question",
     "تابع ln(x)/x را مشتق بگیر و نقطه بحرانی آن را روی دامنه پیدا کن.",
     "Differentiate ln(x)/x and locate its critical point on the domain.",
     ["قاعده تقسیم", "(1 - ln(x))/x^2", "x = e"],
     ["quotient rule", "(1 - ln(x))/x^2", "x = e"]),
    ("derivative", "advanced", "probe",
     "آیا مشتق x^n برابر x^(n-1) است؟",
     "Is the derivative of x^n equal to x^(n-1)?",
     ["نادرست", "n*x^(n-1)"],
     ["not", "n*x^(n-1)"],
     "Dropping the coefficient in the power rule.",
     "d/dx x^n = n*x^(n-1); the coefficient n must be kept."),

    ("integral", "beginner", "question",
     "پادمشتق چیست و چرا ثابت C در جواب می‌آید؟",
     "What is an antiderivative and why does the constant C appear?",
     ["پادمشتق", "خانواده", "مشتق"],
     ["antiderivative", "family", "derivative"]),
    ("integral", "intermediate", "question",
     "انتگرال معین 3*x^2 را از ۰ تا ۲ حساب کن و پاسخ را بررسی کن.",
     "Evaluate the definite integral of 3*x^2 from 0 to 2 and check the answer.",
     ["انتگرال معین", "8", "قضیه اساسی"],
     ["definite integral", "8", "fundamental theorem"]),
    ("integral", "advanced", "question",
     "آیا انتگرال ناسره 1/x^2 از ۱ تا بی‌نهایت همگراست؟ آن را با 1/x مقایسه کن.",
     "Does the improper integral of 1/x^2 from 1 to infinity converge? Compare it with 1/x.",
     ["حد", "همگرا", "واگرا"],
     ["limit", "converge", "diverge"]),
    ("integral", "advanced", "probe",
     "آیا انتگرال معین همیشه همان مساحت هندسی است؟",
     "Is a definite integral always the geometric area?",
     ["نادرست", "علامت‌دار"],
     ["not", "signed"],
     "Reading every definite integral as geometric area, ignoring sign and orientation.",
     "A definite integral is signed accumulation; parts below the axis count negatively, so it need not equal geometric area."),

    ("limits", "beginner", "question",
     "حد f(x) هنگامی که x به a نزدیک می‌شود چه معنایی دارد؟",
     "What does the limit of f(x) as x approaches a mean?",
     ["نزدیک", "دوطرفه", "لزومی ندارد"],
     ["near", "two-sided", "not necessarily"]),
    ("limits", "intermediate", "question",
     "حد (x^2 - 1)/(x - 1) را هنگامی که x به ۱ نزدیک می‌شود بیاب.",
     "Find the limit of (x^2 - 1)/(x - 1) as x approaches 1.",
     ["مبهم", "تجزیه", "2"],
     ["indeterminate", "factor", "2"]),
    ("limits", "advanced", "question",
     "نشان بده حد sin(1/x) هنگام نزدیک شدن x به صفر وجود ندارد و آن را با x*sin(1/x) مقایسه کن.",
     "Show that the limit of sin(1/x) as x approaches 0 does not exist, and compare it with x*sin(1/x).",
     ["نوسان", "دنباله", "قضیه فشردگی"],
     ["oscillation", "sequence", "squeeze"]),
    ("limits", "advanced", "probe",
     "آیا یک جدول مقادیر، وجود حد را اثبات می‌کند؟",
     "Does a table of values prove that a limit exists?",
     ["نادرست", "نشانه"],
     ["not", "suggest"],
     "Treating a numerical table as a proof of a limit.",
     "A table only suggests behaviour; existence needs a two-sided limit argument such as the squeeze theorem."),

    ("matrix", "beginner", "question",
     "ماتریس چیست و در دستگاه معادلات یک سطر چه چیزی را نشان می‌دهد؟",
     "What is a matrix and what does a row represent in a system of equations?",
     ["سطر", "ستون", "ضرایب"],
     ["row", "column", "coefficients"]),
    ("matrix", "intermediate", "question",
     "دستگاه x + 2*y = 5 و 3*x - y = 1 را با حذف گاوسی حل کن.",
     "Solve x + 2*y = 5 and 3*x - y = 1 by Gaussian elimination.",
     ["ماتریس افزوده", "عملیات سطری", "x = 1"],
     ["augmented matrix", "row operation", "x = 1"]),
    ("matrix", "advanced", "question",
     "رتبه و دترمینان چگونه سازگاری و یگانگی جواب دستگاه را تعیین می‌کنند؟",
     "How do rank and the determinant decide consistency and uniqueness of a system?",
     ["رتبه", "سازگار", "دترمینان"],
     ["rank", "consistent", "determinant"]),
    ("matrix", "advanced", "probe",
     "آیا ضرب ماتریس‌ها جابه‌جایی‌پذیر است؟",
     "Is matrix multiplication commutative?",
     ["نادرست", "جابه‌جایی"],
     ["not", "commutative"],
     "Assuming AB = BA for matrices.",
     "In general AB is not BA; matrix multiplication is associative but not commutative."),

    ("probability", "beginner", "question",
     "فضای نمونه چیست و برای پیامدهای هم‌شانس احتمال چگونه تعریف می‌شود؟",
     "What is a sample space and how is probability defined for equally likely outcomes?",
     ["فضای نمونه", "پیشامد", "هم‌شانس"],
     ["sample space", "event", "equally likely"]),
    ("probability", "intermediate", "question",
     "با قاعده جمع، احتمال زوج یا دست‌کم ۵ آمدن در پرتاب یک تاس سالم را بیاب.",
     "Using the addition rule, find the probability of an even result or a result of at least 5 on a fair die.",
     ["قاعده جمع", "اشتراک", "2/3"],
     ["addition rule", "intersection", "2/3"]),
    ("probability", "advanced", "question",
     "آزمونی با حساسیت 0.99 و ویژگی 0.95 و شیوع 0.001؛ احتمال بیماری به شرط مثبت را بیاب.",
     "A test with sensitivity 0.99, specificity 0.95 and prevalence 0.001; find the probability of disease given a positive result.",
     ["بیز", "نرخ پایه", "0.0194"],
     ["Bayes", "base rate", "0.0194"]),
    ("probability", "advanced", "probe",
     "اگر آزمونی ۹۹ درصد حساس باشد، آیا نتیجه مثبت یعنی ۹۹ درصد احتمال بیماری؟",
     "If a test is 99 percent sensitive, does a positive result mean a 99 percent chance of disease?",
     ["نادرست", "نرخ پایه"],
     ["not", "base rate"],
     "Ignoring the base rate and reading sensitivity as the post-test probability.",
     "No. The post-test probability is P(disease | positive), which for a rare condition is far below the sensitivity."),

    ("optimization", "beginner", "question",
     "در یک مسئله بهینه‌سازی تابع هدف، متغیرها، قید و دامنه شدنی چه هستند؟",
     "In an optimization problem, what are the objective, the variables, the constraint and the feasible domain?",
     ["تابع هدف", "قید", "دامنه شدنی"],
     ["objective", "constraint", "feasible domain"]),
    ("optimization", "intermediate", "question",
     "مستطیلی محیط ۲۰ دارد؛ بزرگ‌ترین مساحت ممکن را بیاب.",
     "A rectangle has perimeter 20; find the largest possible area.",
     ["قید", "x = 5", "25"],
     ["constraint", "x = 5", "25"]),
    ("optimization", "advanced", "question",
     "تابع x + 1/x را روی x > 0 کمینه کن و بگو آیا کمینه به دست می‌آید.",
     "Minimize x + 1/x on x > 0 and state whether the minimum is attained.",
     ["مشتق", "x = 1", "به دست می‌آید"],
     ["derivative", "x = 1", "attained"]),
    ("optimization", "advanced", "probe",
     "آیا هر نقطه بحرانی بیشینه یا کمینه است؟",
     "Is every critical point a maximum or a minimum?",
     ["نادرست", "هیچ‌کدام"],
     ["not", "neither"],
     "Assuming a vanishing derivative always marks an extremum.",
     "A critical point can be a maximum, a minimum or neither; the sign change or the second derivative must be checked."),
]


def main():
    problems = []
    seen = set()
    topics = set()
    for entry in ITEMS:
        topic, level, kind = entry[0], entry[1], entry[2]
        topics.add(topic)
        key = (topic, level, kind)
        if key in seen:
            problems.append(f"duplicate item {key}")
        seen.add(key)
        if level not in LEVELS:
            problems.append(f"{key}: unknown level")
        for index, label in ((3, "Persian prompt"), (4, "English prompt")):
            if not entry[index].strip():
                problems.append(f"{key}: empty {label}")
        if kind == "probe" and len(entry) != 9:
            problems.append(f"{key}: probe must carry the wrong belief and the correct claim")
        if kind == "question" and len(entry) != 7:
            problems.append(f"{key}: question must not carry misconception fields")

    registry = json.loads((ROOT / "sources/manifests/topic_registry.json").read_text(encoding="utf-8"))
    core = [row["topic"] for row in registry["topics"]]
    if sorted(topics) != sorted(core):
        problems.append(f"topics covered {sorted(topics)} do not match the core list {sorted(core)}")
    for topic in core:
        for level in LEVELS:
            if (topic, level, "question") not in seen:
                problems.append(f"{topic}/{level}: no level question")
        if (topic, "advanced", "probe") not in seen:
            problems.append(f"{topic}: no misconception probe")

    if problems:
        print(f"Refusing to write: {len(problems)} problem(s).")
        for problem in problems:
            print("  -", problem)
        return 1

    records = []
    for entry in ITEMS:
        topic, level, kind, prompt_fa, prompt_en, expected_fa, expected_en = entry[:7]
        record = dict(id=f"{topic}.{level}.{kind}", topic=topic, learner_level=level, kind=kind,
                      prompt=dict(fa=prompt_fa, en=prompt_en),
                      expected_concepts=dict(fa=expected_fa, en=expected_en))
        if kind == "probe":
            record["misconception"] = entry[7]
            record["correct"] = entry[8]
        records.append(record)

    payload = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        curation_phase="W3",
        items=len(records),
        languages=["fa", "en"],
        levels=list(LEVELS),
        core_topics=core,
        scoring="Concept terms are a coarse presence check for a human read, not an automatic "
                "correctness judgement. Every run is reviewed and the gaps are listed.",
        records=records,
    )
    (ROOT / "sources/manifests/evaluation_set.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# Fixed evaluation set (Phase W3)", "",
             f"{len(records)} items across {len(core)} core topics: one question per level plus one "
             "misconception probe, each in Persian and English.", ""]
    for record in records:
        lines.append(f"## {record['id']}")
        lines.append("")
        lines.append(f"* Topic: {record['topic']} | Level: {record['learner_level']} | Kind: {record['kind']}")
        lines.append(f"* FA: {record['prompt']['fa']}")
        lines.append(f"* EN: {record['prompt']['en']}")
        lines.append(f"* Expected (fa): {', '.join(record['expected_concepts']['fa'])}")
        lines.append(f"* Expected (en): {', '.join(record['expected_concepts']['en'])}")
        if record["kind"] == "probe":
            lines.append(f"* Misconception: {record['misconception']}")
            lines.append(f"* Correct: {record['correct']}")
        lines.append("")
    (ROOT / "sources/manifests/evaluation_set.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote {len(records)} items ({sum(1 for r in records if r['kind'] == 'probe')} probes) "
          f"covering {len(core)} topics in fa/en")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
