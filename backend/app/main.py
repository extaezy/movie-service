from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.core.config import APP_NAME, APP_VERSION


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
)

app.include_router(health_router)
app.include_router(auth_router)

@app.get("/")
def root():
    return {
        "message": APP_NAME,
        "version": APP_VERSION
    }