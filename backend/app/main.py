from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.applications import router as applications_router
from app.api.auth import router as auth_router
from app.api.automation import router as automation_router
from app.api.dashboard import router as dashboard_router
from app.api.documents import router as documents_router
from app.api.job_sources import router as job_sources_router
from app.api.jobs import router as jobs_router
from app.api.notifications import router as notifications_router
from app.api.preferences import router as preferences_router
from app.api.profile import router as profile_router
from app.api.resumes import router as resumes_router
from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import RequestContextMiddleware, configure_logging, get_logger
from app.core.scheduler import start_scheduler, stop_scheduler

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

_DEFAULT_JWT_SECRET = "change-me-in-production"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment == "production" and settings.jwt_secret == _DEFAULT_JWT_SECRET:
        raise RuntimeError(
            "Refusing to start: JWT_SECRET is still the default placeholder in a production "
            "environment. Set a real secret before deploying."
        )
    logger.info("app_startup", environment=settings.environment)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="AI Job Search Automation System", version="0.1.0", lifespan=lifespan)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(auth_router, prefix="/api")
app.include_router(profile_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(job_sources_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(preferences_router, prefix="/api")
app.include_router(resumes_router, prefix="/api")
app.include_router(applications_router, prefix="/api")
app.include_router(automation_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
