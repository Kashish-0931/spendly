# Spec: Login and Logout

## Overview
Give Spendly real authentication. Today `GET /login` renders `login.html` but the
form submission goes nowhere, and `GET /logout` returns the placeholder string
`"Logout — coming in Step 3"`. This step makes `POST /login` look the user up by
email, verify the submitted password against the stored werkzeug hash, and record
the authenticated user in a Flask `session`. `GET /logout` clears that session.
The navbar becomes session-aware: signed-out visitors see "Sign in / Get started"
as now, signed-in users see their name and a "Log out" link. This is the first
feature that establishes who the current user is, and it unblocks every later
step (profile, expense CRUD, dashboard) that must scope data to `session["user_id"]`.

## Depends on
- **Step 1 — Database Setup** (merged to `main`): `database/db.py` provides
  `get_db()` and the `users` table with `id`, `email` (UNIQUE), `password_hash`.
- **Step 2 — Registration** (merged to `main`): `POST /register` creates real
  users with `generate_password_hash` and redirects to `/login`. Without it there
  are no non-seed accounts to sign in with. `app.secret_key` is already set in
  `app.py` (added in Step 2 for `flash()`) and is reused here to sign the session
  cookie.

## Routes
- `GET /login` — render the sign-in form — public *(already exists; keep)*
- `POST /login` — validate input, look the user up by email, verify the password
  hash, set `session["user_id"]` and redirect to `/` on success; re-render the
  form with a generic error on failure — public *(new: same view function, add
  `methods=["GET", "POST"]`)*
- `GET /logout` — clear the session and redirect to `/login` with a flashed
  confirmation — public (safe to hit when already signed out) *(replaces the
  `"coming in Step 3"` placeholder)*

No other new routes. Do **not** implement `/profile` or any `/expenses/*` stub in
this step.

## Database changes
No database changes. The `users` table from Step 1 already has `id`, `email`, and
`password_hash`, which is everything login needs.

## Templates
- **Create:** none.
- **Modify:**
  - `templates/base.html` — make the `.nav-links` block conditional on the
    current user (exposed via a context processor, see Files to change). Signed
    out: keep the existing "Sign in" link and "Get started" CTA. Signed in: show
    the user's name (or email) and a "Log out" link to `url_for('logout')`.
  - `templates/login.html` — point the form at `url_for('login')` instead of the
    hardcoded `action="/login"`; keep the method `POST`. Re-populate the `email`
    field from a passed-back value on a failed attempt so the user does not
    retype it. The existing `{% if error %}` and `get_flashed_messages()` blocks
    already cover error and logout-confirmation display — no new markup needed.

## Files to change
- `app.py`
  - Import `session` from `flask` and `check_password_hash` from
    `werkzeug.security`.
  - `login` view: allow `POST`; read `email` (lowercased, stripped) and
    `password`; if either is blank re-render with an error; otherwise
    `SELECT id, password_hash FROM users WHERE email = ?`; if no row or
    `check_password_hash` fails, re-render with a single generic error
    (`"Incorrect email or password."`) and the entered `email`; on success set
    `session["user_id"] = row["id"]`, `flash("Signed in.")`, and
    `redirect(url_for("landing"))`.
  - `logout` view: `session.pop("user_id", None)` (or `session.clear()`),
    `flash("You have been logged out.")`, `redirect(url_for("login"))`.
  - Add a `@app.context_processor` that returns `current_user` — `None` when
    there is no `session["user_id"]`, otherwise the user row fetched with a
    parameterised `SELECT id, name, email FROM users WHERE id = ?`. This is what
    `base.html` uses to decide which nav to show.
- `templates/base.html` — see Templates.
- `templates/login.html` — see Templates.
- `static/css/style.css` — only if needed: a small rule to align the signed-in
  nav name/label with the existing links. Reuse existing nav classes and
  `var(--...)` tokens; add nothing if the current styles already look right.

## Files to create
- None. (`.claude/specs/03-login-logout.md` is this spec.)

## New dependencies
No new dependencies. `check_password_hash` ships with `werkzeug`, already pinned
in `requirements.txt`.

## Rules for implementation
- No SQLAlchemy or ORMs — use `get_db()` and raw `sqlite3`; close the connection.
- Parameterised queries only — never f-string / `%` SQL.
- Verify passwords with `werkzeug.security.check_password_hash`; never store or
  log the raw password, and never put the password in a template variable.
- Do **not** reveal whether the email exists — use one generic
  `"Incorrect email or password."` message for both "no such user" and "wrong
  password".
- Normalise `email` with `.strip().lower()` before the lookup (registration
  stores it lowercased).
- Session only — store `session["user_id"]` (an int), nothing else; no
  `remember me`, no custom cookies, no Flask-Login.
- Post/Redirect/Get: a successful login and logout both end in a `redirect`, not
  a rendered template.
- `GET /logout` must not error when no one is signed in — pop with a default.
- Use CSS variables from `:root` — never hardcode hex values in new CSS.
- All templates extend `base.html` and use `url_for()` for routes and static
  assets.
- Only touch what this spec lists. Leave `/profile` and the `/expenses/*` stubs
  returning their placeholder strings.
- Keep the commit lowercase and narrowly scoped, e.g.
  `login: authenticate POST /login and manage the session`.

## Definition of done
Run `python app.py` (port 5001) and verify:
- [ ] `GET /login` still renders the form unchanged; `GET /logout` no longer
      shows `"coming in Step 3"`.
- [ ] Signing in with the seeded demo account (`demo@spendly.com` / `demo123`)
      redirects to `/`, shows a "Signed in." flash, and the navbar now shows the
      user's name and a "Log out" link instead of "Sign in / Get started".
- [ ] A wrong password, an unknown email, and a blank field each re-render
      `/login` with the generic `"Incorrect email or password."` (or
      fill-in-the-fields) error and do **not** create a session.
- [ ] The failed-attempt form keeps the entered email pre-filled.
- [ ] Clicking "Log out" clears the session, redirects to `/login` with the
      logout confirmation flash, and the navbar returns to "Sign in / Get
      started".
- [ ] Registering a brand-new account (Step 2 flow) then signing in with those
      credentials works end to end.
- [ ] Email matching is case-insensitive: `DEMO@Spendly.com` signs in fine.
- [ ] No hardcoded hex colours added to `style.css`.
- [ ] `pytest` still passes — the existing `tests/test_registration.py` suite is
      unaffected.
