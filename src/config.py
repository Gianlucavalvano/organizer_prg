import json
import os
import sys
from pathlib import Path


DEFAULT_SETTINGS = {
    "logo_path": "assets/logo.png",
    "firma_path": "assets/firma_footer.png",
}


def get_project_root() -> str:
    """
    Return project root in development or executable directory when frozen.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_src_dir() -> str:
    return os.path.join(get_project_root(), "src")


def get_postgres_config() -> dict:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "organizer_db"),
        "user": os.getenv("DB_USER", "organizer_user"),
        "password": os.getenv("DB_PASSWORD", "organizer_pass"),
    }


def get_postgres_dsn() -> str:
    cfg = get_postgres_config()
    return (
        f"host={cfg['host']} "
        f"port={cfg['port']} "
        f"dbname={cfg['dbname']} "
        f"user={cfg['user']} "
        f"password={cfg['password']}"
    )


def get_api_base_url() -> str:
    return os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


def get_attachments_dir() -> str:
    return os.path.join(get_project_root(), "attachments")


def get_settings_path() -> str:
    return os.path.join(get_src_dir(), "settings.json")


def load_app_settings() -> dict:
    settings = DEFAULT_SETTINGS.copy()
    path = get_settings_path()

    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                settings.update(loaded)
    except Exception:
        pass

    return settings


def save_app_settings(settings: dict) -> bool:
    try:
        path = get_settings_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)

        payload = DEFAULT_SETTINGS.copy()
        payload.update(settings or {})

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def resolve_app_path(path_value: str) -> str:
    """
    Resolve absolute/relative path. Relative paths are considered under src/.
    """
    if not path_value:
        return ""

    p = Path(path_value)
    if p.is_absolute():
        return str(p)

    return str(Path(get_src_dir()) / p)


def to_relative_src(path_value: str) -> str:
    """
    Store paths relative to src whenever possible.
    """
    if not path_value:
        return ""

    p = Path(path_value)
    src = Path(get_src_dir())

    try:
        return str(p.resolve().relative_to(src.resolve())).replace("\\", "/")
    except Exception:
        return str(p)


def get_logo_path() -> str:
    settings = load_app_settings()
    return resolve_app_path(settings.get("logo_path", DEFAULT_SETTINGS["logo_path"]))


def get_firma_path() -> str:
    settings = load_app_settings()
    return resolve_app_path(settings.get("firma_path", DEFAULT_SETTINGS["firma_path"]))
