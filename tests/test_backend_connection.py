"""Step 5 — tests for the profile-page data layer (`database/queries.py`)
and the wired-up `GET /profile` route.

Unit tests exercise the four query helpers directly against a throwaway DB;
route tests drive `/profile` through the Flask test client.
"""

from datetime import date
from pathlib import Path

import database.db as db
import database.queries as queries
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

# The seed expenses are dated in the current month; member_since for any user
# created "now" is the current month. Computed at run time — never hardcoded.
THIS_MONTH = date.today().strftime("%Y-%m")
THIS_MONTH_LABEL = date.today().strftime("%B %Y")


def _make_user(email="new@spendly.com", name="New User", created_at=None):
    """Insert a bare user (placeholder password hash) and return its id."""
    conn = db.get_db()
    try:
        with conn:
            if created_at is None:
                cur = conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, "x"),
                )
            else:
                cur = conn.execute(
                    "INSERT INTO users (name, email, password_hash, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (name, email, "x", created_at),
                )
        return cur.lastrowid
    finally:
        conn.close()


def _add_expense(user_id, amount, category, day, description="x"):
    """Insert one expense dated in the current month on `day`."""
    conn = db.get_db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, f"{THIS_MONTH}-{day:02d}", description),
            )
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# get_user_by_id                                                               #
# --------------------------------------------------------------------------- #

def test_get_user_by_id_seed_fields(seeded):
    assert get_user_by_id(seeded) == {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "member_since": THIS_MONTH_LABEL,
    }


def test_get_user_by_id_formats_member_since(db_path):
    uid = _make_user(created_at="2025-03-14 09:00:00")
    assert get_user_by_id(uid)["member_since"] == "March 2025"


def test_get_user_by_id_unknown_returns_none(db_path):
    assert get_user_by_id(999) is None


# --------------------------------------------------------------------------- #
# module hygiene                                                               #
# --------------------------------------------------------------------------- #

def test_queries_has_no_flask_import():
    source = Path(queries.__file__).read_text(encoding="utf-8").lower()
    assert "flask" not in source


# --------------------------------------------------------------------------- #
# route: unauthenticated                                                       #
# --------------------------------------------------------------------------- #

def test_profile_redirects_when_anonymous(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# --------------------------------------------------------------------------- #
# --- subagent 1: transactions (get_recent_transactions) ---                    #
# --------------------------------------------------------------------------- #

def test_recent_transactions_newest_first(seeded):
    rows = get_recent_transactions(seeded)
    assert len(rows) == 8
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates, reverse=True)
    assert rows[0] == {
        "date": f"{THIS_MONTH}-25",
        "description": "Dinner at a Udupi restaurant",
        "category": "Food",
        "amount": 220.0,
    }
    assert rows[-1]["description"] == "Groceries from the local kirana store"
    assert rows[-1]["amount"] == 480.0
    for r in rows:
        assert set(r.keys()) == {"date", "description", "category", "amount"}


def test_recent_transactions_limit(seeded):
    assert len(get_recent_transactions(seeded, limit=3)) == 3
    assert get_recent_transactions(seeded, limit=3)[0]["date"].endswith("-25")


def test_recent_transactions_empty(db_path):
    uid = _make_user()
    assert get_recent_transactions(uid) == []


# --------------------------------------------------------------------------- #
# --- subagent 2: summary stats (get_summary_stats) ---                         #
# --------------------------------------------------------------------------- #

def test_get_summary_stats_seed(seeded):
    assert get_summary_stats(seeded) == {
        "total_spent": 4708.0,
        "transaction_count": 8,
        "top_category": "Shopping",
    }


def test_get_summary_stats_empty(db_path):
    uid = _make_user()
    assert get_summary_stats(uid) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_get_summary_stats_is_user_scoped(seeded):
    other = _make_user(email="other@spendly.com")
    assert get_summary_stats(other) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }
    assert get_summary_stats(seeded)["transaction_count"] == 8


# --------------------------------------------------------------------------- #
# --- subagent 3: category breakdown (get_category_breakdown) ---               #
# --------------------------------------------------------------------------- #

