"""Run the local web service: ``python -m webapp``.

Binds to loopback only unless TUTOR_WEB_ALLOW_NONLOCAL_BIND is set.
"""
from __future__ import annotations

import sys

import uvicorn

from .main import create_app
from .settings import ServerSettings, ServerSettingsError


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"--help", "-h"}:
        print("usage: python -m webapp\n\nEnvironment: TUTOR_WEB_HOST, TUTOR_WEB_PORT, TUTOR_WEB_OFFLINE")
        return 0
    try:
        settings = ServerSettings.from_env()
    except ServerSettingsError as exc:
        print(str(exc))
        return 2
    uvicorn.run(create_app(settings=settings), host=settings.host, port=settings.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
