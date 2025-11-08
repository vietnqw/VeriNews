"""
Main API Router

Aggregates all API routes.
"""

from fastapi import APIRouter

from app.api import health, verification

api_router = APIRouter()

# Include routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(verification.router)

# Future routers:
# api_router.include_router(articles.router, prefix="/articles", tags=["articles"])
