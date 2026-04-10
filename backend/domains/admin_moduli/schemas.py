from pydantic import BaseModel, Field


class ModuliUtenteSetIn(BaseModel):
    codici: list[str] = Field(default_factory=list)


class AppModuloIn(BaseModel):
    codice: str
    nome: str
    route: str
    descrizione: str | None = None
    icona: str | None = None
    categoria: str | None = None
    ordine_menu: int = 1000
    attiva: bool = True
    visibile_menu: bool = True


class AppAttivaIn(BaseModel):
    attiva: bool
