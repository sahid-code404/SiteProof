from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.db.session import Base, engine
import app.models  # noqa: F401

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
def create_tables_for_phase1() -> None:
    # Phase 1 bootstrap only. Replace with Alembic-managed migrations in Phase 2.
    Base.metadata.create_all(bind=engine)
