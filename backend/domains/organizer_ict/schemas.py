from pydantic import BaseModel


class NoteCreateIn(BaseModel):
    testo: str
    data_nota: str | None = None
    id_progetto: int | None = None
    id_task: int | None = None


class NoteTaskFromIn(BaseModel):
    id_progetto: int


class RisorsaIn(BaseModel):
    nome: str
    cognome: str
    email: str | None = None


class RuoloIn(BaseModel):
    nome_ruolo: str
