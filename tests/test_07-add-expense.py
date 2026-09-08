"""Step 7 — tests for the Add Expense feature (`/expenses/add`).

Covers `GET /expenses/add` rendering the form (amount, category dropdown with
all 7 categories, date field defaulting to today, optional description), the
auth guard on both GET and POST, the happy-path insert (one row scoped to the
session user, redirect to /profile, "Expense added." flash, row visible on the
profile), stored-data normalisation (amount rounding, ISO date, NULL for an
omitted description), server-side validation (bad/zero/negative/blank amount,
future date, unknown category, over-long description), field repopulation after
an error, user_id never trusted from the form body, and the nav link.

Expected behaviour is taken from `.claude/specs/07-add-expense.md` (its Rules
and Definition of done), not from the implementation.
"""

from datetime import date, timedelta

import pytest

import database.db as db

TODAY = date.today().isoformat()
THIS_MONTH = date.today().strftime("%Y-%m")
CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


def _login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _make_user(email="other@spendly.com", name="Other User"):
    conn = db.get_db()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, "x"),
            )
        return cur.lastrowid
    finally:
        conn.close()


def _count_expenses():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()


def _last_expense():
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()


def _valid_form(**overrides):
    data = {
        "amount": "250",
        "category": "Food",
        "date": TODAY,
        "description": "Lunch",
    }
    data.update(overrides)
    return data


# --------------------------------------------------------------------------- #
# GET /expenses/add — renders the form                                         #
# --------------------------------------------------------------------------- #

def test_get_add_expense_renders_form_for_logged_in_user(client, seeded):
    # DoD: GET renders a form with amount, category, date, description fields.
    _login_as(client, seeded)
    resp = client.get("/expenses/add")
    body = resp.data
    assert resp.status_code == 200
    assert b'name="amount"' in body
    assert b'name="category"' in body
    assert b'name="date"' in body
    assert b'name="description"' in body
    assert b'action="/expenses/add"' in body


def test_get_add_expense_lists_all_seven_categories(client, seeded):
    # DoD: category dropdown lists all 7 categories.
    _login_as(client, seeded)
    body = client.get("/expenses/add").data
    assert b"<select" in body
    for category in CATEGORIES:
        assert f'value="{category}"'.encode("utf-8") in body


def test_get_add_expense_date_defaults_to_today(client, seeded):
    # DoD: date picker defaults to today.
    _login_as(client, seeded)
    body = client.get("/expenses/add").data
    assert f'value="{TODAY}"'.encode("utf-8") in body


def test_get_add_expense_description_is_optional(client, seeded):
    # Spec Templates: description input is not `required`, maxlength 200.
    _login_as(client, seeded)
    body = client.get("/expenses/add").data
    # Isolate the description input tag and confirm it carries no `required`.
    start = body.index(b'name="description"')
    tag = body[start:body.index(b">", start)]
    assert b"required" not in tag
    assert b'maxlength="200"' in body


def test_get_add_expense_currency_is_rupee_only(client, seeded):
    # Spec Rules: currency stays ₹; amount label uses rupees.
    _login_as(client, seeded)
    body = client.get("/expenses/add").data
    assert "₹".encode("utf-8") in body
    assert b"$" not in body
    assert "£".encode("utf-8") not in body


# --------------------------------------------------------------------------- #
# Auth guard — logged out                                                      #
# --------------------------------------------------------------------------- #

