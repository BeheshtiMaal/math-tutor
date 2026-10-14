"""Tutor reactions using issued content, never client-supplied math facts."""
import asyncio
import json
from langchain_core.messages import HumanMessage, SystemMessage
from agent import Contract
from pydantic import Field, model_validator
from lesson_steps import sentences
from lesson_presentation import language_matches, without_attribution
from .providers import ProviderFailure, sample_graph
from .ui_blocks import SamplingRequest

class UIReactionDraft(Contract):
    explanation: str = Field(min_length=1,max_length=1400)
    @model_validator(mode='after')
    def short(self):
        if not 2 <= len(sentences(self.explanation)) <= 3:
            raise ValueError('Two or three sentences required')
        return self

async def react(context, state, model, config):
    event, block = context['ui_event'], context['block']
    fa = state.get('language') == 'fa'
    if event['type'] == 'block_error':
        text = block['fallback_text']
        if not language_matches(text,state['language']):
            text = state.get('current_step_explanation','')
        if not language_matches(text,state['language']): text = ''
        return ('نمایش این بخش با مشکل روبه‌رو شد. توضیح را به صورت متن ادامه می‌دهیم. ' if fa else
                'This component could not be displayed. We can continue with text. ') + text
    if event['type'] == 'step_confused':
        steps = block['params']['steps']
        index = next(i for i, step in enumerate(steps) if step['step_id'] == event['payload']['step_id'])
        current, previous = steps[index], steps[index-1] if index else None
        reason=current['justification'] if language_matches(current['justification'],state['language']) else ''
        before=(f"از $${previous['state']}$$ شروع می‌کنیم. " if fa else f"Start from $${previous['state']}$$. ") if previous else ''
        fallback = before + (f"در این گام به $${current['state']}$$ می‌رسیم. {reason}\nجای شما در درس تغییر نکرده است." if fa else
                    f"This step gives $${current['state']}$$. {reason}\nYour lesson position has not changed.")
        if model is not None:
            messages = [SystemMessage(content='Explain only the selected algebra step more simply in 2–3 short sentences in the requested language. Define the symbols and connect previous to current. Do not advance the lesson or add UI blocks. Use only the supplied states/justification. Never claim an unsupported step is verified. No citations, source names or URLs.'),
                        HumanMessage(content=json.dumps({'language':state['language'],'current_step':current,'previous_step':previous,'action':'step_confused'},ensure_ascii=False))]
            try:
                draft = UIReactionDraft.model_validate(await asyncio.wait_for(model.structured(messages,UIReactionDraft),config.limits.request_timeout_seconds))
                if (language_matches(draft.explanation,state['language']) and len(draft.explanation)<=config.limits.max_output_chars
                        and 'http' not in draft.explanation.lower()):
                    return without_attribution(draft.explanation)
            except Exception:
                pass
        return fallback
    params = block['params']
    values = event['payload']['params']
    request = SamplingRequest(thread_id=event['thread_id'],block_id=event['block_id'],
        expressions=params['expressions'],variable=params['variable'],domain=params['domain'],
        parameters=values,sample_count=51,highlight_points=params['highlight_points'])
    prefix = ('در این نمودار، ' if fa else 'For this graph, ') + (', '.join(f'{key} = {value:g}' for key,value in values.items()) or ('پارامتر متغیری نداریم' if fa else 'there are no adjustable parameters')) + '.'
    try:
        result = await sample_graph(request,config.limits)
        if result.status != 'ok': raise ProviderFailure('unavailable')
    except ProviderFailure:
        return prefix + (' این مقادیر به نمودار معتبر منجر نشدند؛ نمی‌توان از آن‌ها مقدار تابع را نتیجه گرفت.' if fa else ' These values could not produce a valid curve; no function values can be inferred from them.')
    facts=[]
    for i, series in enumerate(result.series):
        chosen=[point for point in result.highlight_points if point.series_index==i]
        if chosen:
            facts.extend(f'$x={p.x:g},\\quad {series.label}={p.y:g}$' for p in chosen)
        elif series.points:
            points=series.points
            facts.extend(f'$x={p.x:g},\\quad {series.label}={p.y:g}$' for p in [points[0],points[len(points)//2],points[-1]])
    body = ('نمونه‌های محاسبه‌شده برای همین مقادیر: ' if fa else 'Computed samples for these exact parameters: ') + '؛ '.join(facts) + '.' if facts else ('در این دامنه نقطه تعریف‌شده‌ای به دست نیامد.' if fa else 'No defined sample points were found in this domain.')
    if any(series.gaps for series in result.series):
        body += (' بخش‌های تعریف‌نشده یا خارج از محدوده روی نمودار خالی می‌مانند.' if fa else ' Undefined or out-of-range regions remain gaps in the graph.')
    return prefix + '\n\n' + body
