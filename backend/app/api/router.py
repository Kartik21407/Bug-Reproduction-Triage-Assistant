"""Collects the feature routers under a single /api prefix."""

from fastapi import APIRouter

from app.api import auth, reports

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(reports.router)
