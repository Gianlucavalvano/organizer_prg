from pydantic import BaseModel


class UserCreateIn(BaseModel):
    username: str
    password: str
    ruolo: str = "USER"
    attivo: bool = True


class UserRoleIn(BaseModel):
    ruolo: str


class UserAttivoIn(BaseModel):
    attivo: bool


class UserPasswordIn(BaseModel):
    password: str
