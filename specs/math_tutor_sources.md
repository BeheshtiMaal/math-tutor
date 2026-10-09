# منابع پروژهٔ Math Tutor

تاریخ بررسی: 2026-10-09

## دامنهٔ فهرست

Version 2.6 — four-book acquisition belongs to Phase 3. This is a selection/reference list, not a bulk download instruction. Authorized Phase 3 execution has now downloaded the four books; the execution status below records actual results and remaining formula problems.

Execution and retrieval remain governed by [the specification](math_tutor_spec.md) and [the master prompt](math_tutor_implementation_prompt.md): sole LangGraph orchestration, Persian/English cross-language retrieval with one model/version and a local persisted cache, bounded actual text/provenance, and honest keyword fallback. Earlier PostgreSQL proposals below are optional extensions, not a required database setup or a change to that contract.


## OpenStax — Four required Phase 3 textbooks

| Book | Official source page | PDF path | Extracted text path |
|---|---|---|---|
| Calculus Volume 1 | https://openstax.org/details/books/calculus-volume-1 | sources/raw/openstax/calculus-volume-1.pdf | sources/text/openstax/calculus-volume-1.md |
| Calculus Volume 2 | https://openstax.org/details/books/calculus-volume-2 | sources/raw/openstax/calculus-volume-2.pdf | sources/text/openstax/calculus-volume-2.md |
| College Algebra 2e | https://openstax.org/details/books/college-algebra-2e | sources/raw/openstax/college-algebra-2e.pdf | sources/text/openstax/college-algebra-2e.md |
| Introductory Statistics 2e | https://openstax.org/details/books/introductory-statistics-2e | sources/raw/openstax/introductory-statistics-2e.pdf | sources/text/openstax/introductory-statistics-2e.md |

Save PDFs in sources/raw/openstax/ and extract readable text to sources/text/openstax/. Retain headings, page boundaries, formulas, symbol definitions and assumptions where possible. Record missing glyphs, flattened fractions/powers, lost bounds, image-only/sparse pages and other extraction problems per book. PDF text extraction is not proof of formula fidelity: review representative mathematical content against the original before using it in topic notes or embeddings. Failed downloads/extractions remain failed/incomplete; do not manufacture source text or claim success.

During authorized Phase 3 execution create sources/manifests/openstax_core.json with exactly four book records. Each record includes title, source_url, pdf_url (resolved from the official page), license and license_url as actually observed, raw_path, text_path, download_status, actual_file_size_bytes, extraction_status and extraction_problems. Also retain retrieved_at, edition and hashes where available. Use null for unavailable URLs/licenses/sizes; distinguish not_attempted, failed, incomplete and downloaded. Measure completed PDF sizes from actual local files, report partial-transfer bytes separately, and sum only completed downloads for total_actual_download_bytes; report extracted-text bytes separately. Unknown Content-Length is not a zero-byte file or a measured size.



## نقطه‌های ورود مستقیم برای پروژه

