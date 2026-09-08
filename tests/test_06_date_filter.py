"""Step 6 — tests for the profile-page date filter.

Covers the pure `database.date_range.resolve_range` helper (preset resolution,
explicit start/end passthrough, reversed-range swap, malformed input),
the `start`/`end` keyword parameters added to the three profile query helpers
in `database/queries.py`, and the wired-up `GET /profile` route reading
`start` / `end` / `range` from the query string.

Expected behaviour is taken from `.claude/specs/06-date-filter.md` (its
Definition of done checklist), not from the implementation.
"""

from datetime import date, timedelta

import pytest

import database.db as db
from database.date_range import resolve_range
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)

# Seed expenses are dated in the current calendar month (days 03..25).
THIS_MONTH = date.today().strftime("%Y-%m")


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


def _add_expense_on(user_id, amount, category, iso_date, description="x"):
    """Insert one expense dated exactly on `iso_date` (a YYYY-MM-DD string)."""
    conn = db.get_db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, iso_date, description),
            )
    finally:
        conn.close()


def _login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


# --------------------------------------------------------------------------- #
# resolve_range — no / empty input                                             #
# --------------------------------------------------------------------------- #

def test_resolve_range_no_input_returns_all_time():
    # Spec: "Invalid or partial input falls back to 'All time' (None, None)."
    assert resolve_range() == (None, None, "All time")


def test_resolve_range_none_args_return_all_time():
    assert resolve_range(None, None, None) == (None, None, "All time")


def test_resolve_range_empty_strings_return_all_time():
    # Route passes through `?start=&end=` as "" — must resolve to All time.
    assert resolve_range("", "", "") == (None, None, "All time")


# --------------------------------------------------------------------------- #
# resolve_range — presets                                                      #
# --------------------------------------------------------------------------- #

def test_resolve_range_this_month_window():
    # Preset "this_month" starts on the 1st of the current calendar month.
    start, end, _ = resolve_range(preset="this_month", today=date(2026, 7, 15))
    assert start == "2026-07-01"
    assert start <= end <= "2026-07-31"


def test_resolve_range_this_month_label():
    # Spec lists "This month" as the human-readable label for this preset.
    _, _, label = resolve_range(preset="this_month", today=date(2026, 7, 15))
    assert label == "This month"


def test_resolve_range_last30_window_and_label():
    # "Last 30 days" = today and the 29 days before it, inclusive.
    assert resolve_range(preset="last30", today=date(2026, 3, 15)) == (
        "2026-02-14",
        "2026-03-15",
        "Last 30 days",
    )


def test_resolve_range_last3m_window_and_label():
    # "Last 3 months" counts back 3 whole calendar months from today.
    assert resolve_range(preset="last3m", today=date(2026, 7, 15)) == (
        "2026-04-15",
        "2026-07-15",
        "Last 3 months",
    )


def test_resolve_range_last6m_window_and_label():
    # "Last 6 months" counts back 6 whole calendar months from today.
    assert resolve_range(preset="last6m", today=date(2026, 7, 15)) == (
        "2026-01-15",
        "2026-07-15",
        "Last 6 months",
    )


def test_resolve_range_last3m_clamps_day_to_month_end():
    # 31 Dec - 3 months lands in Sep (30 days) -> day clamped to the 30th.
    start, _, _ = resolve_range(preset="last3m", today=date(2026, 12, 31))
    assert start == "2026-09-30"


def test_resolve_range_last6m_clamps_day_to_month_end():
    # 31 Aug - 6 months lands in Feb (28 days in 2026) -> clamped to the 28th.
    start, _, _ = resolve_range(preset="last6m", today=date(2026, 8, 31))
    assert start == "2026-02-28"


def test_resolve_range_all_preset_returns_all_time():
    # Preset "all" clears the window.
    assert resolve_range(preset="all", today=date(2026, 7, 15)) == (
        None,
        None,
        "All time",
    )


# --------------------------------------------------------------------------- #
# resolve_range — explicit start/end                                           #
# --------------------------------------------------------------------------- #

def test_resolve_range_explicit_start_end_passthrough():
    # Clean explicit dates pass straight through with a readable span label.
    assert resolve_range("2026-07-01", "2026-07-31", None, date(2026, 7, 15)) == (
        "2026-07-01",
        "2026-07-31",
        "1 Jul 2026 – 31 Jul 2026",
    )


def test_resolve_range_reversed_range_is_swapped():
    # Spec: "a start later than end is swapped rather than rejected."
    assert resolve_range("2026-07-31", "2026-07-01", None, date(2026, 7, 15)) == (
        "2026-07-01",
        "2026-07-31",
        "1 Jul 2026 – 31 Jul 2026",
    )


