"""Engine, session, declarative base.

There are no migrations. A prototype's schema is generated whole every time
it changes, and the database is a tmpfs that dies with the container -- an
Alembic history would be a ledger of edits nobody will ever replay.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

# expire_on_commit=False so a template can still read attributes off an object
# after the route committed it. The default expires them and renders a
# DetachedInstanceError instead of a page.
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False, class_=Session
)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
