"""Prepare an example's step reveal; the existing pipeline validates it."""
import asyncio
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent import Contract
from .ui_pipeline import BLOCK_RULES
from .ui_blocks import StepRequest
from .providers import parse_state


class ExampleRevealDraft(Contract):
    block: StepRequest | None = None


def prepare_example_steps(block, language, limits):
    """Keep safe source math rows and make envelope endpoints actual rows."""
    def normalize(value):
        value = value.strip().replace('′', "'").replace('’', "'")
        for start,end in [('\\(', '\\)'), ('\\[', '\\]')]:
            if value.startswith(start) and value.endswith(end):
                value = value[len(start):-len(end)].strip()
        return value
    params = block['params']
    first,last = normalize(params['initial_expression']),normalize(params['final_expression'])
    parse_state(first,limits)
    parse_state(last,limits)
    rows=[]
    for row in params['steps']:
        try:
            state=normalize(row['state'])
            parse_state(state,limits)
            rows.append({**row,'state':state})
        except ValueError:
            # Domain restrictions remain in the complete example text. They
            # cannot be smuggled into an unsafe mathematical state.
            continue
    compare=lambda value: re.sub(r'\s+','',value)
    if not rows or compare(rows[0]['state']) != compare(first):
        rows.insert(0,{'state':first,'justification':'مسئله مثال را می‌نویسیم.' if language=='fa' else 'Write the example problem.'})
    if compare(rows[-1]['state']) != compare(last):
        rows.append({'state':last,'justification':'نتیجه نهایی مثال را می‌خوانیم.' if language=='fa' else 'Read the final result of the example.'})
    if len(rows)>12:
        rows=rows[:11]+[rows[-1]]
    params.update(initial_expression=first,final_expression=last,
                  steps=[{**row,'step_id':f'ex{i}'} for i,row in enumerate(rows)])
    return StepRequest.model_validate(block).model_dump(mode='json')


def requests_example(text):
    return bool(re.search(r"(?i)\bexamples?\b|مثال|نمونه", text or "") and
                not re.search(r"(?i)\b(?:no|without) examples?\b|بدون (?:مثال|نمونه)|مثال نزن", text or ""))


