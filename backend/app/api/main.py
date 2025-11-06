"""
Main API Router

Aggregates all API routes.
"""

from fastapi import APIRouter

from app.api import health

api_router = APIRouter()

# Include routers
api_router.include_router(health.router, tags=["health"])

# Future routers:
# api_router.include_router(verification.router, prefix="/verify", tags=["verification"])
# api_router.include_router(articles.router, prefix="/articles", tags=["articles"])

