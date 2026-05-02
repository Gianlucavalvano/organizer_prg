from pydantic import BaseModel


class ProgettoCreateIn(BaseModel):
    nome_progetto: str
    note: str | None = ""
    id_stato: int = 1
    percentuale_avanzamento: int = 0
    owner_user_id: int | None = None
    ticket_interno: str | None = ""
    ticket_esterno: str | None = ""


class ProgettoUpdateIn(BaseModel):
    nome_progetto: str
    note: str | None = ""
    id_stato: int = 1
    percentuale_avanzamento: int = 0
    ticket_interno: str | None = ""
    ticket_esterno: str | None = ""


class TaskCreateIn(BaseModel):
    id_progetto: int
    titolo: str
    data_inizio: str | None = None
    data_fine: str | None = None
    percentuale_avanzamento: int = 0
    tipo_task: int = 1
    id_stato: int = 1
    id_risorsa: int | None = None
    id_ruolo: int | None = None
    ticket_interno: str | None = ""
    ticket_esterno: str | None = ""


class TaskUpdateIn(BaseModel):
    titolo: str
    data_inizio: str | None = None
    data_fine: str | None = None
    percentuale_avanzamento: int = 0
    tipo_task: int = 1
    id_stato: int = 1
    id_risorsa: int | None = None
    id_ruolo: int | None = None
    ticket_interno: str | None = ""
    ticket_esterno: str | None = ""


class TaskCompleteIn(BaseModel):
    completato: bool = True
