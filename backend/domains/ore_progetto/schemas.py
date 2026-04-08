from pydantic import BaseModel


class OreRigaIn(BaseModel):
    data_lavoro: str
    ore: float
    nome_progetto_snapshot: str
    id_progetto: int | None = None
    note: str | None = ""