def test_get_add_expense_redirects_to_login_when_anonymous(client):
    # DoD: visiting /expenses/add while logged out redirects to /login.
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_get_add_expense_anonymous_flashes_message(client):
    # DoD: the redirect carries a flash prompting the user to sign in.
    resp = client.get("/expenses/add", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Please sign in to add an expense." in resp.data


def test_post_add_expense_redirects_to_login_when_anonymous_and_inserts_no_row(client):
    # DoD: POSTing while logged out also redirects and inserts no row.
    before = _count_expenses()
    resp = client.post("/expenses/add", data=_valid_form())
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert _count_expenses() == before


def test_post_add_expense_stale_session_redirects_and_inserts_no_row(client):
    # Auth guard: a session user_id pointing at a deleted user is rejected.
    _login_as(client, 999999)
    before = _count_expenses()
    resp = client.post("/expenses/add", data=_valid_form())
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert _count_expenses() == before


# --------------------------------------------------------------------------- #
# Happy path                                                                   #
# --------------------------------------------------------------------------- #

def test_post_valid_expense_inserts_one_row_scoped_to_session_user(client, seeded):
    # DoD: submitting a valid expense inserts one row for the current user.
    _login_as(client, seeded)
    before = _count_expenses()
    client.post("/expenses/add", data=_valid_form(amount="250", category="Food",
                                                  description="Lunch"))
    assert _count_expenses() == before + 1
    row = _last_expense()
    assert row["user_id"] == seeded
    assert row["amount"] == 250.0
    assert row["category"] == "Food"
    assert row["date"] == TODAY
    assert row["description"] == "Lunch"


def test_post_valid_expense_redirects_to_profile(client, seeded):
    # DoD: a successful POST redirects to /profile (Post/Redirect/Get).
    _login_as(client, seeded)
    resp = client.post("/expenses/add", data=_valid_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")


def test_post_valid_expense_flashes_expense_added(client, seeded):
    # DoD: a "Expense added." banner is flashed after the redirect.
    _login_as(client, seeded)
    resp = client.post("/expenses/add", data=_valid_form(), follow_redirects=True)
    assert resp.status_code == 200
    assert b"Expense added." in resp.data


def test_post_valid_expense_row_shows_on_profile(client, seeded):
    # DoD: the new row appears in Recent transactions; total +₹250.00, count +1.
    _login_as(client, seeded)
    resp = client.post(
        "/expenses/add",
        data=_valid_form(amount="250", category="Food", description="Canteen lunch"),
        follow_redirects=True,
    )
    body = resp.data
    assert b"Canteen lunch" in body
    assert b"4,958.00" in body  # seed total 4,708.00 + 250.00
    assert b'<span class="mock-tile-value">9</span>' in body  # 8 seed rows + 1


# --------------------------------------------------------------------------- #
# Stored data — normalisation                                                  #
# --------------------------------------------------------------------------- #

def test_post_amount_is_rounded_to_two_decimals(client, seeded):
    # DoD: stored amount is a number rounded to 2 decimals.
    _login_as(client, seeded)
    client.post("/expenses/add", data=_valid_form(amount="10.129"))
    assert _last_expense()["amount"] == 10.13


def test_post_date_stored_in_iso_format(client, seeded):
    # DoD: stored date is YYYY-MM-DD.
    _login_as(client, seeded)
    target = f"{THIS_MONTH}-04"
    client.post("/expenses/add", data=_valid_form(date=target))
    stored = _last_expense()["date"]
    assert stored == target
    date.fromisoformat(stored)  # parses cleanly as ISO


def test_post_omitted_description_stored_as_null(client, seeded):
    # DoD: an omitted description is stored as NULL, not "".
    _login_as(client, seeded)
    data = _valid_form()
    data.pop("description")
    client.post("/expenses/add", data=data)
    assert _last_expense()["description"] is None


def test_post_blank_description_stored_as_null(client, seeded):
    # Spec Rules: description .strip()'d; empty -> SQL NULL (Python None).
    _login_as(client, seeded)
    client.post("/expenses/add", data=_valid_form(description="   "))
    assert _last_expense()["description"] is None


# --------------------------------------------------------------------------- #
# Validation errors — re-render 200, no row inserted                           #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_amount",
    ["0", "0.00", "-5", "-0.01", "abc", "", "   ", "NaN", "inf"],
)
def test_post_invalid_amount_rerenders_and_inserts_no_row(client, seeded, bad_amount):
    # DoD: amount 0 / negative / non-numeric / blank re-renders with an error,
    # inserts no row. Spec Rules also reject NaN / inf.
    _login_as(client, seeded)
    before = _count_expenses()
    resp = client.post("/expenses/add", data=_valid_form(amount=bad_amount))
    assert resp.status_code == 200
    assert b'class="auth-error"' in resp.data
    assert _count_expenses() == before


def test_post_amount_at_sanity_cap_rerenders_and_inserts_no_row(client, seeded):
    # Spec Rules: reject values >= 10_000_000 (₹1 crore) as a sanity cap.
    _login_as(client, seeded)
    before = _count_expenses()
    resp = client.post("/expenses/add", data=_valid_form(amount="10000000"))
    assert resp.status_code == 200
    assert b'class="auth-error"' in resp.data
    assert _count_expenses() == before


def test_post_future_date_rerenders_and_inserts_no_row(client, seeded):
    # DoD: a future date re-renders with a visible error and inserts no row.
    _login_as(client, seeded)
    before = _count_expenses()
    future = (date.today() + timedelta(days=1)).isoformat()
    resp = client.post("/expenses/add", data=_valid_form(date=future))
    assert resp.status_code == 200
    assert b'class="auth-error"' in resp.data
    assert _count_expenses() == before


def test_post_malformed_date_rerenders_and_inserts_no_row(client, seeded):
    # Spec Rules: date must parse as ISO YYYY-MM-DD; anything else is rejected.
    _login_as(client, seeded)
    before = _count_expenses()
    resp = client.post("/expenses/add", data=_valid_form(date="08/09/2026"))
    assert resp.status_code == 200
    assert b'class="auth-error"' in resp.data
    assert _count_expenses() == before


def test_post_unknown_category_rerenders_and_inserts_no_row(client, seeded):
    # DoD: a category not in CATEGORIES (e.g. Rent) re-renders, inserts no row.
    _login_as(client, seeded)
    before = _count_expenses()
    resp = client.post("/expenses/add", data=_valid_form(category="Rent"))
    assert resp.status_code == 200
    assert b'class="auth-error"' in resp.data
    assert _count_expenses() == before


def test_post_description_over_200_chars_rerenders_and_inserts_no_row(client, seeded):
    # Spec Rules: description over 200 chars is rejected.
    _login_as(client, seeded)
    before = _count_expenses()
    resp = client.post("/expenses/add", data=_valid_form(description="x" * 201))
    assert resp.status_code == 200
    assert b'class="auth-error"' in resp.data
    assert _count_expenses() == before


# --------------------------------------------------------------------------- #
# Field repopulation after a validation error                                  #
# --------------------------------------------------------------------------- #

def test_post_validation_error_repopulates_submitted_fields(client, seeded):
    # DoD: after a validation error the already-filled fields are preserved.
    _login_as(client, seeded)
    resp = client.post(
        "/expenses/add",
        data=_valid_form(amount="-5", category="Transport",
                         date=f"{THIS_MONTH}-04", description="Auto fare"),
    )
    body = resp.data
    assert resp.status_code == 200
    assert b'value="-5"' in body
    assert b'value="Auto fare"' in body
    assert f'value="{THIS_MONTH}-04"'.encode("utf-8") in body
    # The chosen category stays selected in the dropdown.
    assert b'value="Transport" selected' in body


# --------------------------------------------------------------------------- #
# user_id is never trusted from the form                                       #
# --------------------------------------------------------------------------- #

def test_post_ignores_injected_user_id_field(client, seeded):
    # DoD: the created row's user_id equals the signed-in user regardless of a
    # user_id field injected into the POST body.
    other = _make_user(email="victim@spendly.com")
    _login_as(client, seeded)
    client.post("/expenses/add", data=_valid_form(user_id=str(other), id="12345"))
    row = _last_expense()
    assert row["user_id"] == seeded


def test_post_expense_not_visible_to_other_user(client, seeded):
    # User isolation: a new expense belongs only to its creator.
    other = _make_user(email="stranger@spendly.com")
    _login_as(client, seeded)
    client.post("/expenses/add", data=_valid_form(description="Private note"))

    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT description FROM expenses WHERE user_id = ?", (other,)
        ).fetchall()
    finally:
        conn.close()
    assert rows == []


