from __future__ import annotations

import uuid


def generate_request_id() -> str:
    try:
        from langsmith import uuid7

        return str(uuid7())
    except Exception:
        return str(uuid.uuid4())
