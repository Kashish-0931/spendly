import database.db as db


def _register(client, **over):
    data = {"name": "Asha Rao", "email": "asha@example.com", "password": "rupees12"}
    data.update(over)
    return client.post("/register", data=data, follow_redirects=True)


def _user_count(email=None):
    conn = db.get_db()
    if email is None:
        n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    else:
        n = conn.execute(
            "SELECT COUNT(*) FROM users WHERE email = ?", (email,)
        ).fetchone()[0]
    conn.close()
    return n


def test_get_register_ok(client):
    assert client.get("/register").status_code == 200


def test_valid_registration_creates_user_and_lands_on_login(client):
    resp = _register(client)
    assert resp.status_code == 200
    assert b"Account created" in resp.data          # flashed on the login page
    assert b'action="/login"' in resp.data          # login form rendered

    conn = db.get_db()
    row = conn.execute(
        "SELECT name, email, password_hash FROM users WHERE email = ?",
        ("asha@example.com",),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["name"] == "Asha Rao"
    assert row["password_hash"] != "rupees12"

    from werkzeug.security import check_password_hash

    assert check_password_hash(row["password_hash"], "rupees12")


def test_email_is_normalised_to_lowercase(client):
    _register(client, email="Asha@Example.COM")
    assert _user_count("asha@example.com") == 1


def test_duplicate_email_rejected(client):
    _register(client)
    resp = _register(client, name="Someone Else")
    assert b"already exists" in resp.data
    assert _user_count("asha@example.com") == 1


def test_short_password_rejected(client):
    resp = _register(client, password="short")
    assert b"at least 8 characters" in resp.data
    assert _user_count() == 0


def test_missing_field_rejected(client):
    resp = _register(client, name="")
    assert b"fill in all fields" in resp.data
    assert _user_count() == 0


def test_malformed_email_rejected(client):
    resp = _register(client, email="not-an-email")
    assert b"valid email" in resp.data
    assert _user_count() == 0
