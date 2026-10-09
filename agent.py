"""MathTutor contracts and exact compiled answer/full-learning LangGraph.

Importing this module does not load .env, create clients, or make network calls.
"""
from __future__ import annotations

from collections import deque
import ast
import asyncio
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
import json
import operator
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Annotated, Any, Literal, Mapping, Protocol, TypeVar, runtime_checkable

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import set_config_context
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.func import task
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, TypeAdapter, ValidationError, field_serializer, model_validator
from typing_extensions import TypedDict

Mode = Literal["answer", "learn"]
Language = Literal["fa", "en"]
LearnerLevel = Literal["beginner", "intermediate", "advanced"]
DeliveryMode = Literal["full", "step"]
EvidenceStatus = Literal["success", "empty", "skipped", "error"]
VerificationStatus = Literal["verified", "rejected", "unknown", "unsupported"]
UserAction = Literal["next", "followup", "simplify", "full", "done"]
LEVEL_LABELS = {"beginner": "مبتدی", "intermediate": "متوسط", "advanced": "پیشرفته"}
PROJECT_ROOT = Path(__file__).resolve().parent


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, hide_input_in_errors=True, validate_default=True)


class Limits(Contract):
    max_input_chars: int = Field(default=16000, ge=128, le=100000)
    max_expression_nodes: int = Field(default=256, ge=1, le=2000)
    max_expression_depth: int = Field(default=24, ge=1, le=64)
    max_matrix_dimension: int = Field(default=8, ge=1, le=32)
    math_timeout_seconds: float = Field(default=5.0, gt=0, le=60, allow_inf_nan=False)
    request_timeout_seconds: float = Field(default=20.0, gt=0, le=120, allow_inf_nan=False)
    max_evidence_records: int = Field(default=8, ge=1, le=32)
    max_evidence_chars: int = Field(default=24000, ge=256, le=100000)
    max_history_messages: int = Field(default=24, ge=2, le=100)
    max_clarifications: int = Field(default=2, ge=1, le=3)
    malformed_output_repairs: int = Field(default=1, ge=0, le=1)
    writer_repairs: int = Field(default=2, ge=0, le=2)
    max_number_digits: int = Field(default=32, ge=1, le=128)
    max_power_magnitude: int = Field(default=1000, ge=1, le=10000)
    max_output_chars: int = Field(default=6000, ge=128, le=20000)


class Preferences(Contract):
    mode: Mode = "answer"
    language: Language = "fa"
    learner_level: LearnerLevel | None = None
    delivery_mode: DeliveryMode = "full"


class AppConfig(Contract):
    provider: Literal["openai"] = "openai"
    model: str | None = Field(default=None, min_length=1, max_length=128)
    model_base_url: str = "https://api.openai.com/v1"
    keys_from_dotenv: bool = False
    preferences: Preferences = Field(default_factory=Preferences)
    limits: Limits = Field(default_factory=Limits)
    sources_dir: Path = PROJECT_ROOT / "sources"
    search_enabled: bool = False
    search_backend: Literal["tavily", "avalai_tavily"] = "tavily"
    search_url: str | None = None
    generated_examples_enabled: bool = False
    semantic_enabled: bool = True
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_revision: str = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
    embedding_dimension: int = Field(default=384, ge=1, le=4096)
    embedding_max_tokens: int = Field(default=512, ge=32, le=8192)
    embedding_cache_dir: Path = PROJECT_ROOT / ".cache" / "retrieval"
    embedding_model_dir: Path | None = None

    @model_validator(mode="after")
    def valid_service_urls(self):
        from urllib.parse import urlsplit
        for value in [self.model_base_url, self.search_url]:
            if value is None:
                continue
            TypeAdapter(HttpUrl).validate_python(value)
            parts = urlsplit(value)
            if parts.scheme != "https" or parts.username or parts.password or parts.query or parts.fragment:
                raise ValueError("Service URLs must be HTTPS without credentials, query or fragment")
        return self


class Credentials(Contract):
    # Never add credentials to TutorState. Both serialization and repr omit them.
    openai_api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    search_api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)


class ConfigurationError(ValueError):
    """Safe human-readable configuration error."""


@lru_cache(maxsize=None)
def load_dotenv_once(path: Path) -> None:
    from dotenv import load_dotenv
    load_dotenv(path, override=False)


def load_config(*, env: Mapping[str, str] | None = None, dotenv_path: Path | None = None) -> tuple[AppConfig, Credentials]:
    """Explicit startup only; injectable env keeps offline checks independent."""
    use_local_credentials = env is None
    local_env_path = (dotenv_path or PROJECT_ROOT / ".env").resolve()
    if env is None:
        load_dotenv_once(local_env_path)
        env = os.environ
    values: dict[str, Any] = {}
    for key, field in [("TUTOR_PROVIDER", "provider"), ("TUTOR_MODEL", "model"), ("TUTOR_SOURCES_DIR", "sources_dir"), ("TUTOR_SEARCH_ENABLED", "search_enabled"), ("TUTOR_GENERATED_EXAMPLES_ENABLED", "generated_examples_enabled"),
                       ("TUTOR_SEARCH_BACKEND", "search_backend"),
                       ("TUTOR_MODEL_BASE_URL", "model_base_url"), ("TUTOR_SEARCH_URL", "search_url"),
                       ("TUTOR_KEYS_FROM_DOTENV", "keys_from_dotenv"),
                       *(("TUTOR_" + field.upper(), field) for field in ["semantic_enabled", "embedding_model", "embedding_revision", "embedding_dimension", "embedding_max_tokens", "embedding_cache_dir", "embedding_model_dir"])]:
        if env.get(key, "").strip():
            values[field] = env[key].strip()
    values["preferences"] = {field: env[key].strip() for key, field in [("TUTOR_MODE", "mode"), ("TUTOR_LANGUAGE", "language"), ("TUTOR_LEVEL", "learner_level"), ("TUTOR_DELIVERY", "delivery_mode")] if env.get(key, "").strip()}
    values["limits"] = {name: env[key].strip() for name in Limits.model_fields if env.get(key := "TUTOR_" + name.upper(), "").strip()}
    try:
        config = AppConfig.model_validate(values)
    except ValidationError as exc:
        locations = ", ".join(".".join(map(str, error["loc"])) for error in exc.errors(include_input=False))
        raise ConfigurationError(f"Invalid configuration fields: {locations}. Check .env or environment variables.") from None
    if not config.sources_dir.is_absolute():
        config.sources_dir = (PROJECT_ROOT / config.sources_dir).resolve()
    for field in ["embedding_cache_dir", "embedding_model_dir"]:
        value = getattr(config, field)
        if value is not None and not value.is_absolute():
            setattr(config, field, (PROJECT_ROOT / value).resolve())
    from urllib.parse import urlsplit
    credential_env = dict(env)
    if use_local_credentials and config.keys_from_dotenv:
        from dotenv import dotenv_values
        credential_env.update({key: value for key, value in dotenv_values(local_env_path).items()
                               if key in {"OPENAI_API_KEY", "AVALAI_API_KEY", "TUTOR_SEARCH_API_KEY"} and value and value.strip()})
    model_key = credential_env.get("OPENAI_API_KEY", "").strip()
    if urlsplit(config.model_base_url).hostname in {"api.avalai.ir", "api.avalai.org"}:
        model_key = credential_env.get("AVALAI_API_KEY", "").strip() or model_key
    credentials = Credentials(openai_api_key=model_key or None, search_api_key=credential_env.get("TUTOR_SEARCH_API_KEY", "").strip() or None)
    return config, credentials


