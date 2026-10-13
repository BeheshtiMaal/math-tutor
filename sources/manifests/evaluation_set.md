# Fixed evaluation set (Phase W3)

40 items across 10 core topics: one question per level plus one misconception probe, each in Persian and English.

## logarithms.beginner.question

* Topic: logarithms | Level: beginner | Kind: question
* FA: لگاریتم چیست و چگونه وارون توان‌رسانی است؟
* EN: What is a logarithm and in what sense is it the inverse of exponentiation?
* Expected (fa): لگاریتم, پایه, توان, وارون
* Expected (en): logarithm, base, exponent, inverse

## logarithms.intermediate.question

* Topic: logarithms | Level: intermediate | Kind: question
* FA: عبارت log_b(x^2*y) را با قواعد لگاریتم بگشا و بگو چرا هر قاعده معتبر است.
* EN: Expand log_b(x^2*y) using the logarithm rules and explain why each rule applies.
* Expected (fa): قاعده ضرب, قاعده توان, دامنه
* Expected (en): product rule, power rule, domain

## logarithms.advanced.question

* Topic: logarithms | Level: advanced | Kind: question
* FA: معادله log_2(x) + log_2(x - 2) = 3 را حل کن و توضیح بده چرا یک ریشه رد می‌شود.
* EN: Solve log_2(x) + log_2(x - 2) = 3 and explain why one root is rejected.
* Expected (fa): دامنه, x = 4, ریشه ناخواسته
* Expected (en): domain, x = 4, extraneous

## logarithms.advanced.probe

* Topic: logarithms | Level: advanced | Kind: probe
* FA: آیا log_b(x + y) برابر log_b(x) + log_b(y) است؟
* EN: Is log_b(x + y) equal to log_b(x) + log_b(y)?
* Expected (fa): ضرب, جمع, نادرست
* Expected (en): product, sum, not
* Misconception: Treating a logarithm as linear: the sum rule applies to a product, not a sum.
* Correct: log_b(x*y) = log_b(x) + log_b(y); no rule turns a sum inside the argument into a sum of logarithms.

## exponentials.beginner.question

* Topic: exponentials | Level: beginner | Kind: question
* FA: تابع نمایی چیست و چرا خطی نیست؟
* EN: What is an exponential function and why is it not linear?
* Expected (fa): پایه, توان, ضرب مکرر
* Expected (en): base, exponent, repeated multiplication

## exponentials.intermediate.question

* Topic: exponentials | Level: intermediate | Kind: question
* FA: معادله 5 * 2^x = 80 را حل کن و هر گام را توضیح بده.
* EN: Solve 5 * 2^x = 80 and explain each step.
* Expected (fa): جدا کردن, x = 4, پایه یکسان
* Expected (en): isolate, x = 4, same base

## exponentials.advanced.question

* Topic: exponentials | Level: advanced | Kind: question
* FA: معادله 2^x = 30 را دقیق و عددی حل کن و بگو چرا گرفتن لگاریتم معتبر است.
* EN: Solve 2^x = 30 exactly and numerically, and explain why taking logarithms is valid.
* Expected (fa): لگاریتم طبیعی, یک‌به‌یک, 4.9069
* Expected (en): natural logarithm, injective, 4.9069

## exponentials.advanced.probe

* Topic: exponentials | Level: advanced | Kind: probe
* FA: آیا (b^x)^y با b^(x^y) برابر است؟
* EN: Is (b^x)^y equal to b^(x^y)?
* Expected (fa): نادرست, ضرب
* Expected (en): not, multiply
* Misconception: Confusing the two exponent laws, so that (b^x)^y and b^(x^y) are treated as interchangeable.
* Correct: (b^x)^y = b^(x*y), which is not b^(x^y); for example (2^2)^3 = 64 while 2^(2^3) = 256.

## trigonometry.beginner.question

* Topic: trigonometry | Level: beginner | Kind: question
* FA: سینوس، کسینوس و تانژانت را روی دایره واحد تعریف کن و مقدارشان را در pi/6 بگو.
* EN: Define sine, cosine and tangent on the unit circle and give their values at pi/6.
* Expected (fa): دایره واحد, مختصات, 1/2
* Expected (en): unit circle, coordinates, 1/2

## trigonometry.intermediate.question

