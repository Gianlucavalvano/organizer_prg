from dataclasses import dataclass

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


@dataclass
class AuthUser:
    id_utente: int
    username: str
    ruolo: str
    ruoli: list[str]
    permessi: list[str]