def test_category_breakdown_seed(seeded):
    result = get_category_breakdown(seeded)
    assert [c["name"] for c in result] == [
        "Shopping",
        "Bills",
        "Food",
        "Health",
        "Entertainment",
        "Other",
        "Transport",
    ]
    assert [c["amount"] for c in result] == [
        1899.0,
        1250.0,
        700.0,
        350.0,
        299.0,
        150.0,
        60.0,
    ]
    pcts = [c["pct"] for c in result]
    assert pcts == [41, 27, 15, 7, 6, 3, 1]
    assert sum(pcts) == 100
    assert all(isinstance(p, int) for p in pcts)
    widths = [c["width"] for c in result]
    assert widths == [40, 30, 20, 10, 10, 10, 10]
    assert all(w % 10 == 0 for w in widths)
    assert all(10 <= w <= 100 for w in widths)
    for c in result:
        assert set(c.keys()) == {"name", "amount", "pct", "width"}


def test_category_breakdown_empty(db_path):
    uid = _make_user()
    assert get_category_breakdown(uid) == []


def test_category_breakdown_single_category(db_path):
    uid = _make_user()
    _add_expense(uid, 100.0, "Food", 5)
    assert get_category_breakdown(uid) == [
        {"name": "Food", "amount": 100.0, "pct": 100, "width": 100}
    ]


def test_category_breakdown_pct_sums_to_100(db_path):
    uid = _make_user()
    _add_expense(uid, 1.0, "Food", 1)
    _add_expense(uid, 1.0, "Bills", 2)
    _add_expense(uid, 1.0, "Transport", 3)
    result = get_category_breakdown(uid)
    assert sum(c["pct"] for c in result) == 100


# --------------------------------------------------------------------------- #
# route: GET /profile (integration)                                            #
# --------------------------------------------------------------------------- #

def _login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_profile_shows_seed_user_data(client, seeded):
    _login_as(client, seeded)
    resp = client.get("/profile")
    body = resp.data

    assert resp.status_code == 200
    assert b"Demo User" in body
    assert b"demo@spendly.com" in body
    assert "₹".encode("utf-8") in body
    assert b"4,708.00" in body
    assert b'<span class="mock-tile-value">8</span>' in body
    assert b"Shopping" in body
    assert f"Member since {THIS_MONTH_LABEL}".encode("utf-8") in body
    # newest transaction rendered before the oldest
    assert body.index(b"Dinner at a Udupi restaurant") < body.index(
        b"Groceries from the local kirana store"
    )
    for name in ("Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"):
        assert name.encode("utf-8") in body
    assert b"cat-meter-fill--shopping w-40" in body


def test_profile_currency_is_rupee_only(client, seeded):
    _login_as(client, seeded)
    body = client.get("/profile").data
    assert b"$" not in body
    assert "£".encode("utf-8") not in body


def test_profile_empty_account(client):
    uid = _make_user()
    _login_as(client, uid)
    resp = client.get("/profile")
    body = resp.data

    assert resp.status_code == 200
    assert "₹0.00".encode("utf-8") in body
    assert b'<span class="mock-tile-value">0</span>' in body
    assert "—".encode("utf-8") in body
    assert b"Recent transactions" in body
    assert b"Category breakdown" in body
    assert body.count(b"cat-meter-fill") == 0


def test_profile_end_to_end_register_login(client):
    client.post(
        "/register",
        data={"name": "Ravi Kumar", "email": "ravi@example.com", "password": "rupees123"},
        follow_redirects=True,
    )
    client.post(
        "/login",
        data={"email": "ravi@example.com", "password": "rupees123"},
        follow_redirects=True,
    )

    conn = db.get_db()
    try:
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("ravi@example.com",)
        ).fetchone()[0]
    finally:
        conn.close()
    _add_expense(uid, 250.0, "Food", 12, "Lunch at the office canteen")

    resp = client.get("/profile")
    body = resp.data
    assert resp.status_code == 200
    assert b"Lunch at the office canteen" in body
    assert "₹".encode("utf-8") in body
    assert b'<span class="mock-tile-value">1</span>' in body


def test_profile_stale_session_user_redirects(client):
    _login_as(client, 4242)
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
