import time

from fastapi import APIRouter, Depends, FastAPI, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, log_event

health_router = APIRouter()


@health_router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


async def request_log(request: Request, call_next):
    started = time.monotonic()
    response = await call_next(request)
    route = request.scope.get("route")
    log_event("request", method=request.method,
              path=getattr(route, "path", "desconhecida"),
              status_code=response.status_code,
              duration_ms=int((time.monotonic() - started) * 1000))
    return response


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="FIAS-ED", docs_url=None, redoc_url=None, openapi_url=None)
    install_error_handlers(app)
    app.middleware("http")(request_log)
    app.include_router(health_router, prefix="/api")

    from app.auth.routes import router as auth_router
    app.include_router(auth_router, prefix="/api")

    from app.admin.routes import router as admin_router
    app.include_router(admin_router, prefix="/api")
    return app


app = create_app()
