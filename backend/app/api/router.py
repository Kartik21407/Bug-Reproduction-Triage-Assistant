from fastapi import APIRouter

from app.api import analysis, auth, duplicates, generated_report, reports, triage

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(reports.router)
api_router.include_router(analysis.router)
api_router.include_router(triage.router)
api_router.include_router(duplicates.router)
api_router.include_router(generated_report.router)
