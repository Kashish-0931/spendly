# Spec: Edit Expense

## Overview
Step 8 turns the `/expenses/<id>/edit` stub (`"Edit expense — coming in Step 8"`)
into a working form that lets a logged-in user change an expense they already
recorded. Step 7 gave users a way to create rows in the `expenses` table; this
step is the first that lets them correct one — a wrong amount, the wrong
category, a typo in the description, or a mis-picked date. `GET
/expenses/<id>/edit` looks the expense up (scoped to the current user) and
renders a pre-filled form; `POST /expenses/<id>/edit` re-validates every field
with the same server-side rules as add-expense, updates that one row in place,
flashes a confirmation, and redirects to `/profile` where the corrected values
show up immediately in the summary tiles, recent-transactions table, and
category breakdown. Recent transactions on `/profile` gains a per-row **Edit**
link so the feature is reachable. It shares the delete-expense dependency
(Step 9) on user-owned rows but does not block it.

## Depends on
- **Step 1 — Database Setup** (merged): `database/db.py` provides `get_db()` and
  the `expenses` table (`id`, `user_id` FK, `amount` REAL, `category` TEXT,
  `date` TEXT `YYYY-MM-DD`, `description` TEXT nullable, `created_at`). The fixed
  `CATEGORIES` list also lives in `database/db.py`.
- **Step 3 — Login / Logout** (merged): `session["user_id"]` identifies the
  current user and is required to reach this route.
- **Step 5 — Profile backend** (merged): `database/queries.py` holds the
  read helpers; `get_recent_transactions` is extended here to also return each
  row's `id` so the profile table can link to the edit route.
- **Step 7 — Add Expense** (merged): supplies the `add_expense.html` form
  furniture this template mirrors and the validation rules this step reuses.
  There is no edit target without user-created rows.

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the
  expense's current values — logged-in only (redirect to `/login` with a flash if
  not authenticated). If no `expenses` row has that `id` **and** `user_id =
  session["user_id"]`, respond `404` (a user must not be able to see or probe
  another user's expense). *(replaces the current stub; add
  `methods=["GET", "POST"]`)*
- `POST /expenses/<int:id>/edit` — re-validate input, `UPDATE` that one row
  (scoped to `id` **and** the current `user_id`), flash a confirmation and
  redirect to `/profile` on success; re-render the form with an error message and
  the submitted values on failure (HTTP 200). Same `404` rule as the `GET` when
  the row is not owned by the current user — logged-in only.

No other new routes.

## Database changes
No database changes. The `expenses` table from Step 1 already has every column
this feature touches. The update only ever writes `amount`, `category`, `date`,
and `description`; `id`, `user_id`, and `created_at` are never modified.

## Templates
- **Create:** `templates/edit_expense.html`
  - Extends `base.html`, uses `{% block content %}`.
  - Same auth-form furniture as `add_expense.html`: `.auth-section` >
    `.auth-container` > `.auth-header` (title "Edit expense", subtitle
    "Track every rupee you spend") + `.auth-card` containing the form.
  - `<form method="POST" action="{{ url_for('edit_expense', id=expense.id) }}">`
    with the same four `.form-group` blocks as add-expense (Amount `type=number`
    `step="0.01"` `min="0.01"`; Category `<select>` with one `<option>` per
    `categories` entry; Date `type=date` `max="{{ today }}"`; Description
    `type=text` `maxlength="200"`, not required).
  - Every field is pre-populated from a `form` dict (`form.amount`,
    `form.category`, `form.date`, `form.description`) — populated from the stored
    expense on `GET`, and from the submitted values on a failed `POST` re-render,
    so the two paths use one code path in the template.
  - `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}` above the
    form (same placement as `add_expense.html`).
  - Submit button: `<button type="submit" class="btn-submit">Save changes</button>`.
- **Modify:** `templates/profile.html`
  - In the **Recent transactions** table, add a final `<th></th>` header cell and
    a final `<td>` per row containing
    `<a href="{{ url_for('edit_expense', id=tx.id) }}" class="profile-table-action">Edit</a>`.
    This relies on `tx.id` being present (see `database/queries.py` change).
  - No other change to the table or the panels.

## Files to change
- `app.py`
  - Replace the `edit_expense` stub with a `GET`/`POST` view
    (`@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])`).
  - Auth guard identical to `add_expense()`: no `session["user_id"]` →
    `flash("Please sign in to edit an expense.")` + `redirect(url_for("login"))`;
    then the `get_user_by_id(user_id) is None` stale-session check, same as
    `add_expense()`.
  - Load the row with a parameterised
    `SELECT id, amount, category, date, description FROM expenses
    WHERE id = ? AND user_id = ?`; if `None`, `abort(404)`.
  - `GET`: render `edit_expense.html` with `expense=<row>`, `categories=CATEGORIES`,
    `today=date.today().isoformat()`, and `form` seeded from the row
    (`amount` formatted so the number input shows a clean value, `date` as the
    stored `YYYY-MM-DD` string, `description` or `""`).
  - `POST`: run the **same** server-side validation as `add_expense` (see Rules);
    on success, parameterised
    `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ?
    WHERE id = ? AND user_id = ?` via `get_db()` inside a `with conn:` block,
    then `conn.close()`, `flash("Expense updated.")`,
    `redirect(url_for("profile"))`. On failure, re-render `edit_expense.html`
    with `error`, `expense`, `categories`, `today`, and the submitted `form`
    values, HTTP 200.
  - Add `abort` to the `flask` import if not already present.
  - Factor the amount/category/date/description validation shared with
    `add_expense` into a small module-level helper
    (e.g. `_validate_expense_form(form) -> (fields, error)`) and call it from both
    views, so the two routes cannot drift. Keep it in `app.py` next to
    `MAX_AMOUNT` / `MAX_DESCRIPTION`.