# --------------------------------------------------------------------------- #
# Nav link                                                                     #
# --------------------------------------------------------------------------- #

def test_nav_shows_add_expense_link_when_logged_in(client, seeded):
    # DoD: the nav bar shows an "Add expense" link for logged-in users.
    _login_as(client, seeded)
    body = client.get("/profile").data
    assert b'href="/expenses/add"' in body
    assert b"Add expense" in body


def test_nav_hides_add_expense_link_when_logged_out(client):
    # DoD: the "Add expense" link is not shown when logged out.
    body = client.get("/").data
    assert b'href="/expenses/add"' not in body
    assert b"Add expense" not in body


# --------------------------------------------------------------------------- #
# End to end                                                                   #
# --------------------------------------------------------------------------- #

def test_add_expense_end_to_end_register_login_add(client):
    # Register -> login -> add: the row lands under the new user's id.
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

    assert client.get("/expenses/add").status_code == 200

    resp = client.post(
        "/expenses/add",
        data=_valid_form(amount="99.5", category="Bills", description="Broadband"),
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Expense added." in resp.data
    assert b"Broadband" in resp.data

    conn = db.get_db()
    try:
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("ravi@example.com",)
        ).fetchone()[0]
        row = conn.execute(
            "SELECT user_id, amount, category, date FROM expenses ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row["user_id"] == uid
    assert row["amount"] == 99.5
    assert row["category"] == "Bills"
    assert row["date"] == TODAY