class RoutingOutput(Contract):
    mode: Mode
    topic: str = Field(min_length=1, max_length=128)
    language: Language
    learner_level: LearnerLevel | None = None
    delivery_mode: DeliveryMode = "full"


class Request(Contract):
    query: str = Field(min_length=1, max_length=100000)
    topic: str | None = Field(default=None, min_length=1, max_length=128)
    mode: Mode | None = None
    language: Language | None = None
    learner_level: LearnerLevel | None = None
    delivery_mode: DeliveryMode | None = None


class Expression(Contract):
    """Allowlisted expression AST, not executable Python or a SymPy input string."""
    op: Literal["number", "symbol", "constant", "add", "sub", "mul", "div", "pow", "neg", "sin", "cos", "tan", "exp", "log", "sqrt", "abs"]
    value: str | None = Field(default=None, max_length=128)
    args: list[Expression] = Field(default_factory=list, max_length=256)

    @model_validator(mode="after")
    def valid_shape(self):
        if self.op in {"number", "symbol", "constant"}:
            if self.args or self.value is None:
                raise ValueError("Leaf expressions require a value and no operands")
            if self.op == "number":
                if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d{1,3})?", self.value):
                    raise ValueError("Number must be a finite decimal literal")
                if not Decimal(self.value).is_finite():
                    raise ValueError("Number must be finite")
            elif self.op == "symbol":
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", self.value) or "__" in self.value:
                    raise ValueError("Invalid symbol name")
            elif self.value not in {"pi", "E", "oo", "-oo"}:
                raise ValueError("Unknown mathematical constant")
        else:
            if self.value is not None:
                raise ValueError("Operator expressions cannot carry a literal value")
            count = len(self.args)
            expected = 2 if self.op in {"sub", "div", "pow"} else 1
            if self.op in {"add", "mul"}:
                if count < 2:
                    raise ValueError("Addition/multiplication requires at least two operands")
            elif count != expected:
                raise ValueError("Incorrect operator operand count")
        return self