- `database/queries.py`
  - `get_recent_transactions`: add `id` to the `SELECT` column list
    (`SELECT id, date, description, category, amount ...`) so each returned dict
    carries the expense `id`. Ordering, bounds handling, and the return shape
    (list of dicts) are otherwise unchanged.
- `templates/profile.html` — add the Edit column (see Templates).
- `static/css/style.css` — add a `.profile-table-action` rule for the Edit link
  (small, uses `var(--accent)` / existing link tokens, no new colour literals).
  Extend the existing responsive `.profile-panels .profile-table td:last-child`
  handling if the extra cell needs it.

## Files to create
- `templates/edit_expense.html` (see Templates).
- `.claude/specs/08-edit-expense.md` — this spec.

## New dependencies
No new dependencies. Uses the standard-library `datetime` and `sqlite3` modules
and the already-pinned Flask / werkzeug.

## Rules for implementation
- No SQLAlchemy or ORMs — `get_db()` and raw `sqlite3` only.
- Parameterised queries only — every value in the `SELECT` lookup and the
  `UPDATE` (including `id` and `user_id`) is a `?` placeholder, never
  string-formatted into the SQL.
- Passwords hashed with werkzeug — no auth changes in this step, but the auth
  guard must match the existing `add_expense()` pattern exactly.
- Use CSS variables — never hardcode hex values in new CSS; reuse the auth-form,
  `.profile-table`, and `:root` tokens.
- All templates extend `base.html`; use `url_for()` for the form action, the
  profile Edit link, and any assets.
- Currency stays ₹; the amount label and confirmation copy use rupees.
- Ownership is enforced on **every** path: the `GET` lookup, the `POST` lookup,
  and the `UPDATE` all filter on `id = ? AND user_id = session["user_id"]`.
  `user_id` is never read from the form or the URL. A row that does not belong to
  the current user is a `404`, not a redirect and not a 403 with detail.
- Validation is server-side and identical to Step 7 (shared helper):
  - **amount** — present; parses as `float`; strictly `> 0`; reject `NaN` /
    `inf`; round to 2 decimals before storing; reject `>= 10_000_000`.
  - **category** — must be exactly one of `database.db.CATEGORIES`.
  - **date** — present; parses as ISO `YYYY-MM-DD` via
    `datetime.strptime`; not in the future. Stored as the normalised string.
  - **description** — optional; `.strip()`; empty → SQL `NULL` (`None`); over
    200 chars is rejected with an error.
- One combined, friendly `error` string on the first failed check (mirrors
  `add_expense`). Bad input never 500s and always re-renders with HTTP 200.
- Post/Redirect/Get: a successful `POST` ends in `redirect(url_for("profile"))`,
  not a rendered template.
- Connection handling like `add_expense()`: `conn = get_db()`, `with conn:` for
  the write, `finally: conn.close()`. The `GET`/`POST` row lookup closes its
  connection in a `finally` too.
- `created_at` is left untouched — the edit does not bump it.
- One lowercase, narrowly-scoped commit, e.g.
  `expenses: handle GET/POST /expenses/<id>/edit and update expense`.

## Definition of done
Run `python app.py` (port 5001), sign in as the seed user
(`demo@spendly.com` / `demo123`) and verify:
- [ ] `/profile` Recent transactions shows an **Edit** link on every row.
- [ ] Clicking Edit opens `/expenses/<id>/edit` with the amount, category, date,
      and description fields pre-filled with that expense's current values.
- [ ] Changing the amount (e.g. `480` → `525.50`) and submitting redirects to
      `/profile`, shows a flashed "Expense updated." banner, and the row now
      reads ₹525.50 with Total spent adjusted by +₹45.50 and the transaction
      count unchanged.
- [ ] Changing the category moves the row's badge and shifts the Category
      breakdown accordingly; clearing the description stores `NULL` (the cell
      renders empty), not `""`.
- [ ] Submitting amount `0`, a negative amount, a non-numeric amount, a blank
      amount, or a future date re-renders `/expenses/<id>/edit` with a visible
      error and leaves the stored row unchanged.
- [ ] Tampering the form to POST a category not in `CATEGORIES` (e.g. `Rent`)
      re-renders with a visible error and does not change the row.
- [ ] After a validation error, the values the user just typed are preserved in
      the re-rendered form.
- [ ] Visiting or POSTing `/expenses/<id>/edit` while logged out redirects to
      `/login` with a flash and changes nothing.
- [ ] Visiting `/expenses/<id>/edit` for an `id` that does not exist, or one that
      belongs to a different user, returns `404` — GET and POST alike.
- [ ] POSTing a `user_id` field in the body has no effect: the row keeps its
      original `user_id` and only the signed-in user's own row can be updated.
- [ ] `created_at` on the edited row is unchanged after the update.
- [ ] No hardcoded hex values added to `style.css`; `pytest` still collects and
      passes.
