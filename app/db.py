from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine


def _db_url() -> str:
    # Default local sqlite file under workspace data/
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    os.makedirs("data", exist_ok=True)
    return "sqlite:///data/zodel.db"


engine = create_engine(_db_url(), echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(engine) as session:
        yield session

