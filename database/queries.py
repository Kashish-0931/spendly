"""Read-only query helpers for the profile page.

Pure data layer: standard-library ``sqlite3`` only, no web-framework imports.
Every function opens its own connection via :func:`database.db.get_db`, closes
it before returning, and scopes every ``expenses`` query to a single ``user_id``
with a parameterised placeholder.
"""

from datetime import datetime

from database.db import get_db


def _date_clause(start, end):
    """Build an ``AND date >= ? AND date <= ?`` fragment for the bounds given.

    Either bound may be ``None`` (open). Returns ``(sql_fragment, params)`` where
    ``params`` lines up with the placeholders in ``sql_fragment``.
    """
    clause, params = "", []
    if start:
        clause += " AND date >= ?"
        params.append(start)
    if end:
        clause += " AND date <= ?"
        params.append(end)
    return clause, params


def get_user_by_id(user_id):
    """Return ``{"name", "email", "member_since"}`` for ``user_id`` or ``None``.

    ``member_since`` is ``users.created_at`` formatted as ``"Month YYYY"``
    (e.g. ``"March 2025"``). Falls back to ``"—"`` if ``created_at`` is
    missing or unparseable.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    created_at = row["created_at"]
    try:
        member_since = datetime.strptime(created_at[:7], "%Y-%m").strftime("%B %Y")
    except (TypeError, ValueError):
        member_since = "—"

    return {"name": row["name"], "email": row["email"], "member_since": member_since}


def get_summary_stats(user_id, start=None, end=None):
    """Return ``{"total_spent", "transaction_count", "top_category"}`` for the user.

    ``start`` / ``end`` are optional inclusive ``YYYY-MM-DD`` bounds. Empty
    account (or empty window) -> ``{"total_spent": 0, "transaction_count": 0,
    "top_category": "—"}``.
    """
    date_sql, date_params = _date_clause(start, end)
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS total "
            f"FROM expenses WHERE user_id = ?{date_sql}",
            (user_id, *date_params),
        ).fetchone()
        top = conn.execute(
            f"SELECT category FROM expenses WHERE user_id = ?{date_sql} "
            "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            (user_id, *date_params),
        ).fetchone()
    finally:
        conn.close()

    cnt = int(totals["cnt"])
    if cnt == 0:
        return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}

    return {
        "total_spent": totals["total"],
        "transaction_count": cnt,
        "top_category": top["category"],
    }


def get_recent_transactions(user_id, limit=10, start=None, end=None):
    """Return the user's ``limit`` most recent expenses, newest first.

    ``start`` / ``end`` are optional inclusive ``YYYY-MM-DD`` bounds. Each item
    is ``{"date", "description", "category", "amount"}``. No rows -> ``[]``.
    """
    date_sql, date_params = _date_clause(start, end)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            f"WHERE user_id = ?{date_sql} "
            "ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *date_params, limit),
        ).fetchall()
    finally:
        conn.close()

    return [dict(row) for row in rows]


def get_category_breakdown(user_id, start=None, end=None):
    """Return per-category spend for the user, largest first.

    ``start`` / ``end`` are optional inclusive ``YYYY-MM-DD`` bounds. Each item
    is ``{"name", "amount", "pct", "width"}`` where ``pct`` values are integers
    summing to 100 and ``width`` is ``pct`` snapped to the nearest 10 (min 10,
    max 100) for the ``.w-*`` CSS meter classes. No rows -> ``[]``.
    """
    date_sql, date_params = _date_clause(start, end)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category AS name, SUM(amount) AS amount FROM expenses "
            f"WHERE user_id = ?{date_sql} "
            "GROUP BY category ORDER BY SUM(amount) DESC, category ASC",
            (user_id, *date_params),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    total = sum(r["amount"] for r in rows)
    pcts = [round(r["amount"] / total * 100) for r in rows]

    diff = 100 - sum(pcts)
    pcts[0] += diff

    result = []
    for r, pct in zip(rows, pcts):
        width = min(100, max(10, round(pct / 10) * 10))
        result.append(
            {"name": r["name"], "amount": r["amount"], "pct": int(pct), "width": int(width)}
        )
    return result
