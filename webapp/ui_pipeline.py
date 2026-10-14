"""Writer-internal block validation; never an orchestration node."""
import asyncio
import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import Field

from agent import BlockRequest, Contract
from .providers import ProviderFailure, parse_graph, parse_state, run_provider
from .threads import _random_suffix
from .ui_blocks import GraphBlock, GraphRequest, SamplingRequest, StepBlock, GeometryBlock, GeometryRequest, proposal_adapter

BLOCK_RULES = r"""Automatically choose block_requests when a visual adds understanding
to THIS explanation, even if the learner never asks for a component. At most two.
Use geometry_canvas for unit-circle sine/cosine, triangles, angles, vector sums
and dot products. Prefer it over a function graph when introducing these geometric ideas.
geometry_canvas params: scene={kind:'unit_circle',angle_degrees:45}, or
scene={kind:'triangle',vertices:[{x:0,y:0},{x:4,y:0},{x:0,y:3}]}, or
scene={kind:'vectors',u:{x:3,y:1},v:{x:1,y:2}}, and language='fa' or 'en'.
Angle range is 0..360 degrees; input coordinates -10..10. The server calculates
all points, lengths, areas and angles. Never supply geometry, measurements, SVG,
HTML, scripts or handlers. Preserve any coordinates specified by the learner.
For a lesson introducing logarithms, exponentials or function behaviour, include
a relevant function_graph. Use function_graph for function behaviour,
On later turns, reuse the visuals listed in existing_visuals: refer to the
existing chart instead of requesting another copy. Return [] for ordinary
follow-ups, simplification, or continuation using the same function. Add a new
visual only for a meaningfully different function or derivation.
Use step_reveal for a requested worked example or multi-step derivation; prioritize
it over a graph when the learner asks for an example. Otherwise return []. Never request
blocks in concise answer mode. Never emit HTML, JS, SVG, sample points, y coordinates
or verification labels. Every block needs type, localized plain title (<=120),
localized standalone plain fallback_text (<=600), and params. Text must still teach
the complete idea without the component. Only safe scalar grammar: x, numeric
literals, pi, E, + - * / ^, sin cos tan exp log sqrt abs; log(x,b) means base b.
function_graph params: expressions=[{label,expression}] (1-3), variable='x',
domain={min,max} (finite, ordered, span<=200), parameters=[{name,min,max,step,default}]
(0-4 unique free symbols besides x), highlight_points=[{x,label}] (0-5),
sample_count=400 (50-2000). No supplied y data. Log bases must be positive and not 1.
Step states may preserve a single source variable such as x, z or t. For
derivatives use formal notation such as \mathrm{d}(x^2)/\mathrm{dx}; do not
equate the original function with its derivative. This notation is honestly
marked unsupported by the transformation checker. Source function notation
such as f(x) or R'(z), including definitions separated by \quad, can also be
displayed as formal unsupported notation; it is never executed or certified.
step_reveal params: initial_expression, final_expression, steps (2-12) each
{step_id,state,justification}, optional topic. State uses safe grammar expressions
or equations, e.g. log(x,2)=3 -> x=2^3 -> x=8. A bounded simple LaTeX subset is also
accepted. For several real numeric roots use x in {2,3}; never discard a root
by replacing a factored quadratic with just x=2. Numeric sets have at most eight entries.
The backend renders LaTeX and checks transformations over their real
domains. Include the initial and final state as first/last rows; unique IDs <=16;
justifications <=300. Do not invent assumptions, sources or worked-example data.
"""


class BlockRepairDraft(Contract):
    # Raw entries preserve lesson text even when a model's block is malformed.
    block: dict | None = Field(default=None)