def test_resolve_range_one_sided_start_only():
    # Whichever of start/end parses cleanly is used; the other stays open.
    start, end, label = resolve_range("2026-07-01", None, None, date(2026, 7, 15))
    assert start == "2026-07-01"
    assert end is None
    assert "1 Jul 2026" in label


def test_resolve_range_malformed_dates_treated_as_absent():
    # Spec: "an unparseable date is treated as absent" -> All time view.
    assert resolve_range("not-a-date", "garbage", None, date(2026, 7, 15)) == (
        None,
        None,
        "All time",
    )


@pytest.mark.parametrize("bad", ["2026-07", "2026", "07/2026", "2026-13-40", "yesterday"])
def test_resolve_range_partial_or_bad_date_treated_as_absent(bad):
    # Spec: "Invalid or partial input falls back to 'All time' (None, None)."
    assert resolve_range(bad, None, None, date(2026, 7, 15)) == (None, None, "All time")


# --------------------------------------------------------------------------- #
# resolve_range — preset precedence                                            #
# --------------------------------------------------------------------------- #

def test_resolve_range_preset_wins_over_start_end():
    # Spec: "an explicit preset (range= param) wins over start/end".
    assert resolve_range("2020-01-01", "2020-12-31", "last30", date(2026, 7, 15)) == (
        "2026-06-16",
        "2026-07-15",
        "Last 30 days",
    )


def test_resolve_range_all_preset_wins_over_start_end():
    assert resolve_range("2020-01-01", "2020-12-31", "all", date(2026, 7, 15)) == (
        None,
        None,
        "All time",
    )


def test_resolve_range_unknown_preset_falls_back_to_dates():
    # An unrecognised range= value is ignored; start/end are used instead.
    assert resolve_range("2026-07-01", "2026-07-31", "bogus", date(2026, 7, 15)) == (
        "2026-07-01",
        "2026-07-31",
        "1 Jul 2026 – 31 Jul 2026",
    )


# --------------------------------------------------------------------------- #
# query helpers — start/end restrict rows (inclusive window)                    #
# --------------------------------------------------------------------------- #

def test_get_summary_stats_window_restricts_rows(db_path):
    uid = _make_user()
    _add_expense_on(uid, 100.0, "Food", "2026-07-01")
    _add_expense_on(uid, 250.0, "Bills", "2026-07-31")
    _add_expense_on(uid, 999.0, "Shopping", "2026-08-01")
    assert get_summary_stats(uid, "2026-07-01", "2026-07-31") == {
        "total_spent": 350.0,
        "transaction_count": 2,
        "top_category": "Bills",
    }


def test_get_summary_stats_open_end_includes_start_boundary(db_path):
    uid = _make_user()
    _add_expense_on(uid, 10.0, "Food", "2026-06-30")
    _add_expense_on(uid, 20.0, "Food", "2026-07-01")
    _add_expense_on(uid, 30.0, "Food", "2026-08-15")
    stats = get_summary_stats(uid, "2026-07-01", None)
    assert stats["total_spent"] == 50.0
    assert stats["transaction_count"] == 2


def test_get_summary_stats_open_start_includes_end_boundary(db_path):
    uid = _make_user()
    _add_expense_on(uid, 10.0, "Food", "2026-06-30")
    _add_expense_on(uid, 20.0, "Food", "2026-07-01")
    _add_expense_on(uid, 30.0, "Food", "2026-08-15")
    stats = get_summary_stats(uid, None, "2026-07-01")
    assert stats["total_spent"] == 30.0
    assert stats["transaction_count"] == 2


def test_get_summary_stats_none_none_matches_no_arg(seeded):
    # Spec: "no filter -> helpers called with start=None, end=None" is identical.
    assert get_summary_stats(seeded, None, None) == get_summary_stats(seeded)


def test_get_summary_stats_empty_window_returns_zeros(seeded):
    assert get_summary_stats(seeded, "2999-01-01", "2999-12-31") == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_get_recent_transactions_window_restricts_rows(db_path):
    uid = _make_user()
    _add_expense_on(uid, 100.0, "Food", "2026-07-05", "in window")
    _add_expense_on(uid, 200.0, "Bills", "2026-08-05", "out of window")
    rows = get_recent_transactions(uid, start="2026-07-01", end="2026-07-31")
    assert [r["description"] for r in rows] == ["in window"]


def test_get_recent_transactions_none_none_matches_no_arg(seeded):
    assert get_recent_transactions(seeded, start=None, end=None) == (
        get_recent_transactions(seeded)
    )


def test_get_recent_transactions_empty_window_returns_empty_list(seeded):
    assert get_recent_transactions(seeded, start="2999-01-01", end="2999-12-31") == []


