"""Safe error codes and mapping for the local web service.

Every error reaching the browser is one of the closed codes below, carries an
i18n key and an optional safe detail string. Exception messages, stack traces,
credentials and filesystem paths are never serialized.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErrorCode(str, Enum):
    """Closed set of error codes (spec v3.0 section 7.7, plus turn_timeout)."""

    BAD_REQUEST = "bad_request"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    THREAD_NOT_FOUND = "thread_not_found"
    TURN_IN_PROGRESS = "turn_in_progress"
    RATE_LIMITED = "rate_limited"
    SESSION_LIMIT = "session_limit"
    TURN_TIMEOUT = "turn_timeout"
    MODEL_UNAVAILABLE = "model_unavailable"
    SEARCH_UNAVAILABLE = "search_unavailable"
    EMBEDDING_UNAVAILABLE = "embedding_unavailable"
    MATH_UNSUPPORTED = "math_unsupported"
    BLOCK_INVALID = "block_invalid"
    PROFILE_INVALID = "profile_invalid"
    INTERNAL_ERROR = "internal_error"


HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.PAYLOAD_TOO_LARGE: 413,
    ErrorCode.THREAD_NOT_FOUND: 404,
    ErrorCode.TURN_IN_PROGRESS: 409,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.SESSION_LIMIT: 429,
    ErrorCode.TURN_TIMEOUT: 504,
    ErrorCode.MODEL_UNAVAILABLE: 503,
    ErrorCode.SEARCH_UNAVAILABLE: 503,
    ErrorCode.EMBEDDING_UNAVAILABLE: 503,
    ErrorCode.MATH_UNSUPPORTED: 422,
    ErrorCode.BLOCK_INVALID: 422,
    ErrorCode.PROFILE_INVALID: 422,
    ErrorCode.INTERNAL_ERROR: 500,
}

INTERNAL_DETAIL = "The request failed safely."


class ApiError(Exception):
    """An error that is safe to return to the browser.

    ``detail`` must be written by this codebase, never copied from a provider
    response, an exception message or user input.
    """

    def __init__(self, code: ErrorCode, message_key: str, *, detail: str | None = None) -> None:
        super().__init__(code.value)
        self.code = code
        self.message_key = message_key
        self.detail = detail

    @property
    def http_status(self) -> int:
        return HTTP_STATUS[self.code]

    def body(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code.value, "message_key": self.message_key}
        if self.detail:
            payload["detail"] = self.detail
        return {"error": payload}


def error_payload(code: ErrorCode, message_key: str, detail: str | None = None) -> dict[str, Any]:
    return ApiError(code, message_key, detail=detail).body()


def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.http_status, content=exc.body())


def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Report which request fields were rejected, without echoing their values."""
    fields = sorted({".".join(str(part) for part in error.get("loc", ())) for error in exc.errors()})
    detail = "Invalid request fields: " + ", ".join(fields) if fields else "Invalid request body."
    return JSONResponse(
        status_code=HTTP_STATUS[ErrorCode.BAD_REQUEST],
        content=error_payload(ErrorCode.BAD_REQUEST, "error.bad_request", detail),
    )


def unhandled_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=HTTP_STATUS[ErrorCode.INTERNAL_ERROR],
        content=error_payload(ErrorCode.INTERNAL_ERROR, "error.internal", INTERNAL_DETAIL),
    )
