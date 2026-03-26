import os


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


def get_api_secret_key() -> str:
    return os.getenv("API_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")


def get_access_token_minutes() -> int:
    return int(os.getenv("API_ACCESS_TOKEN_MINUTES", "120"))