def test_get_category_breakdown_window_restricts_rows(db_path):
    uid = _make_user()
    _add_expense_on(uid, 100.0, "Food", "2026-07-05")
    _add_expense_on(uid, 300.0, "Bills", "2026-07-20")
    _add_expense_on(uid, 999.0, "Shopping", "2026-09-01")
    result = get_category_breakdown(uid, start="2026-07-01", end="2026-07-31")
    assert [c["name"] for c in result] == ["Bills", "Food"]
    assert sum(c["pct"] for c in result) == 100


def test_get_category_breakdown_none_none_matches_no_arg(seeded):
    assert get_category_breakdown(seeded, start=None, end=None) == (
        get_category_breakdown(seeded)
    )


def test_get_category_breakdown_empty_window_returns_empty_list(seeded):
    assert get_category_breakdown(seeded, start="2999-01-01", end="2999-12-31") == []


def test_query_helpers_window_is_user_scoped(db_path):
    a = _make_user(email="a@spendly.com")
    b = _make_user(email="b@spendly.com")
    _add_expense_on(a, 100.0, "Food", "2026-07-10")
    _add_expense_on(b, 500.0, "Bills", "2026-07-10")
    stats = get_summary_stats(a, "2026-07-01", "2026-07-31")
    assert stats["total_spent"] == 100.0
    assert stats["transaction_count"] == 1
    assert get_recent_transactions(a, start="2026-07-01", end="2026-07-31") != (
        get_recent_transactions(b, start="2026-07-01", end="2026-07-31")
    )


# --------------------------------------------------------------------------- #
# GET /profile — auth guard                                                    #
# --------------------------------------------------------------------------- #

