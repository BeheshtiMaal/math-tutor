"""Closed W5 proposal/emission schemas. Models never supply computed data."""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, field_validator, model_validator

from agent import Contract

Finite = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=-1_000_000, le=1_000_000)]
Symbol = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,11}$")]
BlockId = Annotated[str, Field(pattern=r"^blk_[0-7][0-9A-HJKMNP-TV-Z]{25}$")]


def plain(value: str) -> str:
    if re.search(r"[<>`$#*]|https?://|javascript:|data:|[\x00-\x08\x0b\x0c\x0e-\x1f]", value, re.I):
        raise ValueError("Plain text only")
    return value


class Domain(Contract):
    min: Finite
    max: Finite

    @model_validator(mode="after")
    def ordered(self):
        if not 0 < self.max - self.min <= 200:
            raise ValueError("Domain must increase and span at most 200")
        return self


class GraphExpression(Contract):
    label: str = Field(min_length=1, max_length=24)
    expression: str = Field(min_length=1, max_length=1024)
    _label = field_validator("label")(plain)


class Slider(Contract):
    name: Symbol
    min: Finite
    max: Finite
    step: Annotated[float, Field(strict=True, gt=0, le=1_000_000, allow_inf_nan=False)]
    default: Finite

    @model_validator(mode="after")
    def bounded(self):
        if not self.min < self.max or not self.min <= self.default <= self.max or self.step > self.max - self.min:
            raise ValueError("Invalid slider range, step or default")
        if self.name in {"x", "pi", "E", "oo", "sin", "cos", "tan", "log", "exp", "sqrt", "abs"} or "__" in self.name:
            raise ValueError("Invalid parameter symbol")
        return self


class Highlight(Contract):
    x: Finite
    label: str = Field(default="", max_length=40)
    _label = field_validator("label")(plain)


class GraphParams(Contract):
    expressions: list[GraphExpression] = Field(min_length=1, max_length=3)
    variable: Literal["x"] = "x"
    domain: Domain
    parameters: list[Slider] = Field(default_factory=list, max_length=4)
    highlight_points: list[Highlight] = Field(default_factory=list, max_length=5)
    sample_count: int = Field(default=400, ge=50, le=2000, strict=True)
    x_label: str = Field(default="x", max_length=40)
    y_label: str = Field(default="y", max_length=40)
    y_domain: Domain | None = None
    _labels = field_validator("x_label", "y_label")(plain)

    @model_validator(mode="after")
    def unique(self):
        if len({p.name for p in self.parameters}) != len(self.parameters):
            raise ValueError("Duplicate slider")
        return self


class ProposedStep(Contract):
    step_id: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9:_-]+$")
    state: str = Field(min_length=1, max_length=1024)
    justification: str = Field(min_length=1, max_length=300)
    _justification = field_validator("justification")(plain)


class StepParams(Contract):
    initial_expression: str = Field(min_length=1, max_length=1024)
    final_expression: str = Field(min_length=1, max_length=1024)
    steps: list[ProposedStep] = Field(min_length=2, max_length=12)
    topic: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def unique(self):
        if len({s.step_id for s in self.steps}) != len(self.steps):
            raise ValueError("Duplicate step ID")
        return self


class Proposal(Contract):
    title: str = Field(min_length=1, max_length=120)
    fallback_text: str = Field(min_length=1, max_length=600)
    _plain = field_validator("title", "fallback_text")(plain)


class GraphRequest(Proposal):
    type: Literal["function_graph"]
    params: GraphParams


class StepRequest(Proposal):
    type: Literal["step_reveal"]
    params: StepParams


GeometryNumber = Annotated[float, Field(strict=True, ge=-10, le=10, allow_inf_nan=False)]


class GeometryInputPoint(Contract):
    x: GeometryNumber
    y: GeometryNumber


class UnitCircleScene(Contract):
    kind: Literal["unit_circle"]
    angle_degrees: Annotated[float, Field(strict=True, ge=0, le=360, allow_inf_nan=False)] = 45.0


class TriangleScene(Contract):
    kind: Literal["triangle"]
    vertices: list[GeometryInputPoint] = Field(min_length=3, max_length=3)


class VectorsScene(Contract):
    kind: Literal["vectors"]
    u: GeometryInputPoint
    v: GeometryInputPoint


GeometryScene = Annotated[UnitCircleScene | TriangleScene | VectorsScene, Field(discriminator="kind")]
geometry_scene_adapter = TypeAdapter(GeometryScene)


class GeometryParams(Contract):
    scene: GeometryScene
    language: Literal["fa", "en"] = "fa"


class GeometryRequest(Proposal):
    type: Literal["geometry_canvas"]
    params: GeometryParams


BlockProposal = Annotated[GraphRequest | StepRequest | GeometryRequest, Field(discriminator="type")]
proposal_adapter = TypeAdapter(BlockProposal)


class Point(Contract):
    x: Finite
    y: Annotated[float, Field(strict=True, allow_inf_nan=False)]


class Gap(Contract):
    from_: Finite = Field(alias="from")
    to: Finite
    reason: Literal["undefined", "discontinuity", "out_of_range"]


