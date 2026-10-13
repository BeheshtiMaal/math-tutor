"""Local web service for MathTutor (roadmap phase W1).

The FastAPI application gathers input, invokes the compiled LangGraph and maps
its results. It never decides or executes graph routes; LangGraph remains the
only orchestration engine.
"""

from .main import create_app

__all__ = ["create_app"]
