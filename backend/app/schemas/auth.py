from pydantic import BaseModel, EmailStr, model_validator, Field

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

class UserLogin(BaseModel):
    email: EmailStr
    password: str