| کاربرد | لینک |
|---|---|
| مباحث و فرمول‌های حسابان تک‌متغیره | [نمایه Calculus 1](https://openstax.org/books/calculus-volume-1/pages/index) |
| شروع Calculus 1 و دسترسی به فهرست | [فصل اول](https://openstax.org/books/calculus-volume-1/pages/1-introduction) |
| جبر و ماتریس‌ها | [نمایه College Algebra 2e](https://openstax.org/books/college-algebra-2e/pages/index) |
| دستگاه‌ها و ماتریس‌ها | [فصل ۷](https://openstax.org/books/college-algebra-2e/pages/7-introduction-to-systems-of-equations-and-inequalities) |
| پاسخ تمرین‌های فصل ماتریس‌ها | [Answer Key Chapter 7](https://openstax.org/books/college-algebra-2e/pages/chapter-7) |
| آمار و احتمال | [پیشگفتار Introductory Statistics 2e](https://openstax.org/books/introductory-statistics-2e/pages/preface) |

## Paul’s Online Math Notes — مثال‌های حل‌شده

[صفحهٔ اصلی](https://tutorial.math.lamar.edu/)

صفحات زیر درس و مثال دارند. برای شمارهٔ دقیق مثال، وارد همان صفحه شوید؛ شناسهٔ ساختگی برای مثال‌ها درج نشده است.

| موضوع | صفحهٔ مثال‌ها |
|---|---|
| معادلات خطی | [مشاهده](https://tutorial.math.lamar.edu/Classes/Alg/SolveLinearEqns.aspx) |
| معادلات درجه‌دو — بخش ۱ | [مشاهده](https://tutorial.math.lamar.edu/Classes/Alg/SolveQuadraticEqnsI.aspx) |
| معادلات درجه‌دو — بخش ۲ | [مشاهده](https://tutorial.math.lamar.edu/Classes/Alg/SolveQuadraticEqnsII.aspx) |
| دستگاه دو متغیره | [مشاهده](https://tutorial.math.lamar.edu/Classes/Alg/SystemsTwoVrble.aspx) |
| ماتریس افزوده | [مشاهده](https://tutorial.math.lamar.edu/Classes/Alg/AugmentedMatrix.aspx) |
| مفهوم حد | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/TheLimit.aspx) |
| محاسبه حد | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/ComputingLimits.aspx) |
| حد یک‌طرفه | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/OneSidedLimits.aspx) |
| حد در بی‌نهایت | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/LimitsAtInfinityI.aspx) |
| تعریف مشتق | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/DefnOfDerivative.aspx) |
| فرمول‌های مشتق | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/DiffFormulas.aspx) |
| قاعده ضرب و تقسیم | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/ProductQuotientRule.aspx) |
| قاعده زنجیره‌ای | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/ChainRule.aspx) |
| مشتق ضمنی | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/ImplicitDIff.aspx) |
| مشتق مرتبه بالاتر | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/HigherOrderDerivatives.aspx) |
| انتگرال نامعین | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/ComputingIndefiniteIntegrals.aspx) |
| تغییر متغیر | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/SubstitutionRuleIndefinite.aspx) |
| انتگرال معین | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/ComputingDefiniteIntegrals.aspx) |
| بهینه‌سازی | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/Optimization.aspx) |
| تقریب خطی | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcI/LinearApproximations.aspx) |
| جزءبه‌جزء | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcII/IntegrationByParts.aspx) |
| کسرهای جزئی | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcII/PartialFractions.aspx) |
| مشتق جزئی | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcIII/PartialDerivatives.aspx) |
| گرادیان و مشتق جهتی | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcIII/DirectionalDeriv.aspx) |
| ضرایب لاگرانژ | [مشاهده](https://tutorial.math.lamar.edu/Classes/CalcIII/LagrangeMultipliers.aspx) |

## فهرست کامل درس‌های پاول

| درس | لینک |
|---|---|
| Algebra | [فهرست](https://tutorial.math.lamar.edu/Classes/Alg/Alg.aspx) |
| Calculus I | [فهرست](https://tutorial.math.lamar.edu/Classes/CalcI/CalcI.aspx) |
| Calculus II | [فهرست](https://tutorial.math.lamar.edu/Classes/CalcII/CalcII.aspx) |
| Calculus III | [فهرست](https://tutorial.math.lamar.edu/Classes/CalcIII/CalcIII.aspx) |
| Differential Equations | [فهرست](https://tutorial.math.lamar.edu/Classes/DE/DE.aspx) |

## تمرین‌های پاول

صفحات تمرین از صفحات درس جدا هستند. از این فهرست‌ها موضوع را انتخاب کنید و پاسخ موجود هر تمرین را باز کنید.

- [Algebra practice problems](https://tutorial.math.lamar.edu/problems/alg/alg.aspx)
- [Calculus I practice problems](https://tutorial.math.lamar.edu/problems/calci/calci.aspx)
- [Calculus II practice problems](https://tutorial.math.lamar.edu/problems/calcii/calcii.aspx)
- [Calculus III practice problems](https://tutorial.math.lamar.edu/problems/calciii/calciii.aspx)

## چطور برای Agent استفاده شوند

برای شروع، Calculus 1، College Algebra 2e و Introductory Statistics 2e را انتخاب کنید. منابع موضوعی را به derivative.md، integral.md، limits.md، equations.md، matrix.md و probability.md تبدیل کنید. برای هر فایل، URL، عنوان، بخش یا صفحه، مجوز و تاریخ دریافت را نگه دارید.

مثال‌های پاول می‌توانند مرجع یادگیری و انتخاب موضوع باشند؛ لینک‌ها اجازهٔ خودکار برای کپی، استخراج انبوه یا بازنشر محتوا ایجاد نمی‌کنند. [شرایط استفادهٔ پاول](https://tutorial.math.lamar.edu/terms.aspx) و مجوز نسخهٔ دقیق کتاب OpenStax را بررسی کنید. مجوز وب و یک PDF قدیمی ممکن است یکسان نباشد؛ آن‌ها را یکسان فرض نکنید.

verified_examples ابتدا از بانک محلی مثال‌های پاول انتخاب می‌کند و مثال‌های قابل محاسبه را با SymPy بررسی می‌کند. تولید مثال با LLM پیش‌فرض نیست؛ جایگزین اختیاری باید منشأ جدا داشته باشد. منابع آمار و احتمال مکمل هستند؛ این فهرست ادعا نمی‌کند که OpenStax کتاب مستقل جامع جبر خطی یا بهینه‌سازی پیشرفته دارد.


## به‌روزرسانی نسخهٔ ۲ — بانک مثال و اصول آموزش

لینک‌های بالا حفظ شده‌اند. این فایل فهرست لینک و راهنمای آماده‌سازی است؛ متن کتاب‌ها و بانک استخراج‌شدهٔ مثال‌ها همراه آن نیست. چهار نود read_source، verified_examples، teaching_bestpractices و web_search هم‌زمان اجرا می‌شوند.

### تفکیک فایل‌های دانش
| بخش | فایل پیشنهادی | محتوای لازم |
|---|---|---|
| read_source | sources/topics/algebra.md و فایل‌های موضوعی دیگر | متن قابل استفادهٔ کتاب، فرمول‌ها، عنوان بخش و منشأ |
| verified_examples | sources/examples/paul/algebra.jsonl و فایل‌های موضوعی دیگر | صورت مثال، راه‌حل، شمارهٔ واقعی مثال در صفحه، URL و نتیجهٔ بررسی |
| teaching_bestpractices | sources/teaching_bestpractices.md | قواعد اصیل پروژه، نگاشت به سه سطح مبتدی، متوسط و پیشرفته و منابع الهام |

برای مثال‌های حل‌شده از جدول صفحات درس پاول استفاده کن؛ برای تمرین و پاسخ جداگانه از فهرست practice problems. استخراج باید راه‌حل‌های بازشونده و نمادهای MathJax/LaTeX را حفظ کند. لینک صفحه به‌اضافهٔ برچسب واقعی Example برای ارجاع کافی است؛ anchor حدسی نساز. بانک آماده‌سازی‌شده را محلی نگه دار و وضعیت source-backed را از verified با SymPy جدا کن. پیش از بازنشر یا استخراج محتوا شرایط واقعی منبع را بررسی کن؛ در این فهرست مجوزی برای استخراج انبوه ادعا نشده است.

### منابع مشخص برای اصول آموزش
- [IES / What Works Clearinghouse: Organizing Instruction and Study to Improve Student Learning](https://ies.ed.gov/ncee/wwc/PracticeGuide/1)
- [PDF رسمی راهنمای IES](https://ies.ed.gov/ncee/WWC/Docs/PracticeGuide/20072004.pdf)
- [Paul: راهنمای مطالعهٔ ریاضی — از منوی How To Study Math](https://tutorial.math.lamar.edu/)
- [Paul: خطاهای رایج — از منوی Common Math Errors](https://tutorial.math.lamar.edu/)

راهنمای IES پیشنهاد می‌کند مثال حل‌شده با تمرین ترکیب شود، نمایش ملموس و انتزاعی به هم متصل شوند و پرسش‌های توضیحی به فهم کمک کنند. برای پروژه از این‌ها قواعد کوتاه و اصیل بنویس؛ متن منبع را لازم نیست کپی کنی. تقسیم به سه سطح و اندازهٔ دو تا سه جمله در آموزش تعاملی تصمیم طراحی پروژه است، نه یک مقیاس علمی تأییدشده.

### منابع پیاده‌سازی هم‌زمان و توقف
- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph add_edge reference](https://reference.langchain.com/python/langgraph/graph/state/StateGraph/add_edge)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

چهار شاخه از learn منشعب می‌شوند و یک add_edge با فهرست هر چهار نود به write_explanation منتظر همه می‌ماند. user_input با checkpoint و interrupt منتظر پاسخ می‌ماند؛ CLI همان اجرای متوقف‌شده را resume می‌کند.


## سیاست نهایی حجم بانک مثال
فقط سه سطح: مبتدی، متوسط و پیشرفته. برای هر مبحث یا زیرمبحث مشخص و هر سطح، سه مثال منتخب از پاول کافی است؛ یعنی در حالت عادی ۹ مثال برای هر مبحث. مثال چهارم فقط در صورت نیاز؛ تمام مثال‌های یک درس را استخراج نمی‌کنیم. جدول لینک‌ها فهرست مراجع انتخاب است، نه دستور دانلود همهٔ مثال‌ها. ابتدا مبحث و سطح مشخص می‌شود و در انتهای آموزش فقط یک مثال از سه مثال همان گروه نمایش داده می‌شود. اگر منبع مثال مناسب نداشت، کمبود ثبت شود و مثال ساختگی به پاول نسبت داده نشود.

مقصد آینده: PostgreSQL + pgvector برای جستجوی معنایی، همراه فیلتر دقیق topic، subtopic، course و learner_level. فعلاً فقط تصمیم ثبت شده است؛ دریافت منابع، انتخاب مثال‌ها و راه‌اندازی پایگاه داده در مرحلهٔ ساخت انجام می‌شود.

## Phase 3 acquisition limits
Paul policy is unchanged: three selected examples per atomic topic/subtopic and each beginner, intermediate and advanced level where suitable examples exist. Use the existing linked lesson/practice pages selectively; do not crawl/download the entire collection. Keep every selected original problem together with its solution, mathematical notation, visible source example label, attribution, URL, retrieval date and terms. Verify supported calculations with SymPy; preserve verified/rejected/unknown/unsupported status and report missing level coverage without fabricated examples. Display one matching example per explanation according to the existing policy.

Downloading is scheduled for Phase 3 only. If another phase or documentation-only work is currently authorized, update the documents and stop without downloading or extracting. Existing originals remain preserved; additional books are not added to the required scope.

## Phase 3 execution status — 2026-10-09

Phase 3 was explicitly authorized and executed on 2026-10-09. Exactly four official PDFs were resolved and downloaded: **207,178,833 actual bytes**, zero partial transfers; readable extracts total **5,397,578 bytes**. Actual PDF/license URLs, author metadata, paths, hashes, page diagnostics and statuses are in [the core manifest](../sources/manifests/openstax_core.json).

The Phase 3 exit is **incomplete**: visually reviewed pages show missing formula images or flattened notation in all four extracts, which remain excluded from retrieval. Seven clearly attributed original starter notes, 15 original level-specific teaching rules, a schema/deduplicating importer and 51 distinct selected Paul examples are prepared. Mathematical result checks: 27 verified, 23 unsupported, one unknown; 21 topic/level slots remain missing. The three-per-topic-per-level policy is unchanged. No additional books, full-site crawling or entire example collection was downloaded; LangGraph-only execution and bilingual retrieval remain unchanged. No later phase was implemented in this run.

See [the Phase 3 report](../sources/manifests/phase3_report.md), [selected-example counts/rationales](../sources/manifests/paul_selection.json) and [topic registry](../sources/manifests/topic_registry.json) for actual results and remaining work. Earlier acquisition reports are historical.
