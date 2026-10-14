"""Language and attribution boundaries for learner-facing lesson prose."""
import re

PERSIAN = re.compile(r"[\u0621-\u064a\u0671-\u06d3]")


def prose_only(text):
    text = re.sub(r"```[\s\S]*?```|`[^`]*`|\$\$[\s\S]*?\$\$|\$[^$\n]*\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)", " ", text)
    text = re.sub(r"\\[A-Za-z]+|\b(?:log|ln|sin|cos|tan|exp|sqrt|abs|pi|SymPy)\b", " ", text, flags=re.I)
    text = re.sub(r"MATHHOLD\d+TOKEN", " ", text)
    return text


def language_matches(text, language):
    prose = prose_only(text)
    persian = len(PERSIAN.findall(prose))
    latin = sum(len(word) for word in re.findall(r"[A-Za-z]{2,}", prose))
    if language == "fa":
        for sentence in re.split(r"(?<=[.!?؟])\s+|\n+", prose):
            if not PERSIAN.search(sentence) and sum(len(word) for word in re.findall(r"[A-Za-z]{2,}", sentence)) >= 16:
                return False
        return persian > 0 and latin <= max(12, persian * .12)
    return persian == 0


def without_attribution(text):
    # Keep mathematics and normal numbered reasoning; remove only attribution.
    text = re.sub(r"\\(?:eqref|ref|cite|citep|citet)\{[^}]*\}", "", text)
    text = re.sub(r"\\\(\s*\\\)|(?<!\$)\$\s+\$(?!\$)", "", text)
    text = re.sub(r"\[(?!\$)([^\]\n]+)\]\(https?://[^)]+\)", r"\1", text)
    text = re.sub(r"\((?:source|sources|منبع|منابع)\s*:[^)]*\)", "", text, flags=re.I)
    text = re.sub(r"\[(?:\d+(?:\s*[,;–-]\s*\d+)*|[a-f0-9]{24,64})\]", "", text)
    text = re.sub(r"(?im)^\s*(?:sources?|references?|citations?|منابع|ارجاعات)\s*:.*$", "", text)
    text = re.sub(r"(?im)^.*(?:No suitable Paul|مثال مناسب پاول|no .*coverage.*Paul|پوشش.*پاول).*$", "", text)
    text = re.sub(r"https?://\S+", "", text)
    return text.strip()


def protect_math(text):
    """Hold source notation fixed while translating the surrounding prose."""
    held = []
    def save(match):
        held.append(match.group())
        return f"MATHHOLD{len(held) - 1}TOKEN"
    pattern = (r"\$\$[\s\S]*?\$\$|\$[^$\n]*\$|`[^`]*`|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]"
               r"|(?<!\w)(?:[a-zA-Z]\w*\([^\n]*?\)|[a-zA-Z]|\d+(?:\.\d+)?)"
               r"(?:\s*[=+*/^<>-]\s*(?:[a-zA-Z]\w*\([^\n]*?\)|[a-zA-Z]|\d+(?:\.\d+)?|\([^\n]*?\)))+"
               r"|(?<!\w)(?:[a-zA-Z]\w*\([^\n]*?\)|\d+(?:\.\d+)?)(?!\w)")
    return re.sub(pattern, save, text), held


def restore_math(text, held):
    expected = [f"MATHHOLD{i}TOKEN" for i in range(len(held))]
    if re.findall(r"MATHHOLD\d+TOKEN", text) != expected:
        raise ValueError("Translation changed or reordered source mathematics")
    _, added = protect_math(re.sub(r"MATHHOLD\d+TOKEN", "", text))
    if added:
        raise ValueError("Translation added mathematics")
    for token, value in zip(expected, held):
        text = text.replace(token, value)
    return text


def source_language(text, language):
    """Select existing bilingual passages, never translate or invent mathematics."""
    lines, previous_matches = [], False
    protected, held = protect_math(text)
    for line in protected.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if re.search(r"(?i)original mathtutor|reference:|verification record|project exposition", line):
            continue
        matching = language_matches(line, language)
        neutral = not re.search(r"[A-Za-z]{2,}", prose_only(line)) and not PERSIAN.search(prose_only(line))
        if matching or (neutral and previous_matches):
            lines.append(line)
        if not neutral:
            previous_matches = matching
    selected = "\n\n".join(lines)
    for index, value in enumerate(held):
        selected = selected.replace(f"MATHHOLD{index}TOKEN", value)
    return without_attribution(selected)


