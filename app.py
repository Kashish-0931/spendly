import os
import sqlite3

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

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
    if not session.get("user_id"):
        flash("Please sign in to view your profile.")
        return redirect(url_for("login"))

    member_since = "March 2025"  # hardcoded — Step 5 replaces with users.created_at

    summary = {
        "total_spent": 8188,
        "transaction_count": 5,
        "top_category": "Food",
    }

    transactions = [
        {"date": "2026-08-28", "description": "Groceries from the local kirana store", "category": "Food", "amount": 480},
        {"date": "2026-08-25", "description": "Auto rickshaw to office", "category": "Transport", "amount": 60},
        {"date": "2026-08-22", "description": "Electricity bill for the month", "category": "Bills", "amount": 1250},
        {"date": "2026-08-18", "description": "New pair of running shoes", "category": "Shopping", "amount": 1899},
        {"date": "2026-08-14", "description": "OTT subscription renewal", "category": "Entertainment", "amount": 299},
    ]

    categories = [
        {"name": "Food", "amount": 4200, "percent": 70},
        {"name": "Shopping", "amount": 1899, "percent": 40},
        {"name": "Bills", "amount": 1250, "percent": 30},
        {"name": "Transport", "amount": 600, "percent": 15},
        {"name": "Entertainment", "amount": 299, "percent": 10},
    ]

    return render_template(
        "profile.html",
        member_since=member_since,
        summary=summary,
        transactions=transactions,
        categories=categories,
    )


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


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