* Topic: trigonometry | Level: intermediate | Kind: question
* FA: معادله 2*sin(t)^2 - sin(t) - 1 = 0 را برای t حقیقی حل کن.
* EN: Solve 2*sin(t)^2 - sin(t) - 1 = 0 for real t.
* Expected (fa): تجزیه, جواب کلی, 2k*pi
* Expected (en): factor, general solution, 2*k*pi

## trigonometry.advanced.question

* Topic: trigonometry | Level: advanced | Kind: question
* FA: ثابت کن که (1 - cos(2t))/2 = sin(t)^2 برای هر t حقیقی.
* EN: Prove that (1 - cos(2t))/2 = sin(t)^2 for every real t.
* Expected (fa): زاویه دوبرابر, اتحاد فیثاغورسی
* Expected (en): double angle, Pythagorean

## trigonometry.advanced.probe

* Topic: trigonometry | Level: advanced | Kind: probe
* FA: آیا sin(a + b) برابر sin(a) + sin(b) است؟
* EN: Is sin(a + b) equal to sin(a) + sin(b)?
* Expected (fa): نادرست, فرمول جمع
* Expected (en): not, sum formula
* Misconception: Assuming the sine is linear, so that sin(a + b) is written as sin(a) + sin(b).
* Correct: sin(a + b) = sin(a)cos(b) + cos(a)sin(b); the sine is not linear.

## algebra.beginner.question

* Topic: algebra | Level: beginner | Kind: question
* FA: معادله 3*x - 7 = 8 را با عملیات وارون حل کن.
* EN: Solve 3*x - 7 = 8 using inverse operations.
* Expected (fa): x = 5, وارون
* Expected (en): x = 5, inverse

## algebra.intermediate.question

* Topic: algebra | Level: intermediate | Kind: question
* FA: معادله 2*x^2 + 4*x - 6 = 0 را با تجزیه حل کن و پاسخ را بررسی کن.
* EN: Solve 2*x^2 + 4*x - 6 = 0 by factoring and check the answer.
* Expected (fa): تجزیه, x = -3, x = 1
* Expected (en): factor, x = -3, x = 1

## algebra.advanced.question

* Topic: algebra | Level: advanced | Kind: question
* FA: معادله sqrt(x + 5) = x - 1 را حل کن و توضیح بده کدام ریشه ناخواسته است.
* EN: Solve sqrt(x + 5) = x - 1 and explain which root is extraneous.
* Expected (fa): x = 4, ریشه ناخواسته, شرط
* Expected (en): x = 4, extraneous, condition

## algebra.advanced.probe

* Topic: algebra | Level: advanced | Kind: probe
* FA: آیا توان‌رسانی دو طرف معادله همیشه مجموعه جواب را حفظ می‌کند؟
* EN: Does squaring both sides of an equation always preserve the solution set?
* Expected (fa): نادرست, ریشه ناخواسته
* Expected (en): not, extraneous
* Misconception: Believing that squaring is a reversible step, so that no candidate root needs checking.
* Correct: Squaring is not reversible and can introduce extraneous roots, so every candidate must be checked in the original equation.

## derivative.beginner.question

* Topic: derivative | Level: beginner | Kind: question
* FA: مشتق چه چیزی را اندازه می‌گیرد و f'(a) چگونه تعریف می‌شود؟
* EN: What does the derivative measure and how is f'(a) defined?
* Expected (fa): نرخ تغییر, حد, خارج قسمت تفاضلی
* Expected (en): rate of change, limit, difference quotient

## derivative.intermediate.question

* Topic: derivative | Level: intermediate | Kind: question
* FA: تابع f(x) = 4*x^3 - 2*x + 7 را مشتق بگیر و f'(2) را بیاب.
* EN: Differentiate f(x) = 4*x^3 - 2*x + 7 and find f'(2).
* Expected (fa): 12*x^2 - 2, 46
* Expected (en): 12*x^2 - 2, 46

## derivative.advanced.question

* Topic: derivative | Level: advanced | Kind: question
* FA: تابع ln(x)/x را مشتق بگیر و نقطه بحرانی آن را روی دامنه پیدا کن.
* EN: Differentiate ln(x)/x and locate its critical point on the domain.
* Expected (fa): قاعده تقسیم, (1 - ln(x))/x^2, x = e
* Expected (en): quotient rule, (1 - ln(x))/x^2, x = e

## derivative.advanced.probe

