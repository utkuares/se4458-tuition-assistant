
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=60, examples=["student1"])
    password: str = Field(min_length=1, max_length=128, examples=["Passw0rd!"])

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
