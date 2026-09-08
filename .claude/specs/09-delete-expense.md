# Spec: Delete Expense

## Overview
Step 9 turns the `/expenses/<id>/delete` stub (`"Delete expense — coming in
Step 9"`) into a working action that lets a logged-in user permanently remove an
expense they recorded. Step 7 let users create rows in the `expenses` table and
Step 8 let them correct one; this step closes the loop by letting them delete one
outright — a duplicate entry, a purchase that was refunded, or a row added by
mistake. The Recent transactions table on `/profile` already carries a per-row
**Edit** link (Step 8); this step adds a **Delete** control beside it. The
control is a small `POST` form (deletion must never happen on a `GET`), guarded
by a browser confirmation prompt wired up in `static/js/main.js`. On submit the
route re-checks ownership, deletes that one row, flashes a confirmation, and
redirects to `/profile`, where the summary tiles, recent-transactions table, and
category breakdown all reflect the removal immediately.

## Depends on
- **Step 1 — Database Setup** (merged): `database/db.py` provides `get_db()` and
  the `expenses` table (`id`, `user_id` FK, `amount`, `category`, `date`,
  `description`, `created_at`).
- **Step 3 — Login / Logout** (merged): `session["user_id"]` identifies the
  current user and is required to reach this route.
- **Step 5 — Profile backend** (merged): `database/queries.py::get_recent_transactions`
  returns each row's `id`, which the profile table needs to target a row for
  deletion.
- **Step 7 — Add Expense** (merged): there is nothing to delete without
  user-created rows.
- **Step 8 — Edit Expense** (merged): supplies the actions `<td>` in the profile
  Recent transactions table and the `.profile-table-action` link style this step
  sits next to and reuses.