async def validate_blocks(raw_requests, *, model, config, channel, warnings, language=None):
    if channel != "web":
        return [], []
    if not isinstance(raw_requests, list) or len(raw_requests) > 2:
        warnings.append("Visual requests exceeded the block limit; text retained.")
        return [], []
    emitted, requested = [], []
    repairs_left = min(2, config.limits.writer_repairs)
    for raw in raw_requests:
        original = raw.model_dump(mode="json") if isinstance(raw, BlockRequest) else raw
        candidate = original
        # Bound repair context before either validation or model serialization.
        try:
            serialized = json.dumps(candidate, ensure_ascii=False)
        except Exception:
            serialized = ""
        if len(serialized) > 16_384 or not serialized:
            warnings.append("A visual request exceeded its size limit; text retained.")
            continue
        while True:
            try:
                proposal = proposal_adapter.validate_python(candidate)
                if language:
                    from lesson_presentation import language_matches, without_attribution
                    prose = [proposal.title, proposal.fallback_text]
                    if hasattr(proposal.params, "steps"):
                        prose.extend(step.justification for step in proposal.params.steps)
                    if any(not language_matches(value, language) or without_attribution(value) != value for value in prose):
                        raise ValueError("Visual prose must match the lesson language and omit citations")
                if isinstance(proposal, GraphRequest):
                    values = {p.name: p.default for p in proposal.params.parameters}
                    parse_graph(proposal.params.expressions, values, config.limits)
                    sampling = SamplingRequest(thread_id='thr_' + '0' * 26, block_id='blk_' + '0' * 26,
                        expressions=proposal.params.expressions, variable=proposal.params.variable,
                        domain=proposal.params.domain, parameters=values, sample_count=proposal.params.sample_count,
                        highlight_points=proposal.params.highlight_points)
                    samples = await run_provider('sample', sampling.model_dump(mode='json'), config.limits)
                    block = GraphBlock(id='blk_' + _random_suffix(), type=proposal.type,
                        title=proposal.title, fallback_text=proposal.fallback_text,
                        params={**proposal.params.model_dump(mode='json'), 'samples': samples.model_dump(mode='json', by_alias=True)})
                elif isinstance(proposal, GeometryRequest):
                    from .geometry import compute_geometry
                    params = proposal.params.model_copy(update={"language":language or proposal.params.language})
                    geometry = compute_geometry(params.scene)
                    block = GeometryBlock(id='blk_' + _random_suffix(), type=proposal.type,
                        title=proposal.title, fallback_text=proposal.fallback_text,
                        params={**params.model_dump(mode='json'),'geometry':geometry.model_dump(mode='json')})
                else:
                    for value in [proposal.params.initial_expression, proposal.params.final_expression,
                                  *(step.state for step in proposal.params.steps)]:
                        parse_state(value, config.limits)
                    steps = await run_provider('steps', proposal.params.model_dump(mode='json'), config.limits)
                    block = StepBlock(id='blk_' + _random_suffix(), type=proposal.type,
                        title=proposal.title, fallback_text=proposal.fallback_text, params=steps)
                emitted.append(block.model_dump(mode='json', by_alias=True))
                requested.append(BlockRequest.model_validate(proposal.model_dump(mode='json')))
                break
            except Exception:
                if model is None or repairs_left == 0:
                    warnings.append("A visual could not be validated and was dropped; the complete lesson remains as text.")
                    break
                repairs_left -= 1
                messages = [SystemMessage(content="Repair only this invalid visual proposal, or return block=null. "
                    + BLOCK_RULES + f" Keep all prose in {language or 'the original language'}. No citations. Keep its educational intent. Never change lesson text."),
                    HumanMessage(content=serialized)]
                try:
                    result = BlockRepairDraft.model_validate(await asyncio.wait_for(
                        model.structured(messages, BlockRepairDraft), config.limits.request_timeout_seconds))
                    if result.block is None:
                        warnings.append("An invalid visual was dropped; the complete lesson remains as text.")
                        break
                    candidate = result.block
                    serialized = json.dumps(candidate, ensure_ascii=False)
                    if len(serialized) > 16_384:
                        raise ProviderFailure('repair_size')
                except Exception:
                    warnings.append("Visual repair unavailable; the visual was dropped and the complete lesson remains as text.")
                    break
    return requested, emitted
