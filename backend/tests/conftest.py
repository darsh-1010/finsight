from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import ARRAY


@compiles(ARRAY, "sqlite")
def compile_array_sqlite(element, compiler, **kw):
    return "TEXT"


import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
