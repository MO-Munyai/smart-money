import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

import main
import models
from database import Base


@pytest.fixture()
def db_session_factory(tmp_path):
    """
    A throwaway SQLite file per test (tmp_path is unique per test) - never
    touches the real portfolio.db. Importing `main` already ran
    models.Base.metadata.create_all against the real engine as a module-level
    side effect, but that's idempotent (just ensures tables exist) and writes
    no data, so it's harmless to leave as-is rather than restructuring main.py.
    """
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


@pytest.fixture()
def client(db_session_factory):
    """FastAPI TestClient wired to the isolated test DB via dependency override."""
    def override_get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[main.get_db] = override_get_db
    # raise_server_exceptions=False: let the app's own global exception
    # handler produce the response (matching real production behavior),
    # instead of TestClient re-raising for interactive debugging.
    with TestClient(main.app, raise_server_exceptions=False) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


@pytest.fixture()
def db(db_session_factory):
    """A raw DB session for seeding/inspecting rows directly in a test."""
    session = db_session_factory()
    yield session
    session.close()


def seed_instrument(db, ticker, type_="Stock"):
    instrument = models.Instrument(ticker=ticker.upper(), type=type_)
    db.add(instrument)
    db.commit()
    db.refresh(instrument)
    return instrument
