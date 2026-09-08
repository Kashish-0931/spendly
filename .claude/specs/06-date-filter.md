# Spec: Date Filter For Profile Page

## Overview
Step 6 adds a date-range filter to the `/profile` page. Today the profile page
always shows a user's entire expense history — every summary stat, transaction
row, and category-breakdown bar is computed over all time. This step lets a
logged-in user narrow that view to a start/end date window (plus a few quick
presets like "This month" and "Last 30 days") so they can answer questions like
"how much did I spend on Food in July?". The filter is driven entirely by query
string parameters on the existing `GET /profile` route, so filtered views are
shareable and bookmarkable, and the page still works with no parameters at all.

## Depends on
- Step 1: Database setup (`expenses.date` column stored as `YYYY-MM-DD` text)
- Step 3: Login / Logout (`session["user_id"]` identifies the current user)
- Step 4: Profile page static UI (template renders the four sections)
- Step 5: Backend connection (`database/queries.py` helpers power the page)

## Routes
- `GET /profile` — existing route, now also reads optional `start`, `end`, and
  `range` query-string parameters and passes the resolved window to every
  profile query — logged-in only (unchanged: redirect to `/login` if not
  authenticated).

No new routes.

## Database changes
No database changes. `expenses.date` is already stored as ISO `YYYY-MM-DD`
text, which sorts and range-compares lexicographically, so `WHERE date >= ?
AND date <= ?` is sufficient.

## Templates
- **Modify:** `templates/profile.html`
  - Add a filter bar above the summary tiles: a `GET` form (`action="/profile"`)
    with two `<input type="date">` fields (`name="start"`, `name="end"`) and a
    submit button, plus preset links ("This month", "Last 30 days", "Last 3
    months", "Last 6 months", "All time").
  - Show the currently applied range in a readable line (e.g. "Showing 1 Jul
    2026 – 31 Jul 2026") and, when a filter is active, an "All time" clear link.
  - When the filtered window contains no expenses, show an empty-state message
    in the transactions panel instead of an empty table body.
  - No structural changes to the four existing sections — they consume the same
    variable names as today.

## Files to change
- `app.py` — in `profile()`, parse `start` / `end` / `range` from
  `request.args`, resolve them to a concrete `(start, end)` pair, pass that pair
  to the four query helpers, and pass the resolved range back to the template
  for display.
- `database/queries.py` — add optional `start=None`, `end=None` keyword
  parameters to `get_summary_stats`, `get_recent_transactions`, and
  `get_category_breakdown`; when provided, add parameterised
  `AND date >= ? AND date <= ?` clauses. `get_user_by_id` is unchanged.
- `templates/profile.html` — add the filter bar and empty-state (see Templates).
- `static/css/style.css` — add classes for the filter bar / preset links,
  matching the existing profile section styles.

## Files to create
- `database/date_range.py` — a tiny pure helper module (no Flask imports):
  - `resolve_range(start, end, preset, today=None)` → `(start, end, label)`
    where `start`/`end` are `YYYY-MM-DD` strings or `None`, and `label` is a
    human-readable description ("All time", "This month", "Last 30 days", "Last
    3 months", "Last 6 months", "1 Jul 2026 – 31 Jul 2026", …). Invalid or
    partial input falls back to "All time" (`None, None`).
  - Presets accepted on the `range=` param: `this_month`, `last30`, `last3m`,
    `last6m`, `all`. The month-based presets count back whole calendar months
    from today (day clamped to the target month's last day).

## New dependencies
No new dependencies. Date handling uses the standard-library `datetime` module.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only.
- Parameterised queries only — the date bounds must be passed as SQL
  parameters, never string-formatted into the query.
- Passwords hashed with werkzeug (no auth changes in this step).
- Use CSS variables — never hardcode hex values; reuse the existing profile
  palette tokens.
- All templates extend `base.html`. No inline styles — filter-bar styling goes
  in `static/css/style.css`.
- Currency stays ₹ everywhere; keep INR examples.
- Date inputs and stored dates are ISO `YYYY-MM-DD`. Compare as text.
- `resolve_range` precedence: an explicit `preset` (`range=` param) wins over
  `start`/`end`; if no preset, use whatever of `start`/`end` parse cleanly;
  a `start` later than `end` is swapped rather than rejected.
- Bad input never 500s: an unparseable date is treated as absent and the page
  renders the "All time" view.
- When no filter is applied, behaviour is byte-for-byte the same as Step 5
  (helpers called with `start=None, end=None`).
- Query helpers still open their own connection via `get_db()` and close it
  before returning.
- The `end` bound is inclusive (`date <= ?`).

## Definition of done
- [ ] Visiting `/profile` with no query string shows the same totals as before
      (seed user: ₹4,708.00 total, 8 transactions) — no behaviour change.
- [ ] Visiting `/profile?start=<1st of this month>&end=<last of this month>`
      restricts the summary tiles, transaction table, and category breakdown to
      that month's expenses only.
- [ ] The filter bar shows two date pickers pre-filled with the active `start`
      and `end` values after a filter is applied.
- [ ] Clicking "Last 30 days" loads `/profile?range=last30` and shows only
      expenses dated within the last 30 days; the readable range line updates.
- [ ] "Last 3 months" (`range=last3m`) and "Last 6 months" (`range=last6m`)
      each load a window starting that many whole calendar months before today
      and update the readable range line ("Last 3 months" / "Last 6 months").
- [ ] Clicking "All time" / the clear link returns to unfiltered `/profile`.
- [ ] Choosing a range with no expenses (e.g. a future month) returns HTTP 200,
      shows ₹0.00 total, 0 transactions, an empty category breakdown, and an
      empty-state message in the transactions panel — no error.
- [ ] Passing a malformed date (`/profile?start=not-a-date`) returns HTTP 200
      and renders the unfiltered "All time" view.
- [ ] A reversed range (`start` after `end`) is swapped and still returns the
      correct expenses.
- [ ] `/profile` remains logged-in only — unauthenticated requests still
      redirect to `/login`.
- [ ] No hardcoded hex values are added to `style.css`; the filter bar uses
      existing CSS variables.
