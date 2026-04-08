from pathlib import Path

from backend.settings import get_attachments_storage_root


def safe_attachment_filename(name: str) -> str:
    candidate = (name or "file.bin").strip().replace("\\", "_").replace("/", "_")
    candidate = Path(candidate).name
    return candidate or "file.bin"


def attachment_user_dir(owner_user_id: int) -> Path:
    root = get_attachments_storage_root()
    user_dir = root / str(int(owner_user_id))
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def attachment_task_dir(owner_user_id: int, id_task: int) -> Path:
    task_dir = attachment_user_dir(owner_user_id) / str(int(id_task))
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def resolve_attachment_abs(percorso_relativo: str) -> Path | None:
    if not percorso_relativo:
        return None
    root = get_attachments_storage_root().resolve()
    candidate = (root / percorso_relativo).resolve()
    if root not in candidate.parents and candidate != root:
        return None
    return candidate