def test_profile_redirects_to_login_when_anonymous(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_with_filter_param_redirects_when_anonymous(client):
    resp = client.get("/profile?range=last30")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_stale_session_with_filter_redirects(client):
    _login_as(client, 999999)
    resp = client.get("/profile?range=last30")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# --------------------------------------------------------------------------- #
# GET /profile — no filter is unchanged from Step 5                            #
# --------------------------------------------------------------------------- #

def test_profile_no_query_string_shows_full_history(client, seeded):
    _login_as(client, seeded)
    resp = client.get("/profile")
    body = resp.data
    assert resp.status_code == 200
    assert b"4,708.00" in body
    assert b'<span class="mock-tile-value">8</span>' in body
    assert b"Showing All time" in body
    assert b">clear</a>" not in body


def test_profile_empty_start_end_params_show_all_time(client, seeded):
    _login_as(client, seeded)
    resp = client.get("/profile?start=&end=")
    body = resp.data
    assert resp.status_code == 200
    assert b"4,708.00" in body
    assert b'<span class="mock-tile-value">8</span>' in body
    assert b"Showing All time" in body
    assert b">clear</a>" not in body


def test_profile_range_all_returns_unfiltered(client, seeded):
    _login_as(client, seeded)
    resp = client.get("/profile?range=all")
    body = resp.data
    assert resp.status_code == 200
    assert b"4,708.00" in body
    assert b'<span class="mock-tile-value">8</span>' in body
    assert b"Showing All time" in body
    assert b">clear</a>" not in body


# --------------------------------------------------------------------------- #
# GET /profile — filter bar markup                                             #
# --------------------------------------------------------------------------- #

def test_profile_filter_bar_has_two_date_inputs(client, seeded):
    _login_as(client, seeded)
    body = client.get("/profile").data
    assert b'type="date" name="start"' in body
    assert b'type="date" name="end"' in body


def test_profile_filter_bar_has_preset_links(client, seeded):
    _login_as(client, seeded)
    body = client.get("/profile").data
    for label in (
        b"This month",
        b"Last 30 days",
        b"Last 3 months",
        b"Last 6 months",
        b"All time",
    ):
        assert label in body


def test_profile_prefills_date_pickers_with_active_range(client, seeded):
    _login_as(client, seeded)
    body = client.get(f"/profile?start={THIS_MONTH}-01&end={THIS_MONTH}-10").data
    assert f'value="{THIS_MONTH}-01"'.encode("utf-8") in body
    assert f'value="{THIS_MONTH}-10"'.encode("utf-8") in body


def test_profile_active_filter_shows_clear_link_back_to_profile(client, seeded):
    _login_as(client, seeded)
    body = client.get(f"/profile?start={THIS_MONTH}-01&end={THIS_MONTH}-28").data
    assert b">clear</a>" in body
    assert b'href="/profile"' in body


# --------------------------------------------------------------------------- #
# GET /profile — explicit window restricts the page                            #
# --------------------------------------------------------------------------- #

def test_profile_explicit_window_restricts_summary_and_table(client, seeded):
    _login_as(client, seeded)
    # Seed expenses on days 03,05,07,10 => 480 + 60 + 1250 + 350 = 2140 (4 rows).
    resp = client.get(f"/profile?start={THIS_MONTH}-01&end={THIS_MONTH}-10")
    body = resp.data
    assert resp.status_code == 200
    assert b"2,140.00" in body
    assert b'<span class="mock-tile-value">4</span>' in body
    assert b"Groceries from the local kirana store" in body  # day 03 — in window
    assert b"Dinner at a Udupi restaurant" not in body       # day 25 — out of window


def test_profile_reversed_range_is_swapped_and_still_correct(client, seeded):
    _login_as(client, seeded)
    resp = client.get(f"/profile?start={THIS_MONTH}-10&end={THIS_MONTH}-01")
    body = resp.data
    assert resp.status_code == 200
    assert b"2,140.00" in body
    assert b'<span class="mock-tile-value">4</span>' in body
    assert b"Dinner at a Udupi restaurant" not in body


def test_profile_malformed_date_renders_all_time_view(client, seeded):
    _login_as(client, seeded)
    resp = client.get("/profile?start=not-a-date")
    body = resp.data
    assert resp.status_code == 200
    assert b"4,708.00" in body
    assert b'<span class="mock-tile-value">8</span>' in body
    assert b"Showing All time" in body


def test_profile_future_window_shows_empty_state(client, seeded):
    _login_as(client, seeded)
    resp = client.get("/profile?start=2999-01-01&end=2999-12-31")
    body = resp.data
    assert resp.status_code == 200
    assert "₹0.00".encode("utf-8") in body
    assert b'<span class="mock-tile-value">0</span>' in body
    assert "—".encode("utf-8") in body            # top category dash
    assert b"No transactions in this range." in body
    assert body.count(b"cat-meter-fill") == 0


def test_profile_currency_is_rupee_only_with_filter(client, seeded):
    _login_as(client, seeded)
    body = client.get(f"/profile?start={THIS_MONTH}-01&end={THIS_MONTH}-28").data
    assert "₹".encode("utf-8") in body
    assert b"$" not in body
    assert "£".encode("utf-8") not in body


# --------------------------------------------------------------------------- #
# GET /profile — preset windows                                                #
# --------------------------------------------------------------------------- #

def test_profile_this_month_preset_renders_readable_label(client, seeded):
    _login_as(client, seeded)
    resp = client.get("/profile?range=this_month")
    assert resp.status_code == 200
    assert b"Showing This month" in resp.data


def test_profile_last30_preset_restricts_and_labels(client):
    uid = _make_user()
    _login_as(client, uid)
    _add_expense_on(uid, 111.0, "Food", (date.today() - timedelta(days=5)).isoformat(), "recent buy")
    _add_expense_on(uid, 999.0, "Bills", (date.today() - timedelta(days=60)).isoformat(), "old buy")
    resp = client.get("/profile?range=last30")
    body = resp.data
    assert resp.status_code == 200
    assert b"111.00" in body
    assert b"999.00" not in body
    assert b'<span class="mock-tile-value">1</span>' in body
    assert b"Showing Last 30 days" in body


def test_profile_last3m_preset_restricts_and_labels(client):
    uid = _make_user()
    _login_as(client, uid)
    _add_expense_on(uid, 222.0, "Food", (date.today() - timedelta(days=40)).isoformat(), "recent")
    _add_expense_on(uid, 888.0, "Bills", (date.today() - timedelta(days=250)).isoformat(), "old")
    resp = client.get("/profile?range=last3m")
    body = resp.data
    assert resp.status_code == 200
    assert b"222.00" in body
    assert b"888.00" not in body
    assert b"Showing Last 3 months" in body


def test_profile_last6m_preset_restricts_and_labels(client):
    uid = _make_user()
    _login_as(client, uid)
    _add_expense_on(uid, 333.0, "Food", (date.today() - timedelta(days=100)).isoformat(), "recent")
    _add_expense_on(uid, 777.0, "Bills", (date.today() - timedelta(days=250)).isoformat(), "old")
    resp = client.get("/profile?range=last6m")
    body = resp.data
    assert resp.status_code == 200
    assert b"333.00" in body
    assert b"777.00" not in body
    assert b"Showing Last 6 months" in body


# --------------------------------------------------------------------------- #
# GET /profile — end to end                                                    #
# --------------------------------------------------------------------------- #

def test_profile_end_to_end_register_login_then_filter(client):
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

    _add_expense_on(uid, 250.0, "Food", (date.today() - timedelta(days=2)).isoformat(), "Lunch canteen")
    _add_expense_on(uid, 400.0, "Bills", (date.today() - timedelta(days=120)).isoformat(), "Old bill")

    resp = client.get("/profile?range=last30")
    body = resp.data
    assert resp.status_code == 200
    assert b"Lunch canteen" in body
    assert b"Old bill" not in body
    assert b'<span class="mock-tile-value">1</span>' in body
