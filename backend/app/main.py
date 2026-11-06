from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.core.config import settings
from app.db.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(auth_router)


@app.get("/")
def root():
    return {"message": settings.app_name, "version": settings.app_version}