class ScalarProblem(Contract):
    expression: Expression
    variable: str = Field(default="x", pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
    domain: Literal["real", "complex"] = "real"
    assumptions: list[str] = Field(default_factory=list, max_length=16)


class DifferentiateProblem(ScalarProblem):
    operation: Literal["differentiate"]
    order: int = Field(default=1, ge=1, le=10, strict=True)


class IntegrateProblem(ScalarProblem):
    operation: Literal["integrate"]
    lower: Expression | None = None
    upper: Expression | None = None

    @model_validator(mode="after")
    def paired_bounds(self):
        if (self.lower is None) != (self.upper is None):
            raise ValueError("Definite integration requires both bounds")
        return self


class LimitProblem(ScalarProblem):
    operation: Literal["limit"]
    point: Expression
    direction: Literal["left", "right", "both"] = "both"


class SolveProblem(Contract):
    operation: Literal["solve"]
    lhs: Expression
    rhs: Expression
    variable: str = Field(default="x", pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
    domain: Literal["real", "complex"] = "real"
    assumptions: list[str] = Field(default_factory=list, max_length=16)


class MatrixProblem(Contract):
    operation: Literal["matrix"]
    action: Literal["determinant", "inverse", "rank", "transpose", "multiply"]
    matrix: list[list[Expression]] = Field(min_length=1, max_length=32)
    other: list[list[Expression]] | None = None

    @model_validator(mode="after")
    def compatible_dimensions(self):
        for matrix in [self.matrix] + ([self.other] if self.other is not None else []):
            if not matrix or not matrix[0] or any(len(row) != len(matrix[0]) for row in matrix):
                raise ValueError("Matrices must be nonempty and rectangular")
        if self.action in {"determinant", "inverse"} and len(self.matrix) != len(self.matrix[0]):
            raise ValueError("This operation requires a square matrix")
        if self.action == "multiply":
            if self.other is None or len(self.matrix[0]) != len(self.other):
                raise ValueError("Matrix multiplication dimensions are incompatible")
        elif self.other is not None:
            raise ValueError("A second matrix is only valid for multiplication")
        return self


class SimplifyProblem(ScalarProblem):
    operation: Literal["simplify"]


Problem = Annotated[DifferentiateProblem | IntegrateProblem | LimitProblem | SolveProblem | MatrixProblem | SimplifyProblem, Field(discriminator="operation")]
PROBLEM_ADAPTER = TypeAdapter(Problem)


def validate_problem(payload: Any, limits: Limits | None = None) -> Problem:
    """Bound untrusted structures before recursive model construction."""
    limits = limits or Limits()
    if isinstance(payload, BaseModel):
        payload = payload.model_dump()
    def model_json(value):
        if isinstance(value, BaseModel):
            return value.model_dump()
        raise TypeError("Not a JSON payload")
    try:
        encoded = json.dumps(payload, allow_nan=False, default=model_json)
        payload = json.loads(encoded)
    except (TypeError, ValueError, RecursionError):
        raise ValueError("Problem must be a finite JSON-compatible payload") from None
    if len(encoded) > limits.max_input_chars:
        raise ValueError("Problem exceeds input size limit")
    pending = deque([(payload, 0)])
    nodes = 0
    while pending:
        item, depth = pending.pop()
        if isinstance(item, dict):
            expression = "op" in item
            next_depth = depth + int(expression)
            if expression:
                nodes += 1
                if nodes > limits.max_expression_nodes or next_depth > limits.max_expression_depth:
                    raise ValueError("Expression exceeds node/depth limits")
            pending.extend((value, next_depth) for value in item.values() if isinstance(value, (list, dict)))
        elif isinstance(item, list):
            pending.extend((value, depth) for value in item if isinstance(value, (list, dict)))
    problem = PROBLEM_ADAPTER.validate_python(payload)
    if isinstance(problem, MatrixProblem):
        for matrix in [problem.matrix] + ([problem.other] if problem.other is not None else []):
            if max(len(matrix), len(matrix[0])) > limits.max_matrix_dimension:
                raise ValueError("Matrix exceeds configured dimension limit")
    return problem


class MathResult(Contract):
    status: Literal["solved", "unevaluated", "unsupported", "error", "timeout"]
    result: str | None = None
    conditions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    integration_constant_required: bool = False
    warning: str | None = None

    @model_validator(mode="after")
    def consistent_result(self):
        if self.status == "solved" and not self.result:
            raise ValueError("Solved mathematics requires an explicit result")
        if self.status in {"error", "timeout", "unsupported"} and not self.warning:
            raise ValueError("Unsuccessful mathematics requires a readable warning")
        return self


class Provenance(Contract):
    source_url: HttpUrl
    section_title: str = Field(min_length=1)
    source_author: str = Field(min_length=1)
    retrieved_at: datetime
    usage_terms_url: HttpUrl
    usage_terms: str = Field(min_length=1)

    @field_serializer("source_url", "usage_terms_url")
    def serialize_url(self, value):
        # JsonPlus checkpoints cannot encode Pydantic's HttpUrl objects directly.
        # Keep URL validation on load while storing portable string values.
        return str(value)


class SourceRecord(Contract):
    id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    subtopic: str | None = None
    learner_level: LearnerLevel | None = None
    text: str = Field(min_length=1)
    provenance: Provenance
    evidence_origin: Literal["local", "web_snippet"] = "local"
    parent_id: str | None = None
    previous_chunk_id: str | None = None
    next_chunk_id: str | None = None


class ExampleRecord(Contract):
    id: str = Field(min_length=1)
    example_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    subtopic: str = Field(min_length=1)
    course: str = Field(min_length=1)
    learner_level: LearnerLevel
    statement: str = Field(min_length=1)
    solution: str = Field(min_length=1)
    source_example_label: str = Field(min_length=1)
    provenance: Provenance
    origin: Literal["paul", "original"] = "paul"
    operation_payload: Problem | None = None
    proposed_result: str | None = None
    verification_status: VerificationStatus = "unknown"
    verification_method: str | None = None
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def verification_is_explicit(self):
        if self.verification_status in {"verified", "rejected"} and not self.verification_method:
            raise ValueError("A verification decision requires its method")
        return self


class TeachingRule(Contract):
    id: str
    text: str = Field(min_length=1)
    learner_levels: list[LearnerLevel] = Field(min_length=1)


class WebRecord(Contract):
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_url: HttpUrl
    retrieved_at: datetime

    @field_serializer("source_url")
    def serialize_url(self, value):
        return str(value)


class EvidenceResult(Contract):
    status: EvidenceStatus
    records: list[SourceRecord | ExampleRecord | TeachingRule | WebRecord] = Field(default_factory=list, max_length=32)
    warning: str | None = None
    retrieval_method: Literal["local", "keyword", "semantic", "web", "fake", "none"] = "none"
    broader_search: bool = False

    @model_validator(mode="after")
    def consistent_status(self):
        if (self.status == "success") != bool(self.records):
            raise ValueError("Success requires records; empty/skipped/error must not carry records")
        if self.status == "error" and not self.warning:
            raise ValueError("Error evidence requires a readable warning")
        return self


class EvidenceRequest(Contract):
    query: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    learner_level: LearnerLevel
    language: Language
    subtopic: str | None = None
    max_records: int = Field(default=8, ge=1, le=32)
    max_chars: int = Field(default=24000, ge=256, le=100000)


class LessonStep(Contract):
    id: str
    objective: str = Field(min_length=1)
    kind: Literal["concept", "method", "example", "check"] = "concept"
    text: str = Field(default="", max_length=20000)
    source_ids: list[str] = Field(default_factory=list, max_length=32)


class TraceEvent(Contract):
    node: Literal["classify", "answer", "math_tool", "write_answer", "learn", "read_source", "verified_examples", "teaching_bestpractices", "web_search", "write_explanation", "user_input"]
    status: Literal["started", "success", "empty", "skipped", "error", "interrupted"]


class TutorState(TypedDict, total=False):
    mode: Mode
    query: str
    topic: str | None
    language: Language
    learner_level: LearnerLevel | None
    delivery_mode: DeliveryMode
    messages: Annotated[list[BaseMessage], add_messages]
    problem: Problem | None
    math_result: MathResult | None
    source: EvidenceResult | None
    examples: EvidenceResult | None
    teaching_tips: EvidenceResult | None
    websearch: EvidenceResult | None
    explanation: str
    final_answer: str
    lesson_plan: list[LessonStep]
    step_index: int
    last_emitted_step: int | None
    user_decision: Literal["moreQ", "done"] | None
    user_action: UserAction | None
    followup_query: str | None
    evidence_request: dict[str, Any]
    lesson_objective: str
    explanation_version: int
    selected_example_id: str | None
    new_topic_query: str | None
    current_step_explanation: str
    lesson_complete: bool
    clarification_count: int
    repair_count: int
    warnings: Annotated[list[str], operator.add]
    execution_trace: Annotated[list[TraceEvent], operator.add]


def new_request_state(request: Request, config: AppConfig, history: list[BaseMessage] | None = None) -> TutorState:
    """Fresh graph invocation state; caller must use a new/finished thread boundary."""
    if len(request.query) > config.limits.max_input_chars:
        raise ValueError("Request exceeds input size limit")
    preferences = config.preferences.model_dump()
    preferences.update({key: value for key, value in request.model_dump().items() if key in preferences and value is not None})
    if request.mode is None and re.search(r"(?i)\bstep(?:-by-| by )step\b|گام[‌ -]به[‌ -]گام|مرحله[‌ -]به[‌ -]مرحله", request.query):
        preferences["mode"] = "learn"
        if request.delivery_mode is None:
            preferences["delivery_mode"] = "step"
    messages = list(history or [])[-(config.limits.max_history_messages - 1):]
    messages.append(HumanMessage(content=request.query))
    return TutorState(**preferences, query=request.query, topic=request.topic, messages=messages,
                      problem=None, math_result=None, source=None, examples=None, teaching_tips=None, websearch=None,
                      explanation="", final_answer="", lesson_plan=[], step_index=0, last_emitted_step=None,
                      user_decision=None, user_action=None, followup_query=None, clarification_count=0,
                      repair_count=0, warnings=[], execution_trace=[], evidence_request={},
                      lesson_objective="", explanation_version=0, selected_example_id=None, new_topic_query=None,
                      current_step_explanation="", lesson_complete=False)


Schema = TypeVar("Schema", bound=BaseModel)


@runtime_checkable
class ModelClient(Protocol):
    async def structured(self, messages: list[BaseMessage], schema: type[Schema]) -> Schema: ...
    async def text(self, messages: list[BaseMessage]) -> str: ...


@runtime_checkable
class SearchClient(Protocol):
    async def search(self, request: EvidenceRequest) -> EvidenceResult: ...


@runtime_checkable
class RetrievalClient(Protocol):
    async def read_source(self, request: EvidenceRequest) -> EvidenceResult: ...
    async def verified_examples(self, request: EvidenceRequest) -> EvidenceResult: ...
    async def teaching_bestpractices(self, request: EvidenceRequest) -> EvidenceResult: ...


class OpenAIModelClient:
    """Lazy injectable provider adapter; construction makes no model request."""
    def __init__(self, config: AppConfig, credentials: Credentials):
        if credentials.openai_api_key is None:
            raise ConfigurationError("OPENAI_API_KEY is missing. Set it in the environment or local .env.")
        if config.model is None:
            raise ConfigurationError("TUTOR_MODEL is missing. Set an available OpenAI model ID before live use.")
        from langchain_openai import ChatOpenAI
        self._client = ChatOpenAI(model=config.model, api_key=credentials.openai_api_key,
                                  base_url=config.model_base_url, timeout=config.limits.request_timeout_seconds, max_retries=0)

    async def structured(self, messages: list[BaseMessage], schema: type[Schema]) -> Schema:
        result = await self._client.with_structured_output(schema).ainvoke(messages)
        return schema.model_validate(result)

    async def text(self, messages: list[BaseMessage]) -> str:
        result = await self._client.ainvoke(messages)
        if not isinstance(result.content, str):
            raise ValueError("Expected a text model response")
        return result.content


# Declarative architecture contract only. These constants do not schedule anything.
RESOURCE_NODES = ("read_source", "verified_examples", "teaching_bestpractices", "web_search")
NODE_NAMES = ("classify", "answer", "math_tool", "write_answer", "learn", *RESOURCE_NODES, "write_explanation", "user_input")
FIXED_EDGES = ((START, "classify"), ("answer", "math_tool"), ("math_tool", "write_answer"),
               ("write_answer", END), *(("learn", name) for name in RESOURCE_NODES), ("write_explanation", "user_input"))
CONDITIONAL_EDGES = {"classify": {"answer": "answer", "learn": "learn"}, "user_input": {"moreQ": "write_explanation", "done": END}}
RESOURCE_BARRIER = (RESOURCE_NODES, "write_explanation")
EVIDENCE_OWNERS = {"read_source": "source", "verified_examples": "examples", "teaching_bestpractices": "teaching_tips", "web_search": "websearch"}


class NeedsClarification(ValueError):
    pass


class UnsupportedRequest(ValueError):
    pass


def parse_expression(text: str, limits: Limits | None = None) -> Expression:
    """Tokenize a tiny math grammar, then inspect Python AST; never evaluate it."""
    limits = limits or Limits()
    if not text.strip():
        raise NeedsClarification("Supply the missing mathematical expression.")
    if len(text) > limits.max_input_chars:
        raise ValueError("Expression exceeds input size limit")
    text = text.strip().replace("^", "**")
    tokens = re.findall(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[A-Za-z_][A-Za-z_0-9]*|\*\*|[+*/(),-]|\S", text)
    allowed = re.compile(r"^(?:\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[A-Za-z_][A-Za-z_0-9]*|\*\*|[+*/(),-])$")
    if len(tokens) > limits.max_expression_nodes * 4 or any(not allowed.fullmatch(t) for t in tokens):
        raise ValueError("Unsupported characters or excessive expression size")
    functions = {"sin", "cos", "tan", "exp", "log", "sqrt", "abs"}
    forbidden_names = {"eval", "exec", "compile", "open", "globals", "locals", "getattr", "setattr", "lambda", "import", "os", "sys"}
    if any(t in forbidden_names or "__" in t for t in tokens):
        raise ValueError("Code-like identifiers are unsupported")
    normalized = []
    for index, token in enumerate(tokens):
        if index:
            previous = tokens[index - 1]
            left_value = previous == ")" or previous[0].isalnum() or previous[0] == "_"
            right_value = token == "(" or token[0].isalnum() or token[0] == "_"
            if left_value and right_value and not (previous in functions and token == "("):
                normalized.append("*")
        normalized.append(token)
    source = "".join(normalized)
    try:
        tree = ast.parse(source, mode="eval")
    except (SyntaxError, RecursionError):
        raise ValueError("Malformed mathematical expression") from None
    operations = {ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul", ast.Div: "div", ast.Pow: "pow"}

    def convert(node, depth=1):
        if depth > limits.max_expression_depth:
            raise ValueError("Expression exceeds depth limit")
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            return {"op": "number", "value": ast.get_source_segment(source, node)}
        if isinstance(node, ast.Name):
            if node.id in functions:
                raise ValueError("Function arguments must be in parentheses")
            return {"op": "constant" if node.id in {"pi", "E", "oo"} else "symbol", "value": node.id}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            operand = convert(node.operand, depth + 1)
            return {"op": "neg", "args": [operand]} if isinstance(node.op, ast.USub) else operand
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return {"op": operations[type(node.op)], "args": [convert(node.left, depth + 1), convert(node.right, depth + 1)]}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions and len(node.args) == 1 and not node.keywords:
            return {"op": node.func.id, "args": [convert(node.args[0], depth + 1)]}
        raise ValueError("Only allowlisted scalar mathematics is supported")

    expression = convert(tree.body)
    return validate_problem({"operation": "simplify", "expression": expression}, limits).expression


def parse_request(query: str, limits: Limits | None = None) -> Problem:
    """Offline syntax: equations and explicit diff/integrate/limit/matrix/simplify."""
    limits = limits or Limits()
    if len(query) > limits.max_input_chars:
        raise ValueError("Request exceeds input size limit")
    query = query.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")).strip()
    # Recognize a narrow conversational envelope; the remaining expression
    # still goes through the same allowlisted AST and safety limits.
    wrapped = re.fullmatch(r"(?is)(?:can you|could you|please)?\s*(?:help me with|solve)\s+(.+)", query)
    if wrapped:
        query = wrapped[1].strip()
    query = re.sub(r"(?i)\s+step(?:-by-| by )step\s*\??$", "", query).strip()
    if wrapped:
        query = query.removesuffix("?").strip()
    if query.startswith("{"):
        return validate_problem(json.loads(query), limits)
    variable = "x"
    match = re.search(r"\s+wrt\s+([A-Za-z][A-Za-z0-9_]*)$", query)
    if match:
        variable = match[1]
        query = query[:match.start()].strip()
    operation, _, body = query.partition(" ")
    aliases = {"diff": "differentiate", "derivative": "differentiate", "differentiate": "differentiate", "مشتق": "differentiate", "integrate": "integrate", "integral": "integrate", "انتگرال": "integrate", "limit": "limit", "حد": "limit", "solve": "solve", "حل": "solve", "simplify": "simplify", "ساده": "simplify", "matrix": "matrix"}
    kind = aliases.get(operation.lower())
    if kind is None and "=" in query:
        kind, body = "solve", query
    if kind is None:
        raise UnsupportedRequest("Use solve, diff, integrate, limit, matrix or simplify syntax, or configure a model for natural-language extraction.")
    if not body.strip():
        raise NeedsClarification(f"Supply the complete {kind} request.")
    payload = {"operation": kind, "variable": variable}
    if kind == "solve":
        if body.count("=") != 1:
            raise NeedsClarification("Supply one equation with both sides, such as 2x+5=17.")
        left, right = body.split("=", 1)
        payload.update(lhs=parse_expression(left, limits), rhs=parse_expression(right, limits))
    elif kind == "matrix":
        action, _, entries = body.partition(" ")
        if not entries:
            raise NeedsClarification("Supply a matrix action and JSON rows, such as matrix inverse [[1,2],[3,4]].")
        values = json.loads(entries, parse_int=str, parse_float=str)
        if not isinstance(values, list) or not values or len(values) > limits.max_matrix_dimension:
            raise ValueError("Invalid or oversized matrix")
        rows = []
        for row in values:
            if not isinstance(row, list) or not row or len(row) > limits.max_matrix_dimension:
                raise ValueError("Invalid or oversized matrix rows")
            if any(not isinstance(value, str) or not re.fullmatch(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", value) for value in row):
                raise ValueError("Local matrix syntax accepts numeric JSON entries only")
            rows.append([Expression(op="number", value=value) for value in row])
        payload = {"operation": "matrix", "action": action, "matrix": rows}
    elif kind == "limit":
        match = re.fullmatch(r"(.+?)\s+at\s+(.+?)(?:\s+(left|right|both))?", body)
        if not match:
            raise NeedsClarification("Supply the limit point, such as limit sin(x)/x at 0 both.")
        payload.update(expression=parse_expression(match[1], limits), point=parse_expression(match[2], limits), direction=match[3] or "both")
    else:
        expression = body
        if kind == "integrate":
            match = re.fullmatch(r"(.+?)\s+from\s+(.+?)\s+to\s+(.+)", body)
            if match:
                expression = match[1]
                payload.update(lower=parse_expression(match[2], limits), upper=parse_expression(match[3], limits))
            elif re.search(r"\s+(from|to)\s+", body):
                raise NeedsClarification("Supply both integration bounds: integrate x from 0 to 1.")
        payload["expression"] = parse_expression(expression, limits)
    return validate_problem(payload, limits)


def _compute_math(payload, limits: Limits) -> MathResult:
    """Runs exclusively in the spawned, killable worker in production."""
    import sympy as sp
    from sympy.calculus.util import continuous_domain
    problem = validate_problem(payload, limits)
    if getattr(problem, "assumptions", []):
        return MathResult(status="unsupported", warning="Free-text assumptions are not interpreted. Use the explicit real/complex domain instead.")
    domain = getattr(problem, "domain", "real")
    symbols = {}
    nonzero = []

    def symbol(name):
        if name not in symbols:
            symbols[name] = sp.Symbol(name, real=True) if domain == "real" else sp.Symbol(name)
        return symbols[name]

    def build(node):
        if node.op == "number":
            decimal = Decimal(node.value)
            if len(decimal.as_tuple().digits) > limits.max_number_digits or abs(decimal.adjusted()) > limits.max_number_digits:
                raise ValueError("Numeric literal exceeds configured magnitude/digit limits")
            numerator, denominator = decimal.as_integer_ratio()
            return sp.Rational(numerator, denominator)
        if node.op == "symbol":
            return symbol(node.value)
        if node.op == "constant":
            return {"pi": sp.pi, "E": sp.E, "oo": sp.oo, "-oo": -sp.oo}[node.value]
        args = [build(child) for child in node.args]
        if node.op == "add": return sp.Add(*args, evaluate=False)
        if node.op == "sub": return sp.Add(args[0], sp.Mul(-1, args[1], evaluate=False), evaluate=False)
        if node.op == "mul": return sp.Mul(*args, evaluate=False)
        if node.op == "neg": return sp.Mul(-1, args[0], evaluate=False)
        if node.op == "div":
            if sp.simplify(args[1]) == 0:
                raise ValueError("Division by zero")
            nonzero.append(args[1])
            return sp.Mul(args[0], sp.Pow(args[1], -1, evaluate=False), evaluate=False)
        if node.op == "pow":
            # Reject tower expressions before evaluation can create enormous integers.
            if node.args[1].op not in {"number", "symbol", "neg"} or (node.args[1].op == "neg" and node.args[1].args[0].op != "number"):
                raise ValueError("Compound power exponents are unsupported for bounded execution")
            if args[1].is_number and (args[1].is_finite is not True or abs(args[1]) > limits.max_power_magnitude):
                raise ValueError("Power exponent exceeds configured magnitude limit")
            if args[1].is_negative:
                nonzero.append(args[0])
            return sp.Pow(*args, evaluate=False)
        function = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp, "log": sp.log, "sqrt": sp.sqrt, "abs": sp.Abs}[node.op]
        return function(args[0], evaluate=False)

    conditions = []

    def defined_domain(expressions, variable):
        result = sp.S.Reals if domain == "real" else sp.S.Complexes
        if domain == "real":
            for expression in expressions:
                result = result.intersect(continuous_domain(expression, variable, sp.S.Reals))
        for denominator in nonzero:
            result = result - sp.solveset(denominator, variable, domain=result)
        return result

    def domain_condition(allowed, variable):
        if domain == "real" and allowed != sp.S.Reals:
            try:
                conditions.append(str(allowed.as_relational(variable)))
            except (AttributeError, NotImplementedError):
                conditions.append(f"{variable} in {allowed}")

    if isinstance(problem, MatrixProblem):
        matrix = sp.Matrix([[build(cell) for cell in row] for row in problem.matrix])
        if problem.action == "inverse":
            determinant = sp.simplify(matrix.det())
            if determinant == 0:
                return MathResult(status="error", warning="Matrix is singular; inverse does not exist.")
            if determinant.is_zero is None:
                conditions.append(f"{determinant} != 0")
            result = matrix.inv()
        elif problem.action == "multiply":
            other = sp.Matrix([[build(cell) for cell in row] for row in problem.other])
            result = matrix * other
        else:
            result = {"determinant": matrix.det, "rank": matrix.rank, "transpose": matrix.transpose}[problem.action]()
        return MathResult(status="solved", result=str(result), conditions=conditions, exclusions=list(dict.fromkeys(f"{value} != 0" for value in nonzero)))

    variable = symbol(problem.variable)
    expressions = [build(problem.lhs), build(problem.rhs)] if isinstance(problem, SolveProblem) else [build(problem.expression)]
    allowed = defined_domain(expressions, variable)
    if domain == "complex" and any(expression.has(sp.log) for expression in expressions):
        conditions.append("principal complex logarithm branch")
    if domain == "real" and any(expression.is_real is False for expression in expressions):
        return MathResult(status="unsupported", warning="Expression is not real-valued in the requested domain.")
    exclusions = list(dict.fromkeys(f"{value} != 0" for value in nonzero))
    expression = expressions[0]
    constant_required = False
    if isinstance(problem, SolveProblem):
        result = sp.solveset(expressions[0] - expressions[1], variable, domain=allowed)
        if result.has(sp.ConditionSet):
            return MathResult(status="unevaluated", result=str(result), exclusions=exclusions, warning="Solution set remains conditional; completeness is not established.")
        if isinstance(result, sp.FiniteSet):
            if any(sp.simplify((expressions[0] - expressions[1]).subs(variable, root)) != 0 for root in result):
                return MathResult(status="unevaluated", result=str(result), exclusions=exclusions, warning="Root verification was inconclusive.")
            result = f"{variable}={next(iter(result))}" if len(result) == 1 else f"{variable} in {result}"
        else:
            result = f"{variable} in {result}"
    elif isinstance(problem, LimitProblem):
        point = build(problem.point)
        if point.free_symbols:
            return MathResult(status="unsupported", warning="A concrete limit point is required.")
        directions = ["left", "right"] if problem.direction == "both" and point not in {sp.oo, -sp.oo} else [problem.direction]
        values = []
        for direction in directions:
            if domain == "real" and point not in {sp.oo, -sp.oo}:
                neighborhood = sp.Interval.open(-sp.oo, point) if direction == "left" else sp.Interval.open(point, sp.oo)
                if allowed.intersect(neighborhood).closure.contains(point) is not sp.S.true:
                    return MathResult(status="unsupported", warning=f"No {direction} approach in the real domain; specify an available one-sided limit.")
            values.append(sp.limit(expression, variable, point, dir="-" if direction == "left" else "+"))
        if len(values) == 2 and values[0] != values[1]:
            difference = sp.simplify(values[0] - values[1])
            if difference == 0:
                result = values[0]
            elif difference.is_zero is False:
                return MathResult(status="solved", result=f"Limit does not exist (left={values[0]}, right={values[1]}).")
            else:
                return MathResult(status="unevaluated", result=f"left={values[0]}, right={values[1]}", warning="Equality of the one-sided limits is unresolved.")
        else:
            result = values[0]
        if problem.direction != "both" and point not in {sp.oo, -sp.oo}:
            conditions.append(f"{variable} -> {point} from the {problem.direction}")
    elif isinstance(problem, DifferentiateProblem):
        result = sp.diff(expression, variable, problem.order)
        domain_condition(allowed.intersect(continuous_domain(result, variable, sp.S.Reals)) if domain == "real" else allowed, variable)
        if domain == "real":
            for absolute in expression.atoms(sp.Abs):
                conditions.append(f"{absolute.args[0]} != 0 (away from possible absolute-value corners)")
    elif isinstance(problem, IntegrateProblem):
        if problem.lower is None:
            result = sp.integrate(expression, variable)
            if not result.has(sp.Integral) and sp.simplify(sp.diff(result, variable) - expression) != 0:
                return MathResult(status="unevaluated", result=str(result), warning="Antiderivative verification was inconclusive.")
            constant_required = not result.has(sp.Integral)
            if domain == "real" and not result.has(sp.Integral):
                allowed = allowed.intersect(continuous_domain(result, variable, sp.S.Reals))
            domain_condition(allowed, variable)
        else:
            lower, upper = build(problem.lower), build(problem.upper)
            if lower.free_symbols or upper.free_symbols:
                return MathResult(status="unsupported", warning="Concrete integration bounds are required in this phase.")
            if domain == "real" and lower != upper:
                interval = sp.Interval.open(sp.Min(lower, upper), sp.Max(lower, upper))
                if interval.is_subset(allowed) is not True:
                    return MathResult(status="unsupported", warning="The integration interval crosses excluded or unresolved domain points; split the improper integral explicitly.")
            result = sp.integrate(expression, (variable, lower, upper))
            if result in {sp.oo, -sp.oo}:
                return MathResult(status="solved", result=f"Integral diverges to {result}.")
    else:
        result = sp.simplify(expression)
        domain_condition(allowed, variable)
    if isinstance(result, sp.Basic):
        if result.has(sp.Integral, sp.Derivative, sp.Limit, sp.ConditionSet):
            return MathResult(status="unevaluated", result=str(result), conditions=conditions, exclusions=exclusions, warning="SymPy left this calculation unevaluated.")
        if result.has(sp.nan, sp.zoo):
            return MathResult(status="error", warning="Calculation is undefined; check its domain.")
    return MathResult(status="solved", result=str(result), conditions=list(dict.fromkeys(conditions)), exclusions=exclusions, integration_constant_required=constant_required)


def _worker_entry():
    try:
        envelope = json.loads(sys.stdin.read(200001))
        limits = Limits.model_validate(envelope["limits"])
        result = _compute_math(envelope["problem"], limits)
        if len(result.model_dump_json()) > limits.max_output_chars:
            result = MathResult(status="unsupported", warning="Calculation output exceeds the configured size limit.")
    except ModuleNotFoundError:
        result = MathResult(status="error", warning="SymPy is missing. Install requirements.txt before calculating.")
    except (ValueError, ValidationError):
        result = MathResult(status="error", warning="Invalid or unsafe mathematics payload; check supported operations and limits.")
    except Exception:
        result = MathResult(status="unevaluated", warning="The symbolic calculation could not be resolved safely.")
    print(result.model_dump_json())


def run_math_worker(problem: Problem, limits: Limits) -> MathResult:
    """A fresh Windows-compatible interpreter, JSON IPC, and killable deadline."""
    try:
        validated = validate_problem(problem, limits)
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--math-worker"],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except (ValueError, OSError):
        return MathResult(status="error", warning="Could not start a validated math worker.")
    try:
        output, _ = process.communicate(json.dumps({"problem": validated.model_dump(), "limits": limits.model_dump()}), timeout=limits.math_timeout_seconds)
        if process.returncode != 0 or len(output) > limits.max_output_chars:
            return MathResult(status="error", warning="Math worker failed or returned oversized output.")
        return MathResult.model_validate_json(output)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        return MathResult(status="timeout", warning="Calculation exceeded its time limit; simplify the request.")
    except (ValueError, ValidationError):
        return MathResult(status="error", warning="Math worker returned an invalid result.")
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


class ExtractionOutput(Contract):
    problem: Problem | None = None
    clarification: str | None = Field(default=None, min_length=1, max_length=400)

    @model_validator(mode="after")
    def one_outcome(self):
        if (self.problem is None) == (self.clarification is None):
            raise ValueError("Return exactly one problem or clarification")
        return self


def format_answer(result: MathResult) -> str:
    if result.status in {"error", "timeout", "unsupported"}:
        return result.warning or "Calculation unavailable."
    text = result.result or "Calculation unresolved."
    if result.status == "unevaluated":
        text = "Unresolved: " + text
    elif result.integration_constant_required:
        text += " + C"
    restrictions = list(dict.fromkeys(result.conditions + result.exclusions))
    if restrictions:
        text += " (" + "; ".join(restrictions) + ")"
    if result.warning:
        text += " " + result.warning
    return text


def build_graph(config: AppConfig, model: ModelClient | None = None, search_client: SearchClient | None = None,
                *, math_runner=run_math_worker, retrieval_client: RetrievalClient | None = None,
                embedding_client=None, resource_workers=None, checkpointer=None):
    """Actual eleven-node graph; resource_workers inject services, never scheduling.

    External services are injected; live search requires explicit configuration.
    """
    from learning import learning_nodes
    from retrieval import SemanticRetrievalClient
    app_config = config
    def trace(name, status="success"):
        return [TraceEvent(node=name, status=status)]

    def failure(message):
        return MathResult(status="error", warning=message)

    @task
    async def extraction(query):
        # Task results are checkpointed; provider calls are not replayed before
        # an answer-node clarification interrupt. This is not a routing node.
        try:
            return {"problem": parse_request(query, config.limits).model_dump()}
        except NeedsClarification as exc:
            return {"clarification": str(exc)}
        except UnsupportedRequest as exc:
            if model is None:
                return {"error": str(exc) + " Set TUTOR_MODEL and OPENAI_API_KEY for natural-language requests."}
        except (ValueError, ValidationError, RecursionError):
            return {"error": "Invalid or unsafe request. Use supported math syntax and configured limits."}
        messages = [SystemMessage(content="Extract only the supported mathematical operation into the allowlisted AST schema. Never return code. Preserve domain, variable and integration bounds. If essential information is missing, return clarification instead of guessing."), HumanMessage(content=query)]
        for attempt in range(config.limits.malformed_output_repairs + 1):
            try:
                response = await asyncio.wait_for(model.structured(messages, ExtractionOutput), timeout=config.limits.request_timeout_seconds)
                response = ExtractionOutput.model_validate(response)
                if response.problem is not None:
                    response.problem = validate_problem(response.problem, config.limits)
                return {**response.model_dump(exclude_none=True), "repair_count": attempt}
            except (ValidationError, ValueError):
                if attempt == config.limits.malformed_output_repairs:
                    return {"error": "Provider returned malformed or unsupported mathematics after the allowed repair attempt.", "repair_count": attempt}
                messages.append(HumanMessage(content="The output did not satisfy the schema or safety limits. Return one valid problem or essential clarification."))
            except Exception:
                return {"error": "Model request failed or timed out. Check provider configuration or use local math syntax."}

    def classify(state: TutorState, config: RunnableConfig):
        try:
            preferences = Preferences.model_validate({key: state[key] for key in Preferences.model_fields if key in state})
            route = RoutingOutput(**preferences.model_dump(), topic=state.get("topic") or "mathematics")
        except ValidationError:
            return {"mode": "answer", "math_result": failure("Invalid mode, topic, language or teaching preference."), "execution_trace": trace("classify", "error")}
        raw_query = state.get("query", "")
        if not isinstance(raw_query, str):
            return {"mode": "answer", "math_result": failure("Request must be text."), "execution_trace": trace("classify", "error")}
        query = raw_query.strip()
        count = 0
        while not query and count < app_config.limits.max_clarifications:
            with set_config_context(config) as context:
                reply = context.run(interrupt, {"kind": "clarification", "prompt": "Enter a mathematical request."})
            query = str(reply).strip()
            count += 1
        update = {**route.model_dump(), "topic": route.topic.lower(), "query": query, "clarification_count": count, "execution_trace": trace("classify")}
        if not query or len(query) > app_config.limits.max_input_chars:
            update["math_result"] = failure("Request is empty or exceeds the configured input limit.")
            update["mode"] = "answer"
        return update

    async def answer(state: TutorState, config: RunnableConfig):
        if state.get("math_result") is not None:
            return {"execution_trace": trace("answer", "skipped")}
        query = state["query"]
        count = state.get("clarification_count", 0)
        while True:
            # Python 3.10 does not propagate runnable context through async tasks.
            # Use the explicit node config for durable task calls and interrupts.
            with set_config_context(config) as context:
                outcome = await context.run(extraction, query)
            if "problem" in outcome:
                return {"problem": validate_problem(outcome["problem"], app_config.limits), "query": query,
                        "clarification_count": count, "repair_count": outcome.get("repair_count", 0), "execution_trace": trace("answer")}
            if "error" in outcome:
                return {"math_result": failure(outcome["error"]), "clarification_count": count, "repair_count": outcome.get("repair_count", 0), "execution_trace": trace("answer", "error")}
            if count >= app_config.limits.max_clarifications:
                return {"math_result": failure("Essential information is still missing after the allowed clarification attempts."), "clarification_count": count, "execution_trace": trace("answer", "error")}
            with set_config_context(config) as context:
                reply = context.run(interrupt, {"kind": "clarification", "prompt": outcome["clarification"] + " Reply with the complete request."})
            query = str(reply).strip()
            count += 1

    async def math_tool(state: TutorState):
        if state.get("math_result") is not None:
            return {"execution_trace": trace("math_tool", "skipped")}
        try:
            result = await asyncio.to_thread(math_runner, state["problem"], config.limits)
            result = MathResult.model_validate(result)
        except Exception:
            result = failure("Math service failed safely. Try a simpler supported request.")
        return {"math_result": result, "execution_trace": trace("math_tool", "success" if result.status == "solved" else "error")}

    def write_answer(state: TutorState):
        result = state.get("math_result") or failure("No mathematical result was produced.")
        return {"final_answer": format_answer(result), "execution_trace": trace("write_answer")}

    builder = StateGraph(TutorState)
    for name, node in [("classify", classify), ("answer", answer), ("math_tool", math_tool), ("write_answer", write_answer)]:
        builder.add_node(name, node)
    retrieval = retrieval_client or SemanticRetrievalClient(app_config, math_runner, embedding_client=embedding_client)
    for name, node in learning_nodes(app_config, model, retrieval, resource_workers, search_client=search_client).items():
        builder.add_node(name, node)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges("classify", lambda state: state["mode"], CONDITIONAL_EDGES["classify"])
    builder.add_edge("answer", "math_tool")
    builder.add_edge("math_tool", "write_answer")
    builder.add_edge("write_answer", END)
    for name in RESOURCE_NODES:
        builder.add_edge("learn", name)
    builder.add_edge(list(RESOURCE_NODES), "write_explanation")
    builder.add_edge("write_explanation", "user_input")
    builder.add_conditional_edges("user_input", lambda state: state["user_decision"], CONDITIONAL_EDGES["user_input"])
    if checkpointer is None:
        allowed = [(cls.__module__, cls.__name__) for cls in [Expression, DifferentiateProblem, IntegrateProblem, LimitProblem, SolveProblem, MatrixProblem, SimplifyProblem, MathResult, TraceEvent, EvidenceResult, SourceRecord, ExampleRecord, TeachingRule, WebRecord, Provenance, LessonStep]]
        checkpointer = InMemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=allowed))
    return builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    if sys.argv[1:] == ["--math-worker"]:
        _worker_entry()
    else:
        raise SystemExit("Run cli.py to use MathTutor.")
