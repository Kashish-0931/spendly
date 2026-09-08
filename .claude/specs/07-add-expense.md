# Spec: Add Expense

## Overview
Step 7 turns the `/expenses/add` stub (`"Add expense — coming in Step 7"`) into
a working form that lets a logged-in user record a new expense. Until now every
expense in the app comes from `seed_db()`; this is the first feature that lets a
real user write their own spending data. `GET /expenses/add` renders a form
(amount, category, date, optional description); `POST /expenses/add` validates
the fields server-side, inserts one row into the `expenses` table scoped to the
current user, flashes a confirmation, and redirects to `/profile` where the new
row immediately shows up in the summary tiles, recent-transactions table, and
category breakdown. It unblocks Step 8 (edit expense) and Step 9 (delete
expense), which both need user-created rows to act on.

## Depends on
- **Step 1 — Database Setup** (merged): `database/db.py` provides `get_db()` and
  the `expenses` table (`id`, `user_id` FK, `amount` REAL, `category` TEXT,
  `date` TEXT `YYYY-MM-DD`, `description` TEXT nullable, `created_at`). The fixed
  `CATEGORIES` list also lives in `database/db.py`.
- **Step 3 — Login / Logout** (merged): `session["user_id"]` identifies the
  current user and is required to reach this route.
- **Step 5 — Profile backend** (merged): `database/queries.py` helpers render the
  new expense on `/profile` after the redirect — no change needed to them.

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only (redirect to
  `/login` with a flash if not authenticated). *(replaces the current stub; add
  `methods=["GET", "POST"]`)*
- `POST /expenses/add` — validate input, insert one `expenses` row for
  `session["user_id"]`, flash a confirmation and redirect to `/profile` on
  success; re-render the form with an error message and the submitted values on
  failure — logged-in only.

No other new routes.

## Database changes
No database changes. The `expenses` table from Step 1 already has every column
this feature needs. `created_at` defaults to `datetime('now')`; `id` is
autoincrement; `description` is nullable.

## Templates
- **Create:** `templates/add_expense.html`
  - Extends `base.html`, uses `{% block content %}`.
  - Reuses the existing auth-form furniture: `.auth-section` > `.auth-container`
    > `.auth-header` (title "Add an expense") + `.auth-card` containing the form.
  - `<form method="POST" action="{{ url_for('add_expense') }}">` with four
    `.form-group` blocks:
    - **Amount** — `<input type="number" name="amount" step="0.01" min="0.01"
      class="form-input" required autofocus>`, label shows the ₹ unit.
    - **Category** — `<select name="category" class="form-input" required>` with
      one `<option>` per entry in `categories` (passed from the view); no blank
      default selected option beyond a disabled placeholder.
    - **Date** — `<input type="date" name="date" class="form-input" required>`
      defaulting to today (`value="{{ today }}"`), `max="{{ today }}"`.
    - **Description** — `<input type="text" name="description" maxlength="200"
      class="form-input" placeholder="Optional note">` (not required).
  - `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}` above the
    form (same placement as `register.html`).
  - Submit button: `<button type="submit" class="btn-submit">Add expense</button>`.
  - On re-render after a validation error, each field is repopulated from a
    `form` dict (`form.amount`, `form.category`, `form.date`, `form.description`)
    so the user does not retype everything.
- **Modify:** `templates/base.html`
  - In the logged-in branch of `.nav-links`, add
    `<a href="{{ url_for('add_expense') }}" class="nav-link{% if request.endpoint == 'add_expense' %} nav-link--active{% endif %}">Add expense</a>`
    before the Analytics link, so the route is reachable from every page.

## Files to change
- `app.py`
  - Replace the `add_expense` stub with a `GET`/`POST` view.
  - `from database.db import CATEGORIES` (alongside the existing `db` imports).
  - Auth guard identical to `profile()`: no `session["user_id"]` →
    `flash("Please sign in to add an expense.")` + `redirect(url_for("login"))`.
  - `GET`: render `add_expense.html` with `categories=CATEGORIES` and
    `today=date.today().isoformat()`.
  - `POST`: server-side validation (see Rules); on success, parameterised
    `INSERT INTO expenses (user_id, amount, category, date, description) VALUES
    (?, ?, ?, ?, ?)` via `get_db()` inside a `with conn:` block, then
    `conn.close()`, `flash("Expense added.")`, `redirect(url_for("profile"))`.
    On failure, re-render `add_expense.html` with `error`, `categories`, `today`,
    and the submitted `form` values, HTTP 200.
  - Add `from datetime import date` (module currently imports only `os`,
    `sqlite3`).