* Topic: derivative | Level: advanced | Kind: probe
* FA: آیا مشتق x^n برابر x^(n-1) است؟
* EN: Is the derivative of x^n equal to x^(n-1)?
* Expected (fa): نادرست, n*x^(n-1)
* Expected (en): not, n*x^(n-1)
* Misconception: Dropping the coefficient in the power rule.
* Correct: d/dx x^n = n*x^(n-1); the coefficient n must be kept.

## integral.beginner.question

* Topic: integral | Level: beginner | Kind: question
* FA: پادمشتق چیست و چرا ثابت C در جواب می‌آید؟
* EN: What is an antiderivative and why does the constant C appear?
* Expected (fa): پادمشتق, خانواده, مشتق
* Expected (en): antiderivative, family, derivative

## integral.intermediate.question

* Topic: integral | Level: intermediate | Kind: question
* FA: انتگرال معین 3*x^2 را از ۰ تا ۲ حساب کن و پاسخ را بررسی کن.
* EN: Evaluate the definite integral of 3*x^2 from 0 to 2 and check the answer.
* Expected (fa): انتگرال معین, 8, قضیه اساسی
* Expected (en): definite integral, 8, fundamental theorem

## integral.advanced.question

* Topic: integral | Level: advanced | Kind: question
* FA: آیا انتگرال ناسره 1/x^2 از ۱ تا بی‌نهایت همگراست؟ آن را با 1/x مقایسه کن.
* EN: Does the improper integral of 1/x^2 from 1 to infinity converge? Compare it with 1/x.
* Expected (fa): حد, همگرا, واگرا
* Expected (en): limit, converge, diverge

## integral.advanced.probe

* Topic: integral | Level: advanced | Kind: probe
* FA: آیا انتگرال معین همیشه همان مساحت هندسی است؟
* EN: Is a definite integral always the geometric area?
* Expected (fa): نادرست, علامت‌دار
* Expected (en): not, signed
* Misconception: Reading every definite integral as geometric area, ignoring sign and orientation.
* Correct: A definite integral is signed accumulation; parts below the axis count negatively, so it need not equal geometric area.

## limits.beginner.question

* Topic: limits | Level: beginner | Kind: question
* FA: حد f(x) هنگامی که x به a نزدیک می‌شود چه معنایی دارد؟
* EN: What does the limit of f(x) as x approaches a mean?
* Expected (fa): نزدیک, دوطرفه, لزومی ندارد
* Expected (en): near, two-sided, not necessarily

## limits.intermediate.question

* Topic: limits | Level: intermediate | Kind: question
* FA: حد (x^2 - 1)/(x - 1) را هنگامی که x به ۱ نزدیک می‌شود بیاب.
* EN: Find the limit of (x^2 - 1)/(x - 1) as x approaches 1.
* Expected (fa): مبهم, تجزیه, 2
* Expected (en): indeterminate, factor, 2

## limits.advanced.question

* Topic: limits | Level: advanced | Kind: question
* FA: نشان بده حد sin(1/x) هنگام نزدیک شدن x به صفر وجود ندارد و آن را با x*sin(1/x) مقایسه کن.
* EN: Show that the limit of sin(1/x) as x approaches 0 does not exist, and compare it with x*sin(1/x).
* Expected (fa): نوسان, دنباله, قضیه فشردگی
* Expected (en): oscillation, sequence, squeeze

## limits.advanced.probe

* Topic: limits | Level: advanced | Kind: probe
* FA: آیا یک جدول مقادیر، وجود حد را اثبات می‌کند؟
* EN: Does a table of values prove that a limit exists?
* Expected (fa): نادرست, نشانه
* Expected (en): not, suggest
* Misconception: Treating a numerical table as a proof of a limit.
* Correct: A table only suggests behaviour; existence needs a two-sided limit argument such as the squeeze theorem.

## matrix.beginner.question

* Topic: matrix | Level: beginner | Kind: question
* FA: ماتریس چیست و در دستگاه معادلات یک سطر چه چیزی را نشان می‌دهد؟
* EN: What is a matrix and what does a row represent in a system of equations?
* Expected (fa): سطر, ستون, ضرایب
* Expected (en): row, column, coefficients

## matrix.intermediate.question

* Topic: matrix | Level: intermediate | Kind: question
* FA: دستگاه x + 2*y = 5 و 3*x - y = 1 را با حذف گاوسی حل کن.
* EN: Solve x + 2*y = 5 and 3*x - y = 1 by Gaussian elimination.
* Expected (fa): ماتریس افزوده, عملیات سطری, x = 1
* Expected (en): augmented matrix, row operation, x = 1

