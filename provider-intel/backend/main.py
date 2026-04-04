"""Leadway Health — Provider Intelligence Platform (FastAPI backend)."""

import os
import uuid
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import upload, provider_analytics, tariff_intelligence, fwa, tariff_mapper, plan_access

app = FastAPI(title="Leadway Provider Intelligence", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure sessions dir exists
Path(__file__).parent.joinpath("sessions").mkdir(exist_ok=True)

app.include_router(upload.router, prefix="/api")
app.include_router(provider_analytics.router, prefix="/api")
app.include_router(tariff_intelligence.router, prefix="/api")
app.include_router(fwa.router, prefix="/api")
app.include_router(tariff_mapper.router, prefix="/api")
app.include_router(plan_access.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "provider-intelligence"}