## Routes
- `POST /expenses/<int:id>/delete` — delete the expense with that `id`
  **and** `user_id = session["user_id"]`, flash `"Expense deleted."`, and
  redirect to `/profile` — logged-in only (redirect to `/login` with a flash if
  not authenticated, same as `add_expense` / `edit_expense`). If no `expenses`
  row matches both `id` and the current `user_id`, respond `404` (a user must not
  be able to delete — or probe for — another user's expense).
  *(replaces the current stub; change the decorator to
  `methods=["POST"]`.)*
- The route does **not** accept `GET`. A `GET /expenses/<id>/delete` returns
  Flask's default `405 Method Not Allowed`, so the link cannot be triggered by
  prefetch, a crawler, or an accidental navigation.

No other new routes.

## Database changes
No database changes. The delete is a single parameterised
`DELETE FROM expenses WHERE id = ? AND user_id = ?`. `expenses` is the child side
of the `user_id` foreign key, so removing a row has no cascade or referential
consequences. No other table or row is touched.

## Templates
- **Create:** none.
- **Modify:** `templates/profile.html`
  - In the **Recent transactions** table, the existing actions `<td>` currently
    holds a single Edit link. Wrap the Edit link and a new delete form in one
    container:
    ```jinja
    <td>
      <div class="profile-row-actions">
        <a href="{{ url_for('edit_expense', id=tx.id) }}" class="profile-table-action">Edit</a>
        <form method="POST" action="{{ url_for('delete_expense', id=tx.id) }}" class="profile-row-delete">
          <button type="submit"
                  class="profile-table-action profile-table-action--danger"
                  data-confirm="Delete this ₹{{ '%.2f'|format(tx.amount) }} expense? This can't be undone.">
            Delete
          </button>
        </form>
      </div>
    </td>
    ```
  - The `<th>` for the actions column already exists
    (`<th><span class="sr-only">Actions</span></th>`) — leave it as is.
  - No other change to the table or the panels.
- **Modify:** `static/js/main.js`
  - Add one delegated `submit` listener on `document`: if the submitter (or the
    form) carries a `data-confirm` attribute, call `window.confirm()` with that
    message and `event.preventDefault()` when the user cancels. Vanilla JS only,
    no libraries. The form still submits normally when JS is disabled — the
    server-side ownership check is the real guard; the prompt is a convenience.

## Files to change
- `app.py`
  - Replace the `delete_expense` stub with a real view:
    `@app.route("/expenses/<int:id>/delete", methods=["POST"])`.
  - Auth guard identical to `edit_expense()` / `add_expense()`: no
    `session["user_id"]` → `flash("Please sign in to delete an expense.")` +
    `redirect(url_for("login"))`; then the `get_user_by_id(user_id) is None`
    stale-session check with the same message and redirect.
  - Look the row up first with a parameterised
    `SELECT id FROM expenses WHERE id = ? AND user_id = ?`; if `None`,
    `abort(404)`.
  - Delete with a parameterised
    `DELETE FROM expenses WHERE id = ? AND user_id = ?` via `get_db()` inside a
    `with conn:` block, `conn.close()` in a `finally`.
  - `flash("Expense deleted.")`, then `redirect(url_for("profile"))`.
  - Move the view out of the "Placeholder routes" section (it is no longer a
    placeholder); place it after `edit_expense`.
- `templates/profile.html` — add the delete form to the actions cell (see
  Templates).
- `static/js/main.js` — add the `data-confirm` submit guard (see Templates).
- `static/css/style.css`
  - Add `.profile-row-actions` (flex row, small `gap`, `align-items: center`) so
    Edit and Delete sit side by side.
  - Add `.profile-row-delete` (`display: inline`, `margin: 0`) and
    `.profile-table-action--danger` — a button reset (`background: none;
    border: none; padding: 0; cursor: pointer; font: inherit;`) that renders like
    the existing `.profile-table-action` link but in `var(--danger)`.
  - Reuse existing `:root` tokens only. No new colour literals.

## Files to create
- `.claude/specs/09-delete-expense.md` — this spec.

## New dependencies
No new dependencies. Standard-library `sqlite3` and the already-pinned
Flask / werkzeug only.

## Rules for implementation
- No SQLAlchemy or ORMs — `get_db()` and raw `sqlite3` only.
- Parameterised queries only — `id` and `user_id` are always `?` placeholders in
  both the `SELECT` lookup and the `DELETE`, never string-formatted into SQL.
- Passwords hashed with werkzeug — no auth changes here, but the auth guard must
  match the existing `edit_expense()` / `add_expense()` pattern exactly.
- Use CSS variables — never hardcode hex values in new CSS. Use `var(--danger)`
  for the delete affordance and reuse the existing `.profile-table-action`
  sizing/weight.
- All templates extend `base.html`; use `url_for()` for the form `action`.
- Destructive action is `POST` only. The stub's `GET` behaviour is removed; the
  route must not delete anything on a `GET`.
- Ownership is enforced on every path: the lookup `SELECT` **and** the `DELETE`
  both filter on `id = ? AND user_id = session["user_id"]`. `user_id` is never
  read from the form or the URL. A row that is missing or owned by another user
  is a `404` — not a redirect, not a 403 with detail, not a silent no-op with a
  success flash.
- Post/Redirect/Get: a successful `POST` ends in
  `redirect(url_for("profile"))`, never a rendered template.
- Connection handling like the sibling views: `conn = get_db()`, `with conn:` for
  the write, `finally: conn.close()`. The lookup closes its connection in a
  `finally` too.
- Only the targeted row is removed. `created_at` and every other row and column
  are untouched.
- JavaScript is vanilla, lives in `static/js/main.js`, and is a progressive
  enhancement — no library, no CDN, no inline `onclick`. The confirm prompt is
  not a security control; the server check is.
- Currency stays ₹ in the confirm message and the `"Expense deleted."` flash
  copy is lowercase-friendly and matches the `"Expense added."` /
  `"Expense updated."` style.
- One lowercase, narrowly-scoped commit, e.g.
  `expenses: handle POST /expenses/<id>/delete and remove expense`.

## Definition of done
Run `python app.py` (port 5001), sign in as the seed user
(`demo@spendly.com` / `demo123`) and verify:
- [ ] `/profile` Recent transactions shows a **Delete** control beside **Edit**
      on every row.
- [ ] Clicking Delete shows a browser confirm prompt naming the amount; cancelling
      it leaves the row in place and does not hit the server.
- [ ] Confirming the prompt redirects to `/profile`, shows a flashed
      `"Expense deleted."` banner, and the row is gone from the table.
- [ ] After deleting a row, **Total spent** drops by exactly that expense's
      amount, **Transactions** decreases by one, and **Top category** / the
      Category breakdown recompute accordingly.
- [ ] Deleting the last expense in the current filter window shows the
      `"No transactions in this range."` empty state.
- [ ] `GET /expenses/<id>/delete` returns `405` and deletes nothing.
- [ ] `POST /expenses/<id>/delete` while logged out redirects to `/login` with a
      flash and changes nothing.
- [ ] `POST /expenses/<id>/delete` for an `id` that does not exist, or one owned
      by a different user, returns `404` and leaves that row in place.
- [ ] Tampering the form `action` to another user's expense `id` returns `404`;
      that user's row still exists afterwards.
- [ ] `created_at` and every other expense row are unchanged after a delete.
- [ ] No hardcoded hex values added to `style.css`; the delete affordance uses
      `var(--danger)`. `pytest` still collects and passes.
