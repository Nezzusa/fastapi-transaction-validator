import os
from src.app import app, engine, SessionLocal  # noqa: E402
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


TEST_DB = "paymentprocessing_test"
BASE_URL = "postgresql+psycopg2://postgres:admin@localhost:5432"
os.environ["DATABASE_URL"] = f"{BASE_URL}/{TEST_DB}"


def _ensure_test_db() -> None:
    admin = create_engine(f"{BASE_URL}/postgres", isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"),
                {"n": TEST_DB},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    finally:
        admin.dispose()


_ensure_test_db()


@pytest.fixture(scope="session")
def client():
    # Context manager runs the lifespan -> connects and loads src/tables.sql
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_tables(client):
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE TABLE fraud_logs, transactions RESTART IDENTITY CASCADE")
        )
    yield