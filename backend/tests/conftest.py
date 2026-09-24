import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, Company


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as database:
        yield database
    Base.metadata.drop_all(engine)


@pytest.fixture
def companies(session: Session) -> tuple[Company, Company]:
    first = Company(id=uuid.uuid4(), name="Company A", slug="company-a", default_currency="EUR")
    second = Company(id=uuid.uuid4(), name="Company B", slug="company-b", default_currency="USD")
    session.add_all([first, second])
    session.commit()
    return first, second

