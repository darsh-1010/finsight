import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


@compiles(sa.UUID, "sqlite")
def compile_uuid_sqlite(element, compiler, **kw):
    return "VARCHAR(36)"


@compiles(sa.ARRAY, "sqlite")
def compile_array_sqlite(element, compiler, **kw):
    return "TEXT"


from .config import settings

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
)

SESSION_LOCAL = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SESSION_LOCAL()
    try:
        yield db
    finally:
        db.close()
