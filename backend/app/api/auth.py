from fastapi import APIRouter
from app.services.auth_service import register_user
from app.schemas.auth import UserLogin
from app.services.auth_service import authenticate_user

from app.schemas.auth import UserRegister

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

@router.post("/register", status_code=201)
def register(user: UserRegister):
    return register_user(user)

@router.post("/login")
def login(user: UserLogin):
    return authenticate_user(user)