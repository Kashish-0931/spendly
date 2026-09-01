import pytest

import database.db as db
from app import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Redirect the data layer at a throwaway SQLite file per test.
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as c:
        yield c
