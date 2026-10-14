"""FastAPI application factory: builds the app and mounts the API router."""

from fastapi import FastAPI

import app.models  # noqa: F401  imports every model module so its tables register
from app.api.router import api_router

app = FastAPI(title="Bug Reproduction & Triage Assistant")
app.include_router(api_router)
