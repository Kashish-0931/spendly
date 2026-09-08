import os
import sqlite3
from datetime import date, datetime

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database.date_range import resolve_range
from database.db import CATEGORIES, get_db, init_db, seed_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-insecure-change-me")


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            error = "Please fill in all fields."
        elif "@" not in email or "." not in email:
            error = "Please enter a valid email address."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        else:
            error = None

        if error:
            return render_template("register.html", error=error, name=name, email=email)

        conn = get_db()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password)),
                )
        except sqlite3.IntegrityError:
            return render_template(
                "register.html",
                error="An account with that email already exists.",
                name=name,
                email=email,
            )
        finally:
            conn.close()

        flash("Account created — please sign in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template(
                "login.html",
                error="Please enter your email and password.",
                email=email,
            )

        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()
        finally:
            conn.close()

        if row is None or not check_password_hash(row["password_hash"], password):
            return render_template(
                "login.html",
                error="Incorrect email or password.",
                email=email,
            )

        session["user_id"] = row["id"]
        flash("Signed in.")
        return redirect(url_for("landing"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("You have been logged out.")
    return redirect(url_for("login"))


@app.context_processor
def inject_current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return {"current_user": None}

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    return {"current_user": user}


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please sign in to view your profile.")
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
        session.pop("user_id", None)
        flash("Please sign in to view your profile.")
        return redirect(url_for("login"))

    start, end, range_label = resolve_range(
        request.args.get("start"),
        request.args.get("end"),
        request.args.get("range"),
    )

    return render_template(
        "profile.html",
        member_since=user["member_since"],
        summary=get_summary_stats(user_id, start=start, end=end),
        transactions=get_recent_transactions(user_id, start=start, end=end),
        categories=get_category_breakdown(user_id, start=start, end=end),
        filter_start=start,
        filter_end=end,
        range_label=range_label,
        filter_active=bool(start or end),
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        flash("Please sign in to view analytics.")
        return redirect(url_for("login"))

    return render_template("analytics.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Expenses                                                            #
# ------------------------------------------------------------------ #

MAX_AMOUNT = 10_000_000  # ₹1 crore sanity cap
MAX_DESCRIPTION = 200


def _validate_expense_form(form):
    """Validate a submitted expense form dict (``amount``/``category``/``date``/
    ``description``, all pre-stripped strings).

    Returns ``(fields, error)``. On success ``error`` is ``None`` and ``fields``
    is a dict normalised for storage: ``amount`` rounded to 2 decimals,
    ``date`` as a ``YYYY-MM-DD`` string, ``description`` ``None`` when blank.
    On failure ``fields`` is ``None`` and ``error`` is a friendly message.
    """
    try:
        amount = round(float(form["amount"]), 2)
    except (TypeError, ValueError):
        amount = None

    if amount is None or amount != amount or amount in (float("inf"), float("-inf")):
        return None, "Enter a valid amount."
    if amount <= 0:
        return None, "Amount must be greater than zero."
    if amount >= MAX_AMOUNT:
        return None, "That amount looks too large."
    if form["category"] not in CATEGORIES:
        return None, "Choose a category from the list."
    if len(form["description"]) > MAX_DESCRIPTION:
        return None, f"Description must be {MAX_DESCRIPTION} characters or fewer."

    try:
        parsed_date = datetime.strptime(form["date"], "%Y-%m-%d").date()
    except ValueError:
        return None, "Enter a valid date."
    if parsed_date > date.today():
        return None, "The date cannot be in the future."

    return {
        "amount": amount,
        "category": form["category"],
        "date": parsed_date.isoformat(),
        "description": form["description"] or None,
    }, None


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please sign in to add an expense.")
        return redirect(url_for("login"))

    if get_user_by_id(user_id) is None:
        session.pop("user_id", None)
        flash("Please sign in to add an expense.")
        return redirect(url_for("login"))

    today = date.today().isoformat()

    if request.method == "POST":
        form = {
            "amount": request.form.get("amount", "").strip(),
            "category": request.form.get("category", "").strip(),
            "date": request.form.get("date", "").strip(),
            "description": request.form.get("description", "").strip(),
        }

        fields, error = _validate_expense_form(form)
        if error:
            return render_template(
                "add_expense.html",
                error=error,
                categories=CATEGORIES,
                today=today,
                form=form,
            )

        conn = get_db()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO expenses (user_id, amount, category, date, description) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        user_id,
                        fields["amount"],
                        fields["category"],
                        fields["date"],
                        fields["description"],
                    ),
                )
        finally:
            conn.close()

        flash("Expense added.")
        return redirect(url_for("profile"))

    return render_template(
        "add_expense.html",
        categories=CATEGORIES,
        today=today,
        form={"date": today},
    )


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Please sign in to edit an expense.")
        return redirect(url_for("login"))

    if get_user_by_id(user_id) is None:
        session.pop("user_id", None)
        flash("Please sign in to edit an expense.")
        return redirect(url_for("login"))

    today = date.today().isoformat()

    conn = get_db()
    try:
        expense = conn.execute(
            "SELECT id, amount, category, date, description FROM expenses "
            "WHERE id = ? AND user_id = ?",
            (id, user_id),
        ).fetchone()
    finally:
        conn.close()

    if expense is None:
        abort(404)

    if request.method == "POST":
        form = {
            "amount": request.form.get("amount", "").strip(),
            "category": request.form.get("category", "").strip(),
            "date": request.form.get("date", "").strip(),
            "description": request.form.get("description", "").strip(),
        }

        fields, error = _validate_expense_form(form)
        if error:
            return render_template(
                "edit_expense.html",
                error=error,
                expense=expense,
                categories=CATEGORIES,
                today=today,
                form=form,
            )

        conn = get_db()
        try:
            with conn:
                conn.execute(
                    "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? "
                    "WHERE id = ? AND user_id = ?",
                    (
                        fields["amount"],
                        fields["category"],
                        fields["date"],
                        fields["description"],
                        id,
                        user_id,
                    ),
                )
        finally:
            conn.close()

        flash("Expense updated.")
        return redirect(url_for("profile"))

    form = {
        "amount": f"{expense['amount']:.2f}",
        "category": expense["category"],
        "date": expense["date"],
        "description": expense["description"] or "",
    }
    return render_template(
        "edit_expense.html",
        expense=expense,
        categories=CATEGORIES,
        today=today,
        form=form,
    )


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


# ------------------------------------------------------------------ #
# Startup — ensure the database schema and demo data are ready        #
# ------------------------------------------------------------------ #

with app.app_context():
    init_db()
    seed_db()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
