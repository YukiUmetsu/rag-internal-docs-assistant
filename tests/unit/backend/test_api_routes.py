from __future__ import annotations

from src.backend.app.api.routes import router


def test_api_router_includes_public_and_admin_paths() -> None:
    paths = {route.path for route in router.routes}

    assert "/api/health" in paths
    assert "/api/retrieve" in paths
    assert "/api/chat" in paths
    assert "/api/feedback" in paths
    assert "/api/admin/dashboard" in paths
    assert "/api/admin/feedback/{feedback_id}" in paths
    assert "/api/ingest/jobs" in paths
