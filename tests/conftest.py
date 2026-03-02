import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    return TestClient(app)
