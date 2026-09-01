# Spec: Registration

## Overview
Turn the existing static `/register` page into a working sign-up flow. Today
`GET /register` renders `register.html` (name / email / password form) but the
form submission goes nowhere. This step makes `POST /register` validate the
submitted fields, hash the password with werkzeug, insert a row into the `users`
table, and send the new user to the login page. It is the first feature that
writes user data, and it unblocks Step 3 (login / logout), which needs real
accounts to authenticate against.

## Depends on
- **Step 1 — Database Setup** (merged to `main`): `database/db.py` provides
  `get_db()`, `init_db()`, `seed_db()` and the `users` table
  (`id`, `name`, `email` UNIQUE, `password_hash`, `created_at`). No session
  handling exists yet — that is Step 3, not this step.

## Routes
- `GET /register` — render the sign-up form — public *(already exists; keep)*
- `POST /register` — validate input, create the user, redirect to `/login` on
  success or re-render the form with an error — public *(new: same view function,
  add `methods=["GET", "POST"]`)*

No other new routes.

## Database changes
No database changes. The `users` table from Step 1 already has every column this
feature needs, including the `UNIQUE` constraint on `email`.

## Templates
- **Create:** none.
- **Modify:**
  - `templates/register.html` — no structural change required; it already renders
    `{% if error %}<div class="auth-error">`. Optionally re-populate `name` /
    `email` via a `form` dict on validation errors so the user does not retype
    them.
  - `templates/login.html` — render a one-time success notice
    (`get_flashed_messages`) so the redirect after sign-up confirms the account
    was created.

## Files to change
- `app.py` — allow `POST` on the `register` view; add server-side validation,
  password hashing, the `INSERT`, duplicate-email handling, and the redirect.
  Add `app.secret_key` (needed for `flash()`); read it from the environment with
  a dev fallback.
- `templates/register.html` — see Templates.
- `templates/login.html` — see Templates.
- `static/css/style.css` — add an `.auth-success` block mirroring `.auth-error`
  (uses `--accent` / `--accent-light`), placed next to `.auth-error`.

## Files to create
- None. (`.claude/specs/02-registration.md` is this spec.)

## New dependencies
No new dependencies. `werkzeug` is already pinned in `requirements.txt` and
`generate_password_hash` is already imported in `database/db.py`.

## Rules for implementation
- No SQLAlchemy or ORMs — use `get_db()` and raw `sqlite3`.
- Parameterised queries only — never f-string / `%` SQL.
- Passwords hashed with `werkzeug.security.generate_password_hash`; never store
  or log the raw password.
- Use CSS variables from `:root` — never hardcode hex values in new CSS.
- All templates extend `base.html` and use `{% block content %}`; use
  `url_for()` for routes and static assets.
- Validation is server-side even though the form has `required`:
  - all three fields present and non-empty after `.strip()`
  - `email` contains an `@` and a `.` (keep it simple — no regex library)
  - `password` at least 8 characters (matches the "Min. 8 characters" hint)
- Normalise `email` to lowercase and `.strip()` name / email before storing.
- Duplicate email: catch `sqlite3.IntegrityError` (or pre-check with a
  parameterised `SELECT`) and re-render the form with a friendly error — do not
  500.
- On success: `flash(...)` a confirmation and `redirect(url_for("login"))` —
  Post/Redirect/Get, no auto-login (sessions arrive in Step 3).
- Keep the commit lowercase and narrowly scoped, e.g.
  `registration: handle POST /register and create users`.

## Definition of done
Run `python app.py` (port 5001) and verify:
- [ ] `GET /register` still renders the form unchanged.
- [ ] Submitting valid new details redirects to `/login`, which shows a success
      message; a new row exists in `users` with a `pbkdf2:`/`scrypt:` style
      `password_hash` (not the plaintext).
- [ ] Submitting an email that already exists (e.g. `demo@spendly.com` from the
      seed data) re-renders `/register` with a visible error and creates no row.
- [ ] Submitting a blank field, a malformed email, or a < 8-char password
      re-renders `/register` with a visible error and creates no row.
- [ ] Password is verifiable: `check_password_hash(row["password_hash"], "...")`
      returns `True` for the submitted password.
- [ ] No hardcoded hex colours added to `style.css`; `.auth-success` uses
      `var(--...)` tokens.
- [ ] `pytest` still collects/passes (no tests required by this step, but nothing
      breaks).
