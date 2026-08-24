"""Not generated.

Smoke tests run inside the container against an in-process TestClient rather
than over HTTP. Two reasons: the client raises the app's real traceback
instead of a 500 body, and there is no port to race on. Reachability of the
published port is checked separately, by protogen waiting on /healthz.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    # The context manager is what runs lifespan -- without it the tables are
    # never created and every test fails on a missing relation.
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
