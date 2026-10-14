"""Server-side settings for the local web service.

These are transport concerns only. Model, search, embedding and limit settings
keep coming from ``agent.load_config`` so the existing ``.env`` rules stay the
single source of truth (spec v3.0 section 14.3).
"""
from __future__ import annotations

from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
DEFAULT_FRONTEND_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


class ServerSettingsError(ValueError):
    """Safe, human-readable server configuration error."""


class ServerSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    frontend_origins: tuple[str, ...] = DEFAULT_FRONTEND_ORIGINS
    offline: bool = False
    max_request_bytes: int = Field(default=262_144, ge=1024, le=4_194_304)
    turn_timeout_seconds: float = Field(default=120.0, gt=0, le=600)
    thread_idle_seconds: float = Field(default=21_600.0, gt=0, le=2_592_000)
    max_threads: int = Field(default=200, ge=1, le=10_000)
    allow_nonlocal_bind: bool = False
    session_max_turns: int = Field(default=100, ge=1, le=10000)
    session_max_model_calls: int = Field(default=500, ge=1, le=100000)
    session_max_tokens: int = Field(default=200000, ge=1, le=100000000)
    usage_log_path: str = Field(default='.cache/web/usage.jsonl', min_length=1, max_length=1024)

    @model_validator(mode="after")
    def loopback_binding(self):
        if self.host not in LOOPBACK_HOSTS and not self.allow_nonlocal_bind:
            raise ValueError(
                "The web service binds to loopback only. Set TUTOR_WEB_ALLOW_NONLOCAL_BIND=true "
                "to override deliberately."
            )
        return self

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ServerSettings":
        import os

        source = os.environ if env is None else env
        values: dict[str, object] = {}
        mapping = {
            "TUTOR_WEB_HOST": "host",
            "TUTOR_WEB_PORT": "port",
            "TUTOR_WEB_OFFLINE": "offline",
            "TUTOR_WEB_MAX_REQUEST_BYTES": "max_request_bytes",
            "TUTOR_WEB_TURN_TIMEOUT_SECONDS": "turn_timeout_seconds",
            "TUTOR_WEB_THREAD_IDLE_SECONDS": "thread_idle_seconds",
            "TUTOR_WEB_MAX_THREADS": "max_threads",
            "TUTOR_WEB_ALLOW_NONLOCAL_BIND": "allow_nonlocal_bind",
            "TUTOR_WEB_SESSION_MAX_TURNS": "session_max_turns",
            "TUTOR_WEB_SESSION_MAX_MODEL_CALLS": "session_max_model_calls",
            "TUTOR_WEB_SESSION_MAX_TOKENS": "session_max_tokens",
            "TUTOR_WEB_USAGE_LOG_PATH": "usage_log_path",
        }
        for key, field in mapping.items():
            raw = source.get(key, "")
            if raw is not None and str(raw).strip():
                values[field] = str(raw).strip()
        origins = source.get("TUTOR_WEB_FRONTEND_ORIGINS", "")
        if origins and str(origins).strip():
            values["frontend_origins"] = tuple(
                origin.strip() for origin in str(origins).split(",") if origin.strip()
            )
        try:
            return cls.model_validate(values)
        except ValidationError as exc:
            fields = ", ".join(".".join(str(part) for part in error["loc"]) for error in exc.errors())
            raise ServerSettingsError(
                f"Invalid web server settings: {fields}. Check TUTOR_WEB_* environment variables."
            ) from None