class Series(Contract):
    label: str = Field(max_length=24)
    points: list[Point] = Field(max_length=2000)
    gaps: list[Gap] = Field(max_length=4001)


class ResolvedHighlight(Point):
    label: str = Field(max_length=40)
    series_index: int = Field(ge=0, le=2)


class SampleResult(Contract):
    status: Literal["ok", "invalid_expression"] = "ok"
    series: list[Series] = Field(default_factory=list, max_length=3)
    highlight_points: list[ResolvedHighlight] = Field(default_factory=list, max_length=15)
    domain_warnings: list[str] = Field(default_factory=list, max_length=24)


class GraphDataParams(GraphParams):
    samples: SampleResult


class CheckedStep(ProposedStep):
    verification: Literal["verified", "unsupported", "unknown"]


class StepDataParams(StepParams):
    steps: list[CheckedStep] = Field(min_length=2, max_length=12)


class GraphBlock(Proposal):
    id: BlockId
    version: Literal[1] = 1
    type: Literal["function_graph"]
    data_source: Literal["sympy_graph_sampler"] = "sympy_graph_sampler"
    params: GraphDataParams


class StepBlock(Proposal):
    id: BlockId
    version: Literal[1] = 1
    type: Literal["step_reveal"]
    data_source: Literal["sympy_step_builder"] = "sympy_step_builder"
    params: StepDataParams


class GeometryPoint(Point):
    id: Symbol
    label: str = Field(max_length=24)
    draggable: bool = False
    _label = field_validator("label")(plain)


class GeometrySegment(Contract):
    start: Symbol
    end: Symbol
    style: Literal["edge", "projection", "vector"] = "edge"


class GeometryCircle(Contract):
    center: Symbol
    radius: Annotated[float, Field(strict=True, gt=0, le=20, allow_inf_nan=False)]


class GeometryArc(Contract):
    points: list[Point] = Field(min_length=2, max_length=73)


class GeometryMetric(Contract):
    key: Literal["angle_deg", "angle_rad", "cos", "sin", "length_AB", "length_BC", "length_CA",
                 "angle_A", "angle_B", "angle_C", "perimeter", "area", "length_u", "length_v", "length_sum", "dot", "between"]
    value: Finite | None
    unit: Literal["degrees", "radians", "length", "area", "scalar"] = "scalar"


class GeometryResult(Contract):
    status: Literal["ok", "degenerate", "zero_vector"] = "ok"
    scene: GeometryScene
    bounds: Domain
    points: list[GeometryPoint] = Field(min_length=1, max_length=8)
    segments: list[GeometrySegment] = Field(max_length=12)
    circles: list[GeometryCircle] = Field(default_factory=list, max_length=2)
    arcs: list[GeometryArc] = Field(default_factory=list, max_length=3)
    metrics: list[GeometryMetric] = Field(max_length=17)

    @model_validator(mode="after")
    def references(self):
        ids = {point.id for point in self.points}
        if len(ids) != len(self.points) or len({metric.key for metric in self.metrics}) != len(self.metrics):
            raise ValueError("Duplicate geometry IDs")
        if any(segment.start not in ids or segment.end not in ids for segment in self.segments) or any(circle.center not in ids for circle in self.circles):
            raise ValueError("Unknown geometry point reference")
        if any(not self.bounds.min <= value <= self.bounds.max for point in self.points for value in (point.x, point.y)):
            raise ValueError("Geometry point outside bounds")
        return self


class GeometryDataParams(GeometryParams):
    geometry: GeometryResult

    @model_validator(mode="after")
    def scene_matches(self):
        if self.geometry.scene != self.scene:
            raise ValueError("Geometry result belongs to a different scene")
        return self


class GeometryBlock(Proposal):
    id: BlockId
    version: Literal[1] = 1
    type: Literal["geometry_canvas"]
    data_source: Literal["geometry_engine"] = "geometry_engine"
    params: GeometryDataParams


UIBlock = Annotated[GraphBlock | StepBlock | GeometryBlock, Field(discriminator="type")]
block_adapter = TypeAdapter(UIBlock)


class SamplingRequest(Contract):
    thread_id: str = Field(min_length=30, max_length=30)
    block_id: BlockId
    expressions: list[GraphExpression] = Field(min_length=1, max_length=3)
    variable: Literal["x"] = "x"
    domain: Domain
    parameters: dict[Symbol, Finite] = Field(default_factory=dict, max_length=4)
    sample_count: int = Field(default=400, ge=50, le=2000, strict=True)
    highlight_points: list[Highlight] = Field(default_factory=list, max_length=5)

    @field_validator("thread_id")
    @classmethod
    def thread(cls, value):
        from .threads import normalize_thread_id, valid_thread_id
        value = normalize_thread_id(value)
        if not valid_thread_id(value):
            raise ValueError("Invalid thread ID")
        return value


class GeometryUpdateRequest(Contract):
    thread_id: str = Field(min_length=30, max_length=30)
    block_id: BlockId
    scene: GeometryScene
    _thread = field_validator("thread_id")(SamplingRequest.thread.__func__)