def automatic_blocks(topic, text, sources, language, question=""):
    """Grounded visual defaults when the writer omits helpful components.

    Defaults require the corresponding math in the retrieved lesson. Derivations
    additionally require it in the current reply, so step lessons don't spoil it.
    All numeric samples and transformations still go through the real provider.
    """
    evidence = "\n".join(record.text for record in sources)
    fa = language == "fa"
    context = question or text
    if topic == 'geometry' or (topic == 'trigonometry' and ('unit circle' in evidence or 'دایره' in evidence)
                              and not re.search(r'(?i)graph|period|نمودار|دوره|تناوب',context)):
        if not evidence:
            return []
        if topic == 'geometry' and re.search(r'(?i)vector|بردار', context):
            if not re.search(r'(?i)vector|بردار',evidence):return []
            scene={'kind':'vectors','u':{'x':3.,'y':1.},'v':{'x':1.,'y':2.}}
            title='جمع بردارها' if fa else 'Vector addition'
            fallback='بردار جمع از جمع مؤلفه‌های دو بردار به دست می‌آید؛ نوک بردارها را حرکت بده و حاصل را مقایسه کن.' if fa else 'Add corresponding components to get the sum; move the vector tips and compare the result.'
        elif topic == 'geometry' and not re.search(r'(?i)unit circle|دایره',context):
            if not re.search(r'(?i)triangle|مثلث',evidence):return []
            scene={'kind':'triangle','vertices':[{'x':0.,'y':0.},{'x':4.,'y':0.},{'x':0.,'y':3.}]}
            title='زاویه‌ها و ضلع‌های مثلث' if fa else 'Triangle angles and sides'
            fallback='رأس‌ها را حرکت بده؛ طول ضلع‌ها، زاویه‌ها و مساحت تغییر می‌کنند. مجموع زاویه‌های داخلی مثلث غیرمنحط 180 درجه است.' if fa else 'Move the vertices to change the sides, angles and area. A nondegenerate triangle has interior angles totaling 180 degrees.'
        else:
            if not re.search(r'(?i)unit circle|دایره',evidence):return []
            scene={'kind':'unit_circle','angle_degrees':45.}
            title='دایره واحد و زاویه' if fa else 'Unit circle and angle'
            fallback='روی دایره‌ای با شعاع یک، مؤلفه افقی نقطه کسینوس زاویه و مؤلفه عمودی آن سینوس زاویه است؛ زاویه را تغییر بده و مقایسه کن.' if fa else 'On a circle of radius one, the horizontal coordinate is cosine and the vertical coordinate is sine; change the angle to compare them.'
        numeric = context.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹','0123456789'))
        if scene['kind']=='unit_circle':
            degrees=re.search(r'(\d+(?:\.\d+)?)\s*(?:degrees?|درجه|°)',numeric,re.I)
            radians=re.search(r'(?:pi|π)\s*/\s*([1-9]\d{0,2})',numeric,re.I)
            angle=float(degrees.group(1)) if degrees else 180/int(radians.group(1)) if radians else 45.
            if 0<=angle<=360:scene['angle_degrees']=angle
        else:
            pairs=re.findall(r'\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)',numeric)
            coordinates=[{'x':float(x),'y':float(y)} for x,y in pairs]
            count=3 if scene['kind']=='triangle' else 2
            if len(coordinates)==count and all(abs(value)<=10 for point in coordinates for value in point.values()):
                if scene['kind']=='triangle':scene['vertices']=coordinates
                else:scene.update(u=coordinates[0],v=coordinates[1])
        return [{'type':'geometry_canvas','title':title,'fallback_text':fallback,'params':{'scene':scene,'language':language}}]
    graph = None
    if topic == "logarithms" and re.search(r"log[_ (]|لگاریتم", evidence):
        graph = ("log(x,b)", .1, 10.,
                 "نمودار لگاریتم" if fa else "Logarithm graph",
                 "پایه را تغییر بده و مقدار لگاریتم را برای x مثبت مقایسه کن؛ نمودار از نقطه (1, 0) می‌گذرد." if fa else
                 "Change the base to compare logarithms for positive x; every curve passes through (1, 0).")
    elif topic == "derivative" and re.search(r"x\s*(?:\^2|\*\*2)", evidence):
        graph = ("x^2", -4., 4., "نمودار تابع مربعی" if fa else "Quadratic graph",
                 "شیب منحنی x به توان دو با تغییر x عوض می‌شود؛ مشتق آن 2x است." if fa else
                 "The slope of x squared changes with x; its derivative is 2x.")
    elif topic == "exponentials" and "b^x" in evidence:
        graph = ("b^x", -4., 4., "نمودار تابع نمایی" if fa else "Exponential graph",
                 "پایه را تغییر بده و رشد تابع نمایی را مقایسه کن؛ مقدار تابع در x برابر صفر، یک است." if fa else
                 "Change the base to compare exponential growth; its value at x zero is one.")
    elif topic == "trigonometry" and "sin" in evidence:
        graph = ("sin(x)", -6.28, 6.28, "نمودار سینوس" if fa else "Sine graph",
                 "سینوس بین منفی یک و یک نوسان می‌کند؛ محور x زاویه را به رادیان نشان می‌دهد." if fa else
                 "Sine oscillates between negative one and one; x is an angle in radians.")
    blocks = []
    if graph:
        expression, lo, hi, title, fallback = graph
        blocks.append({"type": "function_graph", "title": title, "fallback_text": fallback,
            "params": {"expressions": [{"label": "y", "expression": expression}],
                "domain": {"min": lo, "max": hi}, "sample_count": 200,
                "parameters": [{"name": "b", "min": 2., "max": 10., "step": 1., "default": 2.}]
                if "b" in expression else []}})
    if topic == "logarithms" and "log_2(8)" in evidence and re.search(r"log(?:_2|_\{2\})\s*\(?8|\\log_\{?2\}?\s*(?:\\left)?\(?8|2\^\{?3\}?\s*=\s*8|8\s*=\s*2\^\{?3\}?", text):
        reasons = (["صورت لگاریتمی مثال را بنویس.", "با تعریف لگاریتم به صورت توانی بنویس.", "توان سوم دو برابر هشت است."] if fa else
                   ["Write the logarithmic form.", "Use the definition to write the exponential form.", "Two to the third power equals eight."])
        states = ["log(x,2)=3", "x=2^3", "x=8"]
        blocks.append({"type": "step_reveal", "title": "از لگاریتم به توان" if fa else "From logarithm to exponent",
            "fallback_text": "رابطه log(x,2)=3 یعنی x=2^3، پس x=8." if fa else "The relation log(x,2)=3 means x=2^3, so x=8.",
            "params": {"initial_expression": states[0], "final_expression": states[-1],
                "steps": [{"step_id": f"s{i}", "state": value, "justification": reasons[i]} for i, value in enumerate(states)]}})
    return blocks
