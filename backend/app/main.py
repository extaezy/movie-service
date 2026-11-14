from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.auth import register
from app.api.auth import router as auth_router
from app.api.movies import router as movies_router
from app.api.reviews import router as reviews_router
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

app.include_router(auth_router)
app.include_router(movies_router)
app.include_router(reviews_router)


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    if request.scope.get("endpoint") is not register:
        return await request_validation_exception_handler(request, exc)

    errors = [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/")
def root():
    return {"message": settings.app_name, "version": settings.app_version}
