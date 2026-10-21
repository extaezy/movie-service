from fastapi import APIRouter

from app.schemas.auth import UserRegister

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

@router.post("/register")
def register(user: UserRegister):
    return {"message": "Данные получены"}