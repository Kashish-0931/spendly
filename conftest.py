import pytest

import database.db as db
from app import app as flask_app


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    # Redirect the data layer at a throwaway SQLite file per test.
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return db.DB_PATH


@pytest.fixture
def client(db_path):
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as c:
        yield c


@pytest.fixture
def seeded(db_path):
    """Populate the throwaway DB with the demo user + sample expenses.

    Returns the demo user's id.
    """
    db.seed_db()
    conn = db.get_db()
    try:
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()[0]
    finally:
        conn.close()
    return uid
