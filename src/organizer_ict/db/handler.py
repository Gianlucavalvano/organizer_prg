import db_handler_progetti as _db


def __getattr__(name):
    return getattr(_db, name)
