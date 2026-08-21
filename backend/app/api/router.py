from fastapi import APIRouter

from app.api.routes import (
    advanced_security,
    auth,
    challenges,
    fusion_analysis,
    inspections,
    inspectors,
    receipts,
    sessions,
    verification,
    visual_analysis,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(inspections.router)
api_router.include_router(inspectors.router)
api_router.include_router(sessions.router)
api_router.include_router(challenges.router)
api_router.include_router(visual_analysis.router)
api_router.include_router(fusion_analysis.router)
api_router.include_router(verification.router)
api_router.include_router(receipts.router)
api_router.include_router(advanced_security.router)
