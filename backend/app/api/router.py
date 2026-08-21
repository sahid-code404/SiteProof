from fastapi import APIRouter

from app.api.routes import auth, challenges, inspections, inspectors, sessions, visual_analysis

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(inspections.router)
api_router.include_router(inspectors.router)
api_router.include_router(sessions.router)
api_router.include_router(challenges.router)
api_router.include_router(visual_analysis.router)
