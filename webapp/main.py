"""FastAPI application for the local MathTutor web service (phase W1).

The compiled LangGraph is built exactly once during application startup and
reused for every request. Handlers only validate input, call the service layer
and serialize the result.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import agent

from .errors import (
    ApiError,
    ErrorCode,
    api_error_handler,
    error_payload,
    unhandled_error_handler,
    validation_error_handler,
)
from .schemas import ChatTurnRequest, ChatTurnResponse, HealthResponse, ServiceStatus
from .service import TutorService
from .settings import ServerSettings
from .threads import ThreadRegistry

SERVICE_VERSION = "3.0"


def build_service(
    *,
    settings: ServerSettings,
    config: agent.AppConfig | None = None,
    credentials: agent.Credentials | None = None,
    graph: Any | None = None,
    model: Any | None = None,
    search_client: Any | None = None,
) -> TutorService:
    """Build the graph and service once, honouring the offline switch."""
    from web_search import TavilySearchClient

    if config is None or credentials is None:
        loaded_config, loaded_credentials = agent.load_config()
        config = config or loaded_config
        credentials = credentials or loaded_credentials
    if settings.offline:
        config = config.model_copy(deep=True)
        config.search_enabled = False
        config.semantic_enabled = False
        model = None
    if graph is None:
        if model is None and not settings.offline and config.model:
            model = agent.OpenAIModelClient(config, credentials)
        if search_client is None:
            search_client = TavilySearchClient(config, credentials)
        graph = agent.build_graph(
            config,
            model=model,
            search_client=search_client,
            embedding_credentials=credentials,
        )
    registry = ThreadRegistry(
        max_threads=settings.max_threads,
        idle_seconds=settings.thread_idle_seconds,
    )
    return TutorService(
        config=config,
        graph=graph,
        registry=registry,
        turn_timeout_seconds=settings.turn_timeout_seconds,
    )


def service_status(
    config: agent.AppConfig,
    credentials: agent.Credentials,
    offline: bool,
) -> ServiceStatus:
    """Report configuration presence only. Never reports a credential value."""
    if offline:
        return ServiceStatus(model="disabled", search="disabled", embedding="disabled")
    return ServiceStatus(
        model="configured" if config.model else "missing",
        search="configured" if config.search_enabled and credentials.search_api_key else "missing",
        embedding="configured" if config.semantic_enabled and credentials.embedding_api_key else "missing",
    )


def get_service(request: Request) -> TutorService:
    service = getattr(request.app.state, "service", None)
    if service is None:
        raise ApiError(
            ErrorCode.INTERNAL_ERROR,
            "error.internal",
            detail="The tutor service is not ready.",
        )
    return service


ServiceDep = Annotated[TutorService, Depends(get_service)]

router = APIRouter()


@router.get("/health")
def health(request: Request) -> HealthResponse:
    """Service and configuration status. Makes no external request."""
    state = request.app.state
    config: agent.AppConfig = state.config
    credentials: agent.Credentials = state.credentials
    settings: ServerSettings = state.settings
    stats = state.service.registry.stats() if state.service is not None else {
        "known_threads": 0,
        "active_threads": 0,
    }
    return HealthResponse(
        version=SERVICE_VERSION,
        graph_nodes=list(agent.NODE_NAMES),
        offline=settings.offline,
        services=service_status(config, credentials, settings.offline),
        known_threads=stats["known_threads"],
        active_threads=stats["active_threads"],
    )


@router.post("/api/chat/turn")
async def chat_turn(payload: ChatTurnRequest, service: ServiceDep) -> ChatTurnResponse:
    """Start a new lesson or continue the current one."""
    return await service.turn(payload)


@router.post("/api/chat/resume")
async def chat_resume(payload: ChatTurnRequest, service: ServiceDep) -> ChatTurnResponse:
    """Resume a turn the graph paused at an interrupt."""
    return await service.turn(payload)


def create_app(
    *,
    settings: ServerSettings | None = None,
    config: agent.AppConfig | None = None,
    credentials: agent.Credentials | None = None,
    graph: Any | None = None,
    service: TutorService | None = None,
    model: Any | None = None,
    search_client: Any | None = None,
) -> FastAPI:
    """Build the application. Tests inject ``service`` or ``graph``."""
    resolved_settings = settings or ServerSettings.from_env()
    resolved_config = config
    resolved_credentials = credentials

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal resolved_config, resolved_credentials
        if service is not None:
            app.state.service = service
            app.state.config = service.config
            app.state.credentials = resolved_credentials or agent.Credentials()
        else:
            if resolved_config is None or resolved_credentials is None:
                loaded_config, loaded_credentials = agent.load_config()
                resolved_config = resolved_config or loaded_config
                resolved_credentials = resolved_credentials or loaded_credentials
            app.state.service = build_service(
                settings=resolved_settings,
                config=resolved_config,
                credentials=resolved_credentials,
                graph=graph,
                model=model,
                search_client=search_client,
            )
            app.state.config = resolved_config
            app.state.credentials = resolved_credentials
        app.state.settings = resolved_settings
        yield
        app.state.service = None

    app = FastAPI(
        title="MathTutor local service",
        version=SERVICE_VERSION,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def limit_request_body(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH"}:
            declared = request.headers.get("content-length")
            if declared:
                try:
                    length = int(declared)
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content=error_payload(
                            ErrorCode.BAD_REQUEST,
                            "error.bad_request",
                            "Invalid Content-Length header.",
                        ),
                    )
                if length > resolved_settings.max_request_bytes:
                    return JSONResponse(
                        status_code=413,
                        content=error_payload(
                            ErrorCode.PAYLOAD_TOO_LARGE,
                            "error.payload_too_large",
                            "The request body exceeds the configured limit.",
                        ),
                    )
        return await call_next(request)

    # Added after the body limiter so CORS stays outermost and decorates every
    # response, including a rejected oversized body.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.frontend_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.include_router(router)
    return app


__all__ = ["create_app", "build_service", "service_status", "router"]
