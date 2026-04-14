from __future__ import annotations

import os
import sys


DEFAULT_LANGSMITH_PROJECT = "acme-company-assistant-dev"


def env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_langsmith_project() -> str:
    return os.getenv("LANGSMITH_PROJECT", DEFAULT_LANGSMITH_PROJECT)


def running_under_pytest() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ or any("pytest" in arg for arg in sys.argv)


def langsmith_tracing_enabled() -> bool:
    if running_under_pytest():
        return False

    has_api_key = bool(os.getenv("LANGSMITH_API_KEY"))
    tracing_enabled = env_flag("LANGSMITH_TRACING", default=True)
    tracing_v2_enabled = env_flag("LANGSMITH_TRACING_V2", default=True)
    return has_api_key and tracing_enabled and tracing_v2_enabled


def configure_langsmith() -> None:
    if not langsmith_tracing_enabled():
        if running_under_pytest():
            os.environ["LANGSMITH_TRACING"] = "false"
            os.environ["LANGSMITH_TRACING_V2"] = "false"
        else:
            os.environ.setdefault("LANGSMITH_TRACING", "false")
            os.environ.setdefault("LANGSMITH_TRACING_V2", "false")
        return

    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_TRACING_V2", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", get_langsmith_project())
