from pydantic import BaseModel, EmailStr, model_validator, Field
from typing import Literal

class UserRegister(BaseModel):
    username: str = Field(
        min_length=4,
        max_length=20,
        pattern=r"^[a-zA-Z0-9]+(?:_[a-zA-Z0-9]+)*$"
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128
    )
    password_confirm: str

    @model_validator(mode="after")
    def check_passwords(self):
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают")
        return self

class UserRegisterResponse(BaseModel):
    username: str
    email: EmailStr


class UserLogin(BaseModel):
    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class CurrentUserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
