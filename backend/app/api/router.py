from fastapi import APIRouter

from app.api import analysis, auth, reports

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(reports.router)
api_router.include_router(analysis.router)