## matrix.advanced.question

* Topic: matrix | Level: advanced | Kind: question
* FA: رتبه و دترمینان چگونه سازگاری و یگانگی جواب دستگاه را تعیین می‌کنند؟
* EN: How do rank and the determinant decide consistency and uniqueness of a system?
* Expected (fa): رتبه, سازگار, دترمینان
* Expected (en): rank, consistent, determinant

## matrix.advanced.probe

* Topic: matrix | Level: advanced | Kind: probe
* FA: آیا ضرب ماتریس‌ها جابه‌جایی‌پذیر است؟
* EN: Is matrix multiplication commutative?
* Expected (fa): نادرست, جابه‌جایی
* Expected (en): not, commutative
* Misconception: Assuming AB = BA for matrices.
* Correct: In general AB is not BA; matrix multiplication is associative but not commutative.

## probability.beginner.question

* Topic: probability | Level: beginner | Kind: question
* FA: فضای نمونه چیست و برای پیامدهای هم‌شانس احتمال چگونه تعریف می‌شود؟
* EN: What is a sample space and how is probability defined for equally likely outcomes?
* Expected (fa): فضای نمونه, پیشامد, هم‌شانس
* Expected (en): sample space, event, equally likely

## probability.intermediate.question

* Topic: probability | Level: intermediate | Kind: question
* FA: با قاعده جمع، احتمال زوج یا دست‌کم ۵ آمدن در پرتاب یک تاس سالم را بیاب.
* EN: Using the addition rule, find the probability of an even result or a result of at least 5 on a fair die.
* Expected (fa): قاعده جمع, اشتراک, 2/3
* Expected (en): addition rule, intersection, 2/3

## probability.advanced.question

* Topic: probability | Level: advanced | Kind: question
* FA: آزمونی با حساسیت 0.99 و ویژگی 0.95 و شیوع 0.001؛ احتمال بیماری به شرط مثبت را بیاب.
* EN: A test with sensitivity 0.99, specificity 0.95 and prevalence 0.001; find the probability of disease given a positive result.
* Expected (fa): بیز, نرخ پایه, 0.0194
* Expected (en): Bayes, base rate, 0.0194

## probability.advanced.probe

* Topic: probability | Level: advanced | Kind: probe
* FA: اگر آزمونی ۹۹ درصد حساس باشد، آیا نتیجه مثبت یعنی ۹۹ درصد احتمال بیماری؟
* EN: If a test is 99 percent sensitive, does a positive result mean a 99 percent chance of disease?
* Expected (fa): نادرست, نرخ پایه
* Expected (en): not, base rate
* Misconception: Ignoring the base rate and reading sensitivity as the post-test probability.
* Correct: No. The post-test probability is P(disease | positive), which for a rare condition is far below the sensitivity.

## optimization.beginner.question

* Topic: optimization | Level: beginner | Kind: question
* FA: در یک مسئله بهینه‌سازی تابع هدف، متغیرها، قید و دامنه شدنی چه هستند؟
* EN: In an optimization problem, what are the objective, the variables, the constraint and the feasible domain?
* Expected (fa): تابع هدف, قید, دامنه شدنی
* Expected (en): objective, constraint, feasible domain

## optimization.intermediate.question

* Topic: optimization | Level: intermediate | Kind: question
* FA: مستطیلی محیط ۲۰ دارد؛ بزرگ‌ترین مساحت ممکن را بیاب.
* EN: A rectangle has perimeter 20; find the largest possible area.
* Expected (fa): قید, x = 5, 25
* Expected (en): constraint, x = 5, 25

## optimization.advanced.question

* Topic: optimization | Level: advanced | Kind: question
* FA: تابع x + 1/x را روی x > 0 کمینه کن و بگو آیا کمینه به دست می‌آید.
* EN: Minimize x + 1/x on x > 0 and state whether the minimum is attained.
* Expected (fa): مشتق, x = 1, به دست می‌آید
* Expected (en): derivative, x = 1, attained

## optimization.advanced.probe

* Topic: optimization | Level: advanced | Kind: probe
* FA: آیا هر نقطه بحرانی بیشینه یا کمینه است؟
* EN: Is every critical point a maximum or a minimum?
* Expected (fa): نادرست, هیچ‌کدام
* Expected (en): not, neither
* Misconception: Assuming a vanishing derivative always marks an extremum.
* Correct: A critical point can be a maximum, a minimum or neither; the sign change or the second derivative must be checked.