def focused_quadratic_example(text, *, query, language, limits):
    """Use one source's monic quadratic and matching factorization, without an LLM.

    This deliberately handles the bounded integer-factor case. Other examples
    continue through the existing model conversion and provider validation.
    """
    if not requests_example(query) or not re.search(r'(?i)quadratic|second.degree|درجه\s+(?:دو|دوم|2|۲)(?!\w)', query):
        return None
    text = text.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))
    number = r'[0-9]{1,4}(?![0-9.])'
    equation = re.search(rf'(?<!\w)([A-Za-z])\s*\^\s*2\s*([+-])\s*({number})\s*\*\s*\1\s*([+-])\s*({number})\s*=\s*0(?![0-9.])', text)
    if not equation:
        return None
    variable = equation[1]
    factor = re.search(rf'\(\s*{variable}\s*([+-])\s*({number})\s*\)\s*\*\s*\(\s*{variable}\s*([+-])\s*({number})\s*\)', text[equation.end():equation.end()+1200])
    if not factor:
        return None
    signed = lambda sign, value: int(value) * (-1 if sign == '-' else 1)
    b, c = signed(equation[2], equation[3]), signed(equation[4], equation[5])
    p, q = signed(factor[1], factor[2]), signed(factor[3], factor[4])
    if p+q != b or p*q != c:
        return None
    roots = sorted(set((-p, -q)))
    original = equation[0].strip()
    first_factor, second_factor = f'({variable}{p:+d})', f'({variable}{q:+d})'
    states = [original,
              f'{variable}^2+({p})*{variable}+({q})*{variable}+({c})=0',
              f'{variable}*{first_factor}+({q})*{first_factor}=0',
              f'{first_factor}*{second_factor}=0',
              f'{variable} in {{{",".join(map(str,roots))}}}']
    fa = language == 'fa'
    answers = (' و ' if fa else ' and ').join(map(str,roots))
    reasons = ([
        'این معادله درجه دوم است؛ مقدارهایی را پیدا می‌کنیم که طرف چپ را صفر کنند.',
        f'جمله میانی را با عددهای {p} و {q} می‌شکنیم؛ جمع آن‌ها {b} و حاصل‌ضربشان {c} است.',
        f'از دو جمله اول {variable} و از دو جمله بعد {q} را عامل مشترک می‌گیریم.',
        'عامل مشترک دو گروه را بیرون می‌کشیم تا عبارت به حاصل‌ضرب دو عامل تبدیل شود.',
        f'حاصل‌ضرب صفر است، پس دست‌کم یکی از عامل‌ها صفر می‌شود. جواب‌ها {answers} هستند؛ هر دو در معادله اولیه صدق می‌کنند.' if len(roots)==2 else
        f'هر دو عامل یکسان‌اند و صفر شدن آن‌ها یک جواب می‌دهد: {answers}.'
    ] if fa else [
        'Find all values that make this quadratic equal to zero.',
        f'Split the middle term using {p} and {q}; their sum is {b} and their product is {c}.',
        f'Factor {variable} out of the first pair and {q} out of the second pair.',
        'Factor out the common binomial to obtain a product of two factors.',
        f'A product is zero when either factor is zero. The complete real solution set contains {answers}.'
    ])
    block = {'type':'step_reveal','title':'حل مرحله‌ای یک معادله درجه دوم' if fa else 'Quadratic worked example',
             'fallback_text':f'با تجزیه معادله مثال و صفر قرار دادن عامل‌ها، جواب‌ها {answers} هستند.' if fa else f'Factor the example equation and set each factor to zero; the solutions are {answers}.',
             'params':{'initial_expression':states[0],'final_expression':states[-1],
                       'steps':[{'step_id':f'q{i}','state':state,'justification':reason} for i,(state,reason) in enumerate(zip(states,reasons))]}}
    try:
        block = prepare_example_steps(block, language, limits)
    except ValueError:
        return None
    displayed = original.replace('*', r'\cdot ')
    factored = first_factor + r'\cdot ' + second_factor + '=0'
    answer = variable + r'\in\{' + ','.join(map(str,roots)) + r'\}'
    body = (f'مثال: ${displayed}$. با تجزیه به ${factored}$ می‌رسیم، پس جواب‌ها ${answer}$ هستند. مراحل حل را یکی‌یکی در کادر زیر ببین.' if fa else
            f'Example: ${displayed}$. Factoring gives ${factored}$, so the complete solution set is ${answer}$. Reveal each step below.')
    return body, block


def sourced_derivative_reveal(text, language, limits):
    """Display exact source function/derivative endpoints when conversion fails.

    This is formal differentiation notation, not an equality between a function
    and its derivative. The normal provider determines verification status.
    """
    text=re.sub(r'\\[()\[\]]|\${1,2}',' ',text)
    term=r'(?:\d+(?:\.\d+)?|[A-Za-z_]\w*(?:\([^()\n]*\))?)'
    expression=rf'{term}(?:\s*[+*/^\-]\s*{term})*'
    original=re.search(rf"\b([A-Za-z])\(([A-Za-z])\)\s*=\s*({expression})",text)
    if not original:return []
    name,variable,function=original.groups()
    derivative=re.search(rf"\b{re.escape(name)}['′’]\({re.escape(variable)}\)\s*=\s*({expression})",text)
    if not derivative:return []
    # Reject a partial prefix of unsupported notation, such as the numerator
    # in 5/(2*sqrt(...)); never silently truncate the displayed source math.
    for match in (original,derivative):
        tail=text[match.end():]
        if tail and (tail[0].isalnum() or tail[0] in '{}'):return []
        remaining=tail.lstrip()
        if remaining and remaining[0] in '(+*/^-=\\':return []
    fa=language=='fa'
    first=rf'\mathrm{{d}}({function.strip()})/\mathrm{{d{variable}}}'
    last=derivative.group(1).strip()
    block={'type':'step_reveal','title':'مثال مشتق به‌صورت مرحله‌ای' if fa else 'Derivative worked example',
           'fallback_text':'تابع مثال و مشتق آن را مرحله‌به‌مرحله بخوان.' if fa else 'Read the example function and its derivative step by step.',
           'params':{'initial_expression':first,'final_expression':last,'steps':[
               {'step_id':'ex0','state':first,'justification':'مشتق تابع داده‌شده را می‌خواهیم.' if fa else 'Differentiate the given function.'},
               {'step_id':'ex1','state':last,'justification':'این مشتق در حل همین مثال آمده است.' if fa else 'This derivative appears in this example solution.'}]}}
    try:return [prepare_example_steps(block,language,limits)]
    except ValueError:return []


