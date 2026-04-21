from __future__ import annotations

from fastapi import APIRouter

from src.backend.app.core.settings import get_settings
from src.backend.app.api.admin_routes import router as admin_router
from src.backend.app.api.public_routes import router as public_router


router = APIRouter()
router.include_router(public_router)
router.include_router(admin_router)
