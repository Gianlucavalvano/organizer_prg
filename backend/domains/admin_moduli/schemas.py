from pydantic import BaseModel, Field


class ModuliUtenteSetIn(BaseModel):
    codici: list[str] = Field(default_factory=list)