async def example_reveal(text, *, language, model, config):
    if not text:
        return []
    # The curated introductory logarithm example has a fixed, complete sourced
    # derivation. Use it directly instead of relying on another optional proposal.
    if 'log_2(8)' in text and '2^3' in text:
        fa = language == 'fa'
        states = ['log(8,2)', 'log(2^3,2)', '3']
        reasons = (['مقدار لگاریتم هشت در پایه دو را می‌خواهیم.', 'هشت را به صورت دو به توان سه می‌نویسیم.', 'لگاریتم توان لازم را می‌دهد، پس پاسخ سه است.'] if fa else
                   ['Find the logarithm of eight to base two.', 'Write eight as two to the third power.', 'The logarithm gives the exponent, so the answer is three.'])
        return [{'type':'step_reveal','title':'حل مرحله‌ای مثال لگاریتم' if fa else 'Logarithm worked example',
                 'fallback_text':'چون 8=2^3، مقدار log(8,2) برابر 3 است.' if fa else 'Since 8=2^3, log(8,2) equals 3.',
                 'params':{'initial_expression':states[0],'final_expression':states[-1],
                           'steps':[{'step_id':f's{i}','state':value,'justification':reasons[i]} for i,value in enumerate(states)]}}]
    if model is None:
        return sourced_derivative_reveal(text,language,config.limits)
    messages = [SystemMessage(content=
        "The learner requested a worked example. Convert THIS supplied example into a step_reveal block; "
        "do not replace it with a graph. Preserve the exact question, intermediate mathematics, final result and assumptions. "
        "Choose ONE worked problem if the text contains several; do not chain different problems into one derivation. "
        "Use only transformations supported by this example, not a newly invented example. "
        "For derivatives, keep the differentiation operator in the state, e.g. "
        r"\mathrm{d}(x^2)/\mathrm{dx} -> 2*x; never equate a function with its derivative. "
        "Prefer one expression/equation per state. Source function notation such as R'(z) can be displayed as formal, unsupported notation. "
        "Do not put narrative prose inside a mathematical state. "
        "Preserve a single source variable such as x, z or t. Use explicit multiplication. "
        "The first step state MUST equal initial_expression; the last MUST equal final_expression. "
        "Use two to twelve rows. For a derivative, start with its formal operator applied to the function, then end with the derivative expression alone. "
        "All titles, fallback_text and justifications must be plain prose, without LaTeX or math delimiters. "
        "Formal notation can be shown as unsupported by the checker; never replace it with a false algebraic equality. "
        "Use localized title, fallback_text and justifications in the requested language. No citations. "
        "Return block=null only if this example cannot fit the supported notation; never invent verification. "
        + BLOCK_RULES), HumanMessage(content=json.dumps({'language':language,'example':text},ensure_ascii=False))]
    for attempt in range(config.limits.writer_repairs + 1):
        try:
            result = ExampleRevealDraft.model_validate(await asyncio.wait_for(
                model.structured(messages, ExampleRevealDraft), config.limits.request_timeout_seconds))
            if result.block is None:
                break
            return [prepare_example_steps(result.block.model_dump(mode='json'),language,config.limits)]
        except ValueError:
            messages.append(HumanMessage(content='Return a valid step_reveal with plain localized prose, one safe expression per state, and matching first/last endpoints.'))
        except Exception:
            break
    return sourced_derivative_reveal(text,language,config.limits)