- `templates/base.html` — add the nav link (see Templates).
- `static/css/style.css` — only if needed: a `select.form-input` rule so the
  native select matches `.form-input` height/appearance, using existing tokens
  (`var(--paper)`, `var(--border)`, `var(--ink)`). No new colour literals.

## Files to create
- `templates/add_expense.html` (see Templates).
- `.claude/specs/07-add-expense.md` — this spec.

## New dependencies
No new dependencies. Uses the standard-library `datetime` and `sqlite3` modules
and the already-pinned Flask / werkzeug.

## Rules for implementation
- No SQLAlchemy or ORMs — `get_db()` and raw `sqlite3` only.
- Parameterised queries only — every inserted value is a `?` placeholder, never
  string-formatted into the SQL.
- Passwords hashed with werkzeug — no auth changes in this step, but the auth
  guard must match the existing `profile()` pattern exactly.
- Use CSS variables — never hardcode hex values in new CSS; reuse the auth-form
  and `:root` tokens.
- All templates extend `base.html`; use `url_for()` for the form action, nav
  link, and any assets.
- Currency stays ₹; the amount label and confirmation copy use rupees.
- Validation is server-side even though the form fields are `required`:
  - **amount** — present; parses as `float`; strictly `> 0`; reject `NaN` /
    `inf`; round to 2 decimals before storing. Reject values `>= 10_000_000`
    (₹1 crore) as a sanity cap.
  - **category** — must be exactly one of `database.db.CATEGORIES`; anything else
    is rejected (do not trust the `<select>`).
  - **date** — present; parses as ISO `YYYY-MM-DD` via
    `datetime.strptime(value, "%Y-%m-%d")`; not in the future (`> date.today()`
    rejected). Stored as the normalised `YYYY-MM-DD` string.
  - **description** — optional; `.strip()`; empty → store SQL `NULL` (Python
    `None`); truncate/reject over 200 chars (reject with an error is fine).
- One combined, friendly `error` string on the first failed check is enough
  (mirrors `register()` which sets a single `error`). Bad input never 500s and
  always re-renders with HTTP 200.
- The `INSERT` is always scoped to `session["user_id"]` — a user can only create
  expenses for themselves; `user_id` is never read from the form.
- Post/Redirect/Get: a successful `POST` ends in `redirect(url_for("profile"))`,
  not a rendered template.
- Keep the connection handling like `register()`: `conn = get_db()`, `with conn:`
  for the write, `finally: conn.close()`.
- One lowercase, narrowly-scoped commit, e.g.
  `expenses: handle POST /expenses/add and insert expense`.

## Definition of done
Run `python app.py` (port 5001), sign in as the seed user
(`demo@spendly.com` / `demo123`) and verify:
- [ ] `GET /expenses/add` renders a form with an amount field, a category
      dropdown listing all 7 categories (Food, Transport, Bills, Health,
      Entertainment, Shopping, Other), a date picker defaulting to today, and an
      optional description field.
- [ ] The nav bar shows an "Add expense" link for logged-in users that routes
      here; it is not shown when logged out.
- [ ] Submitting a valid expense (e.g. amount `250`, category `Food`, today's
      date, description "Lunch") redirects to `/profile`, shows a flashed
      "Expense added." banner, and the new row appears in Recent transactions
      with the total spent increased by ₹250.00 and the transaction count +1.
- [ ] The stored `amount` is a number rounded to 2 decimals; the stored `date`
      is `YYYY-MM-DD`; an omitted description is stored as `NULL`, not `""`.
- [ ] Submitting amount `0`, a negative amount, a non-numeric amount, or a blank
      amount re-renders `/expenses/add` with a visible error and inserts no row.
- [ ] Submitting a future date re-renders with a visible error and inserts no
      row.
- [ ] Tampering the form to POST a category not in `CATEGORIES` (e.g. `Rent`)
      re-renders with a visible error and inserts no row.
- [ ] After a validation error, the fields the user already filled are
      preserved in the re-rendered form.
- [ ] Visiting `/expenses/add` while logged out redirects to `/login` with a
      flash; POSTing while logged out also redirects and inserts no row.
- [ ] The created row's `user_id` equals the signed-in user's id regardless of
      any `user_id` field injected into the POST body.
- [ ] No hardcoded hex values added to `style.css`; `pytest` still collects and
      passes.
