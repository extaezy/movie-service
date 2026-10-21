from pydantic import BaseModel, EmailStr, model_validator

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    password_confirmation: str

    @model_validator(mode="after")
    def check_passwords(self):
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают")
        return